use crate::model::{HeartbeatRequest, PromotionRequest};
use camelot_crypto::KeyPair;
use camelot_epoch::{AuthorityEpochCertificate, BrainHeartbeat, BrainId, PromotionMode};
use chrono::{Duration, Utc};
use sqlx::{sqlite::SqliteConnectOptions, Row, SqlitePool};
use std::{str::FromStr, sync::Arc};

#[derive(Clone)]
pub struct EpochStore {
    pool: SqlitePool,
    signer: Arc<KeyPair>,
    max_heartbeat_age: Duration,
}

impl EpochStore {
    pub async fn open(
        database_url: &str,
        signer: Arc<KeyPair>,
        bootstrap_epoch: u64,
        bootstrap_brain: BrainId,
        max_heartbeat_age_seconds: i64,
    ) -> Result<Self, String> {
        let options = SqliteConnectOptions::from_str(database_url)
            .map_err(|error| error.to_string())?
            .create_if_missing(true)
            .journal_mode(sqlx::sqlite::SqliteJournalMode::Wal);
        let pool = SqlitePool::connect_with(options)
            .await
            .map_err(|error| error.to_string())?;
        sqlx::query(
            "CREATE TABLE IF NOT EXISTS epoch_state (
                singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
                epoch INTEGER NOT NULL,
                active_brain TEXT NOT NULL,
                certificate_json TEXT NOT NULL
            )",
        )
        .execute(&pool)
        .await
        .map_err(|error| error.to_string())?;
        sqlx::query(
            "CREATE TABLE IF NOT EXISTS brain_heartbeats (
                brain_id TEXT PRIMARY KEY,
                observed_epoch INTEGER NOT NULL,
                ready INTEGER NOT NULL,
                receipt_head_sequence INTEGER NOT NULL,
                state_digest TEXT NOT NULL,
                observed_at TEXT NOT NULL
            )",
        )
        .execute(&pool)
        .await
        .map_err(|error| error.to_string())?;
        sqlx::query(
            "CREATE TABLE IF NOT EXISTS promotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_epoch INTEGER NOT NULL,
                to_epoch INTEGER NOT NULL,
                from_brain TEXT NOT NULL,
                to_brain TEXT NOT NULL,
                mode TEXT NOT NULL,
                reason TEXT NOT NULL,
                promoted_at TEXT NOT NULL,
                certificate_json TEXT NOT NULL
            )",
        )
        .execute(&pool)
        .await
        .map_err(|error| error.to_string())?;

        let store = Self {
            pool,
            signer,
            max_heartbeat_age: Duration::seconds(max_heartbeat_age_seconds.max(5)),
        };
        if sqlx::query("SELECT singleton FROM epoch_state WHERE singleton = 1")
            .fetch_optional(&store.pool)
            .await
            .map_err(|error| error.to_string())?
            .is_none()
        {
            let digest = format!("sha256:{}", "0".repeat(64));
            let certificate = AuthorityEpochCertificate::bootstrap(
                bootstrap_epoch,
                bootstrap_brain,
                0,
                digest,
                "initial VPS Hub authority epoch".into(),
                &store.signer,
            )?;
            store.persist_current(&certificate).await?;
        }
        let current = store.current().await?;
        current.verify_with_pinned_key(&store.signer.public_key_hex())?;
        Ok(store)
    }

    async fn persist_current(&self, certificate: &AuthorityEpochCertificate) -> Result<(), String> {
        let json = serde_json::to_string(certificate).map_err(|error| error.to_string())?;
        sqlx::query(
            "INSERT INTO epoch_state(singleton, epoch, active_brain, certificate_json)
             VALUES(1, ?1, ?2, ?3)
             ON CONFLICT(singleton) DO UPDATE SET epoch=excluded.epoch,
             active_brain=excluded.active_brain, certificate_json=excluded.certificate_json",
        )
        .bind(certificate.epoch as i64)
        .bind(certificate.active_brain.as_str())
        .bind(json)
        .execute(&self.pool)
        .await
        .map_err(|error| error.to_string())?;
        Ok(())
    }

    pub async fn current(&self) -> Result<AuthorityEpochCertificate, String> {
        let row = sqlx::query("SELECT certificate_json FROM epoch_state WHERE singleton = 1")
            .fetch_one(&self.pool)
            .await
            .map_err(|error| error.to_string())?;
        let raw: String = row.try_get("certificate_json").map_err(|error| error.to_string())?;
        let certificate: AuthorityEpochCertificate =
            serde_json::from_str(&raw).map_err(|error| error.to_string())?;
        certificate.verify_with_pinned_key(&self.signer.public_key_hex())?;
        Ok(certificate)
    }

    pub async fn heartbeat(&self, request: HeartbeatRequest) -> Result<BrainHeartbeat, String> {
        let current = self.current().await?;
        if request.observed_epoch > current.epoch {
            return Err("brain heartbeat cannot claim a future authority epoch".into());
        }
        let heartbeat = BrainHeartbeat {
            brain_id: request.brain_id,
            observed_epoch: request.observed_epoch,
            ready: request.ready,
            receipt_head_sequence: request.receipt_head_sequence,
            state_digest: request.state_digest,
            observed_at: Utc::now(),
        };
        heartbeat.validate()?;
        sqlx::query(
            "INSERT INTO brain_heartbeats(brain_id, observed_epoch, ready, receipt_head_sequence, state_digest, observed_at)
             VALUES(?1, ?2, ?3, ?4, ?5, ?6)
             ON CONFLICT(brain_id) DO UPDATE SET observed_epoch=excluded.observed_epoch,
             ready=excluded.ready, receipt_head_sequence=excluded.receipt_head_sequence,
             state_digest=excluded.state_digest, observed_at=excluded.observed_at",
        )
        .bind(heartbeat.brain_id.as_str())
        .bind(heartbeat.observed_epoch as i64)
        .bind(if heartbeat.ready { 1_i64 } else { 0_i64 })
        .bind(heartbeat.receipt_head_sequence as i64)
        .bind(&heartbeat.state_digest)
        .bind(heartbeat.observed_at.to_rfc3339())
        .execute(&self.pool)
        .await
        .map_err(|error| error.to_string())?;
        Ok(heartbeat)
    }

    pub async fn heartbeats(&self) -> Result<Vec<BrainHeartbeat>, String> {
        let rows = sqlx::query(
            "SELECT brain_id, observed_epoch, ready, receipt_head_sequence, state_digest, observed_at
             FROM brain_heartbeats ORDER BY brain_id",
        )
        .fetch_all(&self.pool)
        .await
        .map_err(|error| error.to_string())?;
        rows.into_iter().map(row_to_heartbeat).collect()
    }

    pub fn heartbeat_is_fresh(&self, heartbeat: &BrainHeartbeat) -> bool {
        Utc::now() - heartbeat.observed_at <= self.max_heartbeat_age
    }

    pub async fn promote(&self, request: PromotionRequest) -> Result<AuthorityEpochCertificate, String> {
        let current = self.current().await?;
        if request.expected_epoch != current.epoch {
            return Err("promotion expected epoch is stale".into());
        }
        if request.expected_active_brain != current.active_brain {
            return Err("promotion expected active brain does not match current authority".into());
        }
        if request.target_brain == current.active_brain {
            return Err("promotion target is already active".into());
        }
        if request.reason.trim().is_empty() || request.reason.len() > 512 {
            return Err("promotion reason must contain 1..512 characters".into());
        }
        let heartbeats = self.heartbeats().await?;
        let target = heartbeats
            .iter()
            .find(|heartbeat| heartbeat.brain_id == request.target_brain)
            .ok_or_else(|| "target brain has not reported a heartbeat".to_string())?;
        if !target.ready || !self.heartbeat_is_fresh(target) {
            return Err("target brain is not ready with a fresh heartbeat".into());
        }
        if target.observed_epoch != current.epoch {
            return Err("target brain has not observed the current authority epoch".into());
        }
        let source = heartbeats
            .iter()
            .find(|heartbeat| heartbeat.brain_id == current.active_brain);
        let source_fresh = source
            .map(|heartbeat| heartbeat.ready && self.heartbeat_is_fresh(heartbeat))
            .unwrap_or(false);
        let mode = if source_fresh {
            let source = source.expect("source heartbeat checked");
            if target.receipt_head_sequence < source.receipt_head_sequence {
                return Err("target brain is behind the active receipt head".into());
            }
            if target.state_digest != source.state_digest {
                return Err("planned promotion requires matching Twin-Brain state digests".into());
            }
            PromotionMode::Planned
        } else {
            if !request.allow_stale_source {
                return Err("active brain is stale; explicit failover permission is required".into());
            }
            if target.receipt_head_sequence < current.receipt_head_sequence {
                return Err("failover target is behind the last promoted receipt floor".into());
            }
            PromotionMode::Failover
        };
        let next = AuthorityEpochCertificate::promoted(
            &current,
            request.target_brain,
            mode,
            target.receipt_head_sequence,
            target.state_digest.clone(),
            request.reason,
            &self.signer,
        )?;
        let json = serde_json::to_string(&next).map_err(|error| error.to_string())?;
        let mut transaction = self.pool.begin().await.map_err(|error| error.to_string())?;
        sqlx::query(
            "UPDATE epoch_state SET epoch=?1, active_brain=?2, certificate_json=?3
             WHERE singleton=1 AND epoch=?4 AND active_brain=?5",
        )
        .bind(next.epoch as i64)
        .bind(next.active_brain.as_str())
        .bind(&json)
        .bind(current.epoch as i64)
        .bind(current.active_brain.as_str())
        .execute(&mut *transaction)
        .await
        .map_err(|error| error.to_string())?;
        sqlx::query(
            "INSERT INTO promotions(from_epoch, to_epoch, from_brain, to_brain, mode, reason, promoted_at, certificate_json)
             VALUES(?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
        )
        .bind(current.epoch as i64)
        .bind(next.epoch as i64)
        .bind(current.active_brain.as_str())
        .bind(next.active_brain.as_str())
        .bind(format!("{:?}", mode))
        .bind(&next.reason)
        .bind(next.promoted_at.to_rfc3339())
        .bind(json)
        .execute(&mut *transaction)
        .await
        .map_err(|error| error.to_string())?;
        transaction.commit().await.map_err(|error| error.to_string())?;
        Ok(next)
    }
}

fn row_to_heartbeat(row: sqlx::sqlite::SqliteRow) -> Result<BrainHeartbeat, String> {
    let brain: String = row.try_get("brain_id").map_err(|error| error.to_string())?;
    let observed_at: String = row.try_get("observed_at").map_err(|error| error.to_string())?;
    Ok(BrainHeartbeat {
        brain_id: BrainId::parse(&brain)?,
        observed_epoch: row.try_get::<i64, _>("observed_epoch").map_err(|error| error.to_string())? as u64,
        ready: row.try_get::<i64, _>("ready").map_err(|error| error.to_string())? != 0,
        receipt_head_sequence: row.try_get::<i64, _>("receipt_head_sequence").map_err(|error| error.to_string())? as u64,
        state_digest: row.try_get("state_digest").map_err(|error| error.to_string())?,
        observed_at: chrono::DateTime::parse_from_rfc3339(&observed_at)
            .map_err(|error| error.to_string())?
            .with_timezone(&Utc),
    })
}
