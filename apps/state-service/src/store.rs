use crate::model::{
    build_event, can_transition, AppendEventRequest, TaskSnapshot, TaskState, TaskStatePayload,
    WorkspaceEvent, WorkspaceSnapshot,
};
use chrono::Utc;
use sqlx::{
    sqlite::{SqliteConnectOptions, SqlitePoolOptions},
    Row, SqlitePool,
};
use std::str::FromStr;

#[derive(Clone)]
pub struct StateStore {
    pool: SqlitePool,
}

impl StateStore {
    pub async fn open(url: &str) -> Result<Self, String> {
        let options = SqliteConnectOptions::from_str(url)
            .map_err(|error| format!("parse state database URL: {error}"))?
            .create_if_missing(true);
        let pool = SqlitePoolOptions::new()
            .max_connections(5)
            .connect_with(options)
            .await
            .map_err(|error| format!("open state database: {error}"))?;

        for statement in [
            "PRAGMA journal_mode=WAL",
            "PRAGMA synchronous=NORMAL",
            "PRAGMA foreign_keys=ON",
            "PRAGMA busy_timeout=5000",
        ] {
            sqlx::query(statement)
                .execute(&pool)
                .await
                .map_err(|error| format!("configure state database: {error}"))?;
        }

        sqlx::query(
            "CREATE TABLE IF NOT EXISTS workspace_heads (
                tenant_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                next_sequence INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, workspace_id)
            )",
        )
        .execute(&pool)
        .await
        .map_err(|error| format!("create workspace_heads: {error}"))?;

        sqlx::query(
            "CREATE TABLE IF NOT EXISTS workspace_events (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                mission_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                sequence INTEGER NOT NULL,
                occurred_at TEXT NOT NULL,
                event_json TEXT NOT NULL,
                UNIQUE (tenant_id, workspace_id, sequence)
            )",
        )
        .execute(&pool)
        .await
        .map_err(|error| format!("create workspace_events: {error}"))?;

        sqlx::query(
            "CREATE INDEX IF NOT EXISTS idx_workspace_events_scope
             ON workspace_events (tenant_id, workspace_id, sequence)",
        )
        .execute(&pool)
        .await
        .map_err(|error| format!("index workspace_events: {error}"))?;

        sqlx::query(
            "CREATE TABLE IF NOT EXISTS task_snapshots (
                tenant_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                mission_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                state TEXT NOT NULL,
                authority_epoch INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                last_event_id TEXT NOT NULL,
                last_sequence INTEGER NOT NULL,
                receipt_id TEXT,
                PRIMARY KEY (tenant_id, workspace_id, task_id)
            )",
        )
        .execute(&pool)
        .await
        .map_err(|error| format!("create task_snapshots: {error}"))?;

        Ok(Self { pool })
    }

    pub async fn ready(&self) -> bool {
        sqlx::query("SELECT 1").execute(&self.pool).await.is_ok()
    }

    pub async fn append(
        &self,
        request: AppendEventRequest,
        authority_epoch: u64,
    ) -> Result<WorkspaceEvent, String> {
        let task_change = if request.event_type == "task.state.changed" {
            let change: TaskStatePayload = serde_json::from_value(request.payload.clone())
                .map_err(|error| format!("invalid task state payload: {error}"))?;
            if change.authority_epoch != authority_epoch {
                return Err("task event carries a stale authority epoch".into());
            }
            Some(change)
        } else {
            None
        };

        let mut transaction = self
            .pool
            .begin()
            .await
            .map_err(|error| format!("begin state transaction: {error}"))?;
        let now = Utc::now().to_rfc3339();

        sqlx::query(
            "INSERT OR IGNORE INTO workspace_heads
             (tenant_id, workspace_id, next_sequence, updated_at)
             VALUES (?, ?, 0, ?)",
        )
        .bind(&request.tenant_id)
        .bind(&request.workspace_id)
        .bind(&now)
        .execute(&mut *transaction)
        .await
        .map_err(|error| format!("ensure workspace head: {error}"))?;

        let sequence: i64 = sqlx::query(
            "SELECT next_sequence FROM workspace_heads
             WHERE tenant_id = ? AND workspace_id = ?",
        )
        .bind(&request.tenant_id)
        .bind(&request.workspace_id)
        .fetch_one(&mut *transaction)
        .await
        .map_err(|error| format!("load workspace sequence: {error}"))?
        .try_get("next_sequence")
        .map_err(|error| format!("decode workspace sequence: {error}"))?;

        if let Some(change) = task_change.as_ref() {
            let current = sqlx::query(
                "SELECT state FROM task_snapshots
                 WHERE tenant_id = ? AND workspace_id = ? AND task_id = ?",
            )
            .bind(&request.tenant_id)
            .bind(&request.workspace_id)
            .bind(&change.task_id)
            .fetch_optional(&mut *transaction)
            .await
            .map_err(|error| format!("load task state: {error}"))?;
            let current_state = current
                .as_ref()
                .and_then(|row| row.try_get::<String, _>("state").ok())
                .as_deref()
                .and_then(TaskState::from_db);
            if !can_transition(current_state, change.state) {
                return Err(format!(
                    "invalid task transition from {} to {}",
                    current_state.map(TaskState::as_str).unwrap_or("NONE"),
                    change.state.as_str()
                ));
            }
            if change.state == TaskState::Receipted && request.provenance.receipt_id.is_none() {
                return Err("RECEIPTED requires provenance.receiptId".into());
            }
        }

        let event = build_event(request, sequence)?;
        let event_json = serde_json::to_string(&event)
            .map_err(|error| format!("serialize workspace event: {error}"))?;

        sqlx::query(
            "INSERT INTO workspace_events
             (id, tenant_id, workspace_id, mission_id, event_type, sequence, occurred_at, event_json)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        )
        .bind(&event.id)
        .bind(&event.tenant_id)
        .bind(&event.workspace_id)
        .bind(&event.mission_id)
        .bind(&event.event_type)
        .bind(event.sequence)
        .bind(event.occurred_at.to_rfc3339())
        .bind(event_json)
        .execute(&mut *transaction)
        .await
        .map_err(|error| format!("insert workspace event: {error}"))?;

        let updated = sqlx::query(
            "UPDATE workspace_heads
             SET next_sequence = next_sequence + 1, updated_at = ?
             WHERE tenant_id = ? AND workspace_id = ? AND next_sequence = ?",
        )
        .bind(&now)
        .bind(&event.tenant_id)
        .bind(&event.workspace_id)
        .bind(sequence)
        .execute(&mut *transaction)
        .await
        .map_err(|error| format!("advance workspace sequence: {error}"))?;
        if updated.rows_affected() != 1 {
            return Err("workspace sequence conflict; retry event append".into());
        }

        if let Some(change) = task_change {
            sqlx::query(
                "INSERT INTO task_snapshots
                 (tenant_id, workspace_id, mission_id, task_id, state, authority_epoch,
                  updated_at, last_event_id, last_sequence, receipt_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                 ON CONFLICT(tenant_id, workspace_id, task_id) DO UPDATE SET
                   mission_id = excluded.mission_id,
                   state = excluded.state,
                   authority_epoch = excluded.authority_epoch,
                   updated_at = excluded.updated_at,
                   last_event_id = excluded.last_event_id,
                   last_sequence = excluded.last_sequence,
                   receipt_id = excluded.receipt_id",
            )
            .bind(&event.tenant_id)
            .bind(&event.workspace_id)
            .bind(&event.mission_id)
            .bind(&change.task_id)
            .bind(change.state.as_str())
            .bind(change.authority_epoch as i64)
            .bind(&now)
            .bind(&event.id)
            .bind(event.sequence)
            .bind(event.provenance.receipt_id.as_deref())
            .execute(&mut *transaction)
            .await
            .map_err(|error| format!("update task snapshot: {error}"))?;
        }

        transaction
            .commit()
            .await
            .map_err(|error| format!("commit state transaction: {error}"))?;
        Ok(event)
    }

    pub async fn events(
        &self,
        tenant_id: &str,
        workspace_id: &str,
        after: i64,
        limit: i64,
    ) -> Result<Vec<WorkspaceEvent>, String> {
        let rows = sqlx::query(
            "SELECT event_json FROM workspace_events
             WHERE tenant_id = ? AND workspace_id = ? AND sequence > ?
             ORDER BY sequence ASC LIMIT ?",
        )
        .bind(tenant_id)
        .bind(workspace_id)
        .bind(after)
        .bind(limit)
        .fetch_all(&self.pool)
        .await
        .map_err(|error| format!("read workspace events: {error}"))?;

        rows.into_iter()
            .map(|row| {
                let raw: String = row
                    .try_get("event_json")
                    .map_err(|error| format!("read event JSON: {error}"))?;
                serde_json::from_str(&raw)
                    .map_err(|error| format!("decode workspace event: {error}"))
            })
            .collect()
    }

    pub async fn snapshot(
        &self,
        tenant_id: String,
        workspace_id: String,
        authority_epoch: u64,
    ) -> Result<WorkspaceSnapshot, String> {
        let rows = sqlx::query(
            "SELECT mission_id, task_id, state, authority_epoch, updated_at,
                    last_event_id, last_sequence, receipt_id
             FROM task_snapshots
             WHERE tenant_id = ? AND workspace_id = ?
             ORDER BY last_sequence ASC",
        )
        .bind(&tenant_id)
        .bind(&workspace_id)
        .fetch_all(&self.pool)
        .await
        .map_err(|error| format!("read task snapshots: {error}"))?;

        let mut tasks = Vec::with_capacity(rows.len());
        for row in rows {
            let state_text: String = row
                .try_get("state")
                .map_err(|error| format!("decode task state: {error}"))?;
            let state = TaskState::from_db(&state_text)
                .ok_or_else(|| format!("invalid stored task state: {state_text}"))?;
            tasks.push(TaskSnapshot {
                mission_id: row.try_get("mission_id").map_err(|e| e.to_string())?,
                task_id: row.try_get("task_id").map_err(|e| e.to_string())?,
                state,
                authority_epoch: row
                    .try_get::<i64, _>("authority_epoch")
                    .map_err(|e| e.to_string())? as u64,
                updated_at: row.try_get("updated_at").map_err(|e| e.to_string())?,
                last_event_id: row.try_get("last_event_id").map_err(|e| e.to_string())?,
                last_sequence: row.try_get("last_sequence").map_err(|e| e.to_string())?,
                receipt_id: row.try_get("receipt_id").map_err(|e| e.to_string())?,
            });
        }

        let last_sequence = sqlx::query(
            "SELECT MAX(sequence) AS max_sequence FROM workspace_events
             WHERE tenant_id = ? AND workspace_id = ?",
        )
        .bind(&tenant_id)
        .bind(&workspace_id)
        .fetch_one(&self.pool)
        .await
        .map_err(|error| format!("read workspace head: {error}"))?
        .try_get::<Option<i64>, _>("max_sequence")
        .map_err(|error| format!("decode workspace head: {error}"))?
        .unwrap_or(-1);

        Ok(WorkspaceSnapshot {
            tenant_id,
            workspace_id,
            authority_epoch,
            generated_at: Utc::now(),
            last_sequence,
            tasks,
        })
    }
}
