use camelot_crypto::{verify_detached_hex, KeyPair};
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

    pub fn parse(value: &str) -> Result<Self, String> {
        match value.trim().to_ascii_lowercase().as_str() {
            "open-notebook" | "open_notebook" | "opennotebook" => Ok(Self::OpenNotebook),
            "notebooklm" | "notebook-lm" | "notebook_lm" => Ok(Self::Notebooklm),
            _ => Err("brain must be open-notebook or notebooklm".into()),
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

impl AuthorityEpochCertificate {
    pub fn signing_payload(&self) -> Result<Vec<u8>, String> {
        let mut unsigned = self.clone();
        unsigned.signature.clear();
        serde_json::to_vec(&unsigned).map_err(|error| error.to_string())
    }

    pub fn sign_with(&mut self, signer: &KeyPair) -> Result<(), String> {
        self.signer_public_key = signer.public_key_hex();
        self.signature = signer.sign_hex(&self.signing_payload()?);
        Ok(())
    }

    pub fn verify_with_pinned_key(&self, pinned_public_key: &str) -> Result<(), String> {
        self.validate_shape()?;
        if self.signer_public_key != pinned_public_key {
            return Err("epoch certificate signer mismatch".into());
        }
        verify_detached_hex(
            pinned_public_key,
            &self.signing_payload()?,
            &self.signature,
        )
    }

    pub fn validate_shape(&self) -> Result<(), String> {
        if self.schema_version != EPOCH_SCHEMA || self.epoch == 0 {
            return Err("invalid authority epoch certificate".into());
        }
        if self.reason.trim().is_empty() || self.reason.len() > 512 {
            return Err("promotion reason must contain 1..512 characters".into());
        }
        if !valid_sha256(&self.state_digest) {
            return Err("state digest must be canonical sha256".into());
        }
        Ok(())
    }
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

impl BrainHeartbeat {
    pub fn validate(&self) -> Result<(), String> {
        if self.observed_epoch == 0 || !valid_sha256(&self.state_digest) {
            return Err("invalid brain heartbeat".into());
        }
        Ok(())
    }
}

pub fn valid_sha256(value: &str) -> bool {
    let Some(hex) = value.strip_prefix("sha256:") else {
        return false;
    };
    hex.len() == 64 && hex.bytes().all(|value| value.is_ascii_hexdigit())
}
