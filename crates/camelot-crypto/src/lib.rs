use chrono::{DateTime, Utc};
use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use rand::rngs::OsRng;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::collections::HashSet;

pub struct KeyPair {
    signing_key: SigningKey,
    verifying_key: VerifyingKey,
}

impl KeyPair {
    pub fn generate() -> Self {
        let mut csprng = OsRng;
        let signing_key = SigningKey::generate(&mut csprng);
        let verifying_key = signing_key.verifying_key();
        Self {
            signing_key,
            verifying_key,
        }
    }

    pub fn from_secret_bytes(bytes: [u8; 32]) -> Self {
        let signing_key = SigningKey::from_bytes(&bytes);
        let verifying_key = signing_key.verifying_key();
        Self {
            signing_key,
            verifying_key,
        }
    }

    pub fn from_secret_hex(value: &str) -> Result<Self, String> {
        let bytes = decode_hex_32(value)?;
        Ok(Self::from_secret_bytes(bytes))
    }

    pub fn secret_key_hex(&self) -> String {
        encode_hex(&self.signing_key.to_bytes())
    }

    pub fn sign(&self, message: &[u8]) -> Signature {
        self.signing_key.sign(message)
    }

    pub fn sign_hex(&self, message: &[u8]) -> String {
        encode_hex(&self.sign(message).to_bytes())
    }

    pub fn verify(
        &self,
        message: &[u8],
        signature: &Signature,
    ) -> Result<(), ed25519_dalek::SignatureError> {
        self.verifying_key.verify(message, signature)
    }

    pub fn public_key_hex(&self) -> String {
        encode_hex(&self.verifying_key.to_bytes())
    }
}

pub fn verify_detached_hex(
    public_key_hex: &str,
    message: &[u8],
    signature_hex: &str,
) -> Result<(), String> {
    let public_key = decode_hex_32(public_key_hex)?;
    let signature = decode_hex_64(signature_hex)?;
    let verifying_key = VerifyingKey::from_bytes(&public_key)
        .map_err(|error| format!("invalid Ed25519 public key: {error}"))?;
    let signature = Signature::from_bytes(&signature);
    verifying_key
        .verify(message, &signature)
        .map_err(|error| format!("Ed25519 signature verification failed: {error}"))
}

pub fn hash_payload(payload: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(payload);
    let result = hasher.finalize();
    format!("sha256:{:x}", result)
}


pub const KEY_RECORD_SCHEMA: &str = "camelot-key-record/1";
pub const KEY_AUTHORITY_SEMANTICS: &str = "key-metadata-not-authority";

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum SignerClass {
    Root,
    Policy,
    Epoch,
    Receipt,
    KnightRegistry,
    ContextCompiler,
    UkgRegistry,
    Release,
    Host,
    Adapter,
    Migration,
    Incident,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum KeyStatus {
    Active,
    Retiring,
    Revoked,
    Expired,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub struct KeyRecord {
    pub schema_version: String,
    pub authority_semantics: String,
    pub key_id: String,
    pub key_epoch: u64,
    pub signer_class: SignerClass,
    pub public_key: String,
    pub allowed_signature_domains: Vec<String>,
    pub not_before: DateTime<Utc>,
    pub expires_at: Option<DateTime<Utc>>,
    pub rotation_window_seconds: u64,
    pub status: KeyStatus,
    pub recovery_class: String,
}

impl KeyRecord {
    pub fn validate_shape(&self) -> Result<(), String> {
        if self.schema_version != KEY_RECORD_SCHEMA
            || self.authority_semantics != KEY_AUTHORITY_SEMANTICS
        {
            return Err("invalid key record schema or authority semantics".into());
        }
        if self.key_id.trim().is_empty() || self.key_id.len() > 160 || self.key_epoch == 0 {
            return Err("key id must contain 1..160 characters and key epoch must be positive".into());
        }
        decode_hex_32(&self.public_key)?;
        if self.allowed_signature_domains.is_empty() {
            return Err("key record requires at least one signature domain".into());
        }
        let mut domains = HashSet::new();
        for domain in &self.allowed_signature_domains {
            let domain = domain.trim();
            if domain.is_empty() || domain.len() > 160 {
                return Err("signature domains must contain 1..160 characters".into());
            }
            if !domains.insert(domain) {
                return Err("signature domains must be unique".into());
            }
        }
        if let Some(expires_at) = self.expires_at {
            if expires_at <= self.not_before {
                return Err("key expiry must be later than notBefore".into());
            }
        }
        if self.recovery_class.trim().is_empty() || self.recovery_class.len() > 160 {
            return Err("recovery class must contain 1..160 characters".into());
        }
        Ok(())
    }

    pub fn permits_verification(
        &self,
        expected_class: SignerClass,
        signature_domain: &str,
        observed_at: DateTime<Utc>,
    ) -> Result<(), String> {
        self.validate_shape()?;
        if self.signer_class != expected_class {
            return Err("signer class mismatch".into());
        }
        if !self
            .allowed_signature_domains
            .iter()
            .any(|domain| domain == signature_domain)
        {
            return Err("signature domain is not allowed for this key".into());
        }
        match self.status {
            KeyStatus::Revoked => return Err("key is revoked".into()),
            KeyStatus::Expired => return Err("key is marked expired".into()),
            KeyStatus::Active | KeyStatus::Retiring => {}
        }
        if observed_at < self.not_before {
            return Err("key is not active yet".into());
        }
        if self
            .expires_at
            .is_some_and(|expires_at| observed_at >= expires_at)
        {
            return Err("key has expired".into());
        }
        Ok(())
    }
}

pub fn verify_detached_hex_for_record(
    record: &KeyRecord,
    expected_class: SignerClass,
    signature_domain: &str,
    observed_at: DateTime<Utc>,
    message: &[u8],
    signature_hex: &str,
) -> Result<(), String> {
    record.permits_verification(expected_class, signature_domain, observed_at)?;
    verify_detached_hex(&record.public_key, message, signature_hex)
}

pub fn validate_key_rotation(previous: &KeyRecord, next: &KeyRecord) -> Result<(), String> {
    previous.validate_shape()?;
    next.validate_shape()?;
    if previous.key_id != next.key_id || previous.signer_class != next.signer_class {
        return Err("rotation must preserve key identity and signer class".into());
    }
    if next.key_epoch != previous.key_epoch.checked_add(1).ok_or("key epoch overflow")? {
        return Err("rotation must increment key epoch by exactly one".into());
    }
    if previous.public_key == next.public_key {
        return Err("rotation must change the public key".into());
    }
    if next.recovery_class != previous.recovery_class {
        return Err("rotation cannot silently change recovery class".into());
    }
    let previous_domains: HashSet<&str> = previous
        .allowed_signature_domains
        .iter()
        .map(String::as_str)
        .collect();
    if next
        .allowed_signature_domains
        .iter()
        .any(|domain| !previous_domains.contains(domain.as_str()))
    {
        return Err("rotation cannot widen signature domains".into());
    }
    Ok(())
}

fn encode_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        output.push(HEX[(byte >> 4) as usize] as char);
        output.push(HEX[(byte & 0x0f) as usize] as char);
    }
    output
}

fn decode_hex_32(value: &str) -> Result<[u8; 32], String> {
    let bytes = decode_hex(value)?;
    bytes
        .try_into()
        .map_err(|_| "expected 32-byte / 64-character hex value".to_string())
}

fn decode_hex_64(value: &str) -> Result<[u8; 64], String> {
    let bytes = decode_hex(value)?;
    bytes
        .try_into()
        .map_err(|_| "expected 64-byte / 128-character hex value".to_string())
}

fn decode_hex(value: &str) -> Result<Vec<u8>, String> {
    let value = value.trim();
    if !value.len().is_multiple_of(2) {
        return Err("hex value must have an even number of characters".into());
    }
    let mut output = Vec::with_capacity(value.len() / 2);
    let bytes = value.as_bytes();
    for index in (0..bytes.len()).step_by(2) {
        let hi = hex_nibble(bytes[index])?;
        let lo = hex_nibble(bytes[index + 1])?;
        output.push((hi << 4) | lo);
    }
    Ok(output)
}

fn hex_nibble(value: u8) -> Result<u8, String> {
    match value {
        b'0'..=b'9' => Ok(value - b'0'),
        b'a'..=b'f' => Ok(value - b'a' + 10),
        b'A'..=b'F' => Ok(value - b'A' + 10),
        _ => Err("invalid hexadecimal character".into()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn record(pair: &KeyPair, class: SignerClass) -> KeyRecord {
        let now = Utc::now();
        KeyRecord {
            schema_version: KEY_RECORD_SCHEMA.into(),
            authority_semantics: KEY_AUTHORITY_SEMANTICS.into(),
            key_id: "camelot.test.signer".into(),
            key_epoch: 1,
            signer_class: class,
            public_key: pair.public_key_hex(),
            allowed_signature_domains: vec!["camelot-signature:test/1".into()],
            not_before: now - chrono::Duration::seconds(1),
            expires_at: Some(now + chrono::Duration::hours(1)),
            rotation_window_seconds: 300,
            status: KeyStatus::Active,
            recovery_class: "operator-quorum".into(),
        }
    }

    #[test]
    fn persistent_key_round_trip_and_detached_verification() {
        let first = KeyPair::generate();
        let secret = first.secret_key_hex();
        let second = KeyPair::from_secret_hex(&secret).expect("reload key");
        assert_eq!(first.public_key_hex(), second.public_key_hex());

        let message = b"camelot-shadow-receipt";
        let signature_hex = second.sign_hex(message);
        verify_detached_hex(&second.public_key_hex(), message, &signature_hex)
            .expect("verify detached signature");
    }

    #[test]
    fn signer_class_and_domain_are_enforced_before_crypto_admission() {
        let pair = KeyPair::generate();
        let key = record(&pair, SignerClass::ContextCompiler);
        let message = b"bounded-spark";
        let signature = pair.sign_hex(message);

        verify_detached_hex_for_record(
            &key,
            SignerClass::ContextCompiler,
            "camelot-signature:test/1",
            Utc::now(),
            message,
            &signature,
        )
        .expect("matching signer class and domain");

        assert!(verify_detached_hex_for_record(
            &key,
            SignerClass::Epoch,
            "camelot-signature:test/1",
            Utc::now(),
            message,
            &signature,
        )
        .unwrap_err()
        .contains("signer class mismatch"));

        assert!(verify_detached_hex_for_record(
            &key,
            SignerClass::ContextCompiler,
            "camelot-signature:authority-epoch/1",
            Utc::now(),
            message,
            &signature,
        )
        .unwrap_err()
        .contains("signature domain"));
    }

    #[test]
    fn revoked_key_is_rejected_even_with_valid_signature() {
        let pair = KeyPair::generate();
        let mut key = record(&pair, SignerClass::Receipt);
        key.status = KeyStatus::Revoked;
        let message = b"receipt";
        let signature = pair.sign_hex(message);
        assert!(verify_detached_hex_for_record(
            &key,
            SignerClass::Receipt,
            "camelot-signature:test/1",
            Utc::now(),
            message,
            &signature,
        )
        .unwrap_err()
        .contains("revoked"));
    }

    #[test]
    fn rotation_increments_epoch_without_widening_domains() {
        let first_pair = KeyPair::generate();
        let second_pair = KeyPair::generate();
        let previous = record(&first_pair, SignerClass::Epoch);
        let mut next = record(&second_pair, SignerClass::Epoch);
        next.key_epoch = 2;
        validate_key_rotation(&previous, &next).expect("bounded rotation");

        next.allowed_signature_domains
            .push("camelot-signature:release/1".into());
        assert!(validate_key_rotation(&previous, &next)
            .unwrap_err()
            .contains("cannot widen"));
    }
}
