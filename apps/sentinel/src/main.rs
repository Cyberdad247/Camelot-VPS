use axum::{
    routing::post,
    Router,
    Json,
    http::StatusCode,
};
use camelot_lease::{CapabilityLease, EffectManifest};
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
pub struct EvaluationRequest {
    pub manifest: EffectManifest,
    pub lease: CapabilityLease,
}

#[derive(Debug, Serialize)]
pub struct PolicyDecision {
    pub allowed: bool,
    pub reason: String,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let app = Router::new()
        .route("/evaluate", post(evaluate_policy));

    // Sentinel runs on internal port 3002. Only Bifrost/Scheduler can talk to it.
    let listener = tokio::net::TcpListener::bind("127.0.0.1:3002").await.unwrap();
    tracing::info!("Sentinel Policy Engine listening on {}", listener.local_addr().unwrap());
    axum::serve(listener, app).await.unwrap();
}

async fn evaluate_policy(
    Json(payload): Json<EvaluationRequest>,
) -> (StatusCode, Json<PolicyDecision>) {
    let req_lease = payload.lease;
    let req_manifest = payload.manifest;

    // 1. Check Lease Expiry & Revocation
    if !req_lease.is_valid() {
        return (
            StatusCode::FORBIDDEN,
            Json(PolicyDecision {
                allowed: false,
                reason: "Lease expired or revoked".to_string(),
            }),
        );
    }

    // 2. Check Cryptographic Signature (Mocked for Phase 0)
    if req_lease.signature.is_none() {
        return (
            StatusCode::UNAUTHORIZED,
            Json(PolicyDecision {
                allowed: false,
                reason: "Missing Ed25519 issuer signature".to_string(),
            }),
        );
    }

    // 3. Verify Required Capability
    if !req_lease.has_capability(&req_manifest.required_lease_type) {
        return (
            StatusCode::FORBIDDEN,
            Json(PolicyDecision {
                allowed: false,
                reason: format!("Lease lacks required capability: {}", req_manifest.required_lease_type),
            }),
        );
    }

    // 4. Verification Passed
    (
        StatusCode::OK,
        Json(PolicyDecision {
            allowed: true,
            reason: "Manifest authorized by active valid lease".to_string(),
        })
    )
}
