use axum::{
    extract::{Request, State},
    http::{header::AUTHORIZATION, StatusCode},
    middleware::{self, Next},
    response::Response,
    routing::{get, post},
    Json, Router,
};
use camelot_crypto::KeyPair;
use camelot_epoch::EpochSource;
use camelot_knight::{is_knight_actor, KnightRegistry};
use camelot_lease::{CapabilityLease, EffectManifest, KnightLeaseBinding};
use chrono::{Duration, Utc};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::{
    env, fs,
    io::Write,
    path::{Path, PathBuf},
    sync::Arc,
};
use tracing::info;
use uuid::Uuid;

const SENTINEL_ISSUER: &str = "camelot-sentinel";
const MAX_LEASE_SECONDS: i64 = 900;
const ALLOWED_CAPABILITIES: &[&str] = &[
    "shadow.read",
    "shadow.write",
    "shadow.plan",
    "bifrost.request",
    "vfs:read",
    "vfs:write",
    "vfs:delete",
    "vfs:quarantine",
    "execute:wasm",
    "cloudbrain:retrieve",
];

#[derive(Clone)]
struct AppState {
    signer: Arc<KeyPair>,
    token: Arc<String>,
    tenant_id: Uuid,
    epoch_source: Arc<EpochSource>,
    knight_registry: Option<Arc<KnightRegistry>>,
}

#[derive(Debug, Deserialize)]
struct IssueLeaseRequest {
    actor_id: String,
    #[serde(default)]
    knight_package_id: Option<String>,
    session_id: Uuid,
    capabilities: Vec<String>,
    resource_bounds: Vec<String>,
    ttl_seconds: Option<i64>,
}

#[derive(Debug, Deserialize)]
pub struct EvaluationRequest {
    pub manifest: EffectManifest,
    pub lease: CapabilityLease,
}

#[derive(Debug, Serialize)]
pub struct PolicyDecision {
    pub allowed: bool,
    pub reason: String,
}

fn load_or_create_signer(path: &Path) -> Result<KeyPair, String> {
    if path.exists() {
        let raw = fs::read_to_string(path)
            .map_err(|error| format!("read Sentinel signing key: {error}"))?;
        return KeyPair::from_secret_hex(raw.trim());
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("create Sentinel key directory: {error}"))?;
    }
    let key = KeyPair::generate();
    let mut options = fs::OpenOptions::new();
    options.create_new(true).write(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    match options.open(path) {
        Ok(mut file) => {
            file.write_all(key.secret_key_hex().as_bytes())
                .map_err(|error| format!("write Sentinel signing key: {error}"))?;
            file.write_all(b"\n")
                .map_err(|error| format!("finalize Sentinel signing key: {error}"))?;
            file.sync_all()
                .map_err(|error| format!("sync Sentinel signing key: {error}"))?;
            Ok(key)
        }
        Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {
            let raw = fs::read_to_string(path)
                .map_err(|read_error| format!("read concurrent Sentinel key: {read_error}"))?;
            KeyPair::from_secret_hex(raw.trim())
        }
        Err(error) => Err(format!("create Sentinel signing key: {error}")),
    }
}

async fn require_token(
    State(state): State<AppState>,
    request: Request,
    next: Next,
) -> Result<Response, StatusCode> {
    let expected = format!("Bearer {}", state.token.as_str());
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

fn resource_allowed_for_session(resource: &str, session_id: Uuid) -> bool {
    let shadow_workspace = format!("shadow://{session_id}/workspace");
    let vfs_workspace = format!("vfs://{session_id}");
    let executor = format!("executor://node-agent/{session_id}");
    let cloudbrain = format!("cloudbrain://notebooklm/{session_id}");
    resource == shadow_workspace
        || resource == format!("{shadow_workspace}/**")
        || resource.starts_with(&format!("{shadow_workspace}/"))
        || resource == vfs_workspace
        || resource == format!("{vfs_workspace}/**")
        || resource.starts_with(&format!("{vfs_workspace}/"))
        || resource == executor
        || resource == cloudbrain
        || resource == format!("{cloudbrain}/**")
        || resource.starts_with(&format!("{cloudbrain}/"))
        || resource == "bifrost://governed"
}

fn current_epoch(state: &AppState) -> Result<u64, String> {
    state.epoch_source.current_epoch()
}

async fn identity(State(state): State<AppState>) -> (StatusCode, Json<serde_json::Value>) {
    match current_epoch(&state) {
        Ok(epoch) => (
            StatusCode::OK,
            Json(json!({
                "issuerId": SENTINEL_ISSUER,
                "publicKey": state.signer.public_key_hex(),
                "tenantId": state.tenant_id,
                "authorityEpoch": epoch,
                "dynamicEpoch": state.epoch_source.is_dynamic(),
                "knightRegistryEnabled": state.knight_registry.is_some(),
                "maxLeaseSeconds": MAX_LEASE_SECONDS,
            })),
        ),
        Err(error) => (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(json!({ "error": format!("authority epoch unavailable: {error}") })),
        ),
    }
}

async fn health(State(state): State<AppState>) -> (StatusCode, Json<serde_json::Value>) {
    match current_epoch(&state) {
        Ok(epoch) => (
            StatusCode::OK,
            Json(json!({
                "status": "ready",
                "service": "sentinel",
                "issuerId": SENTINEL_ISSUER,
                "publicKey": state.signer.public_key_hex(),
                "authorityEpoch": epoch,
                "dynamicEpoch": state.epoch_source.is_dynamic(),
                "knightRegistryEnabled": state.knight_registry.is_some(),
            })),
        ),
        Err(error) => (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(json!({
                "status": "not_ready",
                "service": "sentinel",
                "reason": error
            })),
        ),
    }
}

fn verify_knight_binding(state: &AppState, lease: &CapabilityLease) -> Result<(), String> {
    match (is_knight_actor(&lease.actor_id), lease.knight_binding.as_ref()) {
        (false, None) => Ok(()),
        (false, Some(_)) => Err("non-Knight lease contains Knight package binding".into()),
        (true, None) => Err("Knight lease is missing signed package binding".into()),
        (true, Some(binding)) => {
            let registry = state
                .knight_registry
                .as_ref()
                .ok_or_else(|| "Knight registry is not configured".to_string())?;
            let loaded = registry.load_for_actor(&lease.actor_id, &binding.package_id)?;
            if loaded.package_digest != binding.package_digest
                || loaded.persona_id != binding.persona_id
                || loaded.persona_class != binding.persona_class
            {
                return Err("Knight lease package binding no longer matches registry".into());
            }
            Ok(())
        }
    }
}

async fn issue_lease(
    State(state): State<AppState>,
    Json(request): Json<IssueLeaseRequest>,
) -> Result<(StatusCode, Json<CapabilityLease>), (StatusCode, Json<serde_json::Value>)> {
    let authority_epoch = current_epoch(&state).map_err(|error| {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(json!({ "error": format!("authority epoch unavailable: {error}") })),
        )
    })?;
    let actor = request.actor_id.trim();
    if actor.is_empty() || actor.len() > 96 {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "invalid actor id" })),
        ));
    }

    let knight_binding = if is_knight_actor(actor) {
        let package_id = request.knight_package_id.as_deref().ok_or_else(|| {
            (
                StatusCode::FORBIDDEN,
                Json(json!({ "error": "Knight actors require knight_package_id" })),
            )
        })?;
        let registry = state.knight_registry.as_ref().ok_or_else(|| {
            (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(json!({ "error": "Knight registry is not configured" })),
            )
        })?;
        let loaded = registry.load_for_actor(actor, package_id).map_err(|error| {
            (
                StatusCode::FORBIDDEN,
                Json(json!({ "error": format!("Knight package rejected: {error}") })),
            )
        })?;
        for capability in &request.capabilities {
            if loaded.prohibits(capability) {
                return Err((
                    StatusCode::FORBIDDEN,
                    Json(json!({
                        "error": format!("Knight package prohibits capability: {capability}")
                    })),
                ));
            }
        }
        Some(KnightLeaseBinding {
            package_id: loaded.package_id,
            package_digest: loaded.package_digest,
            persona_id: loaded.persona_id,
            persona_class: loaded.persona_class,
        })
    } else {
        if request.knight_package_id.is_some() {
            return Err((
                StatusCode::BAD_REQUEST,
                Json(json!({ "error": "knight_package_id is valid only for knight: actors" })),
            ));
        }
        None
    };
    if request.capabilities.is_empty() || request.capabilities.len() > ALLOWED_CAPABILITIES.len() {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "invalid capability set" })),
        ));
    }
    for capability in &request.capabilities {
        if !ALLOWED_CAPABILITIES.contains(&capability.as_str()) {
            return Err((
                StatusCode::FORBIDDEN,
                Json(json!({ "error": format!("capability not issuable: {capability}") })),
            ));
        }
    }
    if request.resource_bounds.is_empty() || request.resource_bounds.len() > 4 {
        return Err((
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "invalid resource bounds" })),
        ));
    }
    for resource in &request.resource_bounds {
        if !resource_allowed_for_session(resource, request.session_id) {
            return Err((
                StatusCode::FORBIDDEN,
                Json(json!({ "error": format!("resource outside session authority: {resource}") })),
            ));
        }
    }

    let ttl = request
        .ttl_seconds
        .unwrap_or(300)
        .clamp(30, MAX_LEASE_SECONDS);
    let now = Utc::now();
    let mut lease = CapabilityLease {
        lease_id: Uuid::new_v4(),
        tenant_id: state.tenant_id,
        actor_id: actor.to_owned(),
        knight_binding,
        session_id: Some(request.session_id),
        capabilities: request.capabilities,
        resource_bounds: request.resource_bounds,
        issued_at: now,
        expires_at: now + Duration::seconds(ttl),
        issuer_id: SENTINEL_ISSUER.into(),
        nonce: Uuid::new_v4().to_string(),
        authority_epoch,
        revoked: false,
        issuer_public_key: None,
        signature: None,
    };
    lease.sign_with(&state.signer).map_err(|error| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": error })),
        )
    })?;

    Ok((StatusCode::CREATED, Json(lease)))
}

async fn evaluate_policy(
    State(state): State<AppState>,
    Json(payload): Json<EvaluationRequest>,
) -> (StatusCode, Json<PolicyDecision>) {
    let authority_epoch = match current_epoch(&state) {
        Ok(epoch) => epoch,
        Err(error) => {
            return deny(
                StatusCode::SERVICE_UNAVAILABLE,
                &format!("Authority epoch unavailable: {error}"),
            )
        }
    };
    let lease = payload.lease;
    let manifest = payload.manifest;

    if lease.issuer_id != SENTINEL_ISSUER
        || lease.issuer_public_key.as_deref() != Some(state.signer.public_key_hex().as_str())
    {
        return deny(StatusCode::UNAUTHORIZED, "Lease issuer identity mismatch");
    }
    if let Err(error) = lease.verify_signature() {
        return deny(
            StatusCode::UNAUTHORIZED,
            &format!("Invalid lease signature: {error}"),
        );
    }
    if !lease.is_valid() {
        return deny(StatusCode::FORBIDDEN, "Lease expired or revoked");
    }
    if let Err(error) = verify_knight_binding(&state, &lease) {
        return deny(
            StatusCode::FORBIDDEN,
            &format!("Knight package binding rejected: {error}"),
        );
    }
    if !lease.is_current_epoch(authority_epoch) {
        return deny(StatusCode::FORBIDDEN, "Lease authority epoch is stale");
    }
    if !lease.has_capability(&manifest.required_lease_type) {
        return deny(
            StatusCode::FORBIDDEN,
            &format!(
                "Lease lacks required capability: {}",
                manifest.required_lease_type
            ),
        );
    }
    if !lease.resource_allows(&manifest.target_resource) {
        return deny(
            StatusCode::FORBIDDEN,
            "Target resource is outside lease bounds",
        );
    }
    if let Some(session_id) = lease.session_id {
        if manifest.task_id != session_id {
            return deny(
                StatusCode::FORBIDDEN,
                "Manifest is not bound to the lease session",
            );
        }
    }

    (
        StatusCode::OK,
        Json(PolicyDecision {
            allowed: true,
            reason: "Manifest authorized by current Sentinel-signed capability lease".into(),
        }),
    )
}

fn deny(status: StatusCode, reason: &str) -> (StatusCode, Json<PolicyDecision>) {
    (
        status,
        Json(PolicyDecision {
            allowed: false,
            reason: reason.to_owned(),
        }),
    )
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let token = env::var("CAMELOT_SENTINEL_TOKEN").expect(
        "CAMELOT_SENTINEL_TOKEN must be set; Sentinel refuses unauthenticated authority requests",
    );
    if token.len() < 24 {
        panic!("CAMELOT_SENTINEL_TOKEN must contain at least 24 characters");
    }
    let key_path = PathBuf::from(
        env::var("CAMELOT_SENTINEL_SIGNING_KEY")
            .unwrap_or_else(|_| "/var/lib/camelot/sentinel/lease-ed25519.key".into()),
    );
    let signer = load_or_create_signer(&key_path).expect("load Sentinel signing identity");
    let tenant_id = env::var("CAMELOT_TENANT_ID")
        .ok()
        .and_then(|value| Uuid::parse_str(&value).ok())
        .unwrap_or_else(Uuid::nil);
    let epoch_source =
        Arc::new(EpochSource::from_environment().expect("load signed authority epoch source"));
    let boot_epoch = epoch_source
        .current_epoch()
        .expect("verify current authority epoch at Sentinel startup");
    let knight_registry =
        KnightRegistry::from_environment().expect("configure signed Knight registry");
    let state = AppState {
        signer: Arc::new(signer),
        token: Arc::new(token),
        tenant_id,
        epoch_source,
        knight_registry: knight_registry.map(Arc::new),
    };

    let protected = Router::new()
        .route("/leases/issue", post(issue_lease))
        .route("/evaluate", post(evaluate_policy))
        .route_layer(middleware::from_fn_with_state(state.clone(), require_token));
    let app = Router::new()
        .route("/health", get(health))
        .route("/identity", get(identity))
        .merge(protected)
        .with_state(state.clone());

    let listener = tokio::net::TcpListener::bind("127.0.0.1:3002")
        .await
        .expect("bind Sentinel");
    info!(
        issuer = SENTINEL_ISSUER,
        public_key = %state.signer.public_key_hex(),
        authority_epoch = boot_epoch,
        dynamic_epoch = state.epoch_source.is_dynamic(),
        knight_registry = state.knight_registry.is_some(),
        "Sentinel signed capability authority online"
    );
    axum::serve(listener, app)
        .await
        .expect("Sentinel server failed");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bounds_shadow_vfs_executor_and_cloudbrain_resources_to_the_session() {
        let session = Uuid::new_v4();
        assert!(resource_allowed_for_session(
            &format!("shadow://{session}/workspace/**"),
            session
        ));
        assert!(resource_allowed_for_session(
            &format!("vfs://{session}/**"),
            session
        ));
        assert!(resource_allowed_for_session(
            &format!("executor://node-agent/{session}"),
            session
        ));
        assert!(resource_allowed_for_session(
            &format!("cloudbrain://notebooklm/{session}/notebook-a"),
            session
        ));
        assert!(!resource_allowed_for_session(
            "shadow://someone-else/workspace/**",
            session
        ));
        assert!(!resource_allowed_for_session(
            "vfs://someone-else/**",
            session
        ));
        assert!(!resource_allowed_for_session(
            "executor://node-agent/someone-else",
            session
        ));
        assert!(!resource_allowed_for_session(
            "cloudbrain://notebooklm/someone-else/notebook-a",
            session
        ));
    }
}
