use camelot_crypto::{verify_detached_hex, KeyPair};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct CapabilityLease {
    pub lease_id: Uuid,
    pub tenant_id: Uuid,
    pub actor_id: String,
    #[serde(default)]
    pub session_id: Option<Uuid>,
    pub capabilities: Vec<String>,
    pub resource_bounds: Vec<String>,
    pub issued_at: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
    pub issuer_id: String,
    #[serde(default)]
    pub nonce: String,
    pub revoked: bool,
    #[serde(default)]
    pub issuer_public_key: Option<String>,
    pub signature: Option<String>,
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
    pub hash: String,
}

impl CapabilityLease {
    pub fn is_valid(&self) -> bool {
        let now = Utc::now();
        !self.revoked && self.issued_at <= now && self.expires_at >= now
    }

    pub fn has_capability(&self, capability: &str) -> bool {
        self.capabilities.iter().any(|value| value == capability)
    }

    pub fn binds_session(&self, session_id: Uuid) -> bool {
        self.session_id == Some(session_id)
    }

    pub fn resource_allows(&self, resource: &str) -> bool {
        self.resource_bounds.iter().any(|bound| {
            if let Some(prefix) = bound.strip_suffix("/**") {
                resource == prefix || resource.starts_with(&format!("{prefix}/"))
            } else {
                bound == resource
            }
        })
    }

    pub fn signing_payload(&self) -> Result<Vec<u8>, String> {
        let mut unsigned = self.clone();
        unsigned.signature = None;
        serde_json::to_vec(&unsigned).map_err(|error| format!("serialize capability lease: {error}"))
    }

    pub fn sign_with(&mut self, signer: &KeyPair) -> Result<(), String> {
        self.issuer_public_key = Some(signer.public_key_hex());
        self.signature = None;
        let payload = self.signing_payload()?;
        self.signature = Some(signer.sign_hex(&payload));
        Ok(())
    }

    pub fn verify_signature(&self) -> Result<(), String> {
        let public_key = self
            .issuer_public_key
            .as_deref()
            .ok_or_else(|| "capability lease is missing issuer public key".to_string())?;
        let signature = self
            .signature
            .as_deref()
            .ok_or_else(|| "capability lease is missing signature".to_string())?;
        let payload = self.signing_payload()?;
        verify_detached_hex(public_key, &payload, signature)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::Duration;

    fn lease() -> CapabilityLease {
        let now = Utc::now();
        CapabilityLease {
            lease_id: Uuid::new_v4(),
            tenant_id: Uuid::nil(),
            actor_id: "sir_codex".into(),
            session_id: Some(Uuid::new_v4()),
            capabilities: vec!["shadow.read".into(), "shadow.write".into()],
            resource_bounds: vec!["shadow://abc/workspace/**".into()],
            issued_at: now,
            expires_at: now + Duration::minutes(5),
            issuer_id: "sentinel".into(),
            nonce: Uuid::new_v4().to_string(),
            revoked: false,
            issuer_public_key: None,
            signature: None,
        }
    }

    #[test]
    fn signs_and_verifies_lease() {
        let signer = KeyPair::generate();
        let mut lease = lease();
        lease.sign_with(&signer).expect("sign lease");
        lease.verify_signature().expect("verify lease");
    }

    #[test]
    fn resource_scope_is_prefix_bounded() {
        let lease = lease();
        assert!(lease.resource_allows("shadow://abc/workspace/src/main.rs"));
        assert!(!lease.resource_allows("shadow://other/workspace/src/main.rs"));
    }
}
