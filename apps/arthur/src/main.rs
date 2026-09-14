use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use camelot_crypto::{verify_detached_hex, KeyPair};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    env, fs,
    io::Write,
    net::IpAddr,
    path::{Path, PathBuf},
    sync::Arc,
};
use tracing::info;
use uuid::Uuid;

const RESOLUTION_SCHEMA: &str = "arthur-resolution/1";
const GIDEON_SCHEMA: &str = "gideon-verdict/1";

#[derive(Clone)]
struct AppState {
    signer: Arc<KeyPair>,
    gideon_public_key: Arc<String>,
    authority_epoch: u64,
}

#[derive(Debug, Serialize, Deserialize, Clone, Copy, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
enum GideonKind {
    Pass,
    Fail,
    Inconclusive,
    Quarantine,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
struct GideonVerdict {
    schema_version: String,
    verdict_id: Uuid,
    timestamp: DateTime<Utc>,
    tenant_id: String,
    workspace_id: String,
    mission_id: String,
    task_id: String,
    manifest_hash: String,
    result_hash: String,
    vfs_attestation_id: Option<String>,
    authority_epoch: u64,
    verdict: GideonKind,
    reason: String,
    evidence_hash: String,
    verification_mode: String,
    formal_proof: bool,
    signer_public_key: String,
    signature: String,
}

impl GideonVerdict {
    fn signing_payload(&self) -> Result<Vec<u8>, String> {
        let mut unsigned = self.clone();
        unsigned.signature.clear();
        serde_json::to_vec(&unsigned).map_err(|error| format!("serialize Gideon verdict: {error}"))
    }

    fn verify(&self, expected_key: &str) -> Result<(), String> {
        if self.schema_version != GIDEON_SCHEMA {
            return Err("unsupported Gideon verdict schema".into());
        }
        if self.signer_public_key != expected_key {
            return Err("Gideon verdict signer does not match pinned identity".into());
        }
        let signature = self
            .signature
            .strip_prefix("ed25519:")
            .ok_or_else(|| "Gideon signature must use ed25519 prefix".to_string())?;
        verify_detached_hex(expected_key, &self.signing_payload()?, signature)
    }
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ResolveRequest {
    verdict: GideonVerdict,
    promotion_preconditions_met: bool,
    #[serde(default)]
    retryable: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone, Copy, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
enum ResolutionKind {
    Resolved,
    Retry,
    Rejected,
    Quarantined,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
struct ArthurResolution {
    schema_version: String,
    resolution_id: Uuid,
    timestamp: DateTime<Utc>,
    tenant_id: String,
    workspace_id: String,
    mission_id: String,
    task_id: String,
    gideon_verdict_id: Uuid,
    manifest_hash: String,
    result_hash: String,
    authority_epoch: u64,
    resolution: ResolutionKind,
    reason: String,
    effect_authorized: bool,
    signer_public_key: String,
    signature: String,
}

impl ArthurResolution {
    fn signing_payload(&self) -> Result<Vec<u8>, String> {
        let mut unsigned = self.clone();
        unsigned.signature.clear();
        serde_json::to_vec(&unsigned)
            .map_err(|error| format!("serialize Arthur resolution: {error}"))
    }

    fn sign_with(&mut self, signer: &KeyPair) -> Result<(), String> {
        self.signer_public_key = signer.public_key_hex();
        self.signature = format!("ed25519:{}", signer.sign_hex(&self.signing_payload()?));
        Ok(())
    }

    #[cfg(test)]
    fn verify_signature(&self) -> Result<(), String> {
        let signature = self
            .signature
            .strip_prefix("ed25519:")
            .ok_or_else(|| "Arthur signature must use ed25519 prefix".to_string())?;
        verify_detached_hex(&self.signer_public_key, &self.signing_payload()?, signature)
    }
}

fn valid_key(value: &str) -> bool {
    value.len() == 64 && value.bytes().all(|byte| byte.is_ascii_hexdigit())
}

fn resolve(
    verdict: &GideonVerdict,
    promotion_preconditions_met: bool,
    retryable: bool,
    authority_epoch: u64,
) -> (ResolutionKind, String) {
    if verdict.authority_epoch != authority_epoch {
        return (
            ResolutionKind::Quarantined,
            "Gideon verdict belongs to a stale authority epoch".into(),
        );
    }
    match verdict.verdict {
        GideonKind::Quarantine => (
            ResolutionKind::Quarantined,
            "Gideon explicitly quarantined the result".into(),
        ),
        GideonKind::Inconclusive => (
            ResolutionKind::Retry,
            "verification is inconclusive; more evidence is required".into(),
        ),
        GideonKind::Fail if retryable => (
            ResolutionKind::Retry,
            "verification failed but the task is marked retryable".into(),
        ),
        GideonKind::Fail => (
            ResolutionKind::Rejected,
            "verification failed and result is rejected".into(),
        ),
        GideonKind::Pass if !promotion_preconditions_met => (
            ResolutionKind::Retry,
            "verification passed but promotion preconditions are incomplete".into(),
        ),
        GideonKind::Pass => (
            ResolutionKind::Resolved,
            "verification passed and promotion preconditions are satisfied".into(),
        ),
    }
}

fn load_or_create_signer(path: &Path) -> Result<KeyPair, String> {
    if path.exists() {
        let raw = fs::read_to_string(path)
            .map_err(|error| format!("read Arthur signing key: {error}"))?;
        return KeyPair::from_secret_hex(raw.trim());
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("create Arthur key directory: {error}"))?;
    }
    let signer = KeyPair::generate();
    let mut options = fs::OpenOptions::new();
    options.create_new(true).write(true);
    #[cfg(unix)]
    {
        use std::os::unix::fs::OpenOptionsExt;
        options.mode(0o600);
    }
    let mut file = options
        .open(path)
        .map_err(|error| format!("create Arthur signing key: {error}"))?;
    file.write_all(signer.secret_key_hex().as_bytes())
        .map_err(|error| format!("write Arthur signing key: {error}"))?;
    file.write_all(b"\n")
        .map_err(|error| format!("finalize Arthur signing key: {error}"))?;
    file.sync_all()
        .map_err(|error| format!("sync Arthur signing key: {error}"))?;
    Ok(signer)
}

async fn health(State(state): State<AppState>) -> Json<Value> {
    Json(json!({
        "status": "ready",
        "service": "arthur",
        "schema": RESOLUTION_SCHEMA,
        "authorityEpoch": state.authority_epoch,
        "gideonPublicKey": state.gideon_public_key.as_str(),
        "signerPublicKey": state.signer.public_key_hex(),
        "effectAuthority": false
    }))
}

async fn handle_resolve(
    State(state): State<AppState>,
    Json(request): Json<ResolveRequest>,
) -> Result<(StatusCode, Json<ArthurResolution>), (StatusCode, Json<Value>)> {
    request
        .verdict
        .verify(state.gideon_public_key.as_str())
        .map_err(|error| (StatusCode::UNAUTHORIZED, Json(json!({ "error": error }))))?;

    let (resolution, reason) = resolve(
        &request.verdict,
        request.promotion_preconditions_met,
        request.retryable,
        state.authority_epoch,
    );
    let mut output = ArthurResolution {
        schema_version: RESOLUTION_SCHEMA.into(),
        resolution_id: Uuid::new_v4(),
        timestamp: Utc::now(),
        tenant_id: request.verdict.tenant_id,
        workspace_id: request.verdict.workspace_id,
        mission_id: request.verdict.mission_id,
        task_id: request.verdict.task_id,
        gideon_verdict_id: request.verdict.verdict_id,
        manifest_hash: request.verdict.manifest_hash,
        result_hash: request.verdict.result_hash,
        authority_epoch: request.verdict.authority_epoch,
        resolution,
        reason,
        effect_authorized: false,
        signer_public_key: state.signer.public_key_hex(),
        signature: String::new(),
    };
    output.sign_with(&state.signer).map_err(|error| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": error })),
        )
    })?;
    Ok((StatusCode::OK, Json(output)))
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();
    let authority_epoch = env::var("CAMELOT_AUTHORITY_EPOCH")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(1);
    if authority_epoch == 0 {
        panic!("CAMELOT_AUTHORITY_EPOCH must be greater than zero");
    }
    let gideon_public_key = env::var("CAMELOT_GIDEON_PUBLIC_KEY")
        .expect("CAMELOT_GIDEON_PUBLIC_KEY must pin the Gideon verifier identity");
    if !valid_key(&gideon_public_key) {
        panic!("CAMELOT_GIDEON_PUBLIC_KEY must be a 32-byte Ed25519 public key in hex");
    }
    let key_path = PathBuf::from(
        env::var("CAMELOT_ARTHUR_SIGNING_KEY")
            .unwrap_or_else(|_| "/var/lib/camelot/arthur/resolution-ed25519.key".into()),
    );
    let signer = load_or_create_signer(&key_path).expect("load Arthur signing identity");
    let state = AppState {
        signer: Arc::new(signer),
        gideon_public_key: Arc::new(gideon_public_key),
        authority_epoch,
    };
    let app = Router::new()
        .route("/health", get(health))
        .route("/resolve", post(handle_resolve))
        .with_state(state.clone());

    let host = env::var("CAMELOT_ARTHUR_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let parsed_host: IpAddr = host
        .parse()
        .expect("CAMELOT_ARTHUR_HOST must be an IP address");
    if !parsed_host.is_loopback() {
        panic!("Arthur must remain loopback-only behind Camelot controls");
    }
    let port = env::var("CAMELOT_ARTHUR_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(3013);
    let listener = tokio::net::TcpListener::bind((parsed_host, port))
        .await
        .expect("bind Arthur");
    info!(
        authority_epoch,
        signer_public_key = %state.signer.public_key_hex(),
        "Arthur final resolution gate online; execution authority disabled"
    );
    axum::serve(listener, app)
        .await
        .expect("Arthur server failed");
}

#[cfg(test)]
mod tests {
    use super::*;

    fn verdict(kind: GideonKind, epoch: u64, signer: &KeyPair) -> GideonVerdict {
        let mut value = GideonVerdict {
            schema_version: GIDEON_SCHEMA.into(),
            verdict_id: Uuid::new_v4(),
            timestamp: Utc::now(),
            tenant_id: "tenant-a".into(),
            workspace_id: "workspace-a".into(),
            mission_id: "mission-a".into(),
            task_id: "task-a".into(),
            manifest_hash: format!("sha256:{}", "a".repeat(64)),
            result_hash: format!("sha256:{}", "b".repeat(64)),
            vfs_attestation_id: Some("vfs-a".into()),
            authority_epoch: epoch,
            verdict: kind,
            reason: "test".into(),
            evidence_hash: format!("sha256:{}", "c".repeat(64)),
            verification_mode: "evidence-gate".into(),
            formal_proof: false,
            signer_public_key: signer.public_key_hex(),
            signature: String::new(),
        };
        value.signature = format!(
            "ed25519:{}",
            signer.sign_hex(&value.signing_payload().expect("payload"))
        );
        value
    }

    #[test]
    fn resolves_only_passing_current_epoch() {
        let signer = KeyPair::generate();
        let passing = verdict(GideonKind::Pass, 5, &signer);
        assert_eq!(
            resolve(&passing, true, false, 5).0,
            ResolutionKind::Resolved
        );
        assert_eq!(resolve(&passing, false, false, 5).0, ResolutionKind::Retry);
        assert_eq!(
            resolve(&passing, true, false, 6).0,
            ResolutionKind::Quarantined
        );
    }

    #[test]
    fn signed_resolution_verifies() {
        let signer = KeyPair::generate();
        let mut resolution = ArthurResolution {
            schema_version: RESOLUTION_SCHEMA.into(),
            resolution_id: Uuid::new_v4(),
            timestamp: Utc::now(),
            tenant_id: "tenant-a".into(),
            workspace_id: "workspace-a".into(),
            mission_id: "mission-a".into(),
            task_id: "task-a".into(),
            gideon_verdict_id: Uuid::new_v4(),
            manifest_hash: format!("sha256:{}", "a".repeat(64)),
            result_hash: format!("sha256:{}", "b".repeat(64)),
            authority_epoch: 1,
            resolution: ResolutionKind::Resolved,
            reason: "test".into(),
            effect_authorized: false,
            signer_public_key: signer.public_key_hex(),
            signature: String::new(),
        };
        resolution.sign_with(&signer).expect("sign");
        resolution.verify_signature().expect("verify");
    }
}
