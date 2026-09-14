mod store;

use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use camelot_crypto::KeyPair;
use camelot_receipts::{Receipt, ReceiptDraft, RECEIPT_SCHEMA};
use serde::Deserialize;
use serde_json::{json, Value};
use std::{
    env, fs,
    io::Write,
    net::IpAddr,
    path::{Path as FsPath, PathBuf},
    sync::Arc,
};
use store::LedgerStore;
use tracing::info;
use uuid::Uuid;

#[derive(Debug, Deserialize)]
struct ListQuery {
    after: Option<i64>,
    limit: Option<i64>,
}

type ApiError = (StatusCode, Json<Value>);

fn api_error(status: StatusCode, message: impl Into<String>) -> ApiError {
    (status, Json(json!({ "error": message.into() })))
}

fn load_or_create_signer(path: &FsPath) -> Result<KeyPair, String> {
    if path.exists() {
        let raw = fs::read_to_string(path)
            .map_err(|error| format!("read receipt signing key: {error}"))?;
        return KeyPair::from_secret_hex(raw.trim());
    }
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("create receipt key directory: {error}"))?;
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
        .map_err(|error| format!("create receipt signing key: {error}"))?;
    file.write_all(signer.secret_key_hex().as_bytes())
        .map_err(|error| format!("write receipt signing key: {error}"))?;
    file.write_all(b"\n")
        .map_err(|error| format!("finalize receipt signing key: {error}"))?;
    file.sync_all()
        .map_err(|error| format!("sync receipt signing key: {error}"))?;
    Ok(signer)
}

async fn health_live() -> Json<Value> {
    Json(json!({
        "status": "ok",
        "service": "camelot-receipt-ledger",
        "live": true
    }))
}

async fn health_ready(State(store): State<Arc<LedgerStore>>) -> (StatusCode, Json<Value>) {
    if store.ready().await {
        (
            StatusCode::OK,
            Json(json!({
                "status": "ready",
                "service": "camelot-receipt-ledger",
                "schema": RECEIPT_SCHEMA,
                "authorityEpoch": store.authority_epoch(),
                "signerPublicKey": store.signer_public_key()
            })),
        )
    } else {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(json!({
                "status": "not_ready",
                "service": "camelot-receipt-ledger"
            })),
        )
    }
}

async fn create_receipt(
    State(store): State<Arc<LedgerStore>>,
    Json(draft): Json<ReceiptDraft>,
) -> Result<(StatusCode, Json<Receipt>), ApiError> {
    store
        .append(draft)
        .await
        .map(|receipt| (StatusCode::CREATED, Json(receipt)))
        .map_err(|error| api_error(StatusCode::CONFLICT, error))
}

async fn get_receipt(
    Path(id): Path<Uuid>,
    State(store): State<Arc<LedgerStore>>,
) -> Result<Json<Receipt>, ApiError> {
    match store
        .get(id)
        .await
        .map_err(|error| api_error(StatusCode::INTERNAL_SERVER_ERROR, error))?
    {
        Some(receipt) => Ok(Json(receipt)),
        None => Err(api_error(StatusCode::NOT_FOUND, "receipt not found")),
    }
}

async fn list_receipts(
    Query(query): Query<ListQuery>,
    State(store): State<Arc<LedgerStore>>,
) -> Result<Json<Vec<Receipt>>, ApiError> {
    store
        .list(query.after.unwrap_or(-1), query.limit.unwrap_or(100))
        .await
        .map(Json)
        .map_err(|error| api_error(StatusCode::INTERNAL_SERVER_ERROR, error))
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
    let database_url = env::var("CAMELOT_RECEIPT_DATABASE_URL")
        .unwrap_or_else(|_| "sqlite:///var/lib/camelot/receipts/ledger.sqlite3".into());
    let key_path = PathBuf::from(
        env::var("CAMELOT_RECEIPT_SIGNING_KEY")
            .unwrap_or_else(|_| "/var/lib/camelot/receipts/ledger-ed25519.key".into()),
    );
    let signer = load_or_create_signer(&key_path).expect("load receipt signing identity");
    let store = Arc::new(
        LedgerStore::open(&database_url, signer, authority_epoch)
            .await
            .expect("open and verify receipt ledger"),
    );

    let app = Router::new()
        .route("/health", get(health_ready))
        .route("/health/live", get(health_live))
        .route("/health/ready", get(health_ready))
        .route("/receipts", post(create_receipt).get(list_receipts))
        .route("/receipts/:id", get(get_receipt))
        .with_state(store.clone());

    let host = env::var("CAMELOT_RECEIPT_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let parsed_host: IpAddr = host
        .parse()
        .expect("CAMELOT_RECEIPT_HOST must be an IP address");
    if !parsed_host.is_loopback() {
        panic!("receipt ledger must remain loopback-only behind Camelot controls");
    }
    let port = env::var("CAMELOT_RECEIPT_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(3001);
    let listener = tokio::net::TcpListener::bind((parsed_host, port))
        .await
        .expect("bind receipt ledger");
    info!(
        authority_epoch,
        signer_public_key = %store.signer_public_key(),
        "Camelot signed receipt ledger online"
    );
    axum::serve(listener, app)
        .await
        .expect("receipt ledger failed");
}
