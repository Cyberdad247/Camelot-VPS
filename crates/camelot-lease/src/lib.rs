use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;
use camelot_crypto::KeyPair;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CapabilityLease {
    pub lease_id: Uuid,
    pub tenant_id: Uuid,
    pub actor_id: String,
    pub capabilities: Vec<String>,
    pub resource_bounds: Vec<String>,
    pub issued_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
    pub issuer_id: String,
    pub revoked: bool,
    pub signature: Option<String>, // Ed25519 signature of the serialized lease body
}

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct EffectManifest {
    pub manifest_id: Uuid,
    pub task_id: Uuid,
    pub proposed_action: String,
    pub target_resource: String,
    pub parameters: serde_json::Value,
    pub required_lease_type: String,
    pub estimated_cost_credits: f64,
    pub hash: String, // SHA256 of the manifest parameters
}

impl CapabilityLease {
    pub fn is_valid(&self) -> bool {
        let now = Utc::now();
        !self.revoked && self.issued_at <= now && self.expires_at >= now
    }
    
    pub fn has_capability(&self, cap: &str) -> bool {
        self.capabilities.contains(&cap.to_string())
    }
}
