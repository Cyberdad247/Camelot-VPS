use camelot_epoch::AuthorityEpochCertificate;
use std::{fs, io::Write, path::Path};
use uuid::Uuid;

pub fn publish_certificate(
    path: &Path,
    certificate: &AuthorityEpochCertificate,
) -> Result<(), String> {
    let parent = path
        .parent()
        .ok_or_else(|| "epoch certificate path requires a parent directory".to_string())?;
    fs::create_dir_all(parent).map_err(|error| error.to_string())?;
    let temporary = parent.join(format!(".epoch-{}.tmp", Uuid::new_v4()));
    let payload = serde_json::to_vec_pretty(certificate).map_err(|error| error.to_string())?;
    let mut file = fs::OpenOptions::new()
        .create_new(true)
        .write(true)
        .open(&temporary)
        .map_err(|error| error.to_string())?;
    file.write_all(&payload)
        .map_err(|error| error.to_string())?;
    file.write_all(b"\n").map_err(|error| error.to_string())?;
    file.sync_all().map_err(|error| error.to_string())?;
    fs::rename(&temporary, path).map_err(|error| error.to_string())?;
    Ok(())
}
