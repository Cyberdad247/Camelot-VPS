use crate::{
    model::{
        bounded, valid_classification, valid_visibility, AppendEventRequest, WorkspaceEvent,
        WorkspaceQuery, EVENT_SCHEMA,
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
use futures_util::Stream;
use serde_json::{json, Value};
use std::{convert::Infallible, sync::Arc, time::Duration};
use tokio::sync::broadcast;
use tracing::warn;

#[derive(Clone)]
pub struct ApiState {
    pub store: StateStore,
    pub authority_epoch: u64,
    pub events: broadcast::Sender<WorkspaceEvent>,
}

type ApiError = (StatusCode, Json<Value>);

fn error(status: StatusCode, message: impl Into<String>) -> ApiError {
    (status, Json(json!({ "error": message.into() })))
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
    if state.store.ready().await {
        (
            StatusCode::OK,
            Json(json!({
                "status": "ready",
                "service": "camelot-state-service",
                "schema": EVENT_SCHEMA,
                "authorityEpoch": state.authority_epoch,
                "projectionRule": "RECEIPTED requires receipt-backed provenance"
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

    let event = state
        .store
        .append(request, state.authority_epoch)
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
    state
        .store
        .snapshot(query.tenant_id, workspace_id, state.authority_epoch)
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
