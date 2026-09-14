use camelot_lease::{CapabilityLease, EffectManifest};
use reqwest::{Client, StatusCode};
use serde::{Deserialize, Serialize};
use std::time::Duration;
use uuid::Uuid;

#[derive(Debug, Deserialize)]
struct SentinelIdentity {
    #[serde(rename = "issuerId")]
    issuer_id: String,
    #[serde(rename = "publicKey")]
    public_key: String,
}

#[derive(Debug, Serialize)]
struct IssueLeaseRequest<'a> {
    actor_id: &'a str,
    session_id: Uuid,
    capabilities: &'a [String],
    resource_bounds: &'a [String],
    ttl_seconds: i64,
}

#[derive(Debug, Deserialize)]
struct PolicyDecision {
    allowed: bool,
    reason: String,
}

#[derive(Debug, Serialize)]
struct EvaluationRequest<'a> {
    manifest: &'a EffectManifest,
    lease: &'a CapabilityLease,
}

#[derive(Clone)]
pub(crate) struct SentinelClient {
    http: Client,
    base_url: String,
    token: String,
    issuer_id: String,
    public_key: String,
}

impl SentinelClient {
    pub(crate) async fn connect(base_url: String, token: String) -> Result<Self, String> {
        if token.len() < 24 {
            return Err("CAMELOT_SENTINEL_TOKEN must contain at least 24 characters".into());
        }
        let http = Client::builder()
            .timeout(Duration::from_secs(5))
            .build()
            .map_err(|error| format!("build Sentinel client: {error}"))?;
        let base_url = base_url.trim_end_matches('/').to_owned();
        let response = http
            .get(format!("{base_url}/identity"))
            .send()
            .await
            .map_err(|error| format!("reach Sentinel identity endpoint: {error}"))?;
        if !response.status().is_success() {
            return Err(format!("Sentinel identity endpoint returned {}", response.status()));
        }
        let identity: SentinelIdentity = response
            .json()
            .await
            .map_err(|error| format!("decode Sentinel identity: {error}"))?;
        if identity.issuer_id != "camelot-sentinel" || identity.public_key.len() != 64 {
            return Err("Sentinel identity is not a valid Camelot signing authority".into());
        }
        Ok(Self {
            http,
            base_url,
            token,
            issuer_id: identity.issuer_id,
            public_key: identity.public_key,
        })
    }

    pub(crate) fn public_key(&self) -> &str {
        &self.public_key
    }

    pub(crate) async fn ready(&self) -> bool {
        match self.http.get(format!("{}/identity", self.base_url)).send().await {
            Ok(response) if response.status().is_success() => {
                match response.json::<SentinelIdentity>().await {
                    Ok(identity) => {
                        identity.issuer_id == self.issuer_id && identity.public_key == self.public_key
                    }
                    Err(_) => false,
                }
            }
            _ => false,
        }
    }

    pub(crate) async fn issue_lease(
        &self,
        actor_id: &str,
        session_id: Uuid,
        capabilities: &[String],
        resource_bounds: &[String],
        ttl_seconds: i64,
    ) -> Result<CapabilityLease, String> {
        let response = self
            .http
            .post(format!("{}/leases/issue", self.base_url))
            .bearer_auth(&self.token)
            .json(&IssueLeaseRequest {
                actor_id,
                session_id,
                capabilities,
                resource_bounds,
                ttl_seconds,
            })
            .send()
            .await
            .map_err(|error| format!("request Sentinel lease: {error}"))?;
        if response.status() != StatusCode::CREATED {
            let status = response.status();
            let detail = response.text().await.unwrap_or_default();
            return Err(format!("Sentinel refused lease ({status}): {detail}"));
        }
        let lease: CapabilityLease = response
            .json()
            .await
            .map_err(|error| format!("decode Sentinel lease: {error}"))?;
        self.verify_lease_identity(&lease, session_id)?;
        Ok(lease)
    }

    pub(crate) fn verify_lease_identity(
        &self,
        lease: &CapabilityLease,
        session_id: Uuid,
    ) -> Result<(), String> {
        if lease.issuer_id != self.issuer_id
            || lease.issuer_public_key.as_deref() != Some(self.public_key.as_str())
        {
            return Err("Sentinel lease issuer does not match pinned authority".into());
        }
        if !lease.binds_session(session_id) {
            return Err("Sentinel lease is not bound to this Shadow session".into());
        }
        lease.verify_signature()?;
        if !lease.is_valid() {
            return Err("Sentinel lease is expired or revoked".into());
        }
        Ok(())
    }

    pub(crate) async fn authorize(
        &self,
        lease: &CapabilityLease,
        manifest: &EffectManifest,
    ) -> Result<(), String> {
        self.verify_lease_identity(lease, manifest.task_id)?;
        let response = self
            .http
            .post(format!("{}/evaluate", self.base_url))
            .bearer_auth(&self.token)
            .json(&EvaluationRequest { manifest, lease })
            .send()
            .await
            .map_err(|error| format!("request Sentinel policy decision: {error}"))?;
        let status = response.status();
        let decision: PolicyDecision = response
            .json()
            .await
            .map_err(|error| format!("decode Sentinel policy decision: {error}"))?;
        if !status.is_success() || !decision.allowed {
            return Err(format!("Sentinel denied manifest: {}", decision.reason));
        }
        Ok(())
    }
}
