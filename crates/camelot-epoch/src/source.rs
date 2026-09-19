use crate::AuthorityEpochCertificate;
use std::{env, fs, path::PathBuf};

#[derive(Debug, Clone)]
pub struct EpochSource {
    certificate_path: Option<PathBuf>,
    pinned_public_key: Option<String>,
    static_epoch: u64,
}

impl EpochSource {
    pub fn from_environment() -> Result<Self, String> {
        let certificate_path = env::var("CAMELOT_EPOCH_CERTIFICATE_PATH")
            .ok()
            .filter(|value| !value.trim().is_empty())
            .map(PathBuf::from);
        let pinned_public_key = env::var("CAMELOT_EPOCH_PUBLIC_KEY")
            .ok()
            .map(|value| value.trim().to_string())
            .filter(|value| !value.is_empty());
        let static_epoch = env::var("CAMELOT_AUTHORITY_EPOCH")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(1);

        match (certificate_path, pinned_public_key) {
            (Some(path), Some(key)) => Self::dynamic(path, key, static_epoch),
            (Some(_), None) | (None, Some(_)) => Err(
                "CAMELOT_EPOCH_CERTIFICATE_PATH and CAMELOT_EPOCH_PUBLIC_KEY must be configured together"
                    .into(),
            ),
            (None, None) => Self::static_epoch(static_epoch),
        }
    }

    pub fn dynamic(
        certificate_path: PathBuf,
        pinned_public_key: String,
        fallback_epoch: u64,
    ) -> Result<Self, String> {
        if fallback_epoch == 0 {
            return Err("authority epoch must be positive".into());
        }
        if pinned_public_key.len() != 64
            || !pinned_public_key
                .bytes()
                .all(|value| value.is_ascii_hexdigit())
        {
            return Err(
                "CAMELOT_EPOCH_PUBLIC_KEY must be a 32-byte Ed25519 public key in hex".into(),
            );
        }
        Ok(Self {
            certificate_path: Some(certificate_path),
            pinned_public_key: Some(pinned_public_key),
            static_epoch: fallback_epoch,
        })
    }

    pub fn static_epoch(epoch: u64) -> Result<Self, String> {
        if epoch == 0 {
            return Err("authority epoch must be positive".into());
        }
        Ok(Self {
            certificate_path: None,
            pinned_public_key: None,
            static_epoch: epoch,
        })
    }

    pub fn is_dynamic(&self) -> bool {
        self.certificate_path.is_some()
    }

    pub fn current_certificate(&self) -> Result<Option<AuthorityEpochCertificate>, String> {
        let Some(path) = &self.certificate_path else {
            return Ok(None);
        };
        let pinned = self
            .pinned_public_key
            .as_deref()
            .ok_or_else(|| "dynamic epoch source is missing its pinned public key".to_string())?;
        let raw = fs::read_to_string(path)
            .map_err(|error| format!("read authority epoch certificate: {error}"))?;
        let certificate: AuthorityEpochCertificate = serde_json::from_str(&raw)
            .map_err(|error| format!("decode authority epoch certificate: {error}"))?;
        certificate.verify_with_pinned_key(pinned)?;
        Ok(Some(certificate))
    }

    pub fn current_epoch(&self) -> Result<u64, String> {
        Ok(self
            .current_certificate()?
            .map(|certificate| certificate.epoch)
            .unwrap_or(self.static_epoch))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{BrainId, PromotionMode};
    use camelot_crypto::KeyPair;

    fn digest(ch: char) -> String {
        format!("sha256:{}", ch.to_string().repeat(64))
    }

    #[test]
    fn static_source_is_fail_closed_on_zero() {
        assert!(EpochSource::static_epoch(0).is_err());
        assert_eq!(EpochSource::static_epoch(3).unwrap().current_epoch().unwrap(), 3);
    }

    #[test]
    fn dynamic_source_observes_certificate_rotation_without_restart() {
        let signer = KeyPair::generate();
        let path = std::env::temp_dir().join(format!(
            "camelot-epoch-source-{}.json",
            uuid::Uuid::new_v4()
        ));

        let first = AuthorityEpochCertificate::bootstrap(
            7,
            BrainId::OpenNotebook,
            41,
            digest('a'),
            "bootstrap".into(),
            &signer,
        )
        .unwrap();
        fs::write(&path, serde_json::to_vec(&first).unwrap()).unwrap();

        let source =
            EpochSource::dynamic(path.clone(), signer.public_key_hex(), 1).unwrap();
        assert_eq!(source.current_epoch().unwrap(), 7);

        let next = AuthorityEpochCertificate::promoted(
            &first,
            BrainId::Notebooklm,
            PromotionMode::Planned,
            42,
            digest('b'),
            "planned handoff".into(),
            &signer,
        )
        .unwrap();
        fs::write(&path, serde_json::to_vec(&next).unwrap()).unwrap();

        assert_eq!(source.current_epoch().unwrap(), 8);
        let _ = fs::remove_file(path);
    }
}
