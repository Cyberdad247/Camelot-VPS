use base64::{engine::general_purpose::STANDARD as BASE64, Engine as _};
use camelot_crypto::KeyPair;
use chrono::{DateTime, Duration, Utc};
use ed25519_dalek::{Signature, Verifier, VerifyingKey};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{
    collections::{HashMap, HashSet},
    fs,
    path::Path,
};
use unicode_normalization::UnicodeNormalization;
use uuid::Uuid;

pub const SOUL_SCHEMA: &str = "camelot-soul/1";
pub const ENTERPRISE_ROLE_SCHEMA: &str = "camelot-enterprise-role/1";
pub const PERSONA_SCHEMA: &str = "camelot-persona/1";
pub const KNIGHT_PACKAGE_SCHEMA: &str = "camelot-knight-package/1";
pub const SPARK_SCHEMA: &str = "camelot-spark/1";

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
pub struct Integrity {
    pub canonicalization: String,
    pub digest_algorithm: String,
    pub digest: String,
    pub signature_algorithm: String,
    pub signature_domain: String,
    pub signer_key_id: String,
    pub signature: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommonSigned {
    pub schema_version: String,
    pub object_id: String,
    pub tenant_id: String,
    pub workspace_id: String,
    pub issuer_id: String,
    pub issued_at: DateTime<Utc>,
    pub not_before: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
    pub lifecycle: String,
    #[serde(default)]
    pub derived_from: Vec<String>,
    pub integrity: Integrity,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CommunicationProfile {
    pub voice: String,
    pub interaction_style: String,
    #[serde(default = "default_language")]
    pub language: String,
}

fn default_language() -> String {
    "en".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Soul {
    #[serde(flatten)]
    pub common: CommonSigned,
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
pub struct EnterpriseRole {
    #[serde(flatten)]
    pub common: CommonSigned,
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
pub struct PersonaIdentity {
    pub title: String,
    pub function: String,
    #[serde(default)]
    pub tone: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CompetenceMap {
    pub primary: Vec<String>,
    pub secondary: Vec<String>,
    pub prohibited: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PersonaBudget {
    #[serde(default)]
    pub identity_tokens_max: u64,
    #[serde(default)]
    pub skills_tokens_max: u64,
    #[serde(default)]
    pub constraints_tokens_max: u64,
    #[serde(default)]
    pub examples_tokens_max: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PersonaProfile {
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
    pub runtime_resource_profile: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct KnightPackage {
    pub schema_version: String,
    pub object_id: String,
    pub package_id: String,
    pub tenant_id: String,
    pub workspace_id: String,
    pub issuer_id: String,
    pub issued_at: DateTime<Utc>,
    pub not_before: DateTime<Utc>,
    pub expires_at: DateTime<Utc>,
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
    pub integrity: Integrity,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ContextSource {
    pub r#ref: String,
    pub trust_class: String,
    #[serde(default)]
    pub digest: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SparkCompileRequest {
    pub quest_ref: String,
    pub task_ref: String,
    #[serde(default)]
    pub context_sources: Vec<ContextSource>,
    pub total_tokens: u64,
    #[serde(default)]
    pub scratch_reserve_tokens: u64,
    #[serde(default)]
    pub requested_runes: Vec<String>,
    #[serde(default)]
    pub requested_pills: Vec<String>,
    #[serde(default = "default_ttl")]
    pub ttl_seconds: i64,
}

fn default_ttl() -> i64 {
    900
}

#[derive(Debug, Clone, Serialize)]
pub struct LoadedKnight {
    pub package_id: String,
    pub persona_id: String,
    pub persona_class: String,
    pub canonical_name: String,
    pub department: String,
    pub tenant_id: String,
    pub workspace_id: String,
    pub soul_ref: String,
    pub max_risk_tier: String,
    pub max_cognition_ceiling: String,
    pub allowed_effect_classes: Vec<String>,
    pub allowed_runes: Vec<String>,
    pub allowed_pills: Vec<String>,
    pub communication_profile: CommunicationProfile,
    pub authority: bool,
}

#[derive(Debug, Clone)]
pub struct KnightPolicy {
    pub expected_tenant_id: String,
    pub expected_workspace_id: String,
    pub max_risk_tier: String,
    pub max_cognition_ceiling: String,
    pub allowed_effect_classes: HashSet<String>,
    pub revoked_ids: HashSet<String>,
}

#[derive(Debug, Clone, Default)]
pub struct Keyring {
    keys: HashMap<String, String>,
}

impl Keyring {
    pub fn insert_hex(&mut self, key_id: impl Into<String>, public_key_hex: impl Into<String>) {
        self.keys.insert(key_id.into(), public_key_hex.into());
    }

    fn get(&self, key_id: &str) -> Option<&str> {
        self.keys.get(key_id).map(String::as_str)
    }
}

fn decode_hex_32(value: &str) -> Result<[u8; 32], String> {
    let value = value.trim();
    if value.len() != 64 || !value.bytes().all(|b| b.is_ascii_hexdigit()) {
        return Err("expected a 32-byte Ed25519 public key in hex".into());
    }
    let mut out = [0_u8; 32];
    for (index, chunk) in value.as_bytes().chunks_exact(2).enumerate() {
        let text = std::str::from_utf8(chunk).map_err(|_| "invalid public key hex")?;
        out[index] = u8::from_str_radix(text, 16).map_err(|_| "invalid public key hex")?;
    }
    Ok(out)
}

fn canonical_string(value: &Value) -> Result<String, String> {
    fn write_value(value: &Value, out: &mut String) -> Result<(), String> {
        match value {
            Value::Null => out.push_str("null"),
            Value::Bool(value) => out.push_str(if *value { "true" } else { "false" }),
            Value::Number(number) => {
                if number.is_f64() {
                    return Err("camelot-c14n-json/1 forbids floating-point values".into());
                }
                out.push_str(&number.to_string());
            }
            Value::String(value) => {
                let normalized: String = value.nfc().collect();
                out.push_str(
                    &serde_json::to_string(&normalized)
                        .map_err(|error| format!("encode canonical string: {error}"))?,
                );
            }
            Value::Array(items) => {
                out.push('[');
                for (index, item) in items.iter().enumerate() {
                    if index > 0 {
                        out.push(',');
                    }
                    write_value(item, out)?;
                }
                out.push(']');
            }
            Value::Object(map) => {
                let mut entries = Vec::with_capacity(map.len());
                let mut seen = HashSet::new();
                for (key, value) in map {
                    let normalized_key: String = key.nfc().collect();
                    if !seen.insert(normalized_key.clone()) {
                        return Err("duplicate object key after Unicode NFC normalization".into());
                    }
                    entries.push((normalized_key, value));
                }
                entries.sort_by(|left, right| left.0.cmp(&right.0));                out.push('{');
                for (index, (key, value)) in entries.iter().enumerate() {
                    if index > 0 {
                        out.push(',');
                    }
                    out.push_str(
                        &serde_json::to_string(key)
                            .map_err(|error| format!("encode canonical key: {error}"))?,
                    );
                    out.push(':');
                    write_value(value, out)?;
                }
                out.push('}');
            }
        }
        Ok(())
    }

    let mut out = String::new();
    write_value(value, &mut out)?;
    Ok(out)
}

pub fn canonical_bytes(value: &Value) -> Result<Vec<u8>, String> {
    Ok(canonical_string(value)?.into_bytes())
}

pub fn signing_projection(value: &Value) -> Result<Value, String> {
    let mut projected = value.clone();
    let object = projected
        .as_object_mut()
        .ok_or_else(|| "signed Camelot object must be a JSON object".to_string())?;
    object.remove("integrity");
    Ok(projected)
}

pub fn content_digest(value: &Value) -> Result<String, String> {
    let projection = signing_projection(value)?;
    let digest = Sha256::digest(canonical_bytes(&projection)?);
    Ok(format!("sha256:{digest:x}"))
}

pub fn full_object_digest(value: &Value) -> Result<String, String> {
    let digest = Sha256::digest(canonical_bytes(value)?);
    Ok(format!("sha256:{digest:x}"))
}

pub fn verify_signed_value(
    value: &Value,
    expected_schema: &str,
    keyring: &Keyring,
) -> Result<(), String> {
    let object = value
        .as_object()
        .ok_or_else(|| "signed Camelot object must be a JSON object".to_string())?;
    let schema = object
        .get("schema_version")
        .and_then(Value::as_str)
        .ok_or_else(|| "signed Camelot object is missing schema_version".to_string())?;
    if schema != expected_schema {
        return Err(format!(
            "schema mismatch: expected {expected_schema}, got {schema}"
        ));
    }
    let integrity: Integrity = serde_json::from_value(
        object
            .get("integrity")
            .cloned()
            .ok_or_else(|| "signed Camelot object is missing integrity".to_string())?,
    )
    .map_err(|error| format!("decode integrity: {error}"))?;

    if integrity.canonicalization != "camelot-c14n-json/1"
        || integrity.digest_algorithm != "sha256"
        || integrity.signature_algorithm != "ed25519"
    {
        return Err("unsupported Camelot integrity profile".into());
    }

    let expected_domain = format!("camelot-signature:{schema}");
    if integrity.signature_domain != expected_domain {
        return Err("signature domain mismatch".into());
    }

    let observed_digest = content_digest(value)?;
    if integrity.digest != observed_digest {
        return Err("content digest mismatch".into());
    }

    let public_key_hex = keyring
        .get(&integrity.signer_key_id)
        .ok_or_else(|| "untrusted signer key id".to_string())?;
    let public_key = decode_hex_32(public_key_hex)?;
    let verifying_key = VerifyingKey::from_bytes(&public_key)
        .map_err(|error| format!("invalid Ed25519 public key: {error}"))?;
    let signature_bytes = BASE64
        .decode(integrity.signature.as_bytes())
        .map_err(|_| "invalid Base64 signature".to_string())?;
    let signature_array: [u8; 64] = signature_bytes
        .try_into()
        .map_err(|_| "Ed25519 signature must be 64 bytes".to_string())?;
    let signature = Signature::from_bytes(&signature_array);

    let digest_bytes = hex::decode(
        observed_digest
            .strip_prefix("sha256:")
            .ok_or_else(|| "invalid digest prefix".to_string())?,
    )
    .map_err(|_| "invalid digest hex".to_string())?;
    let mut message = expected_domain.into_bytes();
    message.push(0);
    message.extend_from_slice(&digest_bytes);

    verifying_key
        .verify(&message, &signature)
        .map_err(|error| format!("Ed25519 signature verification failed: {error}"))
}

fn validate_signed_common(common: &CommonSigned, now: DateTime<Utc>) -> Result<(), String> {
    if common.lifecycle != "ACTIVE" {
        return Err(format!("object {} is not ACTIVE", common.object_id));
    }
    if now < common.not_before || now >= common.expires_at {
        return Err(format!(
            "object {} is outside its validity window",
            common.object_id
        ));
    }
    Ok(())
}

fn validate_package_time(package: &KnightPackage, now: DateTime<Utc>) -> Result<(), String> {
    if package.lifecycle != "ACTIVE" {
        return Err(format!(
            "Knight package {} is not ACTIVE",
            package.package_id
        ));
    }
    if now < package.not_before || now >= package.expires_at {
        return Err(format!(
            "Knight package {} is outside its validity window",
            package.package_id
        ));
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
        _ => Err("unknown risk tier".into()),
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
        _ => Err("unknown cognition ceiling".into()),
    }
}

pub fn load_knight_bundle(
    soul_value: &Value,
    persona_value: &Value,
    role_value: &Value,
    package_value: &Value,
    keyring: &Keyring,
    policy: &KnightPolicy,
    now: DateTime<Utc>,
) -> Result<LoadedKnight, String> {
    verify_signed_value(soul_value, SOUL_SCHEMA, keyring)?;
    verify_signed_value(role_value, ENTERPRISE_ROLE_SCHEMA, keyring)?;
    verify_signed_value(package_value, KNIGHT_PACKAGE_SCHEMA, keyring)?;

    let soul: Soul = serde_json::from_value(soul_value.clone())
        .map_err(|error| format!("decode Soul: {error}"))?;
    let persona: PersonaProfile = serde_json::from_value(persona_value.clone())
        .map_err(|error| format!("decode persona: {error}"))?;
    let role: EnterpriseRole = serde_json::from_value(role_value.clone())
        .map_err(|error| format!("decode Enterprise Role: {error}"))?;
    let package: KnightPackage = serde_json::from_value(package_value.clone())
        .map_err(|error| format!("decode Knight package: {error}"))?;

    validate_signed_common(&soul.common, now)?;
    validate_signed_common(&role.common, now)?;
    validate_package_time(&package, now)?;

    if persona.schema_version != PERSONA_SCHEMA {
        return Err("unsupported persona schema".into());
    }
    if soul.common.tenant_id != policy.expected_tenant_id
        || role.common.tenant_id != policy.expected_tenant_id
        || package.tenant_id != policy.expected_tenant_id
    {
        return Err("Knight bundle tenant scope mismatch".into());
    }
    if soul.common.workspace_id != policy.expected_workspace_id
        || role.common.workspace_id != policy.expected_workspace_id
        || package.workspace_id != policy.expected_workspace_id
    {
        return Err("Knight bundle workspace scope mismatch".into());
    }

    for id in [
        soul.common.object_id.as_str(),
        role.common.object_id.as_str(),
        package.object_id.as_str(),
        package.package_id.as_str(),
    ] {
        if policy.revoked_ids.contains(id) {
            return Err(format!("revoked Knight bundle object: {id}"));
        }
    }

    if soul.authority_semantics != "identity-not-authority"
        || role.authority_semantics != "organization-not-authority"
        || package.authority_semantics != "package-not-authority"
    {
        return Err("Knight bundle attempts to change authority semantics".into());
    }

    if package.soul_ref != soul.common.object_id || role.soul_ref != soul.common.object_id {
        return Err("Soul reference mismatch".into());
    }
    if package.enterprise_role_ref != role.common.object_id {
        return Err("Enterprise Role reference mismatch".into());
    }

    if package.soul_digest != full_object_digest(soul_value)? {
        return Err("immutable Soul digest mismatch".into());
    }
    if package.persona_digest != full_object_digest(persona_value)? {
        return Err("persona digest mismatch".into());
    }
    if package.enterprise_role_digest != full_object_digest(role_value)? {
        return Err("Enterprise Role digest mismatch".into());
    }

    if package.persona_id != persona.persona_id
        || package.persona_id != role.persona_id
        || package.persona_class != persona.class
        || package.persona_class != soul.persona_class
    {
        return Err("persona identity/class mismatch".into());
    }

    let persona_prohibited: HashSet<&str> = persona
        .competence_map
        .prohibited
        .iter()
        .map(String::as_str)
        .collect();
    if REQUIRED_PERSONA_PROHIBITIONS
        .iter()
        .any(|item| !persona_prohibited.contains(item))
    {
        return Err("persona profile is missing mandatory authority prohibitions".into());
    }

    let package_prohibited: HashSet<&str> = package
        .prohibited_capabilities
        .iter()
        .map(String::as_str)
        .collect();
    if REQUIRED_PACKAGE_PROHIBITIONS
        .iter()
        .any(|item| !package_prohibited.contains(item))
    {
        return Err("Knight package weakens mandatory authority prohibitions".into());
    }

    if risk_rank(&package.max_risk_tier)? > risk_rank(&policy.max_risk_tier)? {
        return Err("Knight package exceeds policy risk ceiling".into());
    }
    if cognition_rank(&package.max_cognition_ceiling)?
        > cognition_rank(&policy.max_cognition_ceiling)?
    {
        return Err("Knight package exceeds policy cognition ceiling".into());
    }

    for effect in &package.allowed_effect_classes {
        if !policy.allowed_effect_classes.contains(effect) {
            return Err(format!("effect class outside policy allowlist: {effect}"));
        }
    }

    Ok(LoadedKnight {
        package_id: package.package_id,
        persona_id: package.persona_id,
        persona_class: package.persona_class,
        canonical_name: soul.canonical_name,
        department: role.department,
        tenant_id: package.tenant_id,
        workspace_id: package.workspace_id,
        soul_ref: soul.common.object_id,
        max_risk_tier: package.max_risk_tier,
        max_cognition_ceiling: package.max_cognition_ceiling,
        allowed_effect_classes: package.allowed_effect_classes,
        allowed_runes: package.allowed_runes,
        allowed_pills: package.allowed_pills,
        communication_profile: soul.communication_profile,
        authority: false,
    })
}
pub fn load_bundle_dir(
    path: &Path,
    keyring: &Keyring,
    policy: &KnightPolicy,
    now: DateTime<Utc>,
) -> Result<LoadedKnight, String> {
    let read = |name: &str| -> Result<Value, String> {
        let raw =
            fs::read_to_string(path.join(name)).map_err(|error| format!("read {name}: {error}"))?;
        serde_json::from_str(&raw).map_err(|error| format!("decode {name}: {error}"))
    };

    load_knight_bundle(
        &read("soul.json")?,
        &read("persona.json")?,
        &read("enterprise-role.json")?,
        &read("knight-package.json")?,
        keyring,
        policy,
        now,
    )
}

pub fn sign_v3_value(
    mut value: Value,
    signer: &KeyPair,
    signer_key_id: &str,
) -> Result<Value, String> {
    let schema = value
        .get("schema_version")
        .and_then(Value::as_str)
        .ok_or_else(|| "object is missing schema_version".to_string())?
        .to_string();
    let object = value
        .as_object_mut()
        .ok_or_else(|| "object to sign must be a JSON object".to_string())?;
    object.remove("integrity");

    let digest = content_digest(&value)?;
    let digest_hex = digest
        .strip_prefix("sha256:")
        .ok_or_else(|| "invalid digest prefix".to_string())?;
    let digest_bytes = hex::decode(digest_hex).map_err(|_| "invalid digest hex")?;
    let domain = format!("camelot-signature:{schema}");
    let mut message = domain.as_bytes().to_vec();
    message.push(0);
    message.extend_from_slice(&digest_bytes);
    let signature = signer.sign(&message);

    value
        .as_object_mut()
        .expect("value already validated as object")
        .insert(
            "integrity".into(),
            json!({
                "canonicalization": "camelot-c14n-json/1",
                "digest_algorithm": "sha256",
                "digest": digest,
                "signature_algorithm": "ed25519",
                "signature_domain": domain,
                "signer_key_id": signer_key_id,
                "signature": BASE64.encode(signature.to_bytes())
            }),
        );
    Ok(value)
}

fn validate_context_source(source: &ContextSource) -> Result<(), String> {
    const TRUST: &[&str] = &[
        "TRUSTED_CANONICAL",
        "VERIFIED_EXTERNAL",
        "SIGNED_UKG",
        "USER_SUPPLIED",
        "AGENT_GENERATED",
        "UNTRUSTED_EXTERNAL",
        "QUARANTINED",
    ];
    if source.r#ref.trim().is_empty() || !TRUST.contains(&source.trust_class.as_str()) {
        return Err("invalid context source".into());
    }
    if let Some(digest) = &source.digest {
        if !digest.starts_with("sha256:")
            || digest.len() != 71
            || !digest[7..].bytes().all(|byte| byte.is_ascii_hexdigit())
        {
            return Err("invalid context source digest".into());
        }
    }
    Ok(())
}

pub fn compile_signed_spark(
    knight: &LoadedKnight,
    request: SparkCompileRequest,
    signer: &KeyPair,
    signer_key_id: &str,
    now: DateTime<Utc>,
) -> Result<Value, String> {
    if request.quest_ref.trim().is_empty() || request.task_ref.trim().is_empty() {
        return Err("quest_ref and task_ref are required".into());
    }
    if !(30..=1800).contains(&request.ttl_seconds) {
        return Err("Spark ttl_seconds must be between 30 and 1800".into());
    }
    if request.total_tokens == 0 || request.total_tokens > 65_536 {
        return Err("Spark total_tokens must be between 1 and 65536".into());
    }
    if request.scratch_reserve_tokens > request.total_tokens {
        return Err("Spark scratch reserve cannot exceed total token budget".into());
    }
    for source in &request.context_sources {
        validate_context_source(source)?;
    }

    let allowed_runes: HashSet<&str> = knight.allowed_runes.iter().map(String::as_str).collect();
    if request
        .requested_runes
        .iter()
        .any(|rune| !allowed_runes.contains(rune.as_str()))
    {
        return Err("requested Rune is outside the Knight package".into());
    }

    let allowed_pills: HashSet<&str> = knight.allowed_pills.iter().map(String::as_str).collect();
    if request
        .requested_pills
        .iter()
        .any(|pill| !allowed_pills.contains(pill.as_str()))
    {
        return Err("requested Pill is outside the Knight package".into());
    }

    let object_id = format!("spark.{}.{}", knight.persona_id, Uuid::new_v4().simple());
    let expires = now + Duration::seconds(request.ttl_seconds);
    let value = json!({
        "schema_version": SPARK_SCHEMA,
        "object_id": object_id,
        "tenant_id": knight.tenant_id,
        "workspace_id": knight.workspace_id,
        "issuer_id": "camelot-context-compiler",
        "issued_at": now,
        "not_before": now,
        "expires_at": expires,
        "lifecycle": "ACTIVE",
        "derived_from": [
            format!("knight-package://{}", knight.package_id),
            format!("soul://{}", knight.soul_ref)
        ],
        "persona_id": knight.persona_id,
        "soul_ref": knight.soul_ref,
        "quest_ref": request.quest_ref,
        "task_ref": request.task_ref,
        "context_sources": request.context_sources,
        "token_budget": {
            "total_tokens": request.total_tokens,
            "scratch_reserve_tokens": request.scratch_reserve_tokens
        },
        "allowed_runes": request.requested_runes,
        "allowed_pills": request.requested_pills,
        "cognition_ceiling": knight.max_cognition_ceiling,
        "authority_semantics": "context-not-authority"
    });
    sign_v3_value(value, signer, signer_key_id)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixed_now() -> DateTime<Utc> {
        "2026-09-19T20:00:00Z".parse().unwrap()
    }

    fn base_signed(schema: &str, object_id: &str) -> Value {
        json!({
            "schema_version": schema,
            "object_id": object_id,
            "tenant_id": "tenant_primary",
            "workspace_id": "ws_camelot",
            "issuer_id": "camelot://knight-registry",
            "issued_at": "2026-09-19T19:00:00Z",
            "not_before": "2026-09-19T19:00:00Z",
            "expires_at": "2026-09-20T19:00:00Z",
            "lifecycle": "ACTIVE",
            "derived_from": []
        })
    }

    fn fixture() -> (KeyPair, Keyring, KnightPolicy, Value, Value, Value, Value) {
        let registry = KeyPair::from_secret_bytes([7_u8; 32]);
        let mut keyring = Keyring::default();
        keyring.insert_hex("registry/test-1", registry.public_key_hex());

        let mut soul = base_signed(SOUL_SCHEMA, "soul.sir-synthetos.v1");
        soul.as_object_mut().unwrap().extend(
            serde_json::from_value::<serde_json::Map<String, Value>>(json!({
                "canonical_name": "Sir Synthetos",
                "persona_class": "research_synthesist",
                "purpose": "Source-isolated synthesis.",
                "enterprise_mandate": ["source synthesis", "conflict analysis"],
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
            }))
            .unwrap(),
        );
        soul = sign_v3_value(soul, &registry, "registry/test-1").unwrap();

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
                "primary": ["source_synthesis", "citation_lineage"],
                "secondary": ["implementation_drafting"],
                "prohibited": REQUIRED_PERSONA_PROHIBITIONS
            },
            "input_contract": ["scoped_sources"],
            "output_contract": ["synthesis_draft", "citation_lineage"],
            "budget": {
                "identity_tokens_max": 1200,
                "skills_tokens_max": 6000,
                "constraints_tokens_max": 1600,
                "examples_tokens_max": 1200
            }
        });

        let mut role = base_signed(ENTERPRISE_ROLE_SCHEMA, "role.sir-synthetos.v1");
        role.as_object_mut().unwrap().extend(
            serde_json::from_value::<serde_json::Map<String, Value>>(json!({
                "persona_id": "sir_synthetos",
                "soul_ref": "soul.sir-synthetos.v1",
                "department": "Research & Synthesis",
                "responsibilities": ["source synthesis", "citation lineage"],
                "delegates_to": [],
                "collaborates_with": ["anya", "merlin", "gideon"],
                "escalation_targets": ["anya", "gideon"],
                "shared_context_scopes": ["ukg://research/*"],
                "authority_semantics": "organization-not-authority"
            }))
            .unwrap(),
        );
        role = sign_v3_value(role, &registry, "registry/test-1").unwrap();

        let mut package = json!({
            "schema_version": KNIGHT_PACKAGE_SCHEMA,
            "object_id": "knightpkg.sir-synthetos.v1",
            "package_id": "knightpkg_sir_synthetos_v1",
            "tenant_id": "tenant_primary",
            "workspace_id": "ws_camelot",
            "issuer_id": "camelot://knight-registry",
            "issued_at": "2026-09-19T19:00:00Z",
            "not_before": "2026-09-19T19:00:00Z",
            "expires_at": "2026-09-20T19:00:00Z",
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
        });
        package = sign_v3_value(package, &registry, "registry/test-1").unwrap();

        let policy = KnightPolicy {
            expected_tenant_id: "tenant_primary".into(),
            expected_workspace_id: "ws_camelot".into(),
            max_risk_tier: "T1".into(),
            max_cognition_ceiling: "L1".into(),
            allowed_effect_classes: ["ro.fetch", "ro.audit", "internal.synth"]
                .into_iter()
                .map(str::to_string)
                .collect(),
            revoked_ids: HashSet::new(),
        };

        (registry, keyring, policy, soul, persona, role, package)
    }

    #[test]
    fn loads_synthetos_and_compiles_non_authority_spark() {
        let (_, keyring, policy, soul, persona, role, package) = fixture();
        let loaded = load_knight_bundle(
            &soul,
            &persona,
            &role,
            &package,
            &keyring,
            &policy,
            fixed_now(),
        )
        .unwrap();
        assert_eq!(loaded.persona_id, "sir_synthetos");
        assert!(!loaded.authority);

        let spark_signer = KeyPair::from_secret_bytes([9_u8; 32]);
        let spark = compile_signed_spark(
            &loaded,
            SparkCompileRequest {
                quest_ref: "quest://synthesis/1".into(),
                task_ref: "task://synthesis/1".into(),
                context_sources: vec![ContextSource {
                    r#ref: "ukg://research/camelot".into(),
                    trust_class: "SIGNED_UKG".into(),
                    digest: None,
                }],
                total_tokens: 16_000,
                scratch_reserve_tokens: 2_000,
                requested_runes: vec!["rune://omega-synthesize/1".into()],
                requested_pills: vec!["pill://synthesis-phial/1".into()],
                ttl_seconds: 600,
            },
            &spark_signer,
            "context/test-1",
            fixed_now(),
        )
        .unwrap();
        assert_eq!(spark["authority_semantics"], "context-not-authority");
        assert_eq!(spark["cognition_ceiling"], "L1");
    }

    #[test]
    fn soul_mutation_breaks_package_binding() {
        let (_, keyring, policy, mut soul, persona, role, package) = fixture();
        soul["purpose"] = json!("mutated");
        assert!(load_knight_bundle(
            &soul,
            &persona,
            &role,
            &package,
            &keyring,
            &policy,
            fixed_now()
        )
        .is_err());
    }

    #[test]
    fn requested_rune_cannot_exceed_package() {
        let (_, keyring, policy, soul, persona, role, package) = fixture();
        let loaded = load_knight_bundle(
            &soul,
            &persona,
            &role,
            &package,
            &keyring,
            &policy,
            fixed_now(),
        )
        .unwrap();
        let signer = KeyPair::from_secret_bytes([11_u8; 32]);
        let result = compile_signed_spark(
            &loaded,
            SparkCompileRequest {
                quest_ref: "quest://1".into(),
                task_ref: "task://1".into(),
                context_sources: vec![],
                total_tokens: 1_000,
                scratch_reserve_tokens: 100,
                requested_runes: vec!["rune://forbidden/1".into()],
                requested_pills: vec![],
                ttl_seconds: 300,
            },
            &signer,
            "context/test-1",
            fixed_now(),
        );
        assert!(result.is_err());
    }
}