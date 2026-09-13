mod api;
mod model;
mod store;

use api::ApiState;
use std::{env, net::IpAddr, sync::Arc};
use store::StateStore;
use tokio::sync::broadcast;
use tracing::info;

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt::init();

    let authority_epoch = env::var("CAMELOT_AUTHORITY_EPOCH")
        .ok()
        .and_then(|value| value.parse::<u64>().ok())
        .unwrap_or(1);
    if authority_epoch == 0 {
        panic!("CAMELOT_AUTHORITY_EPOCH must be greater than zero");
    }

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
        authority_epoch,
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
        authority_epoch,
        "Camelot authoritative workspace state service online"
    );
    axum::serve(listener, app)
        .await
        .expect("state service failed");
}
