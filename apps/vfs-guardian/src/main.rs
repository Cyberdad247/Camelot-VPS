use axum::{
    extract::{Request, State},
    http::{header::AUTHORIZATION, StatusCode},
    middleware::{self, Next},
    response::Response,
    routing::{get, post},
    Json, Router,
};
use camelot_crypto::KeyPair;
use camelot_lease::CapabilityLease;
use camelot_vfs::{FileOperation, VfsAttestation};
use serde::{Deserialize, Serialize};
use serde_json::json;
use std::{
    env, fs,
    io::Write,
    net::IpAddr,
    path::{Component, Path, PathBuf},
    sync::Arc,
};
use uuid::Uuid;

const DEFAULT_SENTINEL_ISSUER: &str = "camelot-sentinel";

#[derive(Clone)]
struct AppState {
    signer: Arc<KeyPair>,
    api_token: Arc<String>,
    sentinel_issuer: Arc<String>,
    sentinel_public_key: Arc<String>,
    authority_epoch: u64,
}

#[derive(Debug, Deserialize)]
pub struct VfsRequest {
    pub workspace_id: Uuid,
    pub operation: FileOperation,
    pub lease: CapabilityLease,
}

#[derive(Debug, Serialize)]
pub struct VfsResponse {
    pub allowed: bool,
    pub reason: String,
    pub attestation: Option<VfsAttestation>,
}

fn denied(reason: impl Into<String>) -> (StatusCode, Json<VfsResponse>) {
    (
        StatusCode::FORBIDDEN,
        Json(VfsResponse {
            allowed: false,
            reason: reason.into(),
            attestation: None,
        }),
    )
}

fn load_or_create_signer(path: &Path) -> Result<KeyPair, String> {
    if path.exists() {
        let raw = fs::read_to_string(path)
            .map_err(|error| format!("read VFS signing key: {error}"))?;
        return KeyPair::from_secret_hex(raw.trim());
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("create VFS key directory: {error}"))?;
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
                .map_err(|error| format!("write VFS signing key: {error}"))?;
            file.write_all(b"\n")
                .map_err(|error| format!("finalize VFS signing key: {error}"))?;
            file.sync_all()
                .map_err(|error| format!("sync VFS signing key: {error}"))?;
            Ok(key)
        }
        Err(error) if error.kind() == std::io::ErrorKind::AlreadyExists => {
            let raw = fs::read_to_string(path)
                .map_err(|read_error| format!("read concurrent VFS signing key: {read_error}"))?;
            KeyPair::from_secret_hex(raw.trim())
        }
        Err(error) => Err(format!("create VFS signing key: {error}")),
    }
}

fn safe_relative(input: &str) -> Result<PathBuf, String> {
    if input.is_empty() || input.len() > 512 {
        return Err("VFS path must contain 1..512 characters".into());
    }
    let path = Path::new(input);
    if path
        .components()
        .any(|component| !matches!(component, Component::Normal(_)))
    {
        return Err("VFS path must be relative and cannot traverse".into());
    }
    Ok(path.to_path_buf())
}

fn valid_sha256_reference(value: &str) -> bool {
    let Some(hex) = value.strip_prefix("sha256:") else {
        return false;
    };
    hex.len() == 64 && hex.bytes().all(|value| value.is_ascii_hexdigit())
}

fn resource_uri(workspace_id: Uuid, relative: &Path) -> String {
    format!("vfs://{workspace_id}/{}", relative.display())
}

fn verify_lease(
    state: &AppState,
    workspace_id: Uuid,
    operation: &FileOperation,
    resource: &str,
    lease: &CapabilityLease,
) -> Result<(), String> {
    if lease.issuer_id != state.sentinel_issuer.as_str() {
        return Err("VFS lease issuer is not the configured Sentinel authority".into());
    }
    if lease.issuer_public_key.as_deref() != Some(state.sentinel_public_key.as_str()) {
        return Err("VFS lease public key does not match pinned Sentinel identity".into());
    }
    lease
        .verify_signature()
        .map_err(|error| format!("VFS lease signature invalid: {error}"))?;
    if !lease.is_valid() {
        return Err("VFS lease expired or revoked".into());
    }
    if !lease.is_current_epoch(state.authority_epoch) {
        return Err("VFS lease authority epoch is stale".into());
    }
    if !lease.binds_session(workspace_id) {
        return Err("VFS lease is not bound to this task workspace".into());
    }
    let capability = operation.op_type.capability();
    if !lease.has_capability(capability) {
        return Err(format!("VFS lease lacks capability {capability}"));
    }
    if !lease.resource_allows(resource) {
        return Err("VFS resource is outside the lease path bounds".into());
    }
    if let Some(expected_hash) = operation.expected_hash.as_deref() {
        if !valid_sha256_reference(expected_hash) {
            return Err("VFS expected_hash must be a canonical sha256 reference".into());
        }
    }
    Ok(())
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

async fn health_live() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "service": "vfs-guardian",
        "live": true,
    }))
}

async fn health_ready(State(state): State<AppState>) -> Json<serde_json::Value> {
    Json(json!({
        "status": "ready",
        "service": "vfs-guardian",
        "schema": "vfs-attestation/2",
        "authorityEpoch": state.authority_epoch,
        "sentinelIssuer": state.sentinel_issuer.as_str(),
        "sentinelPublicKey": state.sentinel_public_key.as_str(),
        "attestationSigner": state.signer.public_key_hex(),
    }))
}

async fn request_access(
    State(state): State<AppState>,
    Json(payload): Json<VfsRequest>,
) -> (StatusCode, Json<VfsResponse>) {
    let relative = match safe_relative(&payload.operation.path) {
        Ok(path) => path,
        Err(reason) => return denied(reason),
    };
    let resource = resource_uri(payload.workspace_id, &relative);
    if let Err(reason) = verify_lease(
        &state,
        payload.workspace_id,
        &payload.operation,
        &resource,
        &payload.lease,
    ) {
        return denied(reason);
    }

    let operation_hash = match payload.operation.digest() {
        Ok(hash) => hash,
        Err(error) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(VfsResponse {
                    allowed: false,
                    reason: error,
                    attestation: None,
                }),
            )
        }
    };
    let mut attestation = VfsAttestation::new_unsigned(
        payload.workspace_id,
        payload.lease.lease_id,
        state.authority_epoch,
        resource,
        operation_hash,
        state.signer.public_key_hex(),
    );
    if let Err(error) = attestation.sign_with(&state.signer) {
        return (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(VfsResponse {
                allowed: false,
                reason: format!("could not sign VFS preflight attestation: {error}"),
                attestation: None,
            }),
        );
    }

    (
        StatusCode::OK,
        Json(VfsResponse {
            allowed: true,
            reason: "VFS preflight passed under current Sentinel lease and authority epoch".into(),
            attestation: Some(attestation),
        }),
    )
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let token = env::var("CAMELOT_VFS_TOKEN")
        .expect("CAMELOT_VFS_TOKEN must be set; VFS Guardian refuses unauthenticated access");
    if token.len() < 24 {
        panic!("CAMELOT_VFS_TOKEN must contain at least 24 characters");
    }
    let sentinel_public_key = env::var("CAMELOT_SENTINEL_PUBLIC_KEY")
        .expect("CAMELOT_SENTINEL_PUBLIC_KEY must pin the active Sentinel identity");
    if sentinel_public_key.len() != 64 || !sentinel_public_key.bytes().all(|value| value.is_ascii_hexdigit()) {
        panic!("CAMELOT_SENTINEL_PUBLIC_KEY must be a 32-byte Ed25519 public key in hex");
    }
    let sentinel_issuer = env::var("CAMELOT_SENTINEL_ISSUER")
        .unwrap_or_else(|_| DEFAULT_SENTINEL_ISSUER.into());
    let authority_epoch = env::var("CAMELOT_AUTHORITY_EPOCH")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(1);
    if authority_epoch == 0 {
        panic!("CAMELOT_AUTHORITY_EPOCH must be greater than zero");
    }
    let signer_path = PathBuf::from(
        env::var("CAMELOT_VFS_SIGNING_KEY")
            .unwrap_or_else(|_| "/var/lib/camelot/vfs-guardian/attestation-ed25519.key".into()),
    );
    let signer = load_or_create_signer(&signer_path).expect("load VFS attestation signing identity");
    let state = AppState {
        signer: Arc::new(signer),
        api_token: Arc::new(token),
        sentinel_issuer: Arc::new(sentinel_issuer),
        sentinel_public_key: Arc::new(sentinel_public_key),
        authority_epoch,
    };

    let protected = Router::new()
        .route("/vfs/access", post(request_access))
        .route_layer(middleware::from_fn_with_state(state.clone(), require_token));
    let app = Router::new()
        .route("/health", get(health_ready))
        .route("/health/live", get(health_live))
        .route("/health/ready", get(health_ready))
        .merge(protected)
        .with_state(state.clone());

    let host = env::var("CAMELOT_VFS_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let parsed_host: IpAddr = host.parse().expect("CAMELOT_VFS_HOST must be an IP address");
    if !parsed_host.is_loopback() {
        panic!("VFS Guardian must remain loopback-only behind Camelot transport controls");
    }
    let port = env::var("CAMELOT_VFS_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(3003);
    let listener = tokio::net::TcpListener::bind((parsed_host, port))
        .await
        .expect("bind VFS Guardian");
    tracing::info!(
        authority_epoch = state.authority_epoch,
        sentinel_issuer = %state.sentinel_issuer,
        attestation_signer = %state.signer.public_key_hex(),
        "VFS Guardian signed preflight authority online"
    );
    axum::serve(listener, app)
        .await
        .expect("VFS Guardian server failed");
}

#[cfg(test)]
mod tests {
    use super::*;
    use camelot_vfs::FileOperationType;

    #[test]
    fn rejects_unsafe_paths() {
        assert!(safe_relative("worktree/src/main.rs").is_ok());
        assert!(safe_relative("../escape").is_err());
        assert!(safe_relative("/absolute/path").is_err());
        assert!(safe_relative(".").is_err());
    }

    #[test]
    fn validates_expected_hash_shape() {
        let valid = format!("sha256:{}", "a".repeat(64));
        assert!(valid_sha256_reference(&valid));
        assert!(!valid_sha256_reference("sha256:short"));
        assert!(!valid_sha256_reference(&format!("sha256:{}", "z".repeat(64))));
    }

    #[test]
    fn resource_uri_is_workspace_scoped() {
        let workspace = Uuid::nil();
        let operation = FileOperation {
            op_type: FileOperationType::Write,
            path: "worktree/src/main.rs".into(),
            expected_hash: None,
        };
        let relative = safe_relative(&operation.path).expect("safe path");
        assert_eq!(
            resource_uri(workspace, &relative),
            format!("vfs://{workspace}/worktree/src/main.rs")
        );
    }
}
