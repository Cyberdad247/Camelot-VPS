use camelot_crypto::hash_payload;
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use uuid::Uuid;

pub const EVENT_SCHEMA: &str = "workspace-event/1";
pub const MAX_EVENT_BYTES: usize = 64 * 1024;

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct Provenance {
    pub source: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub node_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub policy_decision_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub capability_lease_id: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub receipt_id: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct Integrity {
    pub payload_hash: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "camelCase")]
pub struct WorkspaceEvent {
    pub schema_version: String,
    pub id: String,
    #[serde(rename = "type")]
    pub event_type: String,
    pub occurred_at: DateTime<Utc>,
    pub tenant_id: String,
    pub workspace_id: String,
    pub cartridge_id: String,
    pub mission_id: String,
    pub trace_id: String,
    pub sequence: i64,
    pub classification: String,
    pub visibility: String,
    pub payload: Value,
    pub provenance: Provenance,
    pub integrity: Integrity,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct AppendEventRequest {
    #[serde(rename = "type")]
    pub event_type: String,
    pub tenant_id: String,
    pub workspace_id: String,
    pub cartridge_id: String,
    pub mission_id: String,
    pub trace_id: String,
    pub classification: String,
    pub visibility: String,
    pub payload: Value,
    pub provenance: Provenance,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkspaceQuery {
    pub tenant_id: String,
    #[serde(default)]
    pub after: Option<i64>,
}

#[derive(Debug, Serialize, Deserialize, Clone, Copy, PartialEq, Eq)]
#[serde(rename_all = "SCREAMING_SNAKE_CASE")]
pub enum TaskState {
    Proposed,
    PolicyPending,
    ApprovalPending,
    Leased,
    VfsPreflight,
    Queued,
    Running,
    Verifying,
    Resolved,
    Receipted,
    Denied,
    Failed,
    Revoked,
    Quarantined,
}

impl TaskState {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Proposed => "PROPOSED",
            Self::PolicyPending => "POLICY_PENDING",
            Self::ApprovalPending => "APPROVAL_PENDING",
            Self::Leased => "LEASED",
            Self::VfsPreflight => "VFS_PREFLIGHT",
            Self::Queued => "QUEUED",
            Self::Running => "RUNNING",
            Self::Verifying => "VERIFYING",
            Self::Resolved => "RESOLVED",
            Self::Receipted => "RECEIPTED",
            Self::Denied => "DENIED",
            Self::Failed => "FAILED",
            Self::Revoked => "REVOKED",
            Self::Quarantined => "QUARANTINED",
        }
    }

    pub fn from_db(value: &str) -> Option<Self> {
        match value {
            "PROPOSED" => Some(Self::Proposed),
            "POLICY_PENDING" => Some(Self::PolicyPending),
            "APPROVAL_PENDING" => Some(Self::ApprovalPending),
            "LEASED" => Some(Self::Leased),
            "VFS_PREFLIGHT" => Some(Self::VfsPreflight),
            "QUEUED" => Some(Self::Queued),
            "RUNNING" => Some(Self::Running),
            "VERIFYING" => Some(Self::Verifying),
            "RESOLVED" => Some(Self::Resolved),
            "RECEIPTED" => Some(Self::Receipted),
            "DENIED" => Some(Self::Denied),
            "FAILED" => Some(Self::Failed),
            "REVOKED" => Some(Self::Revoked),
            "QUARANTINED" => Some(Self::Quarantined),
            _ => None,
        }
    }
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TaskStatePayload {
    pub task_id: String,
    pub state: TaskState,
    pub authority_epoch: u64,
    #[serde(default)]
    pub reason: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct TaskSnapshot {
    pub mission_id: String,
    pub task_id: String,
    pub state: TaskState,
    pub authority_epoch: u64,
    pub updated_at: String,
    pub last_event_id: String,
    pub last_sequence: i64,
    pub receipt_id: Option<String>,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct WorkspaceSnapshot {
    pub tenant_id: String,
    pub workspace_id: String,
    pub authority_epoch: u64,
    pub generated_at: DateTime<Utc>,
    pub last_sequence: i64,
    pub tasks: Vec<TaskSnapshot>,
}

pub fn bounded(value: &str) -> bool {
    let value = value.trim();
    !value.is_empty() && value.len() <= 160
}

pub fn valid_classification(value: &str) -> bool {
    matches!(value, "public" | "internal" | "confidential" | "restricted")
}

pub fn valid_visibility(value: &str) -> bool {
    matches!(value, "user" | "operator" | "audit")
}

pub fn can_transition(from: Option<TaskState>, to: TaskState) -> bool {
    match (from, to) {
        (None, TaskState::Proposed) => true,
        (Some(TaskState::Proposed), TaskState::PolicyPending | TaskState::Denied | TaskState::Failed) => true,
        (Some(TaskState::PolicyPending), TaskState::ApprovalPending | TaskState::Leased | TaskState::Denied | TaskState::Failed) => true,
        (Some(TaskState::ApprovalPending), TaskState::Leased | TaskState::Denied | TaskState::Revoked | TaskState::Failed) => true,
        (Some(TaskState::Leased), TaskState::VfsPreflight | TaskState::Revoked | TaskState::Failed) => true,
        (Some(TaskState::VfsPreflight), TaskState::Queued | TaskState::Denied | TaskState::Revoked | TaskState::Failed) => true,
        (Some(TaskState::Queued), TaskState::Running | TaskState::Revoked | TaskState::Failed) => true,
        (Some(TaskState::Running), TaskState::Verifying | TaskState::Revoked | TaskState::Failed) => true,
        (Some(TaskState::Verifying), TaskState::Resolved | TaskState::Quarantined | TaskState::Failed) => true,
        (Some(TaskState::Resolved), TaskState::Receipted | TaskState::Failed) => true,
        _ => false,
    }
}

pub fn build_event(request: AppendEventRequest, sequence: i64) -> Result<WorkspaceEvent, String> {
    let payload_json = serde_json::to_string(&request.payload).map_err(|error| error.to_string())?;
    if payload_json.len() > MAX_EVENT_BYTES {
        return Err("event payload exceeds 64 KiB".into());
    }
    Ok(WorkspaceEvent {
        schema_version: EVENT_SCHEMA.into(),
        id: Uuid::new_v4().to_string(),
        event_type: request.event_type,
        occurred_at: Utc::now(),
        tenant_id: request.tenant_id,
        workspace_id: request.workspace_id,
        cartridge_id: request.cartridge_id,
        mission_id: request.mission_id,
        trace_id: request.trace_id,
        sequence,
        classification: request.classification,
        visibility: request.visibility,
        payload: request.payload,
        provenance: request.provenance,
        integrity: Integrity { payload_hash: hash_payload(&payload_json) },
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn state_machine_rejects_shortcuts() {
        assert!(can_transition(None, TaskState::Proposed));
        assert!(can_transition(Some(TaskState::Proposed), TaskState::PolicyPending));
        assert!(!can_transition(Some(TaskState::Proposed), TaskState::Running));
        assert!(!can_transition(Some(TaskState::Receipted), TaskState::Running));
    }

    #[test]
    fn visibility_is_bounded() {
        assert!(valid_classification("restricted"));
        assert!(!valid_classification("secret-ish"));
        assert!(valid_visibility("operator"));
        assert!(!valid_visibility("everyone"));
    }
}
