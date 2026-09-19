use base64::{engine::general_purpose::STANDARD, Engine as _};
use camelot_crypto::verify_detached_hex;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    collections::HashSet,
    env, fs,
    path::{Path, PathBuf},
};
use unicode_normalization::UnicodeNormalization;

pub const SOUL_SCHEMA: &str = "camelot-soul/1";
pub const ENTERPRISE_ROLE_SCHEMA: &str = "camelot-enterprise-role/1";
pub const PERSONA_SCHEMA: &str = "camelot-persona/1";
pub const KNIGHT_PACKAGE_SCHEMA: &str = "camelot-knight-package/1";
pub const CANONICALIZATION_PROFILE: &str = "camelot-c14n-json/1";

const REQUIRED_PERSONA_PROHIBITIONS: &[&str] = &[
    "policy_decision",
    "lease_issuance",
    "direct_main_branch_write",
    "secret_handling",
    "unrestricted_network_access",
    "auto_merge",
    "auto_deploy",
    "promotion_issue",
    "epoch_increment",
];

const REQUIRED_PACKAGE_PROHIBITIONS: &[&str] =
    &["policy_decision", "lease_issuance", "epoch_increment"];

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct IntegrityEnvelope {
    pub canonicalization: String,
    pub digest_algorithm: String,
    pub digest: String,
    pub signature_algorithm: String,
    pub signature_domain: String,
    pub signer_key_id: String,
    pub signature: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CommunicationProfile {
    pub voice: String,
    pub interaction_style: String,
    #[serde(default)]
    pub language: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Soul {
    pub schema_version: String,
    pub object_id: String,
    pub tenant_id: String,
    pub workspace_id: String,
    pub issuer_id: String,
    pub issued_at: String,
    pub not_before: String,
    pub expires_at: String,
    pub lifecycle: String,
    pub derived_from: Vec<String>,
    pub integrity: IntegrityEnvelope,
    pub canonical_name: String,
    pub persona_class: String,
    pub purpose: String,
    pub enterprise_mandate: Vec<String>,
    pub worldview: Vec<String>,
    pub communication_profile: CommunicationProfile,
    pub constitutional_limits: Vec<String>,
    pub authority_semantics: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct EnterpriseRole {
    pub schema_version: String,
    pub object_id: String,
    pub tenant_id: String,
    pub workspace_id: String,
    pub issuer_id: String,
    pub issued_at: String,
    pub not_before: String,
    pub expires_at: String,
    pub lifecycle: String,
    pub derived_from: Vec<String>,
    pub integrity: IntegrityEnvelope,
    pub persona_id: String,
    pub soul_ref: String,
    pub department: String,
    pub responsibilities: Vec<String>,
    pub delegates_to: Vec<String>,
    pub collaborates_with: Vec<String>,
    pub escalation_targets: Vec<String>,
    pub shared_context_scopes: Vec<String>,
    pub authority_semantics: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PersonaIdentity {
    pub title: String,
    pub function: String,
    #[serde(default)]
    pub tone: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct CompetenceMap {
    pub primary: Vec<String>,
    pub secondary: Vec<String>,
    pub prohibited: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct PersonaBudget {
    #[serde(default)]
    pub identity_tokens_max: Option<u64>,
    #[serde(default)]
    pub skills_tokens_max: Option<u64>,
    #[serde(default)]
    pub constraints_tokens_max: Option<u64>,
    #[serde(default)]
    pub examples_tokens_max: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct RuntimeResourceProfile {
    #[serde(default)]
    pub cpu_quota: Option<String>,
    #[serde(default)]
    pub disk_quota_mb: Option<u64>,
    #[serde(default)]
    pub ephemeral_fds_max: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Persona {
    pub schema_version: String,
    pub persona_id: String,
    pub version: String,
    pub class: String,
    pub identity: PersonaIdentity,
    pub competence_map: CompetenceMap,
    pub input_contract: Vec<String>,
    pub output_contract: Vec<String>,
    pub budget: PersonaBudget,
    #[serde(default)]
    pub runtime_resource_profile: Option<RuntimeResourceProfile>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct KnightPackage {
    pub schema_version: String,
    pub object_id: String,
    pub package_id: String,
    pub tenant_id: String,
    pub workspace_id: String,
    pub issuer_id: String,
    pub issued_at: String,
    pub not_before: String,
    pub expires_at: String,
    pub lifecycle: String,
    pub persona_id: String,
    pub persona_class: String,
    pub soul_ref: String,
    pub soul_digest: String,
    pub persona_digest: String,
    pub enterprise_role_ref: String,
    pub enterprise_role_digest: String,
    pub allowed_runes: Vec<String>,
    pub allowed_pills: Vec<String>,
    pub allowed_effect_classes: Vec<String>,
    pub max_risk_tier: String,
    pub max_cognition_ceiling: String,
    pub prohibited_capabilities: Vec<String>,
    pub authority_semantics: String,
    pub integrity: IntegrityEnvelope,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct KnightBundleFile {
    package: Value,
    soul: Value,
    persona: Value,
    enterprise_role: Value,
}

#[derive(Debug, Clone)]
pub struct LoadedKnight {
    pub package_id: String,
    pub package_digest: String,
    pub persona_id: String,
    pub persona_class: String,
    pub tenant_id: String,
    pub workspace_id: String,
    pub max_risk_tier: String,
    pub max_cognition_ceiling: String,
    pub allowed_effect_classes: Vec<String>,
    pub allowed_runes: Vec<String>,
    pub allowed_pills: Vec<String>,
    pub prohibited_capabilities: Vec<String>,
}

impl LoadedKnight {
    pub fn prohibits(&self, capability: &str) -> bool {
        self.prohibited_capabilities
            .iter()
            .any(|value| value == capability)
    }
}

#[derive(Debug, Clone)]
pub struct KnightRegistry {
    root: PathBuf,
    pinned_public_key: String,
    expected_tenant_id: String,
    expected_workspace_id: String,
    max_risk_tier: String,
    max_cognition_ceiling: String,
    revoked_ids: HashSet<String>,
}

impl KnightRegistry {
    pub fn from_environment() -> Result<Option<Self>, String> {
        let root = env::var("CAMELOT_KNIGHT_REGISTRY_DIR")
            .ok()
            .map(|value| value.trim().to_string())
            .filter(|value| !value.is_empty());
        let public_key = env::var("CAMELOT_KNIGHT_PUBLIC_KEY")
            .ok()
            .map(|value| value.trim().to_string())
            .filter(|value| !value.is_empty());

        match (root, public_key) {
            (None, None) => Ok(None),
            (Some(_), None) | (None, Some(_)) => Err(
                "CAMELOT_KNIGHT_REGISTRY_DIR and CAMELOT_KNIGHT_PUBLIC_KEY must be configured together"
                    .into(),
            ),
            (Some(root), Some(public_key)) => {
                let tenant = env::var("CAMELOT_KNIGHT_TENANT_SCOPE")
                    .map_err(|_| "CAMELOT_KNIGHT_TENANT_SCOPE is required when Knight registry is enabled")?;
                let workspace = env::var("CAMELOT_KNIGHT_WORKSPACE_SCOPE")
                    .map_err(|_| "CAMELOT_KNIGHT_WORKSPACE_SCOPE is required when Knight registry is enabled")?;
                let max_risk = env::var("CAMELOT_KNIGHT_MAX_RISK_TIER")
                    .unwrap_or_else(|_| "T1".into());
                let max_cognition = env::var("CAMELOT_KNIGHT_MAX_COGNITION_CEILING")
                    .unwrap_or_else(|_| "L1".into());
                let revoked_ids = env::var("CAMELOT_KNIGHT_REVOKED_IDS")
                    .unwrap_or_default()
                    .split(',')
                    .map(str::trim)
                    .filter(|value| !value.is_empty())
                    .map(ToOwned::to_owned)
                    .collect();
                Self::new(
                    PathBuf::from(root),
                    public_key,
                    tenant.trim().to_string(),
                    workspace.trim().to_string(),
                    max_risk,
                    max_cognition,
                    revoked_ids,
                )
                .map(Some)
            }
        }
    }

    #[allow(clippy::too_many_arguments)]
    pub fn new(
        root: PathBuf,
        pinned_public_key: String,
        expected_tenant_id: String,
        expected_workspace_id: String,
        max_risk_tier: String,
        max_cognition_ceiling: String,
        revoked_ids: HashSet<String>,
    ) -> Result<Self, String> {
        if pinned_public_key.len() != 64
            || !pinned_public_key
                .bytes()
                .all(|value| value.is_ascii_hexdigit())
        {
            return Err("Knight registry public key must be 32-byte Ed25519 hex".into());
        }
        if expected_tenant_id.trim().is_empty() || expected_workspace_id.trim().is_empty() {
            return Err("Knight registry tenant/workspace scopes must be non-empty".into());
        }
        risk_rank(&max_risk_tier)?;
        cognition_rank(&max_cognition_ceiling)?;
        if !root.is_dir() {
            return Err(format!(
                "Knight registry directory does not exist: {}",
                root.display()
            ));
        }
        Ok(Self {
            root,
            pinned_public_key,
            expected_tenant_id,
            expected_workspace_id,
            max_risk_tier,
            max_cognition_ceiling,
            revoked_ids,
        })
    }

    pub fn load_for_actor(
        &self,
        actor_id: &str,
        package_id: &str,
    ) -> Result<LoadedKnight, String> {
        let persona_id = actor_id
            .strip_prefix("knight:")
            .ok_or_else(|| "Knight package may bind only to actor ids prefixed knight:".to_string())?;
        if persona_id.is_empty() {
            return Err("Knight actor id is missing persona id".into());
        }
        let loaded = self.load(package_id)?;
        if loaded.persona_id != persona_id {
            return Err("Knight actor/persona identity mismatch".into());
        }
        Ok(loaded)
    }

    pub fn load(&self, package_id: &str) -> Result<LoadedKnight, String> {
        validate_package_id(package_id)?;
        if self.revoked_ids.contains(package_id) {
            return Err("Knight package is locally revoked".into());
        }
        let path = self.root.join(format!("{package_id}.bundle.json"));
        let raw = fs::read_to_string(&path)
            .map_err(|error| format!("read Knight bundle {}: {error}", path.display()))?;
        let bundle: KnightBundleFile = serde_json::from_str(&raw)
            .map_err(|error| format!("decode Knight bundle: {error}"))?;
        self.verify_bundle(package_id, bundle, Utc::now())
    }

    fn verify_bundle(
        &self,
        requested_package_id: &str,
        bundle: KnightBundleFile,
        now: DateTime<Utc>,
    ) -> Result<LoadedKnight, String> {
        verify_signed_contract(&bundle.package, KNIGHT_PACKAGE_SCHEMA, &self.pinned_public_key)?;
        verify_signed_contract(&bundle.soul, SOUL_SCHEMA, &self.pinned_public_key)?;
        verify_signed_contract(
            &bundle.enterprise_role,
            ENTERPRISE_ROLE_SCHEMA,
            &self.pinned_public_key,
        )?;

        let package: KnightPackage = serde_json::from_value(bundle.package.clone())
            .map_err(|error| format!("decode Knight package contract: {error}"))?;
        let soul: Soul = serde_json::from_value(bundle.soul.clone())
            .map_err(|error| format!("decode Soul contract: {error}"))?;
        let persona: Persona = serde_json::from_value(bundle.persona.clone())
            .map_err(|error| format!("decode persona contract: {error}"))?;
        let role: EnterpriseRole = serde_json::from_value(bundle.enterprise_role.clone())
            .map_err(|error| format!("decode enterprise role contract: {error}"))?;

        if package.schema_version != KNIGHT_PACKAGE_SCHEMA
            || soul.schema_version != SOUL_SCHEMA
            || role.schema_version != ENTERPRISE_ROLE_SCHEMA
            || persona.schema_version != PERSONA_SCHEMA
        {
            return Err("unsupported Knight bundle schema version".into());
        }
        if package.package_id != requested_package_id {
            return Err("Knight bundle package id does not match requested id".into());
        }
        for (object_id, lifecycle) in [
            (package.object_id.as_str(), package.lifecycle.as_str()),
            (soul.object_id.as_str(), soul.lifecycle.as_str()),
            (role.object_id.as_str(), role.lifecycle.as_str()),
        ] {
            if lifecycle != "ACTIVE" {
                return Err(format!("Knight bundle component {object_id} is not ACTIVE"));
            }
            if self.revoked_ids.contains(object_id) {
                return Err(format!("Knight bundle component {object_id} is locally revoked"));
            }
        }

        validate_time_window(&package.not_before, &package.expires_at, now)?;
        validate_time_window(&soul.not_before, &soul.expires_at, now)?;
        validate_time_window(&role.not_before, &role.expires_at, now)?;

        for (tenant, workspace) in [
            (&package.tenant_id, &package.workspace_id),
            (&soul.tenant_id, &soul.workspace_id),
            (&role.tenant_id, &role.workspace_id),
        ] {
            if tenant != &self.expected_tenant_id || workspace != &self.expected_workspace_id {
                return Err("Knight bundle component scope mismatch".into());
            }
        }

        if package.issuer_id != soul.issuer_id || package.issuer_id != role.issuer_id {
            return Err("Knight bundle issuer mismatch".into());
        }
        if package.authority_semantics != "package-not-authority"
            || soul.authority_semantics != "identity-not-authority"
            || role.authority_semantics != "organization-not-authority"
        {
            return Err("Knight bundle attempts to widen authority semantics".into());
        }
        if package.soul_ref != soul.object_id || role.soul_ref != soul.object_id {
            return Err("Knight bundle Soul reference mismatch".into());
        }
        if package.enterprise_role_ref != role.object_id {
            return Err("Knight bundle enterprise role reference mismatch".into());
        }
        if package.soul_digest != full_object_digest(&bundle.soul)?
            || package.persona_digest != full_object_digest(&bundle.persona)?
            || package.enterprise_role_digest != full_object_digest(&bundle.enterprise_role)?
        {
            return Err("Knight bundle immutable component digest mismatch".into());
        }
        if package.persona_id != persona.persona_id || package.persona_id != role.persona_id {
            return Err("Knight bundle persona identity mismatch".into());
        }
        if package.persona_class != persona.class || package.persona_class != soul.persona_class {
            return Err("Knight bundle persona class mismatch".into());
        }

        for required in REQUIRED_PERSONA_PROHIBITIONS {
            if !persona
                .competence_map
                .prohibited
                .iter()
                .any(|value| value == required)
            {
                return Err(format!(
                    "persona is missing mandatory authority prohibition: {required}"
                ));
            }
        }
        for required in REQUIRED_PACKAGE_PROHIBITIONS {
            if !package
                .prohibited_capabilities
                .iter()
                .any(|value| value == required)
            {
                return Err(format!(
                    "Knight package weakens authority prohibition: {required}"
                ));
            }
        }
        if risk_rank(&package.max_risk_tier)? > risk_rank(&self.max_risk_tier)? {
            return Err("Knight package exceeds registry risk ceiling".into());
        }
        if cognition_rank(&package.max_cognition_ceiling)?
            > cognition_rank(&self.max_cognition_ceiling)?
        {
            return Err("Knight package exceeds registry cognition ceiling".into());
        }

        Ok(LoadedKnight {
            package_id: package.package_id,
            package_digest: full_object_digest(&bundle.package)?,
            persona_id: package.persona_id,
            persona_class: package.persona_class,
            tenant_id: package.tenant_id,
            workspace_id: package.workspace_id,
            max_risk_tier: package.max_risk_tier,
            max_cognition_ceiling: package.max_cognition_ceiling,
            allowed_effect_classes: package.allowed_effect_classes,
            allowed_runes: package.allowed_runes,
            allowed_pills: package.allowed_pills,
            prohibited_capabilities: package.prohibited_capabilities,
        })
    }
}

pub fn is_knight_actor(actor_id: &str) -> bool {
    actor_id.starts_with("knight:")
}

fn validate_package_id(value: &str) -> Result<(), String> {
    if !value.starts_with("knightpkg_")
        || value.len() > 128
        || !value
            .bytes()
            .all(|byte| byte.is_ascii_alphanumeric() || matches!(byte, b'_' | b'-'))
    {
        return Err("invalid Knight package id".into());
    }
    Ok(())
}

fn validate_time_window(not_before: &str, expires_at: &str, now: DateTime<Utc>) -> Result<(), String> {
    let start = DateTime::parse_from_rfc3339(not_before)
        .map_err(|error| format!("invalid not_before timestamp: {error}"))?
        .with_timezone(&Utc);
    let end = DateTime::parse_from_rfc3339(expires_at)
        .map_err(|error| format!("invalid expires_at timestamp: {error}"))?
        .with_timezone(&Utc);
    if now < start {
        return Err("Knight bundle component is not yet valid".into());
    }
    if now >= end {
        return Err("Knight bundle component is expired".into());
    }
    Ok(())
}

fn risk_rank(value: &str) -> Result<u8, String> {
    match value {
        "T0" => Ok(0),
        "T1" => Ok(1),
        "T2" => Ok(2),
        "T3" => Ok(3),
        "T4" => Ok(4),
        _ => Err(format!("unknown risk tier: {value}")),
    }
}

fn cognition_rank(value: &str) -> Result<u8, String> {
    match value {
        "L0" => Ok(0),
        "L1" => Ok(1),
        "L2" => Ok(2),
        "L3" => Ok(3),
        "L4" => Ok(4),
        "L5" => Ok(5),
        _ => Err(format!("unknown cognition ceiling: {value}")),
    }
}

fn verify_signed_contract(
    value: &Value,
    expected_schema: &str,
    pinned_public_key: &str,
) -> Result<(), String> {
    let schema = value
        .get("schema_version")
        .and_then(Value::as_str)
        .ok_or_else(|| "signed contract is missing schema_version".to_string())?;
    if schema != expected_schema {
        return Err(format!("unexpected signed contract schema: {schema}"));
    }

    let integrity_value = value
        .get("integrity")
        .cloned()
        .ok_or_else(|| "signed contract is missing integrity envelope".to_string())?;
    let integrity: IntegrityEnvelope = serde_json::from_value(integrity_value)
        .map_err(|error| format!("decode integrity envelope: {error}"))?;

    let expected_domain = format!("camelot-signature:{expected_schema}");
    if integrity.canonicalization != CANONICALIZATION_PROFILE
        || integrity.digest_algorithm != "sha256"
        || integrity.signature_algorithm != "ed25519"
        || integrity.signature_domain != expected_domain
        || integrity.signer_key_id.trim().is_empty()
    {
        return Err("invalid signed contract integrity profile".into());
    }

    let mut projection = value.clone();
    projection
        .as_object_mut()
        .ok_or_else(|| "signed contract must be a JSON object".to_string())?
        .remove("integrity");
    let bytes = canonical_json_bytes(&projection)?;
    let digest_bytes = Sha256::digest(&bytes);
    let digest = format!("sha256:{digest_bytes:x}");
    if integrity.digest != digest {
        return Err("signed contract digest mismatch".into());
    }

    let mut signature_input = expected_domain.into_bytes();
    signature_input.push(0);
    signature_input.extend_from_slice(&digest_bytes);
    let signature_bytes = STANDARD
        .decode(integrity.signature.as_bytes())
        .map_err(|error| format!("decode Ed25519 signature: {error}"))?;
    if signature_bytes.len() != 64 {
        return Err("Ed25519 signature must be 64 bytes".into());
    }
    let signature_hex = hex_encode(&signature_bytes);
    verify_detached_hex(pinned_public_key, &signature_input, &signature_hex)
}

fn full_object_digest(value: &Value) -> Result<String, String> {
    let bytes = canonical_json_bytes(value)?;
    Ok(format!("sha256:{:x}", Sha256::digest(&bytes)))
}

fn canonical_json_bytes(value: &Value) -> Result<Vec<u8>, String> {
    let mut output = String::new();
    write_canonical(value, &mut output)?;
    Ok(output.into_bytes())
}

fn write_canonical(value: &Value, output: &mut String) -> Result<(), String> {
    match value {
        Value::Null => output.push_str("null"),
        Value::Bool(value) => output.push_str(if *value { "true" } else { "false" }),
        Value::Number(value) => {
            if !value.is_i64() && !value.is_u64() {
                return Err("camelot-c14n-json/1 forbids floating-point values".into());
            }
            output.push_str(&value.to_string());
        }
        Value::String(value) => {
            let normalized: String = value.nfc().collect();
            output.push_str(
                &serde_json::to_string(&normalized)
                    .map_err(|error| format!("canonicalize JSON string: {error}"))?,
            );
        }
        Value::Array(values) => {
            output.push('[');
            for (index, item) in values.iter().enumerate() {
                if index > 0 {
                    output.push(',');
                }
                write_canonical(item, output)?;
            }
            output.push(']');
        }
        Value::Object(values) => {
            let mut entries: Vec<(String, &Value)> = values
                .iter()
                .map(|(key, value)| (key.nfc().collect::<String>(), value))
                .collect();
            entries.sort_by(|left, right| left.0.cmp(&right.0));
            for pair in entries.windows(2) {
                if pair[0].0 == pair[1].0 {
                    return Err("canonical JSON contains duplicate keys after NFC normalization".into());
                }
            }
            output.push('{');
            for (index, (key, item)) in entries.iter().enumerate() {
                if index > 0 {
                    output.push(',');
                }
                output.push_str(
                    &serde_json::to_string(key)
                        .map_err(|error| format!("canonicalize JSON key: {error}"))?,
                );
                output.push(':');
                write_canonical(item, output)?;
            }
            output.push('}');
        }
    }
    Ok(())
}

fn hex_encode(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        output.push(HEX[(byte >> 4) as usize] as char);
        output.push(HEX[(byte & 0x0f) as usize] as char);
    }
    output
}

#[cfg(test)]
mod tests {
    use super::*;
    use camelot_crypto::KeyPair;
    use chrono::Duration;
    use serde_json::json;

    fn sign_contract(mut value: Value, signer: &KeyPair, signer_id: &str) -> Value {
        let schema = value["schema_version"].as_str().unwrap().to_string();
        let projection = value.clone();
        let bytes = canonical_json_bytes(&projection).unwrap();
        let digest_bytes = Sha256::digest(&bytes);
        let digest = format!("sha256:{digest_bytes:x}");
        let domain = format!("camelot-signature:{schema}");
        let mut signature_input = domain.as_bytes().to_vec();
        signature_input.push(0);
        signature_input.extend_from_slice(&digest_bytes);
        let signature = signer.sign(&signature_input).to_bytes();
        value["integrity"] = json!({
            "canonicalization": CANONICALIZATION_PROFILE,
            "digest_algorithm": "sha256",
            "digest": digest,
            "signature_algorithm": "ed25519",
            "signature_domain": domain,
            "signer_key_id": signer_id,
            "signature": STANDARD.encode(signature),
        });
        value
    }

    fn build_bundle(signer: &KeyPair) -> Value {
        let now = Utc::now();
        let not_before = (now - Duration::minutes(2)).to_rfc3339();
        let expires_at = (now + Duration::hours(1)).to_rfc3339();

        let soul = sign_contract(
            json!({
                "schema_version": SOUL_SCHEMA,
                "object_id": "soul.sir-synthetos.v1",
                "tenant_id": "tenant_primary",
                "workspace_id": "ws_camelot",
                "issuer_id": "camelot://knight-registry",
                "issued_at": not_before,
                "not_before": not_before,
                "expires_at": expires_at,
                "lifecycle": "ACTIVE",
                "derived_from": [],
                "canonical_name": "Sir Synthetos",
                "persona_class": "research_synthesist",
                "purpose": "Source-isolated synthesis.",
                "enterprise_mandate": ["source synthesis"],
                "worldview": ["evidence-before-assertion"],
                "communication_profile": {
                    "voice": "analytical",
                    "interaction_style": "source-grounded synthesis",
                    "language": "en"
                },
                "constitutional_limits": [
                    "no policy decisions",
                    "no lease issuance",
                    "no epoch promotion"
                ],
                "authority_semantics": "identity-not-authority"
            }),
            signer,
            "test-knight-registry-key",
        );

        let role = sign_contract(
            json!({
                "schema_version": ENTERPRISE_ROLE_SCHEMA,
                "object_id": "role.sir-synthetos.v1",
                "tenant_id": "tenant_primary",
                "workspace_id": "ws_camelot",
                "issuer_id": "camelot://knight-registry",
                "issued_at": not_before,
                "not_before": not_before,
                "expires_at": expires_at,
                "lifecycle": "ACTIVE",
                "derived_from": [],
                "persona_id": "sir_synthetos",
                "soul_ref": "soul.sir-synthetos.v1",
                "department": "Research & Synthesis",
                "responsibilities": ["source synthesis"],
                "delegates_to": [],
                "collaborates_with": ["anya", "merlin", "gideon"],
                "escalation_targets": ["anya", "gideon"],
                "shared_context_scopes": ["ukg://research/*"],
                "authority_semantics": "organization-not-authority"
            }),
            signer,
            "test-knight-registry-key",
        );

        let persona = json!({
            "schema_version": PERSONA_SCHEMA,
            "persona_id": "sir_synthetos",
            "version": "1.0.0",
            "class": "research_synthesist",
            "identity": {
                "title": "Sir Synthetos",
                "function": "Source-isolated synthesis",
                "tone": "analytical"
            },
            "competence_map": {
                "primary": ["source_synthesis"],
                "secondary": ["implementation_drafting"],
                "prohibited": [
                    "policy_decision",
                    "lease_issuance",
                    "direct_main_branch_write",
                    "secret_handling",
                    "unrestricted_network_access",
                    "auto_merge",
                    "auto_deploy",
                    "promotion_issue",
                    "epoch_increment"
                ]
            },
            "input_contract": ["scoped_sources"],
            "output_contract": ["synthesis_draft"],
            "budget": {
                "identity_tokens_max": 1200,
                "skills_tokens_max": 6000,
                "constraints_tokens_max": 1600,
                "examples_tokens_max": 1200
            },
            "runtime_resource_profile": {
                "cpu_quota": "40%",
                "disk_quota_mb": 128,
                "ephemeral_fds_max": 32
            }
        });

        let package = sign_contract(
            json!({
                "schema_version": KNIGHT_PACKAGE_SCHEMA,
                "object_id": "knightpkg.sir-synthetos.v1",
                "package_id": "knightpkg_sir_synthetos_v1",
                "tenant_id": "tenant_primary",
                "workspace_id": "ws_camelot",
                "issuer_id": "camelot://knight-registry",
                "issued_at": not_before,
                "not_before": not_before,
                "expires_at": expires_at,
                "lifecycle": "ACTIVE",
                "persona_id": "sir_synthetos",
                "persona_class": "research_synthesist",
                "soul_ref": "soul.sir-synthetos.v1",
                "soul_digest": full_object_digest(&soul).unwrap(),
                "persona_digest": full_object_digest(&persona).unwrap(),
                "enterprise_role_ref": "role.sir-synthetos.v1",
                "enterprise_role_digest": full_object_digest(&role).unwrap(),
                "allowed_runes": ["rune://omega-synthesize/1"],
                "allowed_pills": ["pill://synthesis-phial/1"],
                "allowed_effect_classes": ["ro.fetch", "ro.audit", "internal.synth"],
                "max_risk_tier": "T1",
                "max_cognition_ceiling": "L1",
                "prohibited_capabilities": [
                    "policy_decision",
                    "lease_issuance",
                    "epoch_increment",
                    "direct_main_branch_write",
                    "unrestricted_network_access"
                ],
                "authority_semantics": "package-not-authority"
            }),
            signer,
            "test-knight-registry-key",
        );

        json!({
            "package": package,
            "soul": soul,
            "persona": persona,
            "enterprise_role": role
        })
    }

    fn registry(root: &Path, signer: &KeyPair) -> KnightRegistry {
        KnightRegistry::new(
            root.to_path_buf(),
            signer.public_key_hex(),
            "tenant_primary".into(),
            "ws_camelot".into(),
            "T1".into(),
            "L1".into(),
            HashSet::new(),
        )
        .unwrap()
    }

    #[test]
    fn signed_bundle_loads_and_binds_to_knight_actor() {
        let signer = KeyPair::generate();
        let root = std::env::temp_dir().join(format!(
            "camelot-knight-test-{}",
            &signer.public_key_hex()[..12]
        ));
        fs::create_dir_all(&root).unwrap();
        let bundle = build_bundle(&signer);
        fs::write(
            root.join("knightpkg_sir_synthetos_v1.bundle.json"),
            serde_json::to_vec(&bundle).unwrap(),
        )
        .unwrap();

        let loaded = registry(&root, &signer)
            .load_for_actor(
                "knight:sir_synthetos",
                "knightpkg_sir_synthetos_v1",
            )
            .unwrap();
        assert_eq!(loaded.persona_id, "sir_synthetos");
        assert_eq!(loaded.max_risk_tier, "T1");
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn soul_mutation_breaks_bundle_signature_or_digest_binding() {
        let signer = KeyPair::generate();
        let root = std::env::temp_dir().join(format!(
            "camelot-knight-tamper-{}",
            &signer.public_key_hex()[..12]
        ));
        fs::create_dir_all(&root).unwrap();
        let mut bundle = build_bundle(&signer);
        bundle["soul"]["purpose"] = Value::String("tampered purpose".into());
        fs::write(
            root.join("knightpkg_sir_synthetos_v1.bundle.json"),
            serde_json::to_vec(&bundle).unwrap(),
        )
        .unwrap();

        let error = registry(&root, &signer)
            .load("knightpkg_sir_synthetos_v1")
            .unwrap_err();
        assert!(
            error.contains("digest") || error.contains("signature"),
            "{error}"
        );
        let _ = fs::remove_dir_all(root);
    }

    #[test]
    fn actor_identity_and_policy_ceiling_fail_closed() {
        let signer = KeyPair::generate();
        let root = std::env::temp_dir().join(format!(
            "camelot-knight-scope-{}",
            &signer.public_key_hex()[..12]
        ));
        fs::create_dir_all(&root).unwrap();
        let bundle = build_bundle(&signer);
        fs::write(
            root.join("knightpkg_sir_synthetos_v1.bundle.json"),
            serde_json::to_vec(&bundle).unwrap(),
        )
        .unwrap();

        assert!(registry(&root, &signer)
            .load_for_actor("knight:someone_else", "knightpkg_sir_synthetos_v1")
            .is_err());

        let strict = KnightRegistry::new(
            root.clone(),
            signer.public_key_hex(),
            "tenant_primary".into(),
            "ws_camelot".into(),
            "T0".into(),
            "L0".into(),
            HashSet::new(),
        )
        .unwrap();
        assert!(strict.load("knightpkg_sir_synthetos_v1").is_err());
        let _ = fs::remove_dir_all(root);
    }
}
