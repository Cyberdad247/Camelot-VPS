use axum::{
    extract::{Request, State},
    http::{header::AUTHORIZATION, StatusCode},
    middleware::{self, Next},
    response::Response,
    routing::get,
    Json, Router,
};
use camelot_knight::{load_bundle_dir, Keyring, KnightPolicy, LoadedKnight};
use chrono::Utc;
use serde_json::json;
use std::{collections::HashSet, env, net::IpAddr, path::PathBuf, sync::Arc};
use subtle::ConstantTimeEq;

#[derive(Clone)]
struct AppState {
    knight: Arc<LoadedKnight>,
    token: Arc<String>,
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

async fn health_live() -> Json<serde_json::Value> {
    Json(json!({
        "status": "ok",
        "service": "knight-registry",
        "live": true,
        "authority": false
    }))
}

async fn health_ready(State(state): State<AppState>) -> Json<serde_json::Value> {
    Json(json!({
        "status": "ready",
        "service": "knight-registry",
        "personaId": state.knight.persona_id,
        "canonicalName": state.knight.canonical_name,
        "packageId": state.knight.package_id,
        "maxRiskTier": state.knight.max_risk_tier,
        "maxCognitionCeiling": state.knight.max_cognition_ceiling,
        "authority": false
    }))
}

async fn get_knight(State(state): State<AppState>) -> Json<LoadedKnight> {
    Json((*state.knight).clone())
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let token = env_required("CAMELOT_KNIGHT_REGISTRY_TOKEN");
    if token.len() < 24 {
        panic!("CAMELOT_KNIGHT_REGISTRY_TOKEN must contain at least 24 characters");
    }

    let bundle_dir = PathBuf::from(
        env::var("CAMELOT_KNIGHT_BUNDLE_DIR")
            .unwrap_or_else(|_| "/etc/camelot/knights/sir-synthetos".into()),
    );
    let key_id = env_required("CAMELOT_KNIGHT_REGISTRY_KEY_ID");
    let public_key = env_required("CAMELOT_KNIGHT_REGISTRY_PUBLIC_KEY");
    let mut keyring = Keyring::default();
    keyring.insert_hex(key_id, public_key);

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
    if knight.persona_id != "sir_synthetos" && knight.max_risk_tier == "T1" {
        tracing::warn!(
            persona_id = %knight.persona_id,
            "first v3 runtime slice is designed for Sir Synthetos; alternate persona loaded"
        );
    }

    let state = AppState {
        knight,
        token: Arc::new(token),
    };

    let protected = Router::new()
        .route("/v1/knight", get(get_knight))
        .route_layer(middleware::from_fn_with_state(state.clone(), require_token));
    let app = Router::new()
        .route("/health", get(health_ready))
        .route("/health/live", get(health_live))
        .route("/health/ready", get(health_ready))
        .merge(protected)
        .with_state(state.clone());

    let host = env::var("CAMELOT_KNIGHT_REGISTRY_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let parsed_host: IpAddr = host
        .parse()
        .expect("CAMELOT_KNIGHT_REGISTRY_HOST must be an IP address");
    if !parsed_host.is_loopback() {
        panic!("Knight Registry must remain loopback-only");
    }
    let port = env::var("CAMELOT_KNIGHT_REGISTRY_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(3016);
    let listener = tokio::net::TcpListener::bind((parsed_host, port))
        .await
        .expect("bind Knight Registry");
    tracing::info!(
        persona_id = %state.knight.persona_id,
        package_id = %state.knight.package_id,
        "signed Knight Registry online; no effect authority"
    );
    axum::serve(listener, app)
        .await
        .expect("Knight Registry failed");
}
