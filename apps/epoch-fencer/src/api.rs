use crate::{
    auth::{bearer_allowed, promotion_allowed},
    io::publish_certificate,
    model::{BrainStatus, EpochStatus, HeartbeatRequest, PromotionRequest, PromotionResult},
    store::EpochStore,
};
use axum::{
    extract::State,
    http::{HeaderMap, StatusCode},
    Json,
};
use chrono::Utc;
use serde_json::{json, Value};
use std::{path::PathBuf, sync::Arc};

#[derive(Clone)]
pub struct AppState {
    pub store: EpochStore,
    pub api_token: Arc<String>,
    pub promotion_token: Arc<String>,
    pub certificate_path: Arc<PathBuf>,
    pub signer_public_key: Arc<String>,
}

type ApiError = (StatusCode, Json<Value>);

fn error(status: StatusCode, message: impl Into<String>) -> ApiError {
    (status, Json(json!({ "error": message.into() })))
}

pub async fn health_live() -> Json<Value> {
    Json(json!({ "status": "ok", "service": "epoch-fencer", "live": true }))
}

pub async fn health_ready(State(state): State<AppState>) -> Result<Json<Value>, ApiError> {
    let current = state
        .store
        .current()
        .await
        .map_err(|message| error(StatusCode::SERVICE_UNAVAILABLE, message))?;
    if !state.certificate_path.exists() {
        return Err(error(
            StatusCode::SERVICE_UNAVAILABLE,
            "runtime epoch certificate has not been published",
        ));
    }
    Ok(Json(json!({
        "status": "ready",
        "service": "epoch-fencer",
        "schema": current.schema_version,
        "authorityEpoch": current.epoch,
        "activeBrain": current.active_brain,
        "signerPublicKey": state.signer_public_key.as_str()
    })))
}

pub async fn status(State(state): State<AppState>) -> Result<Json<EpochStatus>, ApiError> {
    let certificate = state
        .store
        .current()
        .await
        .map_err(|message| error(StatusCode::SERVICE_UNAVAILABLE, message))?;
    let heartbeats = state
        .store
        .heartbeats()
        .await
        .map_err(|message| error(StatusCode::SERVICE_UNAVAILABLE, message))?;
    let brains = heartbeats
        .into_iter()
        .map(|heartbeat| BrainStatus {
            age_seconds: (Utc::now() - heartbeat.observed_at).num_seconds().max(0),
            fresh: state.store.heartbeat_is_fresh(&heartbeat),
            heartbeat,
        })
        .collect();
    Ok(Json(EpochStatus { certificate, brains }))
}

pub async fn heartbeat(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<HeartbeatRequest>,
) -> Result<(StatusCode, Json<camelot_epoch::BrainHeartbeat>), ApiError> {
    if !bearer_allowed(&headers, &state.api_token) {
        return Err(error(StatusCode::UNAUTHORIZED, "invalid fencer credential"));
    }
    let heartbeat = state
        .store
        .heartbeat(request)
        .await
        .map_err(|message| error(StatusCode::CONFLICT, message))?;
    Ok((StatusCode::ACCEPTED, Json(heartbeat)))
}

pub async fn promote(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<PromotionRequest>,
) -> Result<(StatusCode, Json<PromotionResult>), ApiError> {
    if !bearer_allowed(&headers, &state.api_token) {
        return Err(error(StatusCode::UNAUTHORIZED, "invalid fencer credential"));
    }
    if !promotion_allowed(&headers, &state.promotion_token) {
        return Err(error(
            StatusCode::FORBIDDEN,
            "promotion requires server-side promotion assertion",
        ));
    }
    let before = state
        .store
        .current()
        .await
        .map_err(|message| error(StatusCode::SERVICE_UNAVAILABLE, message))?;
    let source = state
        .store
        .heartbeats()
        .await
        .map_err(|message| error(StatusCode::SERVICE_UNAVAILABLE, message))?
        .into_iter()
        .find(|heartbeat| heartbeat.brain_id == before.active_brain);
    let source_fresh = source
        .as_ref()
        .map(|heartbeat| heartbeat.ready && state.store.heartbeat_is_fresh(heartbeat))
        .unwrap_or(false);
    let certificate = state
        .store
        .promote(request)
        .await
        .map_err(|message| error(StatusCode::CONFLICT, message))?;
    publish_certificate(&state.certificate_path, &certificate)
        .map_err(|message| error(StatusCode::INTERNAL_SERVER_ERROR, message))?;
    Ok((
        StatusCode::CREATED,
        Json(PromotionResult {
            target_receipt_head_sequence: certificate.receipt_head_sequence,
            source_fresh,
            certificate,
        }),
    ))
}
