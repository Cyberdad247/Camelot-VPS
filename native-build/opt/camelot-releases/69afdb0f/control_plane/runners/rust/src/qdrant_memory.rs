// SPDX-License-Identifier: MIT

// qdrant_memory.rs — Qdrant Cloud REST client for CAMELOT harness runner
//
// Cluster:  2b135578-55c5-43d0-b82a-f5061f4ff6ee (GCP us-east4)
// Protocol: HTTPS REST port 6333
// Auth:     JWT API key via QDRANT_API_KEY env var
// URL env:  QDRANT_URL (default: cluster REST endpoint)

use anyhow::{Context, Result};
use reqwest::{Client, ClientBuilder};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::env;
use std::time::Duration;

const DEFAULT_REST_URL: &str =
    "https://2b135578-55c5-43d0-b82a-f5061f4ff6ee.us-east4-0.gcp.cloud.qdrant.io";

pub struct QdrantRest {
    client: Client,
    base_url: String,
    api_key: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CollectionList {
    pub result: CollectionListResult,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CollectionListResult {
    pub collections: Vec<CollectionEntry>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CollectionEntry {
    pub name: String,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SearchResponse {
    pub result: Vec<SearchHit>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SearchHit {
    pub id: Value,
    pub score: f32,
    pub payload: Option<HashMap<String, Value>>,
}

impl QdrantRest {
    pub fn new() -> Result<Self> {
        let base_url = env::var("QDRANT_URL")
            .unwrap_or_else(|_| DEFAULT_REST_URL.to_string());
        let api_key = env::var("QDRANT_API_KEY")
            .context("QDRANT_API_KEY must be set")?;

        let client = ClientBuilder::new()
            .timeout(Duration::from_secs(10))
            .use_rustls_tls()
            .build()?;

        Ok(QdrantRest { client, base_url, api_key })
    }

    fn auth_header(&self) -> String {
        format!("Bearer {}", self.api_key)
    }

    pub async fn list_collections(&self) -> Result<Vec<String>> {
        let resp: CollectionList = self
            .client
            .get(format!("{}/collections", self.base_url))
            .header("Authorization", self.auth_header())
            .send()
            .await?
            .error_for_status()?
            .json()
            .await?;

        Ok(resp.result.collections.into_iter().map(|c| c.name).collect())
    }

    pub async fn create_collection(&self, name: &str, vector_size: u64) -> Result<()> {
        let body = json!({
            "vectors": {
                "size": vector_size,
                "distance": "Cosine"
            }
        });

        self.client
            .put(format!("{}/collections/{}", self.base_url, name))
            .header("Authorization", self.auth_header())
            .json(&body)
            .send()
            .await?
            .error_for_status()?;

        Ok(())
    }

    pub async fn ensure_collection(&self, name: &str, vector_size: u64) -> Result<()> {
        let cols = self.list_collections().await?;
        if !cols.contains(&name.to_string()) {
            self.create_collection(name, vector_size).await?;
        }
        Ok(())
    }

    pub async fn upsert(
        &self,
        collection: &str,
        id: u64,
        vector: Vec<f32>,
        payload: HashMap<String, Value>,
    ) -> Result<()> {
        let body = json!({
            "points": [{
                "id": id,
                "vector": vector,
                "payload": payload
            }]
        });

        self.client
            .put(format!("{}/collections/{}/points?wait=true", self.base_url, collection))
            .header("Authorization", self.auth_header())
            .json(&body)
            .send()
            .await?
            .error_for_status()?;

        Ok(())
    }

    pub async fn search(
        &self,
        collection: &str,
        vector: Vec<f32>,
        limit: u64,
    ) -> Result<Vec<SearchHit>> {
        let body = json!({
            "vector": vector,
            "limit": limit,
            "with_payload": true
        });

        let resp: SearchResponse = self
            .client
            .post(format!("{}/collections/{}/points/search", self.base_url, collection))
            .header("Authorization", self.auth_header())
            .json(&body)
            .send()
            .await?
            .error_for_status()?
            .json()
            .await?;

        Ok(resp.result)
    }

    pub async fn probe(&self) -> Result<Value> {
        let cols = self.list_collections().await?;
        Ok(json!({
            "backend": "qdrant-cloud-rest",
            "status": "live",
            "cluster": "2b135578-55c5-43d0-b82a-f5061f4ff6ee",
            "region": "gcp-us-east4",
            "collections": cols
        }))
    }
}
