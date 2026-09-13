use axum::{
    extract::{Request, State},
    http::{header::AUTHORIZATION, StatusCode},
    middleware::{self, Next},
    response::Response,
    routing::{get, post},
    Json, Router,
};
use base64::{engine::general_purpose::STANDARD as BASE64, Engine as _};
use camelot_epoch::EpochSource;
use camelot_lease::CapabilityLease;
use camelot_vfs::{VfsAttestation, VFS_ATTESTATION_SCHEMA};
use chrono::{Duration, Utc};
use serde::{Deserialize, Serialize};
use serde_json::json;
use sha2::{Digest, Sha256};
use std::{env, net::IpAddr, sync::Arc, time::Instant};
use subtle::ConstantTimeEq;
use uuid::Uuid;
use wasmtime::{Config, Engine, Instance, Module, Store};

const EXECUTOR_CAPABILITY: &str = "execute:wasm";
const SENTINEL_ISSUER: &str = "camelot-sentinel";
const MAX_MODULE_BYTES: usize = 512 * 1024;
const MAX_ATTESTATION_AGE_SECONDS: i64 = 300;
const MAX_FUTURE_SKEW_SECONDS: i64 = 30;
const DEFAULT_FUEL: u64 = 10_000_000;

#[derive(Clone)]
struct AppState {
    token: Arc<String>,
    sentinel_public_key: Arc<String>,
    vfs_public_key: Arc<String>,
    epoch_source: Arc<EpochSource>,
    max_fuel: u64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ExecutionRequest {
    task_id: String,
    workspace_id: Uuid,
    artifact_resource_uri: String,
    module_sha256: String,
    wasm_base64: String,
    lease: CapabilityLease,
    vfs_attestation: VfsAttestation,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct ExecutionResponse {
    status: String,
    task_id: String,
    workspace_id: Uuid,
    artifact_sha256: String,
    attestation_id: Uuid,
    execution_time_ms: u128,
    message: String,
}

fn canonical_sha256(bytes: &[u8]) -> String {
    let digest = Sha256::digest(bytes);
    format!("sha256:{digest:x}")
}

fn valid_sha256(value: &str) -> bool {
    let Some(hex) = value.strip_prefix("sha256:") else {
        return false;
    };
    hex.len() == 64 && hex.bytes().all(|byte| byte.is_ascii_hexdigit())
}

fn validate_request(state: &AppState, payload: &ExecutionRequest) -> Result<Vec<u8>, String> {
    let authority_epoch = state.epoch_source.current_epoch()?;
    if payload.task_id.trim().is_empty() || payload.task_id.len() > 160 {
        return Err("taskId must contain 1..160 characters".into());
    }
    if !valid_sha256(&payload.module_sha256) {
        return Err("moduleSha256 must be a canonical sha256 reference".into());
    }

    let lease = &payload.lease;
    if lease.issuer_id != SENTINEL_ISSUER {
        return Err("lease issuer is not Sentinel".into());
    }
    if lease.issuer_public_key.as_deref() != Some(state.sentinel_public_key.as_str()) {
        return Err("lease signer does not match the pinned Sentinel identity".into());
    }
    lease
        .verify_signature()
        .map_err(|error| format!("invalid Sentinel lease signature: {error}"))?;
    if !lease.is_valid() {
        return Err("Sentinel lease is expired or revoked".into());
    }
    if !lease.is_current_epoch(authority_epoch) {
        return Err("Sentinel lease belongs to a stale authority epoch".into());
    }
    if !lease.binds_session(payload.workspace_id) {
        return Err("Sentinel lease is not bound to this workspace execution session".into());
    }
    if !lease.has_capability(EXECUTOR_CAPABILITY) {
        return Err("Sentinel lease lacks execute:wasm".into());
    }
    let executor_resource = format!("executor://node-agent/{}", payload.workspace_id);
    if !lease.resource_allows(&executor_resource) {
        return Err("Sentinel lease does not authorize this executor resource".into());
    }

    let attestation = &payload.vfs_attestation;
    if attestation.schema_version != VFS_ATTESTATION_SCHEMA {
        return Err("unsupported VFS attestation schema".into());
    }
    if attestation.signer_public_key != state.vfs_public_key.as_str() {
        return Err("VFS attestation signer does not match the pinned VFS identity".into());
    }
    attestation
        .verify_signature()
        .map_err(|error| format!("invalid VFS attestation signature: {error}"))?;
    if attestation.workspace_id != payload.workspace_id {
        return Err("VFS attestation workspace does not match the execution request".into());
    }
    if attestation.lease_id != lease.lease_id {
        return Err("VFS attestation is not bound to this Sentinel lease".into());
    }
    if attestation.epoch != authority_epoch {
        return Err("VFS attestation belongs to a stale authority epoch".into());
    }
    if attestation.resource_uri != payload.artifact_resource_uri {
        return Err("artifact resource URI does not match the VFS attestation".into());
    }
    let expected_prefix = format!("vfs://{}/", payload.workspace_id);
    if !payload.artifact_resource_uri.starts_with(&expected_prefix) {
        return Err("artifact is outside the workspace VFS scope".into());
    }
    if attestation.content_hash.as_deref() != Some(payload.module_sha256.as_str()) {
        return Err("VFS attestation does not bind the exact module hash".into());
    }
    let now = Utc::now();
    if attestation.timestamp > now + Duration::seconds(MAX_FUTURE_SKEW_SECONDS) {
        return Err("VFS attestation timestamp is too far in the future".into());
    }
    if attestation.timestamp < now - Duration::seconds(MAX_ATTESTATION_AGE_SECONDS) {
        return Err("VFS attestation is too old for execution".into());
    }

    if payload.wasm_base64.len() > (MAX_MODULE_BYTES * 4 / 3) + 16 {
        return Err("encoded module exceeds the executor size ceiling".into());
    }
    let bytes = BASE64
        .decode(payload.wasm_base64.as_bytes())
        .map_err(|_| "wasmBase64 is not valid base64".to_string())?;
    if bytes.is_empty() || bytes.len() > MAX_MODULE_BYTES {
        return Err("WASM module must contain 1..524288 bytes".into());
    }
    let observed = canonical_sha256(&bytes);
    if observed != payload.module_sha256 {
        return Err("WASM bytes do not match moduleSha256".into());
    }
    Ok(bytes)
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
    let authorized = actual.as_bytes().ct_eq(expected.as_bytes()).into();
    if !authorized {
        return Err(StatusCode::UNAUTHORIZED);
    }
    Ok(next.run(request).await)
}

async fn health_live() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "service": "node-agent",
        "runtime": "wasmtime",
        "live": true
    }))
}

async fn health_ready(
    State(state): State<AppState>,
) -> (StatusCode, Json<serde_json::Value>) {
    match state.epoch_source.current_epoch() {
        Ok(authority_epoch) => (
            StatusCode::OK,
            Json(json!({
                "status": "ready",
                "service": "node-agent",
                "runtime": "wasmtime",
                "authorityEpoch": authority_epoch,
                "dynamicEpoch": state.epoch_source.is_dynamic(),
                "maxModuleBytes": MAX_MODULE_BYTES,
                "maxFuel": state.max_fuel,
                "hostImports": false,
                "shellExecution": false
            })),
        ),
        Err(error) => (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(json!({
                "status": "not_ready",
                "service": "node-agent",
                "reason": error
            })),
        ),
    }
}

async fn handle_execute(
    State(state): State<AppState>,
    Json(payload): Json<ExecutionRequest>,
) -> (StatusCode, Json<ExecutionResponse>) {
    let bytes = match validate_request(&state, &payload) {
        Ok(bytes) => bytes,
        Err(reason) => {
            return (
                StatusCode::FORBIDDEN,
                Json(ExecutionResponse {
                    status: "denied".into(),
                    task_id: payload.task_id,
                    workspace_id: payload.workspace_id,
                    artifact_sha256: payload.module_sha256,
                    attestation_id: payload.vfs_attestation.attestation_id,
                    execution_time_ms: 0,
                    message: reason,
                }),
            )
        }
    };

    let started = Instant::now();
    let mut config = Config::new();
    config.consume_fuel(true);
    config.wasm_backtrace_details(wasmtime::WasmBacktraceDetails::Disable);
    let engine = match Engine::new(&config) {
        Ok(engine) => engine,
        Err(error) => {
            return (
                StatusCode::INTERNAL_SERVER_ERROR,
                Json(ExecutionResponse {
                    status: "failed".into(),
                    task_id: payload.task_id,
                    workspace_id: payload.workspace_id,
                    artifact_sha256: payload.module_sha256,
                    attestation_id: payload.vfs_attestation.attestation_id,
                    execution_time_ms: started.elapsed().as_millis(),
                    message: format!("Wasmtime engine initialization failed: {error}"),
                }),
            )
        }
    };
    let module = match Module::new(&engine, &bytes) {
        Ok(module) => module,
        Err(error) => {
            return (
                StatusCode::UNPROCESSABLE_ENTITY,
                Json(ExecutionResponse {
                    status: "failed".into(),
                    task_id: payload.task_id,
                    workspace_id: payload.workspace_id,
                    artifact_sha256: payload.module_sha256,
                    attestation_id: payload.vfs_attestation.attestation_id,
                    execution_time_ms: started.elapsed().as_millis(),
                    message: format!("WASM module validation failed: {error}"),
                }),
            )
        }
    };

    let mut store = Store::new(&engine, ());
    if let Err(error) = store.set_fuel(state.max_fuel) {
        return (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ExecutionResponse {
                status: "failed".into(),
                task_id: payload.task_id,
                workspace_id: payload.workspace_id,
                artifact_sha256: payload.module_sha256,
                attestation_id: payload.vfs_attestation.attestation_id,
                execution_time_ms: started.elapsed().as_millis(),
                message: format!("could not apply execution fuel ceiling: {error}"),
            }),
        );
    }

    let instance = match Instance::new(&mut store, &module, &[]) {
        Ok(instance) => instance,
        Err(error) => {
            return (
                StatusCode::UNPROCESSABLE_ENTITY,
                Json(ExecutionResponse {
                    status: "failed".into(),
                    task_id: payload.task_id,
                    workspace_id: payload.workspace_id,
                    artifact_sha256: payload.module_sha256,
                    attestation_id: payload.vfs_attestation.attestation_id,
                    execution_time_ms: started.elapsed().as_millis(),
                    message: format!(
                        "module imports are not permitted in the bounded executor: {error}"
                    ),
                }),
            )
        }
    };

    let entry = instance
        .get_typed_func::<(), ()>(&mut store, "_start")
        .or_else(|_| instance.get_typed_func::<(), ()>(&mut store, "run"));
    let entry = match entry {
        Ok(entry) => entry,
        Err(_) => {
            return (
                StatusCode::UNPROCESSABLE_ENTITY,
                Json(ExecutionResponse {
                    status: "failed".into(),
                    task_id: payload.task_id,
                    workspace_id: payload.workspace_id,
                    artifact_sha256: payload.module_sha256,
                    attestation_id: payload.vfs_attestation.attestation_id,
                    execution_time_ms: started.elapsed().as_millis(),
                    message: "module must export a zero-argument _start or run function".into(),
                }),
            )
        }
    };

    let result = entry.call(&mut store, ());
    let elapsed = started.elapsed().as_millis();
    match result {
        Ok(()) => (
            StatusCode::OK,
            Json(ExecutionResponse {
                status: "executed".into(),
                task_id: payload.task_id,
                workspace_id: payload.workspace_id,
                artifact_sha256: payload.module_sha256,
                attestation_id: payload.vfs_attestation.attestation_id,
                execution_time_ms: elapsed,
                message: "module executed inside the no-host-import Wasmtime sandbox".into(),
            }),
        ),
        Err(error) => (
            StatusCode::UNPROCESSABLE_ENTITY,
            Json(ExecutionResponse {
                status: "failed".into(),
                task_id: payload.task_id,
                workspace_id: payload.workspace_id,
                artifact_sha256: payload.module_sha256,
                attestation_id: payload.vfs_attestation.attestation_id,
                execution_time_ms: elapsed,
                message: format!("sandbox execution trapped: {error}"),
            }),
        ),
    }
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let token = env::var("CAMELOT_NODE_AGENT_TOKEN").expect(
        "CAMELOT_NODE_AGENT_TOKEN must be set; node-agent refuses unauthenticated execution",
    );
    if token.len() < 24 {
        panic!("CAMELOT_NODE_AGENT_TOKEN must contain at least 24 characters");
    }
    let sentinel_public_key = env::var("CAMELOT_SENTINEL_PUBLIC_KEY")
        .expect("CAMELOT_SENTINEL_PUBLIC_KEY must pin the active Sentinel identity");
    let vfs_public_key = env::var("CAMELOT_VFS_PUBLIC_KEY")
        .expect("CAMELOT_VFS_PUBLIC_KEY must pin the active VFS Guardian identity");
    for (name, value) in [
        ("CAMELOT_SENTINEL_PUBLIC_KEY", sentinel_public_key.as_str()),
        ("CAMELOT_VFS_PUBLIC_KEY", vfs_public_key.as_str()),
    ] {
        if value.len() != 64 || !value.bytes().all(|byte| byte.is_ascii_hexdigit()) {
            panic!("{name} must be a 32-byte Ed25519 public key in hex");
        }
    }
    let epoch_source = Arc::new(
        EpochSource::from_environment().expect("load signed authority epoch source"),
    );
    let boot_epoch = epoch_source
        .current_epoch()
        .expect("verify current authority epoch at node-agent startup");
    let max_fuel = env::var("CAMELOT_NODE_AGENT_MAX_FUEL")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .filter(|value| *value > 0)
        .unwrap_or(DEFAULT_FUEL);
    let state = AppState {
        token: Arc::new(token),
        sentinel_public_key: Arc::new(sentinel_public_key),
        vfs_public_key: Arc::new(vfs_public_key),
        epoch_source,
        max_fuel,
    };

    let protected = Router::new()
        .route("/execute/wasm", post(handle_execute))
        .route_layer(middleware::from_fn_with_state(state.clone(), require_token));
    let app = Router::new()
        .route("/health", get(health_ready))
        .route("/health/live", get(health_live))
        .route("/health/ready", get(health_ready))
        .merge(protected)
        .with_state(state.clone());

    let host = env::var("CAMELOT_NODE_AGENT_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let parsed_host: IpAddr = host
        .parse()
        .expect("CAMELOT_NODE_AGENT_HOST must be an IP address");
    if !parsed_host.is_loopback() {
        panic!("node-agent must remain loopback-only behind Camelot authority controls");
    }
    let port = env::var("CAMELOT_NODE_AGENT_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(3010);
    let listener = tokio::net::TcpListener::bind((parsed_host, port))
        .await
        .expect("bind node-agent");
    tracing::info!(
        authority_epoch = boot_epoch,
        dynamic_epoch = state.epoch_source.is_dynamic(),
        max_fuel,
        "governed Wasmtime node executor online; host imports disabled"
    );
    axum::serve(listener, app)
        .await
        .expect("node-agent server failed");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_hash_shape_is_stable() {
        let hash = canonical_sha256(b"camelot");
        assert!(valid_sha256(&hash));
        assert_eq!(hash.len(), 71);
    }

    #[test]
    fn malformed_hash_is_rejected() {
        assert!(!valid_sha256("sha256:short"));
        assert!(!valid_sha256(&format!("sha256:{}", "z".repeat(64))));
    }
}
