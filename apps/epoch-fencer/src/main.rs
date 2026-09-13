mod api;
mod auth;
mod io;
mod model;
mod store;

use api::AppState;
use axum::{
    routing::{get, post},
    Router,
};
use camelot_crypto::KeyPair;
use camelot_epoch::BrainId;
use std::{env, fs, net::IpAddr, path::PathBuf, sync::Arc};
use store::EpochStore;
use tracing::info;

fn credential_path(name: &str, explicit_env: &str) -> PathBuf {
    if let Ok(path) = env::var(explicit_env) {
        return PathBuf::from(path);
    }
    if let Ok(directory) = env::var("CREDENTIALS_DIRECTORY") {
        return PathBuf::from(directory).join(name);
    }
    PathBuf::from("/etc/camelot/credentials").join(name)
}

fn read_credential(name: &str, explicit_env: &str) -> Result<String, String> {
    let path = credential_path(name, explicit_env);
    fs::read_to_string(&path)
        .map(|value| value.trim().to_string())
        .map_err(|error| format!("read pre-provisioned credential {name}: {error}"))
}

fn load_signer() -> Result<KeyPair, String> {
    let raw = read_credential("epoch-signing-key", "CAMELOT_EPOCH_SIGNING_KEY_FILE")?;
    KeyPair::from_secret_hex(&raw)
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let api_token = env::var("CAMELOT_EPOCH_TOKEN")
        .ok()
        .or_else(|| read_credential("epoch-api-token", "CAMELOT_EPOCH_TOKEN_FILE").ok())
        .expect("epoch heartbeat credential must be configured");
    let promotion_token = env::var("CAMELOT_EPOCH_PROMOTION_TOKEN")
        .ok()
        .or_else(|| {
            read_credential(
                "epoch-promotion-token",
                "CAMELOT_EPOCH_PROMOTION_TOKEN_FILE",
            )
            .ok()
        })
        .expect("epoch promotion credential must be configured");
    if api_token.len() < 24 || promotion_token.len() < 24 {
        panic!("epoch fencer credentials must contain at least 24 characters");
    }

    let signer = Arc::new(load_signer().expect("load pre-provisioned epoch signing identity"));
    let signer_public_key = signer.public_key_hex();
    let database_url = env::var("CAMELOT_EPOCH_DATABASE_URL")
        .unwrap_or_else(|_| "sqlite:///var/lib/camelot/epoch-fencer/fencer.sqlite3".into());
    let bootstrap_epoch = env::var("CAMELOT_AUTHORITY_EPOCH")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(1);
    if bootstrap_epoch == 0 {
        panic!("CAMELOT_AUTHORITY_EPOCH must be positive");
    }
    let bootstrap_brain = BrainId::parse(
        &env::var("CAMELOT_ACTIVE_BRAIN").unwrap_or_else(|_| "open-notebook".into()),
    )
    .expect("CAMELOT_ACTIVE_BRAIN must identify a Twin Brain");
    let heartbeat_age = env::var("CAMELOT_EPOCH_HEARTBEAT_MAX_AGE_SECONDS")
        .ok()
        .and_then(|value| value.parse::<i64>().ok())
        .unwrap_or(15);
    let certificate_path = PathBuf::from(
        env::var("CAMELOT_EPOCH_CERTIFICATE_PATH")
            .unwrap_or_else(|_| "/run/camelot/authority/epoch.json".into()),
    );

    let store = EpochStore::open(
        &database_url,
        signer,
        bootstrap_epoch,
        bootstrap_brain,
        heartbeat_age,
    )
    .await
    .expect("open epoch fencing store");
    let certificate = store.current().await.expect("load current authority epoch");
    io::publish_certificate(&certificate_path, &certificate)
        .expect("publish authority epoch certificate");

    let state = AppState {
        store,
        api_token: Arc::new(api_token),
        promotion_token: Arc::new(promotion_token),
        certificate_path: Arc::new(certificate_path),
        signer_public_key: Arc::new(signer_public_key.clone()),
    };
    let app = Router::new()
        .route("/health/live", get(api::health_live))
        .route("/health/ready", get(api::health_ready))
        .route("/v1/epoch", get(api::status))
        .route("/v1/brains/heartbeat", post(api::heartbeat))
        .route("/v1/promote", post(api::promote))
        .with_state(state);

    let host = env::var("CAMELOT_EPOCH_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let parsed_host: IpAddr = host
        .parse()
        .expect("CAMELOT_EPOCH_HOST must be an IP address");
    if !parsed_host.is_loopback() {
        panic!("epoch fencer must remain loopback-only");
    }
    let port = env::var("CAMELOT_EPOCH_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(3014);
    let listener = tokio::net::TcpListener::bind((parsed_host, port))
        .await
        .expect("bind epoch fencer");
    info!(
        authority_epoch = certificate.epoch,
        active_brain = certificate.active_brain.as_str(),
        signer_public_key,
        "Twin-Brain authority epoch fencer online"
    );
    axum::serve(listener, app).await.expect("epoch fencer failed");
}
