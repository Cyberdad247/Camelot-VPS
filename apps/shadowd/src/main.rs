use axum::{
    body::Body,
    extract::{Path, Query, Request, State},
    http::{header::AUTHORIZATION, StatusCode},
    middleware::{self, Next},
    response::Response,
    routing::{get, post},
    Json, Router,
};
use camelot_crypto::{hash_payload, KeyPair};
use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    collections::HashMap,
    env,
    path::{Component, Path as FsPath, PathBuf},
    sync::Arc,
};
use tokio::{
    fs::{self, OpenOptions},
    io::AsyncWriteExt,
    sync::{Mutex, RwLock},
};
use tracing::{info, warn};
use uuid::Uuid;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "UPPERCASE")]
enum RiskRing {
    R0,
    R1,
    R2,
    R3,
    R4,
    R5,
    R6,
}

impl RiskRing {
    fn requires_hitl(self) -> bool {
        self >= Self::R4
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
enum SessionState {
    Summoned,
    Attested,
    Sandboxed,
    Planning,
    WaitingApproval,
    Executing,
    Verifying,
    Sealed,
    Aborted,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
enum EffectStatus {
    Proposed,
    PendingApproval,
    Authorized,
    Denied,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ResourceBounds {
    memory_mb: u64,
    cpu_quota_percent: u8,
    ttl_seconds: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct WorkspaceBoundary {
    mode: String,
    root_uri: String,
    public_inbound: bool,
    allowed_egress: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ApprovalRecord {
    operator: String,
    scope: String,
    note: Option<String>,
    approved_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ShadowEffect {
    effect_id: Uuid,
    intent: String,
    effect: String,
    target: String,
    risk: RiskRing,
    requested_capabilities: Vec<String>,
    status: EffectStatus,
    requires_hitl: bool,
    manifest_hash: String,
    created_at: DateTime<Utc>,
    approval: Option<ApprovalRecord>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ShadowSession {
    session_id: Uuid,
    mission: String,
    knight_id: String,
    delegate_id: Option<String>,
    state: SessionState,
    risk_ceiling: RiskRing,
    capabilities: Vec<String>,
    bounds: ResourceBounds,
    workspace: WorkspaceBoundary,
    created_at: DateTime<Utc>,
    expires_at: DateTime<Utc>,
    effects: Vec<ShadowEffect>,
    receipt_count: u64,
    last_receipt_hash: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct ShadowReceipt {
    receipt_id: Uuid,
    timestamp: DateTime<Utc>,
    session_id: Uuid,
    knight_id: String,
    action: String,
    risk: RiskRing,
    decision: String,
    resource: String,
    payload_hash: String,
    parent_hash: Option<String>,
    receipt_hash: String,
    signer_public_key: String,
    signature: String,
}

#[derive(Clone)]
struct AppState {
    sessions: Arc<RwLock<HashMap<Uuid, ShadowSession>>>,
    signer: Arc<KeyPair>,
    receipt_head: Arc<Mutex<Option<String>>>,
    shadow_root: Arc<PathBuf>,
    receipt_path: Arc<PathBuf>,
    api_token: Arc<String>,
}

#[derive(Debug, Deserialize)]
struct CreateSessionRequest {
    mission: String,
    knight_id: String,
    delegate_id: Option<String>,
    ttl_seconds: Option<i64>,
    risk_ceiling: Option<RiskRing>,
    capabilities: Option<Vec<String>>,
    allowed_egress: Option<Vec<String>>,
    memory_mb: Option<u64>,
    cpu_quota_percent: Option<u8>,
}

#[derive(Debug, Deserialize)]
struct ProposeEffectRequest {
    intent: String,
    effect: String,
    target: String,
    risk: RiskRing,
    requested_capabilities: Option<Vec<String>>,
}

#[derive(Debug, Deserialize)]
struct ApproveEffectRequest {
    operator: String,
    scope: Option<String>,
    note: Option<String>,
}

#[derive(Debug, Deserialize)]
struct DenyEffectRequest {
    operator: String,
    note: Option<String>,
}

#[derive(Debug, Deserialize)]
struct WriteFileRequest {
    path: String,
    content: String,
}

#[derive(Debug, Deserialize)]
struct ReadFileQuery {
    path: String,
}

type ApiError = (StatusCode, Json<Value>);

fn api_error(status: StatusCode, message: impl Into<String>) -> ApiError {
    (status, Json(json!({ "error": message.into() })))
}

fn bytes_to_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push(HEX[(byte >> 4) as usize] as char);
        out.push(HEX[(byte & 0x0f) as usize] as char);
    }
    out
}

fn live_session(session: &ShadowSession) -> Result<(), ApiError> {
    if Utc::now() > session.expires_at {
        return Err(api_error(StatusCode::GONE, "Shadow session expired"));
    }
    if matches!(session.state, SessionState::Sealed | SessionState::Aborted) {
        return Err(api_error(StatusCode::CONFLICT, "Shadow session is closed"));
    }
    Ok(())
}

fn safe_relative_path(input: &str) -> Result<PathBuf, ApiError> {
    if input.is_empty() || input.len() > 512 {
        return Err(api_error(StatusCode::BAD_REQUEST, "Invalid shadow path"));
    }
    let path = FsPath::new(input);
    for component in path.components() {
        match component {
            Component::Normal(_) => {}
            _ => return Err(api_error(StatusCode::BAD_REQUEST, "Shadow path must be relative and cannot traverse")),
        }
    }
    Ok(path.to_path_buf())
}

async fn require_token(
    State(state): State<AppState>,
    req: Request<Body>,
    next: Next,
) -> Result<Response, StatusCode> {
    let expected = format!("Bearer {}", state.api_token.as_str());
    let actual = req
        .headers()
        .get(AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .unwrap_or_default();
    if actual != expected {
        return Err(StatusCode::UNAUTHORIZED);
    }
    Ok(next.run(req).await)
}

async fn record_receipt(
    state: &AppState,
    session_id: Uuid,
    knight_id: &str,
    action: &str,
    risk: RiskRing,
    decision: &str,
    resource: &str,
    payload: &Value,
) -> Result<ShadowReceipt, ApiError> {
    let payload_hash = hash_payload(&payload.to_string());
    let mut head = state.receipt_head.lock().await;
    let timestamp = Utc::now();
    let receipt_id = Uuid::new_v4();
    let canonical = json!({
        "receipt_id": receipt_id,
        "timestamp": timestamp,
        "session_id": session_id,
        "knight_id": knight_id,
        "action": action,
        "risk": risk,
        "decision": decision,
        "resource": resource,
        "payload_hash": payload_hash,
        "parent_hash": *head,
    });
    let receipt_hash = hash_payload(&canonical.to_string());
    let signature = state.signer.sign(receipt_hash.as_bytes());
    let receipt = ShadowReceipt {
        receipt_id,
        timestamp,
        session_id,
        knight_id: knight_id.to_owned(),
        action: action.to_owned(),
        risk,
        decision: decision.to_owned(),
        resource: resource.to_owned(),
        payload_hash,
        parent_hash: head.clone(),
        receipt_hash: receipt_hash.clone(),
        signer_public_key: state.signer.public_key_hex(),
        signature: bytes_to_hex(&signature.to_bytes()),
    };

    if let Some(parent) = state.receipt_path.parent() {
        fs::create_dir_all(parent)
            .await
            .map_err(|error| api_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()))?;
    }
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(state.receipt_path.as_ref())
        .await
        .map_err(|error| api_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()))?;
    let mut line = serde_json::to_vec(&receipt)
        .map_err(|error| api_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()))?;
    line.push(b'\n');
    file.write_all(&line)
        .await
        .map_err(|error| api_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()))?;
    file.flush()
        .await
        .map_err(|error| api_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()))?;
    *head = Some(receipt_hash);
    Ok(receipt)
}

async fn health(State(state): State<AppState>) -> Json<Value> {
    let sessions = state.sessions.read().await;
    Json(json!({
        "status": "ok",
        "service": "camelot-shadowd",
        "sessions": sessions.len(),
        "policy": "loopback-authenticated-hitl",
        "publicInbound": false,
        "signer": state.signer.public_key_hex(),
    }))
}

async fn list_sessions(State(state): State<AppState>) -> Json<Vec<ShadowSession>> {
    let sessions = state.sessions.read().await;
    Json(sessions.values().cloned().collect())
}

async fn get_session(
    State(state): State<AppState>,
    Path(session_id): Path<Uuid>,
) -> Result<Json<ShadowSession>, ApiError> {
    let sessions = state.sessions.read().await;
    sessions
        .get(&session_id)
        .cloned()
        .map(Json)
        .ok_or_else(|| api_error(StatusCode::NOT_FOUND, "Unknown shadow session"))
}

async fn create_session(
    State(state): State<AppState>,
    Json(request): Json<CreateSessionRequest>,
) -> Result<(StatusCode, Json<ShadowSession>), ApiError> {
    let mission = request.mission.trim();
    let knight_id = request.knight_id.trim();
    if mission.is_empty() || mission.len() > 2000 {
        return Err(api_error(StatusCode::BAD_REQUEST, "Mission is required and must be under 2000 characters"));
    }
    if knight_id.is_empty() || knight_id.len() > 96 {
        return Err(api_error(StatusCode::BAD_REQUEST, "Knight id is required"));
    }

    let ttl_seconds = request.ttl_seconds.unwrap_or(1800).clamp(60, 86_400);
    let memory_mb = request.memory_mb.unwrap_or(512).clamp(64, 1536);
    let cpu_quota_percent = request.cpu_quota_percent.unwrap_or(25).clamp(5, 75);
    let capabilities = request.capabilities.unwrap_or_else(|| vec![
        "shadow.read".into(),
        "shadow.write".into(),
        "shadow.plan".into(),
    ]);
    let allowed_egress = request.allowed_egress.unwrap_or_default();
    let session_id = Uuid::new_v4();
    let workspace_path = state.shadow_root.join(session_id.to_string()).join("workspace");
    fs::create_dir_all(&workspace_path)
        .await
        .map_err(|error| api_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()))?;

    let created_at = Utc::now();
    let mut session = ShadowSession {
        session_id,
        mission: mission.to_owned(),
        knight_id: knight_id.to_owned(),
        delegate_id: request.delegate_id,
        state: SessionState::Sandboxed,
        risk_ceiling: request.risk_ceiling.unwrap_or(RiskRing::R5),
        capabilities,
        bounds: ResourceBounds { memory_mb, cpu_quota_percent, ttl_seconds },
        workspace: WorkspaceBoundary {
            mode: "copy-on-write-shadow".into(),
            root_uri: format!("shadow://{session_id}/workspace"),
            public_inbound: false,
            allowed_egress,
        },
        created_at,
        expires_at: created_at + Duration::seconds(ttl_seconds),
        effects: Vec::new(),
        receipt_count: 0,
        last_receipt_hash: None,
    };

    let receipt = record_receipt(
        &state,
        session_id,
        &session.knight_id,
        "shadow.session.summon",
        RiskRing::R1,
        "ALLOW",
        &session.workspace.root_uri,
        &json!({ "mission": session.mission, "bounds": session.bounds, "capabilities": session.capabilities }),
    ).await?;
    session.receipt_count = 1;
    session.last_receipt_hash = Some(receipt.receipt_hash);
    state.sessions.write().await.insert(session_id, session.clone());
    Ok((StatusCode::CREATED, Json(session)))
}

async fn propose_effect(
    State(state): State<AppState>,
    Path(session_id): Path<Uuid>,
    Json(request): Json<ProposeEffectRequest>,
) -> Result<(StatusCode, Json<ShadowEffect>), ApiError> {
    let mut sessions = state.sessions.write().await;
    let session = sessions
        .get_mut(&session_id)
        .ok_or_else(|| api_error(StatusCode::NOT_FOUND, "Unknown shadow session"))?;
    live_session(session)?;
    if request.risk > session.risk_ceiling {
        return Err(api_error(StatusCode::FORBIDDEN, "Requested effect exceeds session risk ceiling"));
    }
    let requested_capabilities = request.requested_capabilities.unwrap_or_default();
    for capability in &requested_capabilities {
        if !session.capabilities.contains(capability) {
            return Err(api_error(StatusCode::FORBIDDEN, format!("Capability not leased to session: {capability}")));
        }
    }
    if request.intent.trim().is_empty() || request.intent.len() > 2000 {
        return Err(api_error(StatusCode::BAD_REQUEST, "Effect intent is required and must be under 2000 characters"));
    }

    let manifest_hash = hash_payload(&json!({
        "intent": request.intent,
        "effect": request.effect,
        "target": request.target,
        "risk": request.risk,
        "capabilities": requested_capabilities,
    }).to_string());
    let requires_hitl = request.risk.requires_hitl();
    let effect = ShadowEffect {
        effect_id: Uuid::new_v4(),
        intent: request.intent.trim().to_owned(),
        effect: request.effect.trim().to_owned(),
        target: request.target.trim().to_owned(),
        risk: request.risk,
        requested_capabilities,
        status: if requires_hitl { EffectStatus::PendingApproval } else { EffectStatus::Authorized },
        requires_hitl,
        manifest_hash,
        created_at: Utc::now(),
        approval: None,
    };
    session.state = if requires_hitl { SessionState::WaitingApproval } else { SessionState::Planning };
    session.effects.push(effect.clone());
    let knight_id = session.knight_id.clone();
    let resource = effect.target.clone();
    drop(sessions);

    let receipt = record_receipt(
        &state,
        session_id,
        &knight_id,
        "shadow.effect.propose",
        effect.risk,
        if requires_hitl { "WAIT_HITL" } else { "ALLOW" },
        &resource,
        &serde_json::to_value(&effect).unwrap_or(Value::Null),
    ).await?;
    if let Some(session) = state.sessions.write().await.get_mut(&session_id) {
        session.receipt_count += 1;
        session.last_receipt_hash = Some(receipt.receipt_hash);
    }
    Ok((StatusCode::CREATED, Json(effect)))
}

async fn approve_effect(
    State(state): State<AppState>,
    Path((session_id, effect_id)): Path<(Uuid, Uuid)>,
    Json(request): Json<ApproveEffectRequest>,
) -> Result<Json<ShadowEffect>, ApiError> {
    if request.operator.trim().is_empty() {
        return Err(api_error(StatusCode::BAD_REQUEST, "Operator identity is required"));
    }
    let scope = request.scope.unwrap_or_else(|| "once".into());
    let mut sessions = state.sessions.write().await;
    let session = sessions
        .get_mut(&session_id)
        .ok_or_else(|| api_error(StatusCode::NOT_FOUND, "Unknown shadow session"))?;
    live_session(session)?;
    let knight_id = session.knight_id.clone();
    let effect = session.effects.iter_mut().find(|effect| effect.effect_id == effect_id)
        .ok_or_else(|| api_error(StatusCode::NOT_FOUND, "Unknown shadow effect"))?;
    if effect.status != EffectStatus::PendingApproval {
        return Err(api_error(StatusCode::CONFLICT, "Effect is not awaiting approval"));
    }
    if effect.risk == RiskRing::R6 && scope != "sovereign" {
        return Err(api_error(StatusCode::FORBIDDEN, "R6 effects require sovereign approval scope"));
    }
    effect.status = EffectStatus::Authorized;
    effect.approval = Some(ApprovalRecord {
        operator: request.operator.trim().to_owned(),
        scope: scope.clone(),
        note: request.note,
        approved_at: Utc::now(),
    });
    session.state = SessionState::Planning;
    let output = effect.clone();
    let resource = effect.target.clone();
    drop(sessions);

    let receipt = record_receipt(
        &state,
        session_id,
        &knight_id,
        "shadow.effect.approve",
        output.risk,
        "HITL_ALLOW",
        &resource,
        &serde_json::to_value(&output).unwrap_or(Value::Null),
    ).await?;
    if let Some(session) = state.sessions.write().await.get_mut(&session_id) {
        session.receipt_count += 1;
        session.last_receipt_hash = Some(receipt.receipt_hash);
    }
    Ok(Json(output))
}

async fn deny_effect(
    State(state): State<AppState>,
    Path((session_id, effect_id)): Path<(Uuid, Uuid)>,
    Json(request): Json<DenyEffectRequest>,
) -> Result<Json<ShadowEffect>, ApiError> {
    if request.operator.trim().is_empty() {
        return Err(api_error(StatusCode::BAD_REQUEST, "Operator identity is required"));
    }
    let mut sessions = state.sessions.write().await;
    let session = sessions
        .get_mut(&session_id)
        .ok_or_else(|| api_error(StatusCode::NOT_FOUND, "Unknown shadow session"))?;
    live_session(session)?;
    let knight_id = session.knight_id.clone();
    let effect = session.effects.iter_mut().find(|effect| effect.effect_id == effect_id)
        .ok_or_else(|| api_error(StatusCode::NOT_FOUND, "Unknown shadow effect"))?;
    effect.status = EffectStatus::Denied;
    effect.approval = Some(ApprovalRecord {
        operator: request.operator.trim().to_owned(),
        scope: "deny".into(),
        note: request.note,
        approved_at: Utc::now(),
    });
    session.state = SessionState::Planning;
    let output = effect.clone();
    let resource = effect.target.clone();
    drop(sessions);

    let receipt = record_receipt(
        &state,
        session_id,
        &knight_id,
        "shadow.effect.deny",
        output.risk,
        "HITL_DENY",
        &resource,
        &serde_json::to_value(&output).unwrap_or(Value::Null),
    ).await?;
    if let Some(session) = state.sessions.write().await.get_mut(&session_id) {
        session.receipt_count += 1;
        session.last_receipt_hash = Some(receipt.receipt_hash);
    }
    Ok(Json(output))
}

async fn write_shadow_file(
    State(state): State<AppState>,
    Path(session_id): Path<Uuid>,
    Json(request): Json<WriteFileRequest>,
) -> Result<Json<Value>, ApiError> {
    if request.content.len() > 256 * 1024 {
        return Err(api_error(StatusCode::PAYLOAD_TOO_LARGE, "Shadow write exceeds 256KB limit"));
    }
    let relative = safe_relative_path(&request.path)?;
    let sessions = state.sessions.read().await;
    let session = sessions
        .get(&session_id)
        .ok_or_else(|| api_error(StatusCode::NOT_FOUND, "Unknown shadow session"))?;
    live_session(session)?;
    if !session.capabilities.iter().any(|capability| capability == "shadow.write") {
        return Err(api_error(StatusCode::FORBIDDEN, "shadow.write capability not leased"));
    }
    let knight_id = session.knight_id.clone();
    drop(sessions);

    let path = state.shadow_root.join(session_id.to_string()).join("workspace").join(&relative);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).await
            .map_err(|error| api_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()))?;
    }
    fs::write(&path, request.content.as_bytes()).await
        .map_err(|error| api_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()))?;
    let receipt = record_receipt(
        &state,
        session_id,
        &knight_id,
        "shadow.vfs.write",
        RiskRing::R2,
        "ALLOW",
        &format!("shadow://{session_id}/workspace/{}", relative.display()),
        &json!({ "path": relative, "bytes": request.content.len() }),
    ).await?;
    if let Some(session) = state.sessions.write().await.get_mut(&session_id) {
        session.receipt_count += 1;
        session.last_receipt_hash = Some(receipt.receipt_hash.clone());
    }
    Ok(Json(json!({ "status": "written", "receipt": receipt, "path": relative })))
}

async fn read_shadow_file(
    State(state): State<AppState>,
    Path(session_id): Path<Uuid>,
    Query(query): Query<ReadFileQuery>,
) -> Result<Json<Value>, ApiError> {
    let relative = safe_relative_path(&query.path)?;
    let sessions = state.sessions.read().await;
    let session = sessions
        .get(&session_id)
        .ok_or_else(|| api_error(StatusCode::NOT_FOUND, "Unknown shadow session"))?;
    live_session(session)?;
    if !session.capabilities.iter().any(|capability| capability == "shadow.read") {
        return Err(api_error(StatusCode::FORBIDDEN, "shadow.read capability not leased"));
    }
    drop(sessions);
    let path = state.shadow_root.join(session_id.to_string()).join("workspace").join(&relative);
    let metadata = fs::metadata(&path).await
        .map_err(|_| api_error(StatusCode::NOT_FOUND, "Shadow file not found"))?;
    if metadata.len() > 256 * 1024 {
        return Err(api_error(StatusCode::PAYLOAD_TOO_LARGE, "Shadow read exceeds 256KB limit"));
    }
    let content = fs::read_to_string(&path).await
        .map_err(|error| api_error(StatusCode::BAD_REQUEST, format!("Shadow file is not readable text: {error}")))?;
    Ok(Json(json!({ "path": relative, "content": content })))
}

async fn list_receipts(
    State(state): State<AppState>,
    Path(session_id): Path<Uuid>,
) -> Result<Json<Vec<ShadowReceipt>>, ApiError> {
    let raw = match fs::read_to_string(state.receipt_path.as_ref()).await {
        Ok(raw) => raw,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => String::new(),
        Err(error) => return Err(api_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string())),
    };
    let receipts = raw
        .lines()
        .filter_map(|line| serde_json::from_str::<ShadowReceipt>(line).ok())
        .filter(|receipt| receipt.session_id == session_id)
        .take(250)
        .collect();
    Ok(Json(receipts))
}

async fn seal_session(
    State(state): State<AppState>,
    Path(session_id): Path<Uuid>,
) -> Result<Json<Value>, ApiError> {
    let mut sessions = state.sessions.write().await;
    let session = sessions
        .get_mut(&session_id)
        .ok_or_else(|| api_error(StatusCode::NOT_FOUND, "Unknown shadow session"))?;
    live_session(session)?;
    session.state = SessionState::Verifying;
    let knight_id = session.knight_id.clone();
    drop(sessions);

    let receipt = record_receipt(
        &state,
        session_id,
        &knight_id,
        "shadow.session.seal",
        RiskRing::R3,
        "SEALED",
        &format!("shadow://{session_id}"),
        &json!({ "ephemeralWorkspace": true }),
    ).await?;
    let workspace = state.shadow_root.join(session_id.to_string());
    if let Err(error) = fs::remove_dir_all(&workspace).await {
        if error.kind() != std::io::ErrorKind::NotFound {
            warn!(%session_id, %error, "failed removing sealed shadow workspace");
        }
    }
    if let Some(session) = state.sessions.write().await.get_mut(&session_id) {
        session.state = SessionState::Sealed;
        session.receipt_count += 1;
        session.last_receipt_hash = Some(receipt.receipt_hash.clone());
    }
    Ok(Json(json!({ "status": "sealed", "sessionId": session_id, "workspaceRemoved": true, "receipt": receipt })))
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let host = env::var("CAMELOT_SHADOW_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let port: u16 = env::var("CAMELOT_SHADOW_PORT")
        .ok()
        .and_then(|value| value.parse().ok())
        .unwrap_or(4190);
    let api_token = env::var("CAMELOT_SHADOW_TOKEN")
        .expect("CAMELOT_SHADOW_TOKEN must be set; shadowd refuses unauthenticated startup");
    if api_token.len() < 24 {
        panic!("CAMELOT_SHADOW_TOKEN must contain at least 24 characters");
    }
    if host != "127.0.0.1" && host != "::1" {
        panic!("camelot-shadowd is intentionally loopback-only; use Bifrost for governed access");
    }

    let shadow_root = PathBuf::from(env::var("CAMELOT_SHADOW_ROOT").unwrap_or_else(|_| "/var/lib/camelot/shadow".into()));
    let receipt_path = shadow_root.join("ledger").join("receipts.jsonl");
    fs::create_dir_all(&shadow_root).await.expect("create shadow root");

    let state = AppState {
        sessions: Arc::new(RwLock::new(HashMap::new())),
        signer: Arc::new(KeyPair::generate()),
        receipt_head: Arc::new(Mutex::new(None)),
        shadow_root: Arc::new(shadow_root),
        receipt_path: Arc::new(receipt_path),
        api_token: Arc::new(api_token),
    };

    let protected = Router::new()
        .route("/v1/shadow/sessions", get(list_sessions).post(create_session))
        .route("/v1/shadow/sessions/:session_id", get(get_session))
        .route("/v1/shadow/sessions/:session_id/effects", post(propose_effect))
        .route("/v1/shadow/sessions/:session_id/effects/:effect_id/approve", post(approve_effect))
        .route("/v1/shadow/sessions/:session_id/effects/:effect_id/deny", post(deny_effect))
        .route("/v1/shadow/sessions/:session_id/files/write", post(write_shadow_file))
        .route("/v1/shadow/sessions/:session_id/files/read", get(read_shadow_file))
        .route("/v1/shadow/sessions/:session_id/receipts", get(list_receipts))
        .route("/v1/shadow/sessions/:session_id/seal", post(seal_session))
        .route_layer(middleware::from_fn_with_state(state.clone(), require_token));

    let app = Router::new()
        .route("/health", get(health))
        .merge(protected)
        .with_state(state.clone());

    let listener = tokio::net::TcpListener::bind(format!("{host}:{port}"))
        .await
        .expect("bind shadowd");
    info!(host, port, signer = %state.signer.public_key_hex(), "camelot-shadowd online");
    axum::serve(listener, app).await.expect("shadowd server failed");
}
