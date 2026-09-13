pub mod source;
pub use source::EpochSource;

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
    pub fn bootstrap(
        epoch: u64,
        active_brain: BrainId,
        receipt_head_sequence: u64,
        state_digest: String,
        reason: String,
        signer: &KeyPair,
    ) -> Result<Self, String> {
        let mut value = Self {
            schema_version: EPOCH_SCHEMA.into(),
            certificate_id: Uuid::new_v4(),
            epoch,
            active_brain,
            previous_brain: None,
            promotion_mode: PromotionMode::Bootstrap,
            promoted_at: Utc::now(),
            reason,
            receipt_head_sequence,
            state_digest,
            signer_public_key: signer.public_key_hex(),
            signature: String::new(),
        };
        value.validate_shape()?;
        value.sign_with(signer)?;
        Ok(value)
    }

    pub fn promoted(
        previous: &Self,
        target_brain: BrainId,
        mode: PromotionMode,
        receipt_head_sequence: u64,
        state_digest: String,
        reason: String,
        signer: &KeyPair,
    ) -> Result<Self, String> {
        if target_brain == previous.active_brain {
            return Err("target brain is already active".into());
        }
        let mut value = Self {
            schema_version: EPOCH_SCHEMA.into(),
            certificate_id: Uuid::new_v4(),
            epoch: previous.epoch.checked_add(1).ok_or("authority epoch overflow")?,
            active_brain: target_brain,
            previous_brain: Some(previous.active_brain),
            promotion_mode: mode,
            promoted_at: Utc::now(),
            reason,
            receipt_head_sequence,
            state_digest,
            signer_public_key: signer.public_key_hex(),
            signature: String::new(),
        };
        value.validate_shape()?;
        value.sign_with(signer)?;
        Ok(value)
    }

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

#[cfg(test)]
mod tests {
    use super::*;

    fn digest(ch: char) -> String {
        format!("sha256:{}", ch.to_string().repeat(64))
    }

    #[test]
    fn promotion_increments_epoch_and_rotates_brain() {
        let signer = KeyPair::generate();
        let first = AuthorityEpochCertificate::bootstrap(
            7,
            BrainId::OpenNotebook,
            41,
            digest('a'),
            "bootstrap".into(),
            &signer,
        )
        .unwrap();
        let next = AuthorityEpochCertificate::promoted(
            &first,
            BrainId::Notebooklm,
            PromotionMode::Planned,
            41,
            digest('a'),
            "planned handoff".into(),
            &signer,
        )
        .unwrap();
        assert_eq!(next.epoch, 8);
        assert_eq!(next.previous_brain, Some(BrainId::OpenNotebook));
        assert_eq!(next.active_brain, BrainId::Notebooklm);
        next.verify_with_pinned_key(&signer.public_key_hex()).unwrap();
    }
}
