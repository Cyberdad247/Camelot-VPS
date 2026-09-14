use camelot_epoch::{AuthorityEpochCertificate, BrainHeartbeat, BrainId};
use serde::{Deserialize, Serialize};

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct HeartbeatRequest {
    pub brain_id: BrainId,
    pub observed_epoch: u64,
    pub ready: bool,
    pub receipt_head_sequence: u64,
    pub state_digest: String,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct PromotionRequest {
    pub expected_epoch: u64,
    pub expected_active_brain: BrainId,
    pub target_brain: BrainId,
    pub reason: String,
    #[serde(default)]
    pub allow_stale_source: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct BrainStatus {
    pub heartbeat: BrainHeartbeat,
    pub age_seconds: i64,
    pub fresh: bool,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct EpochStatus {
    pub certificate: AuthorityEpochCertificate,
    pub brains: Vec<BrainStatus>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct PromotionResult {
    pub certificate: AuthorityEpochCertificate,
    pub source_fresh: bool,
    pub target_receipt_head_sequence: u64,
}
