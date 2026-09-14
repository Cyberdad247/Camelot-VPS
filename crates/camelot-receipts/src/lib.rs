use camelot_crypto::{hash_payload, verify_detached_hex, KeyPair};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

pub const RECEIPT_SCHEMA: &str = "receipt/2";

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct ReceiptDraft {
    pub tenant_id: String,
    pub workspace_id: String,
    pub mission_id: String,
    pub task_id: String,
    pub actor_id: String,
    pub action_type: String,
    pub resource_uri: String,
    pub manifest_hash: String,
    #[serde(default)]
    pub capability_lease_id: Option<String>,
    #[serde(default)]
    pub approval_id: Option<String>,
    #[serde(default)]
    pub vfs_attestation_id: Option<String>,
    #[serde(default)]
    pub gideon_verdict_id: Option<String>,
    #[serde(default)]
    pub arthur_resolution_id: Option<String>,
    pub result_hash: String,
    pub authority_epoch: u64,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct Receipt {
    pub schema_version: String,
    pub receipt_id: Uuid,
    pub sequence: u64,
    pub timestamp: DateTime<Utc>,
    pub tenant_id: String,
    pub workspace_id: String,
    pub mission_id: String,
    pub task_id: String,
    pub actor_id: String,
    pub action_type: String,
    pub resource_uri: String,
    pub manifest_hash: String,
    pub capability_lease_id: Option<String>,
    pub approval_id: Option<String>,
    pub vfs_attestation_id: Option<String>,
    pub gideon_verdict_id: Option<String>,
    pub arthur_resolution_id: Option<String>,
    pub result_hash: String,
    pub authority_epoch: u64,
    pub parent_receipt_hash: Option<String>,
    pub receipt_hash: String,
    pub signer_public_key: String,
    pub signature: String,
}

impl Receipt {
    pub fn new_unsigned(
        draft: ReceiptDraft,
        sequence: u64,
        parent_receipt_hash: Option<String>,
        signer_public_key: String,
    ) -> Self {
        Self {
            schema_version: RECEIPT_SCHEMA.into(),
            receipt_id: Uuid::new_v4(),
            sequence,
            timestamp: Utc::now(),
            tenant_id: draft.tenant_id,
            workspace_id: draft.workspace_id,
            mission_id: draft.mission_id,
            task_id: draft.task_id,
            actor_id: draft.actor_id,
            action_type: draft.action_type,
            resource_uri: draft.resource_uri,
            manifest_hash: draft.manifest_hash,
            capability_lease_id: draft.capability_lease_id,
            approval_id: draft.approval_id,
            vfs_attestation_id: draft.vfs_attestation_id,
            gideon_verdict_id: draft.gideon_verdict_id,
            arthur_resolution_id: draft.arthur_resolution_id,
            result_hash: draft.result_hash,
            authority_epoch: draft.authority_epoch,
            parent_receipt_hash,
            receipt_hash: String::new(),
            signer_public_key,
            signature: String::new(),
        }
    }

    fn canonical_payload(&self) -> Result<Vec<u8>, String> {
        let mut unsigned = self.clone();
        unsigned.receipt_hash.clear();
        unsigned.signature.clear();
        serde_json::to_vec(&unsigned).map_err(|error| format!("serialize receipt: {error}"))
    }

    pub fn recompute_hash(&self) -> Result<String, String> {
        let payload = self.canonical_payload()?;
        let text = std::str::from_utf8(&payload)
            .map_err(|error| format!("receipt canonical payload is not UTF-8: {error}"))?;
        Ok(hash_payload(text))
    }

    pub fn sign_with(&mut self, signer: &KeyPair) -> Result<(), String> {
        self.signer_public_key = signer.public_key_hex();
        self.receipt_hash = self.recompute_hash()?;
        self.signature = format!("ed25519:{}", signer.sign_hex(self.receipt_hash.as_bytes()));
        Ok(())
    }

    pub fn verify_integrity(&self) -> Result<(), String> {
        if self.schema_version != RECEIPT_SCHEMA {
            return Err("unsupported receipt schema".into());
        }
        let expected = self.recompute_hash()?;
        if expected != self.receipt_hash {
            return Err("receipt hash does not match canonical payload".into());
        }
        let signature = self
            .signature
            .strip_prefix("ed25519:")
            .ok_or_else(|| "receipt signature must use ed25519 prefix".to_string())?;
        verify_detached_hex(
            &self.signer_public_key,
            self.receipt_hash.as_bytes(),
            signature,
        )
    }
}

pub fn is_sha256_reference(value: &str) -> bool {
    let Some(hex) = value.strip_prefix("sha256:") else {
        return false;
    };
    hex.len() == 64 && hex.bytes().all(|value| value.is_ascii_hexdigit())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn draft() -> ReceiptDraft {
        ReceiptDraft {
            tenant_id: "tenant-a".into(),
            workspace_id: "workspace-a".into(),
            mission_id: "mission-a".into(),
            task_id: "task-a".into(),
            actor_id: "sir-codex".into(),
            action_type: "vfs.promote_diff".into(),
            resource_uri: "vfs://workspace-a/worktree".into(),
            manifest_hash: format!("sha256:{}", "a".repeat(64)),
            capability_lease_id: Some("lease-a".into()),
            approval_id: Some("approval-a".into()),
            vfs_attestation_id: Some("vfs-a".into()),
            gideon_verdict_id: Some("gideon-a".into()),
            arthur_resolution_id: Some("arthur-a".into()),
            result_hash: format!("sha256:{}", "b".repeat(64)),
            authority_epoch: 4,
        }
    }

    #[test]
    fn signed_receipt_round_trip() {
        let signer = KeyPair::generate();
        let mut receipt = Receipt::new_unsigned(draft(), 7, None, signer.public_key_hex());
        receipt.sign_with(&signer).expect("sign receipt");
        receipt.verify_integrity().expect("verify receipt");
    }

    #[test]
    fn canonical_hash_shape_is_enforced() {
        assert!(is_sha256_reference(&format!("sha256:{}", "c".repeat(64))));
        assert!(!is_sha256_reference("sha256:short"));
    }
}
