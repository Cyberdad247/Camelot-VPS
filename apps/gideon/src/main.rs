use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
#[cfg(test)]
use camelot_crypto::verify_detached_hex;
use camelot_crypto::{hash_payload, KeyPair};
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

const VERDICT_SCHEMA: &str = "gideon-verdict/1";

#[derive(Clone)]
struct AppState {
    signer: Arc<KeyPair>,
    authority_epoch: u64,
}

#[derive(Debug, Deserialize, Serialize, Clone)]
#[serde(rename_all = "camelCase")]
struct EvidenceCheck {
    name: String,
    passed: bool,
    #[serde(default = "required_default")]
    required: bool,
    #[serde(default)]
    evidence_hash: Option<String>,
}

fn required_default() -> bool {
    true
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct VerifyRequest {
    tenant_id: String,
    workspace_id: String,
    mission_id: String,
    task_id: String,
    manifest_hash: String,
    result_hash: String,
    vfs_attestation_id: Option<String>,
    authority_epoch: u64,
    executor_exit_code: i32,
    #[serde(default)]
    checks: Vec<EvidenceCheck>,
}

#[derive(Debug, Serialize, Deserialize, Clone, Copy, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
enum VerdictKind {
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
    verdict: VerdictKind,
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
            .ok_or_else(|| "verdict signature must use ed25519 prefix".to_string())?;
        verify_detached_hex(&self.signer_public_key, &self.signing_payload()?, signature)
    }
}

fn load_or_create_signer(path: &Path) -> Result<KeyPair, String> {
    if path.exists() {
        let raw = fs::read_to_string(path)
            .map_err(|error| format!("read Gideon signing key: {error}"))?;
        return KeyPair::from_secret_hex(raw.trim());
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("create Gideon key directory: {error}"))?;
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
        .map_err(|error| format!("create Gideon signing key: {error}"))?;
    file.write_all(signer.secret_key_hex().as_bytes())
        .map_err(|error| format!("write Gideon signing key: {error}"))?;
    file.write_all(b"\n")
        .map_err(|error| format!("finalize Gideon signing key: {error}"))?;
    file.sync_all()
        .map_err(|error| format!("sync Gideon signing key: {error}"))?;
    Ok(signer)
}

fn valid_scope(value: &str) -> bool {
    let value = value.trim();
    !value.is_empty() && value.len() <= 160
}

fn valid_sha256(value: &str) -> bool {
    let Some(hex) = value.strip_prefix("sha256:") else {
        return false;
    };
    hex.len() == 64 && hex.bytes().all(|value| value.is_ascii_hexdigit())
}

fn evaluate(request: &VerifyRequest, current_epoch: u64) -> Result<(VerdictKind, String), String> {
    for (name, value) in [
        ("tenantId", request.tenant_id.as_str()),
        ("workspaceId", request.workspace_id.as_str()),
        ("missionId", request.mission_id.as_str()),
        ("taskId", request.task_id.as_str()),
    ] {
        if !valid_scope(value) {
            return Err(format!("invalid {name}"));
        }
    }
    if !valid_sha256(&request.manifest_hash) || !valid_sha256(&request.result_hash) {
        return Err("manifestHash and resultHash must be canonical sha256 references".into());
    }
    if request.authority_epoch != current_epoch {
        return Ok((
            VerdictKind::Quarantine,
            "authority epoch mismatch; result is fenced from promotion".into(),
        ));
    }
    if request.executor_exit_code != 0 {
        return Ok((
            VerdictKind::Fail,
            format!("executor exited with code {}", request.executor_exit_code),
        ));
    }
    if request
        .vfs_attestation_id
        .as_deref()
        .unwrap_or_default()
        .is_empty()
    {
        return Ok((
            VerdictKind::Inconclusive,
            "no VFS preflight attestation was supplied".into(),
        ));
    }
    if request.checks.is_empty() {
        return Ok((
            VerdictKind::Inconclusive,
            "no verification checks were supplied".into(),
        ));
    }
    for check in &request.checks {
        if !valid_scope(&check.name) {
            return Err("verification check name is invalid".into());
        }
        if let Some(hash) = check.evidence_hash.as_deref() {
            if !valid_sha256(hash) {
                return Err(format!(
                    "check {} carries an invalid evidence hash",
                    check.name
                ));
            }
        }
        if check.required && !check.passed {
            return Ok((
                VerdictKind::Fail,
                format!("required verification check failed: {}", check.name),
            ));
        }
    }
    Ok((
        VerdictKind::Pass,
        "all supplied required checks passed under the current authority epoch".into(),
    ))
}

async fn health(State(state): State<AppState>) -> Json<Value> {
    Json(json!({
        "status": "ready",
        "service": "gideon",
        "schema": VERDICT_SCHEMA,
        "authorityEpoch": state.authority_epoch,
        "verificationMode": "evidence-gate",
        "formalProof": false,
        "signerPublicKey": state.signer.public_key_hex()
    }))
}

async fn handle_verify(
    State(state): State<AppState>,
    Json(request): Json<VerifyRequest>,
) -> Result<(StatusCode, Json<GideonVerdict>), (StatusCode, Json<Value>)> {
    let (verdict, reason) = evaluate(&request, state.authority_epoch)
        .map_err(|error| (StatusCode::BAD_REQUEST, Json(json!({ "error": error }))))?;
    let evidence_json = serde_json::to_string(&request.checks).map_err(|error| {
        (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": error.to_string() })),
        )
    })?;
    let mut response = GideonVerdict {
        schema_version: VERDICT_SCHEMA.into(),
        verdict_id: Uuid::new_v4(),
        timestamp: Utc::now(),
        tenant_id: request.tenant_id,
        workspace_id: request.workspace_id,
        mission_id: request.mission_id,
        task_id: request.task_id,
        manifest_hash: request.manifest_hash,
        result_hash: request.result_hash,
        vfs_attestation_id: request.vfs_attestation_id,
        authority_epoch: request.authority_epoch,
        verdict,
        reason,
        evidence_hash: hash_payload(&evidence_json),
        verification_mode: "evidence-gate".into(),
        formal_proof: false,
        signer_public_key: state.signer.public_key_hex(),
        signature: String::new(),
    };
    response
        .sign_with(&state.signer)
        .map_err(|error| (StatusCode::INTERNAL_SERVER_ERROR, Json(json!({ "error": error }))))?;
    Ok((StatusCode::OK, Json(response)))
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
    let key_path = PathBuf::from(
        env::var("CAMELOT_GIDEON_SIGNING_KEY")
            .unwrap_or_else(|_| "/var/lib/camelot/gideon/verdict-ed25519.key".into()),
    );
    let signer = load_or_create_signer(&key_path).expect("load Gideon signing identity");
    let state = AppState {
        signer: Arc::new(signer),
        authority_epoch,
    };
    let app = Router::new()
        .route("/health", get(health))
        .route("/verify", post(handle_verify))
        .with_state(state.clone());

    let host = env::var("CAMELOT_GIDEON_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let parsed_host: IpAddr = host
        .parse()
        .expect("CAMELOT_GIDEON_HOST must be an IP address");
    if !parsed_host.is_loopback() {
        panic!("Gideon must remain loopback-only behind Camelot controls");
    }
    let port = env::var("CAMELOT_GIDEON_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(3011);
    let listener = tokio::net::TcpListener::bind((parsed_host, port))
        .await
        .expect("bind Gideon");
    info!(
        authority_epoch,
        signer_public_key = %state.signer.public_key_hex(),
        "Gideon evidence verification gate online; formal proof disabled"
    );
    axum::serve(listener, app)
        .await
        .expect("Gideon server failed");
}

#[cfg(test)]
mod tests {
    use super::*;

    fn request() -> VerifyRequest {
        VerifyRequest {
            tenant_id: "tenant-a".into(),
            workspace_id: "workspace-a".into(),
            mission_id: "mission-a".into(),
            task_id: "task-a".into(),
            manifest_hash: format!("sha256:{}", "a".repeat(64)),
            result_hash: format!("sha256:{}", "b".repeat(64)),
            vfs_attestation_id: Some("vfs-a".into()),
            authority_epoch: 3,
            executor_exit_code: 0,
            checks: vec![EvidenceCheck {
                name: "tests".into(),
                passed: true,
                required: true,
                evidence_hash: Some(format!("sha256:{}", "c".repeat(64))),
            }],
        }
    }

    #[test]
    fn passes_only_with_required_evidence() {
        let (verdict, _) = evaluate(&request(), 3).expect("evaluate");
        assert_eq!(verdict, VerdictKind::Pass);
        let mut missing = request();
        missing.checks.clear();
        let (verdict, _) = evaluate(&missing, 3).expect("evaluate");
        assert_eq!(verdict, VerdictKind::Inconclusive);
    }

    #[test]
    fn fences_stale_epoch() {
        let (verdict, _) = evaluate(&request(), 4).expect("evaluate");
        assert_eq!(verdict, VerdictKind::Quarantine);
    }

    #[test]
    fn signed_verdict_verifies() {
        let signer = KeyPair::generate();
        let request = request();
        let (verdict, reason) = evaluate(&request, 3).expect("evaluate");
        let mut output = GideonVerdict {
            schema_version: VERDICT_SCHEMA.into(),
            verdict_id: Uuid::new_v4(),
            timestamp: Utc::now(),
            tenant_id: request.tenant_id,
            workspace_id: request.workspace_id,
            mission_id: request.mission_id,
            task_id: request.task_id,
            manifest_hash: request.manifest_hash,
            result_hash: request.result_hash,
            vfs_attestation_id: request.vfs_attestation_id,
            authority_epoch: 3,
            verdict,
            reason,
            evidence_hash: format!("sha256:{}", "d".repeat(64)),
            verification_mode: "evidence-gate".into(),
            formal_proof: false,
            signer_public_key: signer.public_key_hex(),
            signature: String::new(),
        };
        output.sign_with(&signer).expect("sign");
        output.verify_signature().expect("verify");
    }
}
