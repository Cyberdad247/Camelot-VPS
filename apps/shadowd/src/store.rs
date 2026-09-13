use crate::{ShadowReceipt, ShadowSession};
use chrono::Utc;
use sqlx::{sqlite::{SqliteConnectOptions, SqliteJournalMode, SqlitePoolOptions, SqliteSynchronous}, Row, SqlitePool};
use std::{path::Path, time::Duration};
use uuid::Uuid;

#[derive(Clone)]
pub(crate) struct ShadowStore { pool: SqlitePool }

impl ShadowStore {
    pub(crate) async fn open(path: &Path) -> Result<Self, String> {
        let options = SqliteConnectOptions::new()
            .filename(path)
            .create_if_missing(true)
            .journal_mode(SqliteJournalMode::Wal)
            .synchronous(SqliteSynchronous::Full)
            .foreign_keys(true)
            .busy_timeout(Duration::from_secs(5));
        let pool = SqlitePoolOptions::new().max_connections(4).connect_with(options).await
            .map_err(|e| format!("open shadow database: {e}"))?;
        let store = Self { pool };
        store.migrate().await?;
        Ok(store)
    }

    async fn migrate(&self) -> Result<(), String> {
        sqlx::query("CREATE TABLE IF NOT EXISTS shadow_sessions (session_id TEXT PRIMARY KEY, state_version INTEGER NOT NULL, session_json TEXT NOT NULL, updated_at TEXT NOT NULL)")
            .execute(&self.pool).await.map_err(|e| e.to_string())?;
        sqlx::query("CREATE TABLE IF NOT EXISTS shadow_receipts (sequence INTEGER PRIMARY KEY, receipt_id TEXT NOT NULL UNIQUE, session_id TEXT NOT NULL, receipt_hash TEXT NOT NULL UNIQUE, parent_hash TEXT, receipt_json TEXT NOT NULL, created_at TEXT NOT NULL)")
            .execute(&self.pool).await.map_err(|e| e.to_string())?;
        sqlx::query("CREATE INDEX IF NOT EXISTS idx_shadow_receipts_session ON shadow_receipts(session_id, sequence)")
            .execute(&self.pool).await.map_err(|e| e.to_string())?;
        Ok(())
    }

    pub(crate) async fn ping(&self) -> Result<(), String> {
        sqlx::query("SELECT 1").execute(&self.pool).await.map_err(|e| e.to_string())?;
        Ok(())
    }

    pub(crate) async fn insert_session(&self, session: &ShadowSession) -> Result<(), String> {
        let body = serde_json::to_string(session).map_err(|e| e.to_string())?;
        sqlx::query("INSERT INTO shadow_sessions(session_id, state_version, session_json, updated_at) VALUES (?, ?, ?, ?)")
            .bind(session.session_id.to_string()).bind(session.state_version as i64).bind(body).bind(Utc::now().to_rfc3339())
            .execute(&self.pool).await.map_err(|e| e.to_string())?;
        Ok(())
    }

    pub(crate) async fn update_session(&self, session: &ShadowSession, expected_version: u64) -> Result<bool, String> {
        let body = serde_json::to_string(session).map_err(|e| e.to_string())?;
        let result = sqlx::query("UPDATE shadow_sessions SET state_version = ?, session_json = ?, updated_at = ? WHERE session_id = ? AND state_version = ?")
            .bind(session.state_version as i64).bind(body).bind(Utc::now().to_rfc3339())
            .bind(session.session_id.to_string()).bind(expected_version as i64)
            .execute(&self.pool).await.map_err(|e| e.to_string())?;
        Ok(result.rows_affected() == 1)
    }

    pub(crate) async fn get_session(&self, id: Uuid) -> Result<Option<ShadowSession>, String> {
        let row = sqlx::query("SELECT session_json FROM shadow_sessions WHERE session_id = ?")
            .bind(id.to_string()).fetch_optional(&self.pool).await.map_err(|e| e.to_string())?;
        row.map(|row| { let raw: String = row.get("session_json"); serde_json::from_str(&raw).map_err(|e| e.to_string()) }).transpose()
    }

    pub(crate) async fn list_sessions(&self) -> Result<Vec<ShadowSession>, String> {
        let rows = sqlx::query("SELECT session_json FROM shadow_sessions ORDER BY updated_at DESC").fetch_all(&self.pool).await.map_err(|e| e.to_string())?;
        rows.into_iter().map(|row| { let raw: String = row.get("session_json"); serde_json::from_str(&raw).map_err(|e| e.to_string()) }).collect()
    }

    pub(crate) async fn next_receipt_sequence(&self) -> Result<u64, String> {
        let row = sqlx::query("SELECT COALESCE(MAX(sequence), 0) + 1 AS next_sequence FROM shadow_receipts").fetch_one(&self.pool).await.map_err(|e| e.to_string())?;
        let value: i64 = row.get("next_sequence");
        u64::try_from(value).map_err(|_| "receipt sequence overflow".to_string())
    }

    pub(crate) async fn insert_receipt(&self, receipt: &ShadowReceipt) -> Result<(), String> {
        let body = serde_json::to_string(receipt).map_err(|e| e.to_string())?;
        sqlx::query("INSERT INTO shadow_receipts(sequence, receipt_id, session_id, receipt_hash, parent_hash, receipt_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)")
            .bind(receipt.sequence as i64).bind(receipt.receipt_id.to_string()).bind(receipt.session_id.to_string())
            .bind(&receipt.receipt_hash).bind(&receipt.parent_hash).bind(body).bind(receipt.timestamp.to_rfc3339())
            .execute(&self.pool).await.map_err(|e| e.to_string())?;
        Ok(())
    }

    pub(crate) async fn ledger_head(&self) -> Result<Option<String>, String> {
        let row = sqlx::query("SELECT receipt_hash FROM shadow_receipts ORDER BY sequence DESC LIMIT 1").fetch_optional(&self.pool).await.map_err(|e| e.to_string())?;
        Ok(row.map(|row| row.get("receipt_hash")))
    }

    pub(crate) async fn receipts_for(&self, id: Uuid) -> Result<Vec<ShadowReceipt>, String> {
        let rows = sqlx::query("SELECT receipt_json FROM shadow_receipts WHERE session_id = ? ORDER BY sequence DESC LIMIT 250")
            .bind(id.to_string()).fetch_all(&self.pool).await.map_err(|e| e.to_string())?;
        rows.into_iter().map(|row| { let raw: String = row.get("receipt_json"); serde_json::from_str(&raw).map_err(|e| e.to_string()) }).collect()
    }

    pub(crate) async fn all_receipts(&self) -> Result<Vec<ShadowReceipt>, String> {
        let rows = sqlx::query("SELECT receipt_json FROM shadow_receipts ORDER BY sequence ASC").fetch_all(&self.pool).await.map_err(|e| e.to_string())?;
        rows.into_iter().map(|row| { let raw: String = row.get("receipt_json"); serde_json::from_str(&raw).map_err(|e| e.to_string()) }).collect()
    }
}
