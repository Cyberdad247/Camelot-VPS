use axum::{
    extract::{Request, State},
    http::{header::AUTHORIZATION, StatusCode},
    middleware::{self, Next},
    response::Response,
    routing::{get, post},
    Json, Router,
};
use camelot_crypto::KeyPair;
use camelot_knight::{
    compile_signed_spark, load_bundle_dir, Keyring, KnightPolicy, LoadedKnight, SparkCompileRequest,
};
use chrono::Utc;
use serde_json::{json, Value};
use std::{
    collections::HashSet,
    env, fs,
    io::Write,
    net::IpAddr,
    path::{Path, PathBuf},
    sync::Arc,
};
use subtle::ConstantTimeEq;

#[derive(Clone)]
struct AppState {
    knight: Arc<LoadedKnight>,
    signer: Arc<KeyPair>,
    signer_key_id: Arc<String>,
    token: Arc<String>,
}

type ApiError = (StatusCode, Json<Value>);

fn api_error(status: StatusCode, message: impl Into<String>) -> ApiError {
    (status, Json(json!({ "error": message.into() })))
}

fn env_required(name: &str) -> String {
    env::var(name).unwrap_or_else(|_| panic!("{name} must be configured"))
}

fn csv_set(name: &str, default: &[&str]) -> HashSet<String> {
    env::var(name)
        .ok()
        .map(|value| {
            value
                .split(',')
                .map(str::trim)
                .filter(|value| !value.is_empty())
                .map(str::to_string)
                .collect()
        })
        .unwrap_or_else(|| default.iter().map(|value| (*value).to_string()).collect())
}

fn load_or_create_signer(path: &Path) -> Result<KeyPair, String> {
    if path.exists() {
        let raw = fs::read_to_string(path)
            .map_err(|error| format!("read Context Compiler signing key: {error}"))?;
        return KeyPair::from_secret_hex(raw.trim());
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("create Context Compiler key directory: {error}"))?;
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
        .map_err(|error| format!("create Context Compiler signing key: {error}"))?;
    file.write_all(signer.secret_key_hex().as_bytes())
        .map_err(|error| format!("write Context Compiler signing key: {error}"))?;
    file.write_all(b"\n")
        .map_err(|error| format!("finalize Context Compiler signing key: {error}"))?;
    file.sync_all()
        .map_err(|error| format!("sync Context Compiler signing key: {error}"))?;
    Ok(signer)
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
    let allowed: bool = actual.as_bytes().ct_eq(expected.as_bytes()).into();
    if !allowed {
        return Err(StatusCode::UNAUTHORIZED);
    }
    Ok(next.run(request).await)
}

async fn health_live() -> Json<Value> {
    Json(json!({
        "status": "ok",
        "service": "context-compiler",
        "live": true,
        "authority": false
    }))
}

async fn health_ready(State(state): State<AppState>) -> Json<Value> {
    Json(json!({
        "status": "ready",
        "service": "context-compiler",
        "personaId": state.knight.persona_id,
        "packageId": state.knight.package_id,
        "maxCognitionCeiling": state.knight.max_cognition_ceiling,
        "sparkSignerPublicKey": state.signer.public_key_hex(),
        "authority": false,
        "toolExecution": false,
        "leaseIssuance": false
    }))
}

async fn compile(
    State(state): State<AppState>,
    Json(request): Json<SparkCompileRequest>,
) -> Result<(StatusCode, Json<Value>), ApiError> {
    compile_signed_spark(
        &state.knight,
        request,
        &state.signer,
        state.signer_key_id.as_str(),
        Utc::now(),
    )
    .map(|spark| (StatusCode::CREATED, Json(spark)))
    .map_err(|error| api_error(StatusCode::FORBIDDEN, error))
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let token = env_required("CAMELOT_CONTEXT_COMPILER_TOKEN");
    if token.len() < 24 {
        panic!("CAMELOT_CONTEXT_COMPILER_TOKEN must contain at least 24 characters");
    }

    let bundle_dir = PathBuf::from(
        env::var("CAMELOT_KNIGHT_BUNDLE_DIR")
            .unwrap_or_else(|_| "/etc/camelot/knights/sir-synthetos".into()),
    );
    let registry_key_id = env_required("CAMELOT_KNIGHT_REGISTRY_KEY_ID");
    let registry_public_key = env_required("CAMELOT_KNIGHT_REGISTRY_PUBLIC_KEY");
    let mut keyring = Keyring::default();
    keyring.insert_hex(registry_key_id, registry_public_key);

    let policy = KnightPolicy {
        expected_tenant_id: env_required("CAMELOT_KNIGHT_TENANT_ID"),
        expected_workspace_id: env_required("CAMELOT_KNIGHT_WORKSPACE_ID"),
        max_risk_tier: env::var("CAMELOT_KNIGHT_MAX_RISK_TIER").unwrap_or_else(|_| "T1".into()),
        max_cognition_ceiling: env::var("CAMELOT_KNIGHT_MAX_COGNITION_CEILING")
            .unwrap_or_else(|_| "L1".into()),
        allowed_effect_classes: csv_set(
            "CAMELOT_KNIGHT_ALLOWED_EFFECT_CLASSES",
            &["ro.fetch", "ro.audit", "internal.synth"],
        ),
        revoked_ids: csv_set("CAMELOT_KNIGHT_REVOKED_IDS", &[]),
    };
    let knight = Arc::new(
        load_bundle_dir(&bundle_dir, &keyring, &policy, Utc::now())
            .expect("verify signed Knight bundle"),
    );

    let key_path = PathBuf::from(
        env::var("CAMELOT_CONTEXT_SIGNING_KEY")
            .unwrap_or_else(|_| "/var/lib/camelot/context-compiler/spark-ed25519.key".into()),
    );
    let signer = Arc::new(load_or_create_signer(&key_path).expect("load Spark signing identity"));
    let signer_key_id = Arc::new(
        env::var("CAMELOT_CONTEXT_SIGNER_KEY_ID")
            .unwrap_or_else(|_| "camelot-context-compiler/default".into()),
    );

    let state = AppState {
        knight,
        signer,
        signer_key_id,
        token: Arc::new(token),
    };

    let protected = Router::new()
        .route("/v1/sparks", post(compile))
        .route_layer(middleware::from_fn_with_state(state.clone(), require_token));
    let app = Router::new()
        .route("/health", get(health_ready))
        .route("/health/live", get(health_live))
        .route("/health/ready", get(health_ready))
        .merge(protected)
        .with_state(state.clone());

    let host = env::var("CAMELOT_CONTEXT_COMPILER_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let parsed_host: IpAddr = host
        .parse()
        .expect("CAMELOT_CONTEXT_COMPILER_HOST must be an IP address");
    if !parsed_host.is_loopback() {
        panic!("Context Compiler must remain loopback-only");
    }
    let port = env::var("CAMELOT_CONTEXT_COMPILER_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(3017);
    let listener = tokio::net::TcpListener::bind((parsed_host, port))
        .await
        .expect("bind Context Compiler");
    tracing::info!(
        persona_id = %state.knight.persona_id,
        max_cognition_ceiling = %state.knight.max_cognition_ceiling,
        spark_signer_public_key = %state.signer.public_key_hex(),
        "Context Compiler online; context signing only, no effect authority"
    );
    axum::serve(listener, app)
        .await
        .expect("Context Compiler failed");
}
