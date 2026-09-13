use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

pub const EPOCH_SCHEMA: &str = "authority-epoch/1";

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "kebab-case")]
pub enum BrainId {
    OpenNotebook,
    Notebooklm,
}

impl BrainId {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::OpenNotebook => "open-notebook",
            Self::Notebooklm => "notebooklm",
        }
    }
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum PromotionMode {
    Bootstrap,
    Planned,
    Failover,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AuthorityEpochCertificate {
    pub schema_version: String,
    pub certificate_id: Uuid,
    pub epoch: u64,
    pub active_brain: BrainId,
    pub previous_brain: Option<BrainId>,
    pub promotion_mode: PromotionMode,
    pub promoted_at: DateTime<Utc>,
    pub reason: String,
    pub receipt_head_sequence: u64,
    pub state_digest: String,
    pub signer_public_key: String,
    pub signature: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct BrainHeartbeat {
    pub brain_id: BrainId,
    pub observed_epoch: u64,
    pub ready: bool,
    pub receipt_head_sequence: u64,
    pub state_digest: String,
    pub observed_at: DateTime<Utc>,
}
