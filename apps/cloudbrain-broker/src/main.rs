use axum::{
    extract::{Request, State},
    http::{header::AUTHORIZATION, StatusCode},
    middleware::{self, Next},
    response::Response,
    routing::{get, post},
    Json, Router,
};
use camelot_cloudbrain::{
    conservative_token_estimate, content_reference, ContextKind, ContextPacket, ContextSection,
};
use camelot_crypto::{hash_payload, KeyPair};
use camelot_epoch::EpochSource;
use camelot_lease::CapabilityLease;
use camelot_receipts::{Receipt, ReceiptDraft};
use reqwest::{header::ACCEPT, Client, Url};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    env, fs,
    io::Write,
    net::IpAddr,
    path::{Path, PathBuf},
    sync::Arc,
    time::Duration,
};
use subtle::ConstantTimeEq;
use tracing::info;
use uuid::Uuid;

const SENTINEL_ISSUER: &str = "camelot-sentinel";
const RETRIEVAL_CAPABILITY: &str = "cloudbrain:retrieve";
const DEFAULT_MAX_TOKENS: u64 = 4096;
const ABSOLUTE_MAX_TOKENS: u64 = 16_384;
const MAX_QUESTION_CHARS: usize = 16_000;
const MAX_PROVIDER_BODY_BYTES: usize = 512 * 1024;
const TRUNCATION_MARKER: &str = "\n[CONTEXT_TRUNCATED_BY_CAMELOT_TOKEN_BUDGET]";

#[derive(Clone)]
struct AppState {
    token: Arc<String>,
    sentinel_public_key: Arc<String>,
    epoch_source: Arc<EpochSource>,
    signer: Arc<KeyPair>,
    receipt_url: Arc<String>,
    mcp: Arc<NotebookLmMcp>,
    max_tokens: u64,
    client: Client,
}

#[derive(Clone)]
struct NotebookLmMcp {
    url: String,
    health_url: String,
    protocol_version: String,
    query_tool: String,
    client: Client,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct CloudbrainQueryRequest {
    workspace_id: Uuid,
    mission_id: String,
    task_id: String,
    correlation_id: String,
    notebook_id: String,
    question: String,
    #[serde(default)]
    max_tokens: Option<u64>,
    lease: CapabilityLease,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct CloudbrainQueryResponse {
    answer: String,
    references: Value,
    provider: &'static str,
    trust_class: &'static str,
    truncated: bool,
    context_packet: ContextPacket,
}

type ApiError = (StatusCode, Json<Value>);

fn api_error(status: StatusCode, message: impl Into<String>) -> ApiError {
    (status, Json(json!({ "error": message.into() })))
}

fn load_or_create_signer(path: &Path) -> Result<KeyPair, String> {
    if path.exists() {
        let raw = fs::read_to_string(path)
            .map_err(|error| format!("read Cloudbrain signing key: {error}"))?;
        return KeyPair::from_secret_hex(raw.trim());
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("create Cloudbrain key directory: {error}"))?;
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
        .map_err(|error| format!("create Cloudbrain signing key: {error}"))?;
    file.write_all(signer.secret_key_hex().as_bytes())
        .map_err(|error| format!("write Cloudbrain signing key: {error}"))?;
    file.write_all(b"\n")
        .map_err(|error| format!("finalize Cloudbrain signing key: {error}"))?;
    file.sync_all()
        .map_err(|error| format!("sync Cloudbrain signing key: {error}"))?;
    Ok(signer)
}

fn validate_loopback_url(name: &str, value: &str) -> Result<(), String> {
    let url = Url::parse(value).map_err(|error| format!("{name} is not a valid URL: {error}"))?;
    if url.scheme() != "http" {
        return Err(format!(
            "{name} must use loopback HTTP behind the local service boundary"
        ));
    }
    let host = url
        .host_str()
        .ok_or_else(|| format!("{name} must include a host"))?;
    let allowed = host.eq_ignore_ascii_case("localhost")
        || host
            .parse::<IpAddr>()
            .map(|ip| ip.is_loopback())
            .unwrap_or(false);
    if !allowed {
        return Err(format!("{name} must remain loopback-only"));
    }
    Ok(())
}

fn bounded_label(name: &str, value: &str) -> Result<(), ApiError> {
    let value = value.trim();
    if value.is_empty() || value.len() > 160 {
        return Err(api_error(
            StatusCode::BAD_REQUEST,
            format!("invalid {name}"),
        ));
    }
    Ok(())
}

fn valid_notebook_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= 192
        && value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'-' | b'_'))
}

fn resource_uri(workspace_id: Uuid, notebook_id: &str) -> String {
    format!("cloudbrain://notebooklm/{workspace_id}/{notebook_id}")
}

fn validate_lease(
    state: &AppState,
    request: &CloudbrainQueryRequest,
    authority_epoch: u64,
) -> Result<(), ApiError> {
    let lease = &request.lease;
    if lease.issuer_id != SENTINEL_ISSUER {
        return Err(api_error(
            StatusCode::UNAUTHORIZED,
            "lease issuer is not Sentinel",
        ));
    }
    if lease.issuer_public_key.as_deref() != Some(state.sentinel_public_key.as_str()) {
        return Err(api_error(
            StatusCode::UNAUTHORIZED,
            "lease signer does not match pinned Sentinel identity",
        ));
    }
    lease.verify_signature().map_err(|error| {
        api_error(
            StatusCode::UNAUTHORIZED,
            format!("invalid Sentinel lease signature: {error}"),
        )
    })?;
    if !lease.is_valid() {
        return Err(api_error(
            StatusCode::FORBIDDEN,
            "lease is expired or revoked",
        ));
    }
    if !lease.is_current_epoch(authority_epoch) {
        return Err(api_error(
            StatusCode::FORBIDDEN,
            "lease belongs to a stale authority epoch",
        ));
    }
    if !lease.binds_session(request.workspace_id) {
        return Err(api_error(
            StatusCode::FORBIDDEN,
            "retrieval lease is not bound to this workspace",
        ));
    }
    if !lease.has_capability(RETRIEVAL_CAPABILITY) {
        return Err(api_error(
            StatusCode::FORBIDDEN,
            "lease lacks cloudbrain:retrieve",
        ));
    }
    let resource = resource_uri(request.workspace_id, &request.notebook_id);
    if !lease.resource_allows(&resource) {
        return Err(api_error(
            StatusCode::FORBIDDEN,
            "NotebookLM resource is outside retrieval lease bounds",
        ));
    }
    Ok(())
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
    let authorized: bool = actual.as_bytes().ct_eq(expected.as_bytes()).into();
    if !authorized {
        return Err(StatusCode::UNAUTHORIZED);
    }
    Ok(next.run(request).await)
}

impl NotebookLmMcp {
    async fn health(&self) -> Result<(), String> {
        let response = self
            .client
            .get(&self.health_url)
            .send()
            .await
            .map_err(|error| format!("NotebookLM MCP health request failed: {error}"))?;
        if !response.status().is_success() {
            return Err(format!(
                "NotebookLM MCP health returned {}",
                response.status()
            ));
        }
        Ok(())
    }

    async fn post_rpc(
        &self,
        body: Value,
        session_id: Option<&str>,
    ) -> Result<(Option<Value>, Option<String>), String> {
        let mut request = self
            .client
            .post(&self.url)
            .header(ACCEPT, "application/json, text/event-stream")
            .json(&body);
        if let Some(session_id) = session_id {
            request = request.header("Mcp-Session-Id", session_id);
        }
        let response = request
            .send()
            .await
            .map_err(|error| format!("NotebookLM MCP request failed: {error}"))?;
        let status = response.status();
        let session = response
            .headers()
            .get("Mcp-Session-Id")
            .and_then(|value| value.to_str().ok())
            .map(ToOwned::to_owned);
        let text = response
            .text()
            .await
            .map_err(|error| format!("read NotebookLM MCP response: {error}"))?;
        if !status.is_success() {
            return Err(format!(
                "NotebookLM MCP returned {status}: {}",
                truncate_log(&text)
            ));
        }
        if text.trim().is_empty() {
            return Ok((None, session));
        }
        let value = parse_mcp_body(&text)?;
        if let Some(error) = value.get("error") {
            return Err(format!("NotebookLM MCP JSON-RPC error: {error}"));
        }
        Ok((Some(value), session))
    }

    async fn query(&self, notebook_id: &str, question: &str) -> Result<(String, Value), String> {
        let initialize = json!({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": self.protocol_version,
                "capabilities": {},
                "clientInfo": { "name": "camelot-cloudbrain", "version": "0.1.0" }
            }
        });
        let (_, session) = self.post_rpc(initialize, None).await?;
        let session = session.ok_or_else(|| {
            "NotebookLM MCP did not return Mcp-Session-Id during initialize".to_string()
        })?;

        self.post_rpc(
            json!({ "jsonrpc": "2.0", "method": "notifications/initialized" }),
            Some(&session),
        )
        .await?;

        let call = json!({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": self.query_tool,
                "arguments": {
                    "notebook_id": notebook_id,
                    "query": question,
                    "new_conversation": true
                }
            }
        });
        let (response, _) = self.post_rpc(call, Some(&session)).await?;
        let response =
            response.ok_or_else(|| "NotebookLM MCP returned an empty tool response".to_string())?;
        extract_answer(&response)
    }
}

fn parse_mcp_body(text: &str) -> Result<Value, String> {
    if text.len() > MAX_PROVIDER_BODY_BYTES {
        return Err("NotebookLM MCP response exceeds provider body ceiling".into());
    }
    if let Ok(value) = serde_json::from_str::<Value>(text) {
        return Ok(value);
    }
    for line in text.lines() {
        if let Some(data) = line.strip_prefix("data:") {
            let data = data.trim();
            if !data.is_empty() {
                if let Ok(value) = serde_json::from_str::<Value>(data) {
                    return Ok(value);
                }
            }
        }
    }
    Err("NotebookLM MCP response was neither JSON nor parseable SSE data".into())
}

fn extract_answer(value: &Value) -> Result<(String, Value), String> {
    let result = value.get("result").unwrap_or(value);
    if let Some(structured) = result.get("structuredContent") {
        if let Some(answer) = structured.get("answer").and_then(Value::as_str) {
            return Ok((
                answer.to_owned(),
                structured
                    .get("references")
                    .cloned()
                    .unwrap_or_else(|| json!([])),
            ));
        }
    }
    if let Some(content) = result.get("content").and_then(Value::as_array) {
        let mut texts = Vec::new();
        let mut references = json!([]);
        for item in content {
            if let Some(text) = item.get("text").and_then(Value::as_str) {
                if let Ok(parsed) = serde_json::from_str::<Value>(text) {
                    if let Some(answer) = parsed.get("answer").and_then(Value::as_str) {
                        if let Some(found) = parsed.get("references") {
                            references = found.clone();
                        }
                        texts.push(answer.to_owned());
                        continue;
                    }
                }
                texts.push(text.to_owned());
            }
        }
        if !texts.is_empty() {
            return Ok((texts.join("\n"), references));
        }
    }
    Err("NotebookLM MCP tool result contained no answer text".into())
}

fn truncate_log(value: &str) -> String {
    value.chars().take(512).collect()
}

fn enforce_budget(answer: String, max_tokens: u64) -> (String, u64, bool) {
    let estimated = conservative_token_estimate(&answer);
    if estimated <= max_tokens {
        return (answer, estimated, false);
    }

    let max_chars = max_tokens.saturating_mul(4) as usize;
    let marker_chars = TRUNCATION_MARKER.chars().count();
    let content_chars = max_chars.saturating_sub(marker_chars);
    let mut truncated: String = answer.chars().take(content_chars).collect();
    if marker_chars <= max_chars {
        truncated.push_str(TRUNCATION_MARKER);
    }
    let tokens = conservative_token_estimate(&truncated).min(max_tokens);
    (truncated, tokens, true)
}

async fn create_retrieval_receipt(
    state: &AppState,
    request: &CloudbrainQueryRequest,
    authority_epoch: u64,
    answer_hash: &str,
) -> Result<Receipt, ApiError> {
    let resource = resource_uri(request.workspace_id, &request.notebook_id);
    let manifest = json!({
        "action": "cloudbrain.notebooklm.query",
        "resource": resource,
        "questionHash": hash_payload(&request.question),
        "correlationId": request.correlation_id
    });
    let manifest_text = serde_json::to_string(&manifest)
        .map_err(|error| api_error(StatusCode::INTERNAL_SERVER_ERROR, error.to_string()))?;
    let draft = ReceiptDraft {
        tenant_id: request.lease.tenant_id.to_string(),
        workspace_id: request.workspace_id.to_string(),
        mission_id: request.mission_id.clone(),
        task_id: request.task_id.clone(),
        actor_id: request.lease.actor_id.clone(),
        action_type: "cloudbrain.notebooklm.query".into(),
        resource_uri: resource,
        manifest_hash: hash_payload(&manifest_text),
        capability_lease_id: Some(request.lease.lease_id.to_string()),
        approval_id: None,
        vfs_attestation_id: None,
        gideon_verdict_id: None,
        arthur_resolution_id: None,
        result_hash: answer_hash.to_owned(),
        authority_epoch,
    };
    let response = state
        .client
        .post(format!(
            "{}/receipts",
            state.receipt_url.trim_end_matches('/')
        ))
        .json(&draft)
        .send()
        .await
        .map_err(|error| {
            api_error(
                StatusCode::SERVICE_UNAVAILABLE,
                format!("receipt ledger unavailable: {error}"),
            )
        })?;
    if !response.status().is_success() {
        let status = response.status();
        let body = response.text().await.unwrap_or_default();
        return Err(api_error(
            StatusCode::BAD_GATEWAY,
            format!(
                "receipt ledger rejected retrieval ({status}): {}",
                truncate_log(&body)
            ),
        ));
    }
    response.json::<Receipt>().await.map_err(|error| {
        api_error(
            StatusCode::BAD_GATEWAY,
            format!("receipt ledger returned invalid receipt: {error}"),
        )
    })
}

async fn health_live() -> Json<Value> {
    Json(json!({
        "status": "ok",
        "service": "cloudbrain-broker",
        "live": true,
        "authority": false
    }))
}

async fn health_ready(State(state): State<AppState>) -> (StatusCode, Json<Value>) {
    let epoch = match state.epoch_source.current_epoch() {
        Ok(epoch) => epoch,
        Err(error) => {
            return (
                StatusCode::SERVICE_UNAVAILABLE,
                Json(json!({ "status": "not_ready", "reason": error })),
            )
        }
    };
    if let Err(error) = state.mcp.health().await {
        return (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(json!({ "status": "not_ready", "reason": error })),
        );
    }
    (
        StatusCode::OK,
        Json(json!({
            "status": "ready",
            "service": "cloudbrain-broker",
            "provider": "notebooklm-mcp",
            "authority": false,
            "authorityEpoch": epoch,
            "dynamicEpoch": state.epoch_source.is_dynamic(),
            "maxContextTokens": state.max_tokens,
            "contextPacketSchema": "camelot-context-packet/1",
            "signerPublicKey": state.signer.public_key_hex(),
            "queryTool": state.mcp.query_tool
        })),
    )
}

async fn handle_query(
    State(state): State<AppState>,
    Json(request): Json<CloudbrainQueryRequest>,
) -> Result<(StatusCode, Json<CloudbrainQueryResponse>), ApiError> {
    bounded_label("missionId", &request.mission_id)?;
    bounded_label("taskId", &request.task_id)?;
    bounded_label("correlationId", &request.correlation_id)?;
    if !valid_notebook_id(&request.notebook_id) {
        return Err(api_error(
            StatusCode::BAD_REQUEST,
            "invalid NotebookLM notebook id",
        ));
    }
    let question = request.question.trim();
    if question.is_empty() || question.chars().count() > MAX_QUESTION_CHARS {
        return Err(api_error(
            StatusCode::BAD_REQUEST,
            "question must contain 1..16000 characters",
        ));
    }
    let authority_epoch = state.epoch_source.current_epoch().map_err(|error| {
        api_error(
            StatusCode::SERVICE_UNAVAILABLE,
            format!("authority epoch unavailable: {error}"),
        )
    })?;
    validate_lease(&state, &request, authority_epoch)?;

    let requested_max = request.max_tokens.unwrap_or(DEFAULT_MAX_TOKENS);
    let hard_max = requested_max.clamp(1, state.max_tokens);
    let (answer, references) = state
        .mcp
        .query(&request.notebook_id, question)
        .await
        .map_err(|error| api_error(StatusCode::BAD_GATEWAY, error))?;
    let (answer, tokens, truncated) = enforce_budget(answer, hard_max);
    let answer_hash = content_reference(&answer);

    let receipt = create_retrieval_receipt(&state, &request, authority_epoch, &answer_hash).await?;
    let mut packet = ContextPacket::new(
        request.lease.tenant_id,
        &request.correlation_id,
        &request.task_id,
        request.lease.lease_id,
        vec![ContextSection {
            kind: ContextKind::L2Evidence,
            content_ref: answer_hash,
            tokens,
        }],
        tokens,
        hard_max,
    );
    packet.receipt_ref = Some(format!("receipt://{}", receipt.receipt_id));
    packet.sign_with(&state.signer).map_err(|error| {
        api_error(
            StatusCode::INTERNAL_SERVER_ERROR,
            format!("sign context packet: {error}"),
        )
    })?;

    Ok((
        StatusCode::OK,
        Json(CloudbrainQueryResponse {
            answer,
            references,
            provider: "notebooklm-mcp",
            trust_class: "external_provider_evidence",
            truncated,
            context_packet: packet,
        }),
    ))
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let token = env::var("CAMELOT_CLOUDBRAIN_TOKEN")
        .expect("CAMELOT_CLOUDBRAIN_TOKEN must be set for internal Cloudbrain requests");
    if token.len() < 24 {
        panic!("CAMELOT_CLOUDBRAIN_TOKEN must contain at least 24 characters");
    }
    let sentinel_public_key = env::var("CAMELOT_SENTINEL_PUBLIC_KEY")
        .expect("CAMELOT_SENTINEL_PUBLIC_KEY must pin the Sentinel identity");
    if sentinel_public_key.len() != 64
        || !sentinel_public_key
            .bytes()
            .all(|byte| byte.is_ascii_hexdigit())
    {
        panic!("CAMELOT_SENTINEL_PUBLIC_KEY must be a 32-byte Ed25519 public key in hex");
    }
    let key_path = PathBuf::from(
        env::var("CAMELOT_CLOUDBRAIN_SIGNING_KEY")
            .unwrap_or_else(|_| "/var/lib/camelot/cloudbrain/context-ed25519.key".into()),
    );
    let signer = load_or_create_signer(&key_path).expect("load Cloudbrain signing identity");
    let epoch_source =
        Arc::new(EpochSource::from_environment().expect("load signed authority epoch source"));
    epoch_source
        .current_epoch()
        .expect("verify current authority epoch at Cloudbrain startup");

    let mcp_url = env::var("CAMELOT_NOTEBOOKLM_MCP_URL")
        .unwrap_or_else(|_| "http://127.0.0.1:8484/mcp".into());
    let mcp_health_url = env::var("CAMELOT_NOTEBOOKLM_MCP_HEALTH_URL")
        .unwrap_or_else(|_| "http://127.0.0.1:8484/healthz".into());
    validate_loopback_url("CAMELOT_NOTEBOOKLM_MCP_URL", &mcp_url).expect("validate MCP URL");
    validate_loopback_url("CAMELOT_NOTEBOOKLM_MCP_HEALTH_URL", &mcp_health_url)
        .expect("validate MCP health URL");

    let client = Client::builder()
        .connect_timeout(Duration::from_secs(5))
        .timeout(Duration::from_secs(150))
        .build()
        .expect("build Cloudbrain HTTP client");
    let mcp = NotebookLmMcp {
        url: mcp_url,
        health_url: mcp_health_url,
        protocol_version: env::var("CAMELOT_NOTEBOOKLM_MCP_PROTOCOL_VERSION")
            .unwrap_or_else(|_| "2025-06-18".into()),
        query_tool: env::var("CAMELOT_NOTEBOOKLM_QUERY_TOOL")
            .unwrap_or_else(|_| "notebook_query".into()),
        client: client.clone(),
    };
    let max_tokens = env::var("CAMELOT_CLOUDBRAIN_MAX_TOKENS")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(8192)
        .clamp(1, ABSOLUTE_MAX_TOKENS);
    let state = AppState {
        token: Arc::new(token),
        sentinel_public_key: Arc::new(sentinel_public_key),
        epoch_source,
        signer: Arc::new(signer),
        receipt_url: Arc::new(
            env::var("CAMELOT_RECEIPT_URL").unwrap_or_else(|_| "http://127.0.0.1:3001".into()),
        ),
        mcp: Arc::new(mcp),
        max_tokens,
        client,
    };

    let protected = Router::new()
        .route("/v1/cloudbrain/query", post(handle_query))
        .route_layer(middleware::from_fn_with_state(state.clone(), require_token));
    let app = Router::new()
        .route("/health", get(health_ready))
        .route("/health/live", get(health_live))
        .route("/health/ready", get(health_ready))
        .merge(protected)
        .with_state(state.clone());

    let host = env::var("CAMELOT_CLOUDBRAIN_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let parsed_host: IpAddr = host
        .parse()
        .expect("CAMELOT_CLOUDBRAIN_HOST must be an IP address");
    if !parsed_host.is_loopback() {
        panic!("Cloudbrain broker must remain loopback-only behind Camelot governance");
    }
    let port = env::var("CAMELOT_CLOUDBRAIN_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(3015);
    let listener = tokio::net::TcpListener::bind((parsed_host, port))
        .await
        .expect("bind Cloudbrain broker");
    info!(
        signer_public_key = %state.signer.public_key_hex(),
        max_tokens,
        "Cloudbrain broker online; NotebookLM MCP is a non-authority evidence provider"
    );
    axum::serve(listener, app)
        .await
        .expect("Cloudbrain broker failed");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn notebook_resource_is_workspace_scoped() {
        let workspace = Uuid::nil();
        assert_eq!(
            resource_uri(workspace, "abc-123"),
            format!("cloudbrain://notebooklm/{workspace}/abc-123")
        );
    }

    #[test]
    fn provider_response_extracts_structured_answer() {
        let value = json!({
            "result": {
                "structuredContent": {
                    "answer": "Camelot",
                    "references": [{"source_id": "s1"}]
                }
            }
        });
        let (answer, references) = extract_answer(&value).expect("answer");
        assert_eq!(answer, "Camelot");
        assert_eq!(references.as_array().map(Vec::len), Some(1));
    }

    #[test]
    fn context_budget_truncates_provider_output() {
        let (answer, tokens, truncated) = enforce_budget("x".repeat(100), 20);
        assert!(truncated);
        assert!(tokens <= 20);
        assert!(answer.contains("CONTEXT_TRUNCATED"));
        assert!(conservative_token_estimate(&answer) <= 20);
    }

    #[test]
    fn rejects_non_loopback_mcp() {
        assert!(validate_loopback_url("mcp", "https://example.com/mcp").is_err());
        assert!(validate_loopback_url("mcp", "http://127.0.0.1:8484/mcp").is_ok());
    }
}
