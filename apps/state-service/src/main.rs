mod api;
mod model;
mod store;

use api::ApiState;
use camelot_epoch::EpochSource;
use std::{env, net::IpAddr, sync::Arc};
use store::StateStore;
use tokio::sync::broadcast;
use tracing::info;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let epoch_source = Arc::new(
        EpochSource::from_environment().expect("load signed authority epoch source"),
    );
    let boot_epoch = epoch_source
        .current_epoch()
        .expect("verify current authority epoch at State Service startup");

    let database_url = env::var("CAMELOT_STATE_DATABASE_URL")
        .unwrap_or_else(|_| "sqlite:///var/lib/camelot/state/runtime.sqlite3".into());
    let receipt_base_url = env::var("CAMELOT_RECEIPT_URL")
        .unwrap_or_else(|_| "http://127.0.0.1:3001".into());
    let store = StateStore::open(&database_url)
        .await
        .expect("initialize authoritative state database");
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(5))
        .build()
        .expect("build receipt verification client");
    let (events, _) = broadcast::channel(1024);
    let app = api::router(ApiState {
        store,
        epoch_source: epoch_source.clone(),
        events,
        receipt_base_url: Arc::new(receipt_base_url),
        client,
    });

    let host = env::var("CAMELOT_STATE_HOST").unwrap_or_else(|_| "127.0.0.1".into());
    let parsed_host: IpAddr = host
        .parse()
        .expect("CAMELOT_STATE_HOST must be an IP address");
    if !parsed_host.is_loopback() {
        panic!("Camelot State Service must remain loopback-only behind the projection gateway");
    }
    let port = env::var("CAMELOT_STATE_PORT")
        .ok()
        .and_then(|value| value.parse::<u16>().ok())
        .unwrap_or(3012);

    let listener = tokio::net::TcpListener::bind((parsed_host, port))
        .await
        .expect("bind state service");
    info!(
        authority_epoch = boot_epoch,
        dynamic_epoch = epoch_source.is_dynamic(),
        "Camelot authoritative workspace state service online"
    );
    axum::serve(listener, app)
        .await
        .expect("state service failed");
}
