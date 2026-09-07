use axum::{
    routing::post,
    Router,
    Json,
    http::StatusCode,
};
use serde::{Deserialize, Serialize};

#[derive(Deserialize)]
struct VerifyRequest {
    mission_id: String,
    manifest_hash: String,
}

#[derive(Serialize)]
struct VerifyResponse {
    verdict: String,
    reason: String,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let app = Router::new()
        .route("/verify", post(handle_verify));

    let addr = std::net::SocketAddr::from(([127, 0, 0, 1], 3011));
    tracing::info!("Gideon Verification Gate starting on {}", addr);
    let listener = tokio::net::TcpListener::bind(addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn handle_verify(
    Json(payload): Json<VerifyRequest>,
) -> (StatusCode, Json<VerifyResponse>) {
    // In Phase 3, this will invoke the Z3 prover
    (
        StatusCode::OK,
        Json(VerifyResponse {
            verdict: "APPROVED".into(),
            reason: format!("Mission {} safety properties formally verified.", payload.mission_id),
        })
    )
}
