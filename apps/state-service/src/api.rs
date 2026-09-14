use crate::{
    model::{
        bounded, valid_classification, valid_visibility, AppendEventRequest, TaskState,
        TaskStatePayload, WorkspaceEvent, WorkspaceQuery, EVENT_SCHEMA,
    },
    store::StateStore,
};
use async_stream::stream;
use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    response::sse::{Event as SseEvent, KeepAlive},
    response::Sse,
    routing::{get, post},
    Json, Router,
};
use camelot_epoch::EpochSource;
use futures_util::Stream;
use serde::Deserialize;
use serde_json::{json, Value};
use std::{convert::Infallible, sync::Arc, time::Duration};
use tokio::sync::broadcast;
use tracing::warn;

#[derive(Clone)]
pub struct ApiState {
    pub store: StateStore,
    pub epoch_source: Arc<EpochSource>,
    pub events: broadcast::Sender<WorkspaceEvent>,
    pub receipt_base_url: Arc<String>,
    pub client: reqwest::Client,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ReceiptProjection {
    schema_version: String,
    receipt_id: String,
    tenant_id: String,
    workspace_id: String,
    mission_id: String,
    task_id: String,
    authority_epoch: u64,
}

type ApiError = (StatusCode, Json<Value>);

fn error(status: StatusCode, message: impl Into<String>) -> ApiError {
    (status, Json(json!({ "error": message.into() })))
}

fn current_epoch(state: &ApiState) -> Result<u64, ApiError> {
    state.epoch_source.current_epoch().map_err(|message| {
        error(
            StatusCode::SERVICE_UNAVAILABLE,
            format!("authority epoch unavailable: {message}"),
        )
    })
}

pub fn router(state: ApiState) -> Router {
    Router::new()
        .route("/health", get(health_ready))
        .route("/health/live", get(health_live))
        .route("/health/ready", get(health_ready))
        .route("/v1/events", post(append_event))
        .route("/v1/workspaces/:workspace_id/snapshot", get(get_snapshot))
        .route("/v1/workspaces/:workspace_id/events", get(get_events))
        .route("/v1/workspaces/:workspace_id/stream", get(stream_workspace))
        .with_state(Arc::new(state))
}

async fn health_live() -> Json<Value> {
    Json(json!({
        "status": "ok",
        "service": "camelot-state-service",
        "live": true
    }))
}

async fn health_ready(State(state): State<Arc<ApiState>>) -> (StatusCode, Json<Value>) {
    let authority_epoch = match current_epoch(&state) {
        Ok(epoch) => epoch,
        Err((status, body)) => return (status, body),
    };
    if state.store.ready().await {
        (
            StatusCode::OK,
            Json(json!({
                "status": "ready",
                "service": "camelot-state-service",
                "schema": EVENT_SCHEMA,
                "authorityEpoch": authority_epoch,
                "dynamicEpoch": state.epoch_source.is_dynamic(),
                "receiptLedger": state.receipt_base_url.as_str(),
                "projectionRule": "RECEIPTED requires a matching receipt/2 ledger record"
            })),
        )
    } else {
        (
            StatusCode::SERVICE_UNAVAILABLE,
            Json(json!({
                "status": "not_ready",
                "service": "camelot-state-service"
            })),
        )
    }
}

async fn verify_receipted_transition(
    state: &ApiState,
    request: &AppendEventRequest,
    authority_epoch: u64,
) -> Result<(), ApiError> {
    if request.event_type != "task.state.changed" {
        return Ok(());
    }
    let change: TaskStatePayload = serde_json::from_value(request.payload.clone())
        .map_err(|err| error(StatusCode::BAD_REQUEST, format!("invalid task state payload: {err}")))?;
    if change.state != TaskState::Receipted {
        return Ok(());
    }
    let receipt_id = request
        .provenance
        .receipt_id
        .as_deref()
        .filter(|value| !value.trim().is_empty())
        .ok_or_else(|| error(StatusCode::CONFLICT, "RECEIPTED requires provenance.receiptId"))?;
    let target = format!(
        "{}/receipts/{}",
        state.receipt_base_url.trim_end_matches('/'),
        receipt_id
    );
    let response = state.client.get(target).send().await.map_err(|err| {
        error(
            StatusCode::SERVICE_UNAVAILABLE,
            format!("receipt ledger unavailable: {err}"),
        )
    })?;
    if response.status() == reqwest::StatusCode::NOT_FOUND {
        return Err(error(
            StatusCode::CONFLICT,
            "referenced receipt does not exist in the ledger",
        ));
    }
    if !response.status().is_success() {
        return Err(error(
            StatusCode::SERVICE_UNAVAILABLE,
            format!("receipt ledger returned {}", response.status()),
        ));
    }
    let receipt: ReceiptProjection = response.json().await.map_err(|err| {
        error(
            StatusCode::BAD_GATEWAY,
            format!("receipt ledger returned invalid JSON: {err}"),
        )
    })?;
    if receipt.schema_version != "receipt/2"
        || receipt.receipt_id != receipt_id
        || receipt.tenant_id != request.tenant_id
        || receipt.workspace_id != request.workspace_id
        || receipt.mission_id != request.mission_id
        || receipt.task_id != change.task_id
        || receipt.authority_epoch != authority_epoch
    {
        return Err(error(
            StatusCode::CONFLICT,
            "receipt scope does not match this task transition",
        ));
    }
    Ok(())
}

async fn append_event(
    State(state): State<Arc<ApiState>>,
    Json(request): Json<AppendEventRequest>,
) -> Result<(StatusCode, Json<WorkspaceEvent>), ApiError> {
    for (name, value) in [
        ("type", request.event_type.as_str()),
        ("tenantId", request.tenant_id.as_str()),
        ("workspaceId", request.workspace_id.as_str()),
        ("cartridgeId", request.cartridge_id.as_str()),
        ("missionId", request.mission_id.as_str()),
        ("traceId", request.trace_id.as_str()),
        ("provenance.source", request.provenance.source.as_str()),
    ] {
        if !bounded(value) {
            return Err(error(StatusCode::BAD_REQUEST, format!("invalid {name}")));
        }
    }
    if !valid_classification(&request.classification) || !valid_visibility(&request.visibility) {
        return Err(error(
            StatusCode::BAD_REQUEST,
            "invalid classification or visibility",
        ));
    }

    let authority_epoch = current_epoch(&state)?;
    verify_receipted_transition(&state, &request, authority_epoch).await?;

    let event = state
        .store
        .append(request, authority_epoch)
        .await
        .map_err(|message| error(StatusCode::CONFLICT, message))?;
    let _ = state.events.send(event.clone());
    Ok((StatusCode::CREATED, Json(event)))
}

async fn get_events(
    Path(workspace_id): Path<String>,
    Query(query): Query<WorkspaceQuery>,
    State(state): State<Arc<ApiState>>,
) -> Result<Json<Vec<WorkspaceEvent>>, ApiError> {
    if !bounded(&workspace_id) || !bounded(&query.tenant_id) {
        return Err(error(StatusCode::BAD_REQUEST, "invalid workspace scope"));
    }
    let events = state
        .store
        .events(
            &query.tenant_id,
            &workspace_id,
            query.after.unwrap_or(-1),
            500,
        )
        .await
        .map_err(|message| error(StatusCode::INTERNAL_SERVER_ERROR, message))?;
    Ok(Json(events))
}

async fn get_snapshot(
    Path(workspace_id): Path<String>,
    Query(query): Query<WorkspaceQuery>,
    State(state): State<Arc<ApiState>>,
) -> Result<Json<crate::model::WorkspaceSnapshot>, ApiError> {
    if !bounded(&workspace_id) || !bounded(&query.tenant_id) {
        return Err(error(StatusCode::BAD_REQUEST, "invalid workspace scope"));
    }
    let authority_epoch = current_epoch(&state)?;
    state
        .store
        .snapshot(query.tenant_id, workspace_id, authority_epoch)
        .await
        .map(Json)
        .map_err(|message| error(StatusCode::INTERNAL_SERVER_ERROR, message))
}

async fn stream_workspace(
    Path(workspace_id): Path<String>,
    Query(query): Query<WorkspaceQuery>,
    State(state): State<Arc<ApiState>>,
) -> Result<Sse<impl Stream<Item = Result<SseEvent, Infallible>>>, ApiError> {
    if !bounded(&workspace_id) || !bounded(&query.tenant_id) {
        return Err(error(StatusCode::BAD_REQUEST, "invalid workspace scope"));
    }
    let after = query.after.unwrap_or(-1);
    let replay = state
        .store
        .events(&query.tenant_id, &workspace_id, after, 1000)
        .await
        .map_err(|message| error(StatusCode::INTERNAL_SERVER_ERROR, message))?;
    let tenant_id = query.tenant_id;
    let mut receiver = state.events.subscribe();

    let output = stream! {
        let mut high_water = after;
        for item in replay {
            high_water = high_water.max(item.sequence);
            if let Ok(data) = serde_json::to_string(&item) {
                yield Ok(SseEvent::default()
                    .id(item.sequence.to_string())
                    .event("workspace-event")
                    .data(data));
            }
        }
        loop {
            match receiver.recv().await {
                Ok(item)
                    if item.tenant_id == tenant_id
                        && item.workspace_id == workspace_id
                        && item.sequence > high_water =>
                {
                    high_water = item.sequence;
                    if let Ok(data) = serde_json::to_string(&item) {
                        yield Ok(SseEvent::default()
                            .id(item.sequence.to_string())
                            .event("workspace-event")
                            .data(data));
                    }
                }
                Ok(_) => {}
                Err(broadcast::error::RecvError::Lagged(skipped)) => {
                    warn!(skipped, "workspace stream lagged; projection client must replay");
                    yield Ok(SseEvent::default()
                        .event("replay-required")
                        .data(high_water.to_string()));
                }
                Err(broadcast::error::RecvError::Closed) => break,
            }
        }
    };

    Ok(Sse::new(output).keep_alive(
        KeepAlive::new()
            .interval(Duration::from_secs(15))
            .text("camelot-state"),
    ))
}
