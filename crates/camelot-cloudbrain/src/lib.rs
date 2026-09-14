use camelot_crypto::{hash_payload, verify_detached_hex, KeyPair};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

pub const CONTEXT_PACKET_SCHEMA: &str = "camelot-context-packet/1";

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ActorRef {
    pub id: String,
    pub role: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub tenant_id: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ContextKind {
    SystemPolicy,
    L0Summary,
    L1Verified,
    L2Evidence,
    GraphTraversal,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct ContextSection {
    pub kind: ContextKind,
    pub content_ref: String,
    pub tokens: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContextPacket {
    pub schema_version: String,
    pub packet_id: String,
    pub tenant_id: String,
    pub correlation_id: String,
    pub task_id: String,
    pub retrieval_lease_id: String,
    pub compiled_by: ActorRef,
    pub sections: Vec<ContextSection>,
    pub total_input_tokens: u64,
    pub hard_max_tokens: u64,
    #[serde(default)]
    pub untrusted_content_stripped: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cache_key: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cache_signature: Option<String>,
    pub signature: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub receipt_ref: Option<String>,
}

impl ContextPacket {
    pub fn new(
        tenant_id: Uuid,
        correlation_id: &str,
        task_id: &str,
        lease_id: Uuid,
        sections: Vec<ContextSection>,
        total_input_tokens: u64,
        hard_max_tokens: u64,
    ) -> Self {
        Self {
            schema_version: CONTEXT_PACKET_SCHEMA.into(),
            packet_id: format!("pkt_{}", Uuid::new_v4().simple()),
            tenant_id: format!("tenant_{}", tenant_id.simple()),
            correlation_id: normalize_prefixed("cor", correlation_id),
            task_id: normalize_prefixed("task", task_id),
            retrieval_lease_id: format!("rl_{}", lease_id.simple()),
            compiled_by: ActorRef {
                id: "cloudbrain-broker".into(),
                role: "context-compiler".into(),
                tenant_id: Some(format!("tenant_{}", tenant_id.simple())),
            },
            sections,
            total_input_tokens,
            hard_max_tokens,
            untrusted_content_stripped: 0,
            cache_key: None,
            cache_signature: None,
            signature: String::new(),
            receipt_ref: None,
        }
    }

    pub fn signing_payload(&self) -> Result<Vec<u8>, String> {
        let mut unsigned = self.clone();
        unsigned.signature.clear();
        serde_json::to_vec(&unsigned).map_err(|error| format!("serialize context packet: {error}"))
    }

    pub fn sign_with(&mut self, signer: &KeyPair) -> Result<(), String> {
        self.signature = format!("ed25519:{}", signer.sign_hex(&self.signing_payload()?));
        Ok(())
    }

    pub fn verify_with(&self, expected_public_key: &str) -> Result<(), String> {
        if self.schema_version != CONTEXT_PACKET_SCHEMA {
            return Err("unsupported context packet schema".into());
        }
        if self.total_input_tokens > self.hard_max_tokens {
            return Err("context packet exceeds hard token budget".into());
        }
        let signature = self
            .signature
            .strip_prefix("ed25519:")
            .ok_or_else(|| "context packet signature must use ed25519 prefix".to_string())?;
        verify_detached_hex(expected_public_key, &self.signing_payload()?, signature)
    }
}

pub fn content_reference(content: &str) -> String {
    hash_payload(content)
}

pub fn conservative_token_estimate(text: &str) -> u64 {
    let chars = text.chars().count() as u64;
    chars.div_ceil(4).max(1)
}

pub fn normalize_prefixed(prefix: &str, value: &str) -> String {
    let cleaned: String = value
        .chars()
        .filter(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '_' | '-'))
        .collect();
    let expected_prefix = format!("{prefix}_");
    let cleaned = cleaned.strip_prefix(&expected_prefix).unwrap_or(&cleaned);
    if cleaned.is_empty() {
        format!("{prefix}_{}", Uuid::new_v4().simple())
    } else {
        format!("{prefix}_{cleaned}")
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn signed_packet_round_trip() {
        let signer = KeyPair::generate();
        let mut packet = ContextPacket::new(
            Uuid::nil(),
            "corr-a",
            "task-a",
            Uuid::new_v4(),
            vec![ContextSection {
                kind: ContextKind::L2Evidence,
                content_ref: content_reference("answer"),
                tokens: 2,
            }],
            2,
            128,
        );
        packet.sign_with(&signer).expect("sign");
        packet
            .verify_with(&signer.public_key_hex())
            .expect("verify");
    }

    #[test]
    fn budget_is_enforced() {
        let signer = KeyPair::generate();
        let mut packet = ContextPacket::new(
            Uuid::nil(),
            "corr-a",
            "task-a",
            Uuid::new_v4(),
            Vec::new(),
            100,
            10,
        );
        packet.sign_with(&signer).expect("sign");
        assert!(packet.verify_with(&signer.public_key_hex()).is_err());
    }

    #[test]
    fn prefixes_are_stable() {
        assert_eq!(normalize_prefixed("cor", "cor_abc-123"), "cor_abc-123");
        assert_eq!(normalize_prefixed("task", "task_abc_123"), "task_abc_123");
    }
}
