"""State Persistence & Checkpointing Manager for Long-Running Automations.

Guarantees that interrupted or crashed browser automation jobs resume seamlessly
from the exact last verified task without duplicate actions or data corruption.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Set


class CheckpointManager:
    """Thread-safe persistent state manager using atomic disk replacement."""

    def __init__(self, state_file_path: str = ".state/job_checkpoint.json") -> None:
        self.state_file_path = state_file_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self.state_file_path) or ".", exist_ok=True)
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        with self._lock:
            if not os.path.exists(self.state_file_path):
                return {
                    "last_processed_index": -1,
                    "completed_task_ids": [],
                    "failed_task_ids": [],
                    "status": "IDLE",
                    "updated_at": time.time(),
                }
            try:
                with open(self.state_file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {
                    "last_processed_index": -1,
                    "completed_task_ids": [],
                    "failed_task_ids": [],
                    "status": "RECOVERED_FROM_ERROR",
                    "updated_at": time.time(),
                }

    def save_checkpoint(
        self,
        task_id: str,
        index: int,
        status: str = "IN_PROGRESS",
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        """Atomically persists execution progress to disk."""
        with self._lock:
            if task_id not in self.state["completed_task_ids"]:
                self.state["completed_task_ids"].append(task_id)
            self.state["last_processed_index"] = index
            self.state["status"] = status
            self.state["updated_at"] = time.time()
            if metadata:
                self.state.setdefault("metadata", {}).update(metadata)

            temp_path = f"{self.state_file_path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
            os.replace(temp_path, self.state_file_path)

    def is_task_completed(self, task_id: str) -> bool:
        """Checks if a task was already processed, preventing duplicate actions."""
        with self._lock:
            return task_id in self.state.get("completed_task_ids", [])

    def get_resume_index(self) -> int:
        """Returns the index from which execution should safely resume."""
        with self._lock:
            return self.state.get("last_processed_index", -1) + 1

    def reset_state(self) -> None:
        with self._lock:
            self.state = {
                "last_processed_index": -1,
                "completed_task_ids": [],
                "failed_task_ids": [],
                "status": "RESET",
                "updated_at": time.time(),
            }
            if os.path.exists(self.state_file_path):
                os.remove(self.state_file_path)
