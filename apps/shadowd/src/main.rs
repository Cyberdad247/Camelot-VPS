mod store;

use axum::{
    extract::{DefaultBodyLimit, Path, Query, Request, State},
    http::{header::AUTHORIZATION, StatusCode},
    middleware::{self, Next},
    response::Response,
    routing::{get, post},
    Json, Router,
};
use camelot_crypto::{hash_payload, verify_detached_hex, KeyPair};
use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    env,
    fs as stdfs,
    io::Write as _,
    path::{Component, Path as FsPath, PathBuf},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
};
use store::ShadowStore;
use tokio::{
    fs::{self, OpenOptions},
    io::AsyncWriteExt,
    sync::Mutex,
};
use tower_http::trace::TraceLayer;
use tracing::{info, warn};
use uuid::Uuid;

const POLICY_VERSION: &str = "shadow-policy/0.2";
const MAX_TEXT_FILE_BYTES: usize = 256 * 1024;
const ALLOWED_CAPABILITIES: &[&str] = &[
    "shadow.read",
    "shadow.write",
    "shadow.plan",
    "bifrost.request",
];
const ALLOWED_EGRESS: &[&str] = &["bifrost://governed"];

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, PartialOrd, Ord)]
#[serde(rename_all = "UPPERCASE")]
pub(crate) enum RiskRing {
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

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub(crate) enum SessionState {
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

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub(crate) enum EffectStatus {
    Proposed,
    PendingApproval,
    Authorized,
    Denied,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub(crate) struct ResourceBounds {
    memory_mb: u64,
    cpu_quota_percent: u8,
    ttl_seconds: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub(crate) struct WorkspaceBoundary {
    mode: String,
    root_uri: String,
    public_inbound: bool,
    allowed_egress: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub(crate) struct ApprovalRecord {
    operator: String,
    scope: String,
    note: Option<String>,
    approved_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub(crate) struct ShadowEffect {
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
pub(crate) struct ShadowSession {
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
    #[serde(default = "initial_state_version")]
    state_version: u64,
}

fn initial_state_version() -> u64 {
    1
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub(crate) struct ShadowReceipt {
    sequence: u64,
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
    instance_id: Uuid,
    policy_version: String,
}

#[derive(Clone)]
struct AppState {
    store: ShadowStore,
    signer: Arc<KeyPair>,
    ledger_lock: Arc<Mutex<()>>,
    ledger_verified: Arc<AtomicBool>,
    shadow_root: Arc<PathBuf>,
    receipt_path: Arc<PathBuf>,
    api_token: Arc<String>,
    allow_r6: bool,
    instance_id: Uuid,
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

fn internal(error: impl ToString) -> ApiError {
    api_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string())
}

fn hex(bytes: &[u8]) -> String {
    const H: &[u8; 16] = b"0123456789abcdef";
    let mut out = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        out.push(H[(byte >> 4) as usize] as char);
        out.push(H[(byte & 0x0f) as usize] as char);
    }
    out
}

fn live(session: &ShadowSession) -> Result<(), ApiError> {
    if Utc::now() > session.expires_at {
        return Err(api_error(StatusCode::GONE, "Shadow session expired"));
    }
    if matches!(session.state, SessionState::Sealed | SessionState::Aborted) {
        return Err(api_error(StatusCode::CONFLICT, "Shadow session is closed"));
    }
    Ok(())
}

fn safe_relative(input: &str) -> Result<PathBuf, ApiError> {
    if input.is_empty() || input.len() > 512 {
        return Err(api_error(StatusCode::BAD_REQUEST, "Invalid shadow path"));
    }
    let path = FsPath::new(input);
    if path.components().any(|component| !matches!(component, Component::Normal(_))) {
        return Err(api_error(
            StatusCode::BAD_REQUEST,
            "Shadow path must be relative and cannot traverse",
        ));
    }
    Ok(path.to_path_buf())
}

fn bounded_capabilities(requested: Option<Vec<String>>) -> Result<Vec<String>, ApiError> {
    let requested = requested.unwrap_or_else(|| {
        vec!["shadow.read".into(), "shadow.write".into(), "shadow.plan".into()]
    });
    if requested.len() > ALLOWED_CAPABILITIES.len() {
        return Err(api_error(StatusCode::BAD_REQUEST, "Too many capabilities"));
    }
    for capability in &requested {
        if !ALLOWED_CAPABILITIES.contains(&capability.as_str()) {
            return Err(api_error(
                StatusCode::FORBIDDEN,
                format!("Capability is not allowlisted: {capability}"),
            ));
        }
    }
    Ok(requested)
}

fn bounded_egress(requested: Option<Vec<String>>) -> Result<Vec<String>, ApiError> {
    let requested = requested.unwrap_or_default();
    if requested.len() > ALLOWED_EGRESS.len() {
        return Err(api_error(StatusCode::BAD_REQUEST, "Too many egress routes"));
    }
    for route in &requested {
        if !ALLOWED_EGRESS.contains(&route.as_str()) {
            return Err(api_error(
                StatusCode::FORBIDDEN,
                format!("Egress route is not allowlisted: {route}"),
            ));
        }
    }
    Ok(requested)
}

async fn require_token(
    State(state): State<AppState>,
    request: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    let expected = format!("Bearer {}", state.api_token.as_str());
    let actual = request
        .headers()
        .get(AUTHORIZATION)
        .and_then(|value| value.to_str().ok())
        .unwrap_or_default();
    if actual != expected {
        return Err(StatusCode::UNAUTHORIZED);
    }
    Ok(next.run(request).await)
}

fn receipt_canonical(item: &ShadowReceipt) -> Value {
    json!({
        "sequence": item.sequence,
        "receipt_id": item.receipt_id,
        "timestamp": item.timestamp,
        "session_id": item.session_id,
        "knight_id": item.knight_id,
        "action": item.action,
        "risk": item.risk,
        "decision": item.decision,
        "resource": item.resource,
        "payload_hash": item.payload_hash,
        "parent_hash": item.parent_hash,
        "instance_id": item.instance_id,
        "policy_version": item.policy_version,
    })
}

async fn verify_ledger(store: &ShadowStore) -> Result<Option<String>, String> {
    let receipts = store.all_receipts().await?;
    let mut expected_sequence = 1_u64;
    let mut parent: Option<String> = None;
    for item in receipts {
        if item.sequence != expected_sequence {
            return Err(format!(
                "receipt sequence break: expected {expected_sequence}, observed {}",
                item.sequence
            ));
        }
        if item.parent_hash != parent {
            return Err(format!("receipt parent mismatch at sequence {}", item.sequence));
        }
        let expected_hash = hash_payload(&receipt_canonical(&item).to_string());
        if expected_hash != item.receipt_hash {
            return Err(format!("receipt hash mismatch at sequence {}", item.sequence));
        }
        verify_detached_hex(
            &item.signer_public_key,
            item.receipt_hash.as_bytes(),
            &item.signature,
        )?;
        parent = Some(item.receipt_hash.clone());
        expected_sequence += 1;
    }
    Ok(parent)
}

fn load_or_create_signer(path: &FsPath) -> Result<KeyPair, String> {
    if path.exists() {
        let raw = stdfs::read_to_string(path)
            .map_err(|error| format!("read Shadow signing key: {error}"))?;
        return KeyPair::from_secret_hex(raw.trim());
    }
    if let Some(parent) = path.parent() {
        stdfs::create_dir_all(parent)
            .map_err(|error| format!("create Shadow key directory: {error}"))?;
    }
    let key = KeyPair::generate();
    let mut options = stdfs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    match options.open(path) {
        Ok(mut file) => {
            file.write_all(key.secret_key_hex().as_bytes())
                .map_err(|error| format!("write Shadow signing key: {error}"))?;
            file.write_all(b"\n")
                .map_err(|error| format!("finalize Shadow signing key: {error}"))?;
            file.sync_all()
                .map_err(|error| format!("sync Shadow signing key: {error}"))?;
            Ok(key)
        }
        Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {
            let raw = stdfs::read_to_string(path)
                .map_err(|read_error| format!("read concurrently-created signing key: {read_error}"))?;
            KeyPair::from_secret_hex(raw.trim())
        }
        Err(error) => Err(format!("create Shadow signing key: {error}")),
    }
}

async fn append_audit_mirror(path: &FsPath, item: &ShadowReceipt) {
    if let Some(parent) = path.parent() {
        if let Err(error) = fs::create_dir_all(parent).await {
            warn!(%error, "could not create JSONL audit mirror directory");
            return;
        }
    }
    let mut line = match serde_json::to_vec(item) {
        Ok(value) => value,
        Err(error) => {
            warn!(%error, "could not serialize JSONL audit mirror entry");
            return;
        }
    };
    line.push(b'\n');
    match OpenOptions::new().create(true).append(true).open(path).await {
        Ok(mut file) => {
            if let Err(error) = file.write_all(&line).await {
                warn!(%error, "could not append JSONL audit mirror");
            } else if let Err(error) = file.flush().await {
                warn!(%error, "could not flush JSONL audit mirror");
            }
        }
        Err(error) => warn!(%error, "could not open JSONL audit mirror"),
    }
}

async fn receipt(
    state: &AppState,
    session_id: Uuid,
    knight_id: &str,
    action: &str,
    risk: RiskRing,
    decision: &str,
    resource: &str,
    payload: &Value,
) -> Result<ShadowReceipt, ApiError> {
    let _guard = state.ledger_lock.lock().await;
    let sequence = state.store.next_receipt_sequence().await.map_err(internal)?;
    let parent_hash = state.store.ledger_head().await.map_err(internal)?;
    let timestamp = Utc::now();
    let mut item = ShadowReceipt {
        sequence,
        receipt_id: Uuid::new_v4(),
        timestamp,
        session_id,
        knight_id: knight_id.to_owned(),
        action: action.to_owned(),
        risk,
        decision: decision.to_owned(),
        resource: resource.to_owned(),
        payload_hash: hash_payload(&payload.to_string()),
        parent_hash,
        receipt_hash: String::new(),
        signer_public_key: state.signer.public_key_hex(),
        signature: String::new(),
        instance_id: state.instance_id,
        policy_version: POLICY_VERSION.into(),
    };
    item.receipt_hash = hash_payload(&receipt_canonical(&item).to_string());
    item.signature = hex(&state.signer.sign(item.receipt_hash.as_bytes()).to_bytes());
    state.store.insert_receipt(&item).await.map_err(internal)?;
    append_audit_mirror(state.receipt_path.as_ref(), &item).await;
    Ok(item)
}

async fn load_session(state: &AppState, id: Uuid) -> Result<ShadowSession, ApiError> {
    state
        .store
        .get_session(id)
        .await
        .map_err(internal)?
        .ok_or_else(|| api_error(StatusCode::NOT_FOUND, "Unknown shadow session"))
}

async fn persist_session(
    state: &AppState,
    session: &mut ShadowSession,
    expected_version: u64,
) -> Result<(), ApiError> {
    session.state_version = expected_version + 1;
    if state
        .store
        .update_session(session, expected_version)
        .await
        .map_err(internal)?
    {
        Ok(())
    } else {
        Err(api_error(
            StatusCode::CONFLICT,
            "Shadow session changed concurrently; reload before retrying",
        ))
    }
}

async fn bump_receipt_metadata(state: &AppState, id: Uuid, hash: &str) -> Result<(), ApiError> {
    for _ in 0..3 {
        let mut session = load_session(state, id).await?;
        let expected = session.state_version;
        session.receipt_count += 1;
        session.last_receipt_hash = Some(hash.to_owned());
        session.state_version = expected + 1;
        let updated = state
            .store
            .update_session(&session, expected)
            .await
            .map_err(internal)?;
        if updated {
            return Ok(());
        }
    }
    Err(api_error(
        StatusCode::CONFLICT,
        "Could not reconcile receipt metadata after concurrent updates",
    ))
}

async fn recover_sessions(state: &AppState) -> Result<usize, String> {
    let sessions = state.store.list_sessions().await?;
    let mut recovered = 0_usize;
    for mut session in sessions {
        let expected = session.state_version;
        let mut changed = false;
        if Utc::now() > session.expires_at
            && !matches!(session.state, SessionState::Sealed | SessionState::Aborted)
        {
            session.state = SessionState::Aborted;
            changed = true;
        } else if session.state == SessionState::Summoned && session.receipt_count == 0 {
            session.state = SessionState::Aborted;
            changed = true;
        } else if session.state == SessionState::Executing {
            session.state = SessionState::Aborted;
            changed = true;
        } else if session.state == SessionState::Verifying {
            let receipts = state.store.receipts_for(session.session_id).await?;
            let has_seal = receipts.iter().any(|item| {
                item.action == "shadow.session.seal" && item.decision == "SEALED"
            });
            session.state = if has_seal {
                let workspace = state.shadow_root.join(session.session_id.to_string());
                let _ = fs::remove_dir_all(workspace).await;
                SessionState::Sealed
            } else {
                SessionState::Aborted
            };
            changed = true;
        }
        if changed {
            session.state_version = expected + 1;
            if state.store.update_session(&session, expected).await? {
                recovered += 1;
            }
        }
    }
    Ok(recovered)
}

async fn health_live() -> Json<Value> {
    Json(json!({ "status": "ok", "service": "camelot-shadowd", "live": true }))
}

async fn health_ready(State(state): State<AppState>) -> (StatusCode, Json<Value>) {
    let database = state.store.ping().await;
    let ledger = state.ledger_verified.load(Ordering::SeqCst);
    let root = fs::metadata(state.shadow_root.as_ref()).await.is_ok();
    let ready = database.is_ok() && ledger && root;
    (
        if ready { StatusCode::OK } else { StatusCode::SERVICE_UNAVAILABLE },
        Json(json!({
            "status": if ready { "ready" } else { "degraded" },
            "service": "camelot-shadowd",
            "database": database.is_ok(),
            "ledgerVerified": ledger,
            "workspaceRoot": root,
            "policy": POLICY_VERSION,
            "publicInbound": false,
            "r6Enabled": state.allow_r6,
            "signer": state.signer.public_key_hex(),
            "instanceId": state.instance_id,
        })),
    )
}

async fn list_sessions(State(state): State<AppState>) -> Result<Json<Vec<ShadowSession>>, ApiError> {
    Ok(Json(state.store.list_sessions().await.map_err(internal)?))
}

async fn get_session(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<ShadowSession>, ApiError> {
    Ok(Json(load_session(&state, id).await?))
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
    let risk_ceiling = request.risk_ceiling.unwrap_or(RiskRing::R5);
    if risk_ceiling == RiskRing::R6 && !state.allow_r6 {
        return Err(api_error(StatusCode::FORBIDDEN, "R6 sessions are disabled until sovereign authentication is configured"));
    }
    let capabilities = bounded_capabilities(request.capabilities)?;
    let allowed_egress = bounded_egress(request.allowed_egress)?;
    let ttl_seconds = request.ttl_seconds.unwrap_or(1800).clamp(60, 86_400);
    let memory_mb = request.memory_mb.unwrap_or(512).clamp(64, 1536);
    let cpu_quota_percent = request.cpu_quota_percent.unwrap_or(25).clamp(5, 75);
    let id = Uuid::new_v4();
    let workspace_path = state.shadow_root.join(id.to_string()).join("workspace");
    fs::create_dir_all(&workspace_path).await.map_err(internal)?;

    let created_at = Utc::now();
    let mut session = ShadowSession {
        session_id: id,
        mission: mission.to_owned(),
        knight_id: knight_id.to_owned(),
        delegate_id: request.delegate_id,
        state: SessionState::Summoned,
        risk_ceiling,
        capabilities,
        bounds: ResourceBounds { memory_mb, cpu_quota_percent, ttl_seconds },
        workspace: WorkspaceBoundary {
            mode: "copy-on-write-shadow".into(),
            root_uri: format!("shadow://{id}/workspace"),
            public_inbound: false,
            allowed_egress,
        },
        created_at,
        expires_at: created_at + Duration::seconds(ttl_seconds),
        effects: vec![],
        receipt_count: 0,
        last_receipt_hash: None,
        state_version: 1,
    };
    state.store.insert_session(&session).await.map_err(internal)?;
    let item = receipt(
        &state,
        id,
        &session.knight_id,
        "shadow.session.summon",
        RiskRing::R1,
        "ALLOW",
        &session.workspace.root_uri,
        &json!({
            "mission": session.mission,
            "bounds": session.bounds,
            "capabilities": session.capabilities,
            "allowed_egress": session.workspace.allowed_egress,
        }),
    )
    .await?;
    let expected = session.state_version;
    session.state = SessionState::Sandboxed;
    session.receipt_count = 1;
    session.last_receipt_hash = Some(item.receipt_hash);
    persist_session(&state, &mut session, expected).await?;
    Ok((StatusCode::CREATED, Json(session)))
}

async fn propose_effect(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
    Json(request): Json<ProposeEffectRequest>,
) -> Result<(StatusCode, Json<ShadowEffect>), ApiError> {
    let mut session = load_session(&state, id).await?;
    live(&session)?;
    if request.risk == RiskRing::R6 && !state.allow_r6 {
        return Err(api_error(StatusCode::FORBIDDEN, "R6 effects are fail-closed until sovereign authentication is configured"));
    }
    if request.risk > session.risk_ceiling {
        return Err(api_error(StatusCode::FORBIDDEN, "Requested effect exceeds session risk ceiling"));
    }
    if request.effect.trim().is_empty() || request.effect.len() > 128 {
        return Err(api_error(StatusCode::BAD_REQUEST, "Invalid effect type"));
    }
    if request.target.trim().is_empty() || request.target.len() > 512 {
        return Err(api_error(StatusCode::BAD_REQUEST, "Invalid effect target"));
    }
    if request.intent.trim().is_empty() || request.intent.len() > 2000 {
        return Err(api_error(StatusCode::BAD_REQUEST, "Invalid effect intent"));
    }
    let capabilities = request.requested_capabilities.unwrap_or_default();
    for capability in &capabilities {
        if !ALLOWED_CAPABILITIES.contains(&capability.as_str()) || !session.capabilities.contains(capability) {
            return Err(api_error(StatusCode::FORBIDDEN, format!("Capability not leased to session: {capability}")));
        }
    }
    let manifest_hash = hash_payload(&json!({
        "intent": request.intent.trim(),
        "effect": request.effect.trim(),
        "target": request.target.trim(),
        "risk": request.risk,
        "capabilities": capabilities,
    }).to_string());
    if let Some(existing) = session.effects.iter().find(|effect| effect.manifest_hash == manifest_hash) {
        return Ok((StatusCode::OK, Json(existing.clone())));
    }
    let requires_hitl = request.risk.requires_hitl();
    let effect = ShadowEffect {
        effect_id: Uuid::new_v4(),
        intent: request.intent.trim().to_owned(),
        effect: request.effect.trim().to_owned(),
        target: request.target.trim().to_owned(),
        risk: request.risk,
        requested_capabilities: capabilities,
        status: if requires_hitl { EffectStatus::PendingApproval } else { EffectStatus::Authorized },
        requires_hitl,
        manifest_hash,
        created_at: Utc::now(),
        approval: None,
    };
    let expected = session.state_version;
    session.state = if requires_hitl { SessionState::WaitingApproval } else { SessionState::Planning };
    session.effects.push(effect.clone());
    persist_session(&state, &mut session, expected).await?;
    let item = receipt(
        &state,
        id,
        &session.knight_id,
        "shadow.effect.propose",
        effect.risk,
        if requires_hitl { "WAIT_HITL" } else { "ALLOW" },
        &effect.target,
        &serde_json::to_value(&effect).unwrap_or(Value::Null),
    ).await?;
    bump_receipt_metadata(&state, id, &item.receipt_hash).await?;
    Ok((StatusCode::CREATED, Json(effect)))
}

async fn approve_effect(
    State(state): State<AppState>,
    Path((session_id, effect_id)): Path<(Uuid, Uuid)>,
    Json(request): Json<ApproveEffectRequest>,
) -> Result<Json<ShadowEffect>, ApiError> {
    if request.operator.trim().is_empty() || request.operator.len() > 160 {
        return Err(api_error(StatusCode::BAD_REQUEST, "Invalid operator identity"));
    }
    let scope = request.scope.unwrap_or_else(|| "once".into());
    let mut session = load_session(&state, session_id).await?;
    live(&session)?;
    let effect_index = session.effects.iter().position(|effect| effect.effect_id == effect_id)
        .ok_or_else(|| api_error(StatusCode::NOT_FOUND, "Unknown shadow effect"))?;
    let current = session.effects[effect_index].clone();
    if current.status == EffectStatus::Authorized {
        if current.approval.as_ref().map(|a| (a.operator.as_str(), a.scope.as_str()))
            == Some((request.operator.trim(), scope.as_str())) {
            return Ok(Json(current));
        }
        return Err(api_error(StatusCode::CONFLICT, "Effect already authorized by another decision"));
    }
    if current.status != EffectStatus::PendingApproval {
        return Err(api_error(StatusCode::CONFLICT, "Effect is not awaiting approval"));
    }
    if current.risk == RiskRing::R6 {
        if !state.allow_r6 || scope != "sovereign" {
            return Err(api_error(StatusCode::FORBIDDEN, "R6 requires enabled sovereign authentication and sovereign scope"));
        }
    }
    let expected = session.state_version;
    let effect = &mut session.effects[effect_index];
    effect.status = EffectStatus::Authorized;
    effect.approval = Some(ApprovalRecord {
        operator: request.operator.trim().to_owned(),
        scope,
        note: request.note,
        approved_at: Utc::now(),
    });
    let output = effect.clone();
    session.state = SessionState::Planning;
    persist_session(&state, &mut session, expected).await?;
    let item = receipt(
        &state,
        session_id,
        &session.knight_id,
        "shadow.effect.approve",
        output.risk,
        "HITL_ALLOW",
        &output.target,
        &serde_json::to_value(&output).unwrap_or(Value::Null),
    ).await?;
    bump_receipt_metadata(&state, session_id, &item.receipt_hash).await?;
    Ok(Json(output))
}

async fn deny_effect(
    State(state): State<AppState>,
    Path((session_id, effect_id)): Path<(Uuid, Uuid)>,
    Json(request): Json<DenyEffectRequest>,
) -> Result<Json<ShadowEffect>, ApiError> {
    if request.operator.trim().is_empty() || request.operator.len() > 160 {
        return Err(api_error(StatusCode::BAD_REQUEST, "Invalid operator identity"));
    }
    let mut session = load_session(&state, session_id).await?;
    live(&session)?;
    let effect_index = session.effects.iter().position(|effect| effect.effect_id == effect_id)
        .ok_or_else(|| api_error(StatusCode::NOT_FOUND, "Unknown shadow effect"))?;
    let current = session.effects[effect_index].clone();
    if current.status == EffectStatus::Denied {
        if current.approval.as_ref().map(|a| a.operator.as_str()) == Some(request.operator.trim()) {
            return Ok(Json(current));
        }
        return Err(api_error(StatusCode::CONFLICT, "Effect already denied by another decision"));
    }
    if current.status != EffectStatus::PendingApproval {
        return Err(api_error(StatusCode::CONFLICT, "Only effects awaiting HITL may be denied"));
    }
    let expected = session.state_version;
    let effect = &mut session.effects[effect_index];
    effect.status = EffectStatus::Denied;
    effect.approval = Some(ApprovalRecord {
        operator: request.operator.trim().to_owned(),
        scope: "deny".into(),
        note: request.note,
        approved_at: Utc::now(),
    });
    let output = effect.clone();
    session.state = SessionState::Planning;
    persist_session(&state, &mut session, expected).await?;
    let item = receipt(
        &state,
        session_id,
        &session.knight_id,
        "shadow.effect.deny",
        output.risk,
        "HITL_DENY",
        &output.target,
        &serde_json::to_value(&output).unwrap_or(Value::Null),
    ).await?;
    bump_receipt_metadata(&state, session_id, &item.receipt_hash).await?;
    Ok(Json(output))
}

async fn write_shadow_file(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
    Json(request): Json<WriteFileRequest>,
) -> Result<Json<Value>, ApiError> {
    if request.content.len() > MAX_TEXT_FILE_BYTES {
        return Err(api_error(StatusCode::PAYLOAD_TOO_LARGE, "Shadow write exceeds 256KB limit"));
    }
    let relative = safe_relative(&request.path)?;
    let session = load_session(&state, id).await?;
    live(&session)?;
    if !session.capabilities.iter().any(|cap| cap == "shadow.write") {
        return Err(api_error(StatusCode::FORBIDDEN, "shadow.write capability not leased"));
    }
    let path = state.shadow_root.join(id.to_string()).join("workspace").join(&relative);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent).await.map_err(internal)?;
    }
    fs::write(&path, request.content.as_bytes()).await.map_err(internal)?;
    let item = receipt(
        &state,
        id,
        &session.knight_id,
        "shadow.vfs.write",
        RiskRing::R2,
        "ALLOW",
        &format!("shadow://{id}/workspace/{}", relative.display()),
        &json!({ "path": relative, "bytes": request.content.len(), "contentHash": hash_payload(&request.content) }),
    ).await?;
    bump_receipt_metadata(&state, id, &item.receipt_hash).await?;
    Ok(Json(json!({ "status": "written", "path": relative, "receipt": item })))
}

async fn read_shadow_file(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
    Query(query): Query<ReadFileQuery>,
) -> Result<Json<Value>, ApiError> {
    let relative = safe_relative(&query.path)?;
    let session = load_session(&state, id).await?;
    live(&session)?;
    if !session.capabilities.iter().any(|cap| cap == "shadow.read") {
        return Err(api_error(StatusCode::FORBIDDEN, "shadow.read capability not leased"));
    }
    let path = state.shadow_root.join(id.to_string()).join("workspace").join(&relative);
    let metadata = fs::metadata(&path).await.map_err(|_| api_error(StatusCode::NOT_FOUND, "Shadow file not found"))?;
    if metadata.len() > MAX_TEXT_FILE_BYTES as u64 {
        return Err(api_error(StatusCode::PAYLOAD_TOO_LARGE, "Shadow read exceeds 256KB limit"));
    }
    let content = fs::read_to_string(&path).await.map_err(|error| api_error(StatusCode::BAD_REQUEST, format!("Shadow file is not readable text: {error}")))?;
    Ok(Json(json!({ "path": relative, "content": content, "contentHash": hash_payload(&content) })))
}

async fn list_receipts(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<Vec<ShadowReceipt>>, ApiError> {
    Ok(Json(state.store.receipts_for(id).await.map_err(internal)?))
}

async fn seal_session(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Result<Json<Value>, ApiError> {
    let mut session = load_session(&state, id).await?;
    if session.state == SessionState::Sealed {
        return Ok(Json(json!({ "status": "sealed", "sessionId": id, "workspaceRemoved": true, "idempotent": true })));
    }
    live(&session)?;
    let expected = session.state_version;
    session.state = SessionState::Verifying;
    persist_session(&state, &mut session, expected).await?;
    let item = receipt(
        &state,
        id,
        &session.knight_id,
        "shadow.session.seal",
        RiskRing::R3,
        "SEALED",
        &format!("shadow://{id}"),
        &json!({ "ephemeralWorkspace": true }),
    ).await?;
    let workspace = state.shadow_root.join(id.to_string());
    if let Err(error) = fs::remove_dir_all(&workspace).await {
        if error.kind() != std::io::ErrorKind::NotFound {
            return Err(internal(error));
        }
    }
    let mut session = load_session(&state, id).await?;
    let expected = session.state_version;
    session.state = SessionState::Sealed;
    session.receipt_count += 1;
    session.last_receipt_hash = Some(item.receipt_hash.clone());
    persist_session(&state, &mut session, expected).await?;
    Ok(Json(json!({ "status": "sealed", "sessionId": id, "workspaceRemoved": true, "receipt": item })))
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let host = env::var("CAMELOT_SHADOW_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let port = env::var("CAMELOT_SHADOW_PORT").ok().and_then(|value| value.parse::<u16>().ok()).unwrap_or(4190);
    let token = env::var("CAMELOT_SHADOW_TOKEN").expect("CAMELOT_SHADOW_TOKEN must be set; shadowd refuses unauthenticated startup");
    let allow_r6 = env::var("CAMELOT_SHADOW_ALLOW_R6").map(|value| value == "1").unwrap_or(false);
    if token.len() < 24 {
        panic!("CAMELOT_SHADOW_TOKEN must contain at least 24 characters");
    }
    if host != "127.0.0.1" && host != "::1" {
        panic!("camelot-shadowd is loopback-only; use Bifrost for governed access");
    }

    let shadow_root = PathBuf::from(env::var("CAMELOT_SHADOW_ROOT").unwrap_or_else(|_| "/var/lib/camelot/shadow".into()));
    fs::create_dir_all(&shadow_root).await.expect("create shadow root");
    let db_path = PathBuf::from(env::var("CAMELOT_SHADOW_DB").unwrap_or_else(|_| shadow_root.join("shadow.db").to_string_lossy().into_owned()));
    let receipt_path = PathBuf::from(env::var("CAMELOT_SHADOW_RECEIPT_MIRROR").unwrap_or_else(|_| shadow_root.join("ledger").join("receipts.jsonl").to_string_lossy().into_owned()));
    let signer_path = PathBuf::from(env::var("CAMELOT_SHADOW_SIGNING_KEY").unwrap_or_else(|_| shadow_root.join("keys").join("receipt-ed25519.key").to_string_lossy().into_owned()));

    let store = ShadowStore::open(&db_path).await.expect("open durable Shadow store");
    let signer = load_or_create_signer(&signer_path).expect("load persistent Shadow signing identity");
    let verified_head = verify_ledger(&store).await.expect("Shadow receipt ledger verification failed; refusing startup");
    let state = AppState {
        store,
        signer: Arc::new(signer),
        ledger_lock: Arc::new(Mutex::new(())),
        ledger_verified: Arc::new(AtomicBool::new(true)),
        shadow_root: Arc::new(shadow_root),
        receipt_path: Arc::new(receipt_path),
        api_token: Arc::new(token),
        allow_r6,
        instance_id: Uuid::new_v4(),
    };
    let recovered = recover_sessions(&state).await.expect("recover durable Shadow sessions");

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
        .route("/health", get(health_ready))
        .route("/health/live", get(health_live))
        .route("/health/ready", get(health_ready))
        .merge(protected)
        .layer(DefaultBodyLimit::max(512 * 1024))
        .layer(TraceLayer::new_for_http())
        .with_state(state.clone());

    let listener = tokio::net::TcpListener::bind(format!("{host}:{port}")).await.expect("bind shadowd");
    info!(
        host,
        port,
        recovered_sessions = recovered,
        ledger_head = ?verified_head,
        policy = POLICY_VERSION,
        r6_enabled = allow_r6,
        signer = %state.signer.public_key_hex(),
        instance_id = %state.instance_id,
        "camelot-shadowd production-hardened runtime online"
    );
    axum::serve(listener, app).await.expect("shadowd server failed");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_unsafe_shadow_paths() {
        assert!(safe_relative("workspace/file.txt").is_ok());
        assert!(safe_relative("../escape").is_err());
        assert!(safe_relative("/absolute/path").is_err());
        assert!(safe_relative(".").is_err());
    }

    #[test]
    fn bounds_capabilities_and_egress() {
        assert!(bounded_capabilities(Some(vec!["shadow.read".into()])).is_ok());
        assert!(bounded_capabilities(Some(vec!["host.shell".into()])).is_err());
        assert!(bounded_egress(Some(vec!["bifrost://governed".into()])).is_ok());
        assert!(bounded_egress(Some(vec!["https://example.com".into()])).is_err());
    }
}
