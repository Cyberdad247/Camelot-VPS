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

        match (&certificate_path, &pinned_public_key) {
            (Some(_), None) | (None, Some(_)) => {
                return Err(
                    "CAMELOT_EPOCH_CERTIFICATE_PATH and CAMELOT_EPOCH_PUBLIC_KEY must be configured together"
                        .into(),
                )
            }
            _ => {}
        }

        if let Some(key) = &pinned_public_key {
            if key.len() != 64 || !key.bytes().all(|value| value.is_ascii_hexdigit()) {
                return Err("CAMELOT_EPOCH_PUBLIC_KEY must be a 32-byte Ed25519 public key in hex".into());
            }
        }

        let static_epoch = env::var("CAMELOT_AUTHORITY_EPOCH")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(1);
        if static_epoch == 0 {
            return Err("CAMELOT_AUTHORITY_EPOCH must be greater than zero".into());
        }

        Ok(Self {
            certificate_path,
            pinned_public_key,
            static_epoch,
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

    #[test]
    fn static_source_is_fail_closed_on_zero() {
        assert!(EpochSource::static_epoch(0).is_err());
        assert_eq!(EpochSource::static_epoch(3).unwrap().current_epoch().unwrap(), 3);
    }
}
