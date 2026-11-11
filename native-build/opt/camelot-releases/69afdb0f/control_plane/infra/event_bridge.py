# SPDX-License-Identifier: MIT

"""Event Bridge — Ingests OpenClaw events and routes to Omni-Router.

# HITL: file-ops pre-approved — writes bounded to event queue and runtime logs
"""

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

# Add control_plane to path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from control_plane.soul_router import SoulRouter

app = FastAPI(title="Camelot Event Bridge")
router = SoulRouter()

# Paths
CAMELOT_HOME = Path(os.environ.get("CAMELOT_OS_HOME", Path.home() / "CAMELOT_OS")).resolve()
QUEUE_FILE = CAMELOT_HOME / "logs" / "harness_queue.jsonl"

class ClawEvent(BaseModel):
    type: str
    timestamp: int
    payload: dict

SECRET = os.getenv("CAMELOT_EVENT_SECRET", "v400-omni-gate")

def _submit_task(knight: str, directive: str, priority: int = 1):
    task_id = f"claw-{uuid.uuid4().hex[:8]}"
    task = {
        "id": task_id,
        "knight": knight,
        "directive": directive,
        "priority": priority,
        "submitted": datetime.now(timezone.utc).isoformat(),
        "source": "openclaw"
    }
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(QUEUE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(task) + "\n")
    return task_id

@app.post("/v1/events")
async def handle_event(event: ClawEvent, authorization: str = Header(None)):
    if not authorization or authorization != f"Bearer {SECRET}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Log to file
    log_entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "event": event.dict()
    }
    event_log = CAMELOT_HOME / "logs" / "events.jsonl"
    event_log.parent.mkdir(parents=True, exist_ok=True)
    with open(event_log, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")

    print(f"📡 [EVENT] Received {event.type} from OpenClaw")
    
    if event.type == "message_received":
        content = event.payload.get("content", "")
        _sender = event.payload.get("from", "unknown")
        
        if content:
            # Trigger Omni-Routing for the incoming message
            print(f"🤖 [ROUTING] Processing intent: {content}")
            decision = router.route(content)
            print(f"🎯 [DECISION] Routed to {decision.knight_id} ({decision.engine})")
            
            # Dispatch to Harness
            task_id = _submit_task(decision.knight_id, content)
            print(f"🚀 [DISPATCH] Task {task_id} queued for {decision.knight_id}")
            return {"status": "dispatched", "task_id": task_id, "knight": decision.knight_id}
            
    return {"status": "ingested"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8088)
