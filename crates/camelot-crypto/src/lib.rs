use ed25519_dalek::{Signature, Signer, SigningKey, Verifier, VerifyingKey};
use rand::rngs::OsRng;
use sha2::{Digest, Sha256};

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
}
