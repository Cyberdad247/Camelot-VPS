use camelot_crypto::{hash_payload, verify_detached_hex, KeyPair};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

pub const VFS_ATTESTATION_SCHEMA: &str = "vfs-attestation/2";

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct VfsAttestation {
    pub schema_version: String,
    pub attestation_id: Uuid,
    pub workspace_id: Uuid,
    pub lease_id: Uuid,
    pub epoch: u64,
    pub resource_uri: String,
    pub operation_hash: String,
    pub timestamp: DateTime<Utc>,
    pub signer_public_key: String,
    pub vfs_signature: String,
}

impl VfsAttestation {
    pub fn new_unsigned(
        workspace_id: Uuid,
        lease_id: Uuid,
        epoch: u64,
        resource_uri: String,
        operation_hash: String,
        signer_public_key: String,
    ) -> Self {
        Self {
            schema_version: VFS_ATTESTATION_SCHEMA.into(),
            attestation_id: Uuid::new_v4(),
            workspace_id,
            lease_id,
            epoch,
            resource_uri,
            operation_hash,
            timestamp: Utc::now(),
            signer_public_key,
            vfs_signature: String::new(),
        }
    }

    pub fn signing_payload(&self) -> Result<Vec<u8>, String> {
        let mut unsigned = self.clone();
        unsigned.vfs_signature.clear();
        serde_json::to_vec(&unsigned).map_err(|error| format!("serialize VFS attestation: {error}"))
    }

    pub fn sign_with(&mut self, signer: &KeyPair) -> Result<(), String> {
        self.signer_public_key = signer.public_key_hex();
        self.vfs_signature.clear();
        self.vfs_signature = signer.sign_hex(&self.signing_payload()?);
        Ok(())
    }

    pub fn verify_signature(&self) -> Result<(), String> {
        verify_detached_hex(
            &self.signer_public_key,
            &self.signing_payload()?,
            &self.vfs_signature,
        )
    }
}

#[derive(Debug, Serialize, Deserialize, Clone, Copy, PartialEq, Eq)]
#[serde(rename_all = "UPPERCASE")]
pub enum FileOperationType {
    Read,
    Write,
    Delete,
    Quarantine,
}

impl FileOperationType {
    pub fn capability(self) -> &'static str {
        match self {
            Self::Read => "vfs:read",
            Self::Write => "vfs:write",
            Self::Delete => "vfs:delete",
            Self::Quarantine => "vfs:quarantine",
        }
    }
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct FileOperation {
    pub op_type: FileOperationType,
    pub path: String,
    pub expected_hash: Option<String>,
}

impl FileOperation {
    pub fn digest(&self) -> Result<String, String> {
        serde_json::to_string(self)
            .map(|value| hash_payload(&value))
            .map_err(|error| format!("serialize VFS operation: {error}"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn vfs_attestation_signature_round_trip() {
        let signer = KeyPair::generate();
        let mut attestation = VfsAttestation::new_unsigned(
            Uuid::new_v4(),
            Uuid::new_v4(),
            7,
            "vfs://workspace/worktree/src/main.rs".into(),
            "sha256:operation".into(),
            signer.public_key_hex(),
        );
        attestation.sign_with(&signer).expect("sign attestation");
        attestation.verify_signature().expect("verify attestation");
    }

    #[test]
    fn operation_capabilities_are_typed() {
        assert_eq!(FileOperationType::Read.capability(), "vfs:read");
        assert_eq!(FileOperationType::Write.capability(), "vfs:write");
        assert_eq!(FileOperationType::Delete.capability(), "vfs:delete");
        assert_eq!(
            FileOperationType::Quarantine.capability(),
            "vfs:quarantine"
        );
    }
}
