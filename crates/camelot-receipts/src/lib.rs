use serde::{Deserialize, Serialize};
use uuid::Uuid;
use chrono::{DateTime, Utc};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Receipt {
    pub receipt_id: Uuid,
    pub timestamp: DateTime<Utc>,
    pub tenant_id: Uuid,
    pub actor_id: String,
    pub action_type: String,
    pub resource_uri: String,
    pub payload_hash: String,
    pub parent_receipt_hash: Option<String>,
    pub signature: String,
}

impl Receipt {
    pub fn new(
        tenant_id: Uuid,
        actor_id: String,
        action_type: String,
        resource_uri: String,
        payload_hash: String,
        parent_receipt_hash: Option<String>,
        signature: String,
    ) -> Self {
        Self {
            receipt_id: Uuid::new_v4(),
            timestamp: Utc::now(),
            tenant_id,
            actor_id,
            action_type,
            resource_uri,
            payload_hash,
            parent_receipt_hash,
            signature,
        }
    }
}
