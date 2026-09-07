use axum::{
    routing::post,
    Router,
    Json,
    http::StatusCode,
};
use camelot_vfs::{VfsAttestation, FileOperation};
use camelot_lease::CapabilityLease;
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::Utc;

#[derive(Debug, Deserialize)]
pub struct VfsRequest {
    pub workspace_id: Uuid,
    pub operation: FileOperation,
    pub lease: CapabilityLease,
}

#[derive(Debug, Serialize)]
pub struct VfsResponse {
    pub allowed: bool,
    pub reason: String,
    pub attestation: Option<VfsAttestation>,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let app = Router::new()
        .route("/vfs/access", post(request_access));

    // VFS Guardian runs on internal port 3003
    let listener = tokio::net::TcpListener::bind("127.0.0.1:3003").await.unwrap();
    tracing::info!("VFS Guardian listening on {}", listener.local_addr().unwrap());
    axum::serve(listener, app).await.unwrap();
}

async fn request_access(
    Json(payload): Json<VfsRequest>,
) -> (StatusCode, Json<VfsResponse>) {
    
    // Hard check: Path escape denial
    if payload.operation.path.contains("..") || payload.operation.path.starts_with('/') {
        return (
            StatusCode::FORBIDDEN,
            Json(VfsResponse {
                allowed: false,
                reason: "VFS Path Escape Denied. Paths must be relative to workspace root.".into(),
                attestation: None,
            })
        );
    }

    // Hard check: Lease validation (in reality, we would ask Sentinel here)
    if !payload.lease.is_valid() || !payload.lease.has_capability(&format!("vfs:{}", payload.operation.op_type.to_lowercase())) {
        return (
            StatusCode::FORBIDDEN,
            Json(VfsResponse {
                allowed: false,
                reason: "Missing or invalid VFS capability lease".into(),
                attestation: None,
            })
        );
    }

    // Generate Attestation (Mocking Merkle Root for Phase 0)
    let attestation = VfsAttestation {
        attestation_id: Uuid::new_v4(),
        workspace_id: payload.workspace_id,
        epoch: 1,
        merkle_root: "sha256:0000000000000000000000000000000000000000000000000000000000000000".into(),
        timestamp: Utc::now(),
        vfs_signature: "mock_signature".into(),
    };

    (
        StatusCode::OK,
        Json(VfsResponse {
            allowed: true,
            reason: "Access granted and workspace state attested.".into(),
            attestation: Some(attestation),
        })
    )
}
