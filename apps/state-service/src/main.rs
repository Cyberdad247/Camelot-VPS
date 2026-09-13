use axum::{routing::get, Json, Router};
use serde_json::json;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();
    let app = Router::new().route(
        "/health/live",
        get(|| async { Json(json!({"status":"ok","service":"camelot-state-service"})) }),
    );
    let listener = tokio::net::TcpListener::bind("127.0.0.1:3012")
        .await
        .expect("bind state service");
    axum::serve(listener, app).await.expect("state service failed");
}
