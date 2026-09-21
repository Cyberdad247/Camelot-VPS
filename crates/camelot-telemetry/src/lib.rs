use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

pub const TELEMETRY_SCHEMA: &str = "camelot-telemetry-envelope/1";
pub const TELEMETRY_AUTHORITY_SEMANTICS: &str = "telemetry-not-authority";
pub const MAX_ATTRIBUTES: usize = 64;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct TelemetryEnvelope {
    pub schema_version: String,
    pub authority_semantics: String,
    pub trace_id: String,
    pub span_id: String,
    pub parent_span_id: Option<String>,
    pub quest_id: Option<String>,
    pub task_id: Option<String>,
    pub tenant_id: Option<String>,
    pub workspace_id: Option<String>,
    pub persona_id: Option<String>,
    pub effect_id: Option<String>,
    pub lease_id: Option<String>,
    pub authority_epoch: Option<u64>,
    pub knowledge_epoch: Option<u64>,
    pub receipt_id: Option<String>,
    pub service: String,
    pub service_version: String,
    pub release_proof_id: Option<String>,
    pub contract_registry_digest: Option<String>,
    pub observed_at: DateTime<Utc>,
    #[serde(default)]
    pub attributes: BTreeMap<String, String>,
}

impl TelemetryEnvelope {
    pub fn new(
        trace_id: impl Into<String>,
        span_id: impl Into<String>,
        service: impl Into<String>,
        service_version: impl Into<String>,
    ) -> Result<Self, String> {
        let value = Self {
            schema_version: TELEMETRY_SCHEMA.into(),
            authority_semantics: TELEMETRY_AUTHORITY_SEMANTICS.into(),
            trace_id: trace_id.into(),
            span_id: span_id.into(),
            parent_span_id: None,
            quest_id: None,
            task_id: None,
            tenant_id: None,
            workspace_id: None,
            persona_id: None,
            effect_id: None,
            lease_id: None,
            authority_epoch: None,
            knowledge_epoch: None,
            receipt_id: None,
            service: service.into(),
            service_version: service_version.into(),
            release_proof_id: None,
            contract_registry_digest: None,
            observed_at: Utc::now(),
            attributes: BTreeMap::new(),
        };
        value.validate()?;
        Ok(value)
    }

    pub fn validate(&self) -> Result<(), String> {
        if self.schema_version != TELEMETRY_SCHEMA
            || self.authority_semantics != TELEMETRY_AUTHORITY_SEMANTICS
        {
            return Err("invalid telemetry schema or authority semantics".into());
        }
        validate_trace_id(&self.trace_id)?;
        validate_span_id(&self.span_id)?;
        if let Some(parent) = &self.parent_span_id {
            validate_span_id(parent)?;
        }
        bounded("service", &self.service, 1, 120)?;
        bounded("serviceVersion", &self.service_version, 1, 120)?;

        for (name, value) in [
            ("questId", self.quest_id.as_deref()),
            ("taskId", self.task_id.as_deref()),
            ("tenantId", self.tenant_id.as_deref()),
            ("workspaceId", self.workspace_id.as_deref()),
            ("personaId", self.persona_id.as_deref()),
            ("effectId", self.effect_id.as_deref()),
            ("leaseId", self.lease_id.as_deref()),
            ("receiptId", self.receipt_id.as_deref()),
            ("releaseProofId", self.release_proof_id.as_deref()),
        ] {
            if let Some(value) = value {
                bounded(name, value, 1, 200)?;
            }
        }

        if self.authority_epoch == Some(0) {
            return Err("authorityEpoch must be positive when present".into());
        }
        if let Some(digest) = &self.contract_registry_digest {
            validate_sha256(digest)?;
        }
        if self.attributes.len() > MAX_ATTRIBUTES {
            return Err(format!(
                "telemetry attributes exceed {MAX_ATTRIBUTES} entries"
            ));
        }
        for (key, value) in &self.attributes {
            bounded("attribute key", key, 1, 80)?;
            bounded("attribute value", value, 0, 1024)?;
            let lowered = key.to_ascii_lowercase();
            if [
                "authorization",
                "cookie",
                "password",
                "secret",
                "token",
                "private_key",
            ]
            .iter()
            .any(|needle| lowered.contains(needle))
            {
                return Err(format!("telemetry attribute key is secret-like: {key}"));
            }
        }
        Ok(())
    }

    pub fn traceparent(&self) -> Result<String, String> {
        self.validate()?;
        Ok(format!("00-{}-{}-01", self.trace_id, self.span_id))
    }

    pub fn from_traceparent(
        value: &str,
        service: impl Into<String>,
        service_version: impl Into<String>,
    ) -> Result<Self, String> {
        let parts: Vec<&str> = value.trim().split('-').collect();
        if parts.len() != 4 || parts[0] != "00" || parts[3].len() != 2 {
            return Err("unsupported traceparent".into());
        }
        if !parts[3].bytes().all(is_lower_hex) {
            return Err("invalid trace flags".into());
        }
        Self::new(parts[1], parts[2], service, service_version)
    }

    pub fn child(
        &self,
        span_id: impl Into<String>,
        service: impl Into<String>,
        service_version: impl Into<String>,
    ) -> Result<Self, String> {
        self.validate()?;
        let mut child = self.clone();
        child.parent_span_id = Some(self.span_id.clone());
        child.span_id = span_id.into();
        child.service = service.into();
        child.service_version = service_version.into();
        child.observed_at = Utc::now();
        child.attributes = BTreeMap::new();
        child.validate()?;
        Ok(child)
    }
}

fn bounded(name: &str, value: &str, min: usize, max: usize) -> Result<(), String> {
    let length = value.len();
    if length < min || length > max {
        return Err(format!("{name} must contain {min}..{max} bytes"));
    }
    Ok(())
}

fn is_lower_hex(value: u8) -> bool {
    value.is_ascii_digit() || (b'a'..=b'f').contains(&value)
}

fn validate_trace_id(value: &str) -> Result<(), String> {
    if value.len() != 32
        || value.bytes().all(|byte| byte == b'0')
        || !value.bytes().all(is_lower_hex)
    {
        return Err("traceId must be a non-zero lowercase 32-character hex value".into());
    }
    Ok(())
}

fn validate_span_id(value: &str) -> Result<(), String> {
    if value.len() != 16
        || value.bytes().all(|byte| byte == b'0')
        || !value.bytes().all(is_lower_hex)
    {
        return Err("spanId must be a non-zero lowercase 16-character hex value".into());
    }
    Ok(())
}

fn validate_sha256(value: &str) -> Result<(), String> {
    let Some(hex) = value.strip_prefix("sha256:") else {
        return Err("digest must use sha256: prefix".into());
    };
    if hex.len() != 64 || !hex.bytes().all(is_lower_hex) {
        return Err("digest must contain 64 lowercase sha256 hex characters".into());
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn envelope() -> TelemetryEnvelope {
        TelemetryEnvelope::new(
            "11111111111111111111111111111111",
            "2222222222222222",
            "sentinel",
            "0.2.0",
        )
        .expect("valid envelope")
    }

    #[test]
    fn creates_w3c_traceparent() {
        assert_eq!(
            envelope().traceparent().unwrap(),
            "00-11111111111111111111111111111111-2222222222222222-01"
        );
    }

    #[test]
    fn parses_traceparent_without_inventing_authority() {
        let value = TelemetryEnvelope::from_traceparent(
            "00-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-bbbbbbbbbbbbbbbb-01",
            "bifrost",
            "1.0.0",
        )
        .unwrap();
        assert_eq!(value.trace_id, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
        assert_eq!(value.authority_semantics, TELEMETRY_AUTHORITY_SEMANTICS);
        assert_eq!(value.authority_epoch, None);
        assert_eq!(value.lease_id, None);
    }

    #[test]
    fn child_preserves_trace_and_records_parent() {
        let parent = envelope();
        let child = parent.child("3333333333333333", "gideon", "0.1.0").unwrap();
        assert_eq!(child.trace_id, parent.trace_id);
        assert_eq!(
            child.parent_span_id.as_deref(),
            Some(parent.span_id.as_str())
        );
        assert_eq!(child.span_id, "3333333333333333");
    }

    #[test]
    fn rejects_zero_ids_and_secret_like_attributes() {
        assert!(TelemetryEnvelope::new(
            "00000000000000000000000000000000",
            "2222222222222222",
            "sentinel",
            "0.2.0",
        )
        .is_err());

        let mut value = envelope();
        value
            .attributes
            .insert("authorization_token".into(), "never-log-me".into());
        assert!(value.validate().unwrap_err().contains("secret-like"));
    }

    #[test]
    fn validates_contract_registry_digest() {
        let mut value = envelope();
        value.contract_registry_digest = Some(format!("sha256:{}", "a".repeat(64)));
        value.validate().expect("valid digest");

        value.contract_registry_digest = Some("sha256:BAD".into());
        assert!(value.validate().is_err());
    }
}
