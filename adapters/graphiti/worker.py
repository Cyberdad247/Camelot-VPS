from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GraphitiWorker")

app = FastAPI(title="Camelot Graphiti Adapter")

class SourceAdmission(BaseModel):
    tenant_id: str
    source_uri: str
    content_hash: str
    policy_decision_id: str

@app.post("/ingest")
async def ingest_source(admission: SourceAdmission):
    # Rule Enforcement:
    # 1. Store canonical in Neo4j
    # 2. Extract entities/facts
    # 3. Emit memory.promoted receipts
    logger.info(f"Ingesting {admission.source_uri} for tenant {admission.tenant_id}")
    return {
        "status": "quarantined_for_extraction",
        "job_id": "JOB-9999",
        "neo4j_nodes_created": 0
    }

if __name__ == "__main__":
    import uvicorn
    # Worker runs on internal port 3007
    uvicorn.run(app, host="127.0.0.1", port=3007)
