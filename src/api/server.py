"""Internal Monitoring & Control API for Browser Automation Jobs.

Provides HTTP control endpoints to supervise, trigger, pause, and inspect
long-running browser automation runs.
"""
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from src.state.checkpoint import CheckpointManager
from src.browser.worker import ResilientBrowserWorker

app = FastAPI(title="Browser Automation Controller API", version="1.0.0")

checkpoint_mgr = CheckpointManager()
worker = ResilientBrowserWorker(checkpoint_manager=checkpoint_mgr)


class JobTriggerRequest(BaseModel):
    job_id: str
    target_tasks: List[Dict[str, Any]]


@app.get("/health")
def health():
    return {"status": "ok", "service": "browser-automation-controller"}


@app.get("/jobs/status")
def get_job_status():
    """Inspects execution state, last processed index, and completion history."""
    state = checkpoint_mgr.state
    return {
        "status": state.get("status", "IDLE"),
        "last_processed_index": state.get("last_processed_index", -1),
        "total_completed": len(state.get("completed_task_ids", [])),
        "is_worker_running": worker.is_running,
        "last_updated": state.get("updated_at"),
    }


@app.post("/jobs/pause")
def pause_job():
    """Gracefully pauses execution at the next checkpoint boundary."""
    worker.stop()
    return {"success": True, "message": "Worker signaled to pause gracefully."}


@app.post("/jobs/reset")
def reset_job_state():
    """Resets checkpoint tracking to allow fresh replay if explicitly needed."""
    checkpoint_mgr.reset_state()
    return {"success": True, "message": "Checkpoint state reset successfully."}
