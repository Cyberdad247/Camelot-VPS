use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct VfsAttestation {
    pub attestation_id: Uuid,
    pub workspace_id: Uuid,
    pub epoch: u64,
    pub merkle_root: String,
    pub timestamp: DateTime<Utc>,
    pub vfs_signature: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct FileOperation {
    pub op_type: String, // "READ", "WRITE", "DELETE", "QUARANTINE"
    pub path: String,
    pub expected_hash: Option<String>,
}
