use camelot_crypto::KeyPair;
use camelot_receipts::{is_sha256_reference, Receipt, ReceiptDraft};
use sqlx::{
    sqlite::{SqliteConnectOptions, SqlitePoolOptions},
    Row, SqlitePool,
};
use std::{str::FromStr, sync::Arc};
use uuid::Uuid;

#[derive(Clone)]
pub struct LedgerStore {
    pool: SqlitePool,
    signer: Arc<KeyPair>,
    authority_epoch: u64,
}

impl LedgerStore {
    pub async fn open(
        database_url: &str,
        signer: KeyPair,
        authority_epoch: u64,
    ) -> Result<Self, String> {
        let options = SqliteConnectOptions::from_str(database_url)
            .map_err(|error| format!("parse receipt database URL: {error}"))?
            .create_if_missing(true);
        let pool = SqlitePoolOptions::new()
            .max_connections(4)
            .connect_with(options)
            .await
            .map_err(|error| format!("open receipt database: {error}"))?;
        for statement in [
            "PRAGMA journal_mode=WAL",
            "PRAGMA synchronous=FULL",
            "PRAGMA foreign_keys=ON",
            "PRAGMA busy_timeout=5000",
        ] {
            sqlx::query(statement)
                .execute(&pool)
                .await
                .map_err(|error| format!("configure receipt database: {error}"))?;
        }
        sqlx::query(
            "CREATE TABLE IF NOT EXISTS receipts (
                sequence INTEGER PRIMARY KEY,
                receipt_id TEXT NOT NULL UNIQUE,
                receipt_hash TEXT NOT NULL UNIQUE,
                receipt_json TEXT NOT NULL
            )",
        )
        .execute(&pool)
        .await
        .map_err(|error| format!("create receipts table: {error}"))?;
        sqlx::query(
            "CREATE TABLE IF NOT EXISTS ledger_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                next_sequence INTEGER NOT NULL,
                head_hash TEXT
            )",
        )
        .execute(&pool)
        .await
        .map_err(|error| format!("create ledger_meta: {error}"))?;
        sqlx::query(
            "INSERT OR IGNORE INTO ledger_meta (id, next_sequence, head_hash)
             VALUES (1, 0, NULL)",
        )
        .execute(&pool)
        .await
        .map_err(|error| format!("initialize ledger_meta: {error}"))?;

        let store = Self {
            pool,
            signer: Arc::new(signer),
            authority_epoch,
        };
        store.verify_chain().await?;
        Ok(store)
    }

    pub fn signer_public_key(&self) -> String {
        self.signer.public_key_hex()
    }

    pub fn authority_epoch(&self) -> u64 {
        self.authority_epoch
    }

    pub async fn ready(&self) -> bool {
        sqlx::query("SELECT 1").execute(&self.pool).await.is_ok()
    }

    pub async fn append(&self, draft: ReceiptDraft) -> Result<Receipt, String> {
        validate_draft(&draft, self.authority_epoch)?;
        let mut tx = self
            .pool
            .begin()
            .await
            .map_err(|error| format!("begin receipt transaction: {error}"))?;
        let row = sqlx::query("SELECT next_sequence, head_hash FROM ledger_meta WHERE id = 1")
            .fetch_one(&mut *tx)
            .await
            .map_err(|error| format!("load ledger head: {error}"))?;
        let sequence: i64 = row
            .try_get("next_sequence")
            .map_err(|error| format!("decode ledger sequence: {error}"))?;
        let parent: Option<String> = row
            .try_get("head_hash")
            .map_err(|error| format!("decode ledger head: {error}"))?;

        let mut receipt =
            Receipt::new_unsigned(draft, sequence as u64, parent, self.signer.public_key_hex());
        receipt.sign_with(&self.signer)?;
        receipt.verify_integrity()?;
        let encoded = serde_json::to_string(&receipt)
            .map_err(|error| format!("serialize receipt: {error}"))?;

        sqlx::query(
            "INSERT INTO receipts (sequence, receipt_id, receipt_hash, receipt_json)
             VALUES (?, ?, ?, ?)",
        )
        .bind(sequence)
        .bind(receipt.receipt_id.to_string())
        .bind(&receipt.receipt_hash)
        .bind(encoded)
        .execute(&mut *tx)
        .await
        .map_err(|error| format!("insert receipt: {error}"))?;
        let update = sqlx::query(
            "UPDATE ledger_meta SET next_sequence = next_sequence + 1, head_hash = ?
             WHERE id = 1 AND next_sequence = ?",
        )
        .bind(&receipt.receipt_hash)
        .bind(sequence)
        .execute(&mut *tx)
        .await
        .map_err(|error| format!("advance ledger head: {error}"))?;
        if update.rows_affected() != 1 {
            return Err("receipt sequence conflict; retry append".into());
        }
        tx.commit()
            .await
            .map_err(|error| format!("commit receipt: {error}"))?;
        Ok(receipt)
    }

    pub async fn get(&self, id: Uuid) -> Result<Option<Receipt>, String> {
        let row = sqlx::query("SELECT receipt_json FROM receipts WHERE receipt_id = ?")
            .bind(id.to_string())
            .fetch_optional(&self.pool)
            .await
            .map_err(|error| format!("read receipt: {error}"))?;
        row.map(|row| {
            let raw: String = row
                .try_get("receipt_json")
                .map_err(|error| format!("decode receipt row: {error}"))?;
            serde_json::from_str(&raw).map_err(|error| format!("decode receipt JSON: {error}"))
        })
        .transpose()
    }

    pub async fn list(&self, after: i64, limit: i64) -> Result<Vec<Receipt>, String> {
        let rows = sqlx::query(
            "SELECT receipt_json FROM receipts WHERE sequence > ? ORDER BY sequence ASC LIMIT ?",
        )
        .bind(after)
        .bind(limit.clamp(1, 500))
        .fetch_all(&self.pool)
        .await
        .map_err(|error| format!("list receipts: {error}"))?;
        decode_receipts(rows)
    }

    async fn all_receipts(&self) -> Result<Vec<Receipt>, String> {
        let rows = sqlx::query("SELECT receipt_json FROM receipts ORDER BY sequence ASC")
            .fetch_all(&self.pool)
            .await
            .map_err(|error| format!("read full receipt chain: {error}"))?;
        decode_receipts(rows)
    }

    pub async fn verify_chain(&self) -> Result<(), String> {
        let receipts = self.all_receipts().await?;
        let mut expected_sequence = 0_u64;
        let mut expected_parent: Option<String> = None;
        for receipt in receipts {
            if receipt.sequence != expected_sequence {
                return Err(format!(
                    "receipt sequence discontinuity: expected {expected_sequence}, got {}",
                    receipt.sequence
                ));
            }
            if receipt.parent_receipt_hash != expected_parent {
                return Err(format!(
                    "receipt parent mismatch at sequence {}",
                    receipt.sequence
                ));
            }
            receipt.verify_integrity()?;
            expected_parent = Some(receipt.receipt_hash.clone());
            expected_sequence += 1;
        }

        let meta = sqlx::query("SELECT next_sequence, head_hash FROM ledger_meta WHERE id = 1")
            .fetch_one(&self.pool)
            .await
            .map_err(|error| format!("read ledger metadata: {error}"))?;
        let next_sequence: i64 = meta
            .try_get("next_sequence")
            .map_err(|error| format!("decode ledger metadata sequence: {error}"))?;
        let head_hash: Option<String> = meta
            .try_get("head_hash")
            .map_err(|error| format!("decode ledger metadata head: {error}"))?;
        if next_sequence as u64 != expected_sequence {
            return Err(format!(
                "ledger metadata sequence mismatch: expected {expected_sequence}, got {next_sequence}"
            ));
        }
        if head_hash != expected_parent {
            return Err("ledger metadata head hash does not match verified receipt chain".into());
        }
        Ok(())
    }
}

fn decode_receipts(rows: Vec<sqlx::sqlite::SqliteRow>) -> Result<Vec<Receipt>, String> {
    rows.into_iter()
        .map(|row| {
            let raw: String = row
                .try_get("receipt_json")
                .map_err(|error| format!("decode receipt row: {error}"))?;
            serde_json::from_str(&raw).map_err(|error| format!("decode receipt JSON: {error}"))
        })
        .collect()
}

fn validate_draft(draft: &ReceiptDraft, authority_epoch: u64) -> Result<(), String> {
    for (name, value, max) in [
        ("tenantId", draft.tenant_id.as_str(), 160_usize),
        ("workspaceId", draft.workspace_id.as_str(), 160),
        ("missionId", draft.mission_id.as_str(), 160),
        ("taskId", draft.task_id.as_str(), 160),
        ("actorId", draft.actor_id.as_str(), 160),
        ("actionType", draft.action_type.as_str(), 160),
        ("resourceUri", draft.resource_uri.as_str(), 512),
    ] {
        if value.trim().is_empty() || value.len() > max {
            return Err(format!("invalid receipt field {name}"));
        }
    }
    if draft.authority_epoch != authority_epoch {
        return Err("receipt draft carries a stale authority epoch".into());
    }
    if !is_sha256_reference(&draft.manifest_hash) || !is_sha256_reference(&draft.result_hash) {
        return Err("manifestHash and resultHash must be canonical sha256 references".into());
    }
    Ok(())
}
