use axum::{
    routing::{get, post},
    Router,
    extract::{State, Path},
    Json,
    http::StatusCode,
};
use camelot_receipts::Receipt;
use std::sync::Arc;
use tokio::sync::RwLock;
use std::collections::HashMap;
use uuid::Uuid;

type AppState = Arc<RwLock<HashMap<Uuid, Receipt>>>;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let state: AppState = Arc::new(RwLock::new(HashMap::new()));

    let app = Router::new()
        .route("/receipts", post(create_receipt))
        .route("/receipts/:id", get(get_receipt))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:3001").await.unwrap();
    tracing::info!("Receipt service listening on {}", listener.local_addr().unwrap());
    axum::serve(listener, app).await.unwrap();
}

async fn create_receipt(
    State(state): State<AppState>,
    Json(payload): Json<Receipt>,
) -> (StatusCode, Json<Receipt>) {
    // TODO: Verify payload signature and parent hash linkage via camelot-crypto
    let mut store = state.write().await;
    store.insert(payload.receipt_id, payload.clone());
    (StatusCode::CREATED, Json(payload))
}

async fn get_receipt(
    Path(id): Path<Uuid>,
    State(state): State<AppState>,
) -> Result<Json<Receipt>, StatusCode> {
    let store = state.read().await;
    if let Some(receipt) = store.get(&id) {
        Ok(Json(receipt.clone()))
    } else {
        Err(StatusCode::NOT_FOUND)
    }
}
