"""Resilient Browser Automation Worker with Self-Healing Actions.

Automates complex multi-step web interactions with pre-action validation,
resilient locator strategies, and safe timeout recovery.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional
from src.state.checkpoint import CheckpointManager

logger = logging.getLogger(__name__)


class ResilientBrowserWorker:
    """Manages robust browser automation runs with state recovery and validation gates."""

    def __init__(
        self,
        checkpoint_manager: Optional[CheckpointManager] = None,
        max_retries: int = 3,
        backoff_sec: float = 2.0,
    ) -> None:
        self.checkpoint_manager = checkpoint_manager or CheckpointManager()
        self.max_retries = max_retries
        self.backoff_sec = backoff_sec
        self.is_running = False

    def validate_action_preconditions(self, payload: Dict[str, Any], required_fields: List[str]) -> bool:
        """Pre-action validation gate: ensures all required parameters are valid before UI execution."""
        for field in required_fields:
            val = payload.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                logger.error(f"[Validation Guard] Missing or invalid required field: {field!r}")
                return False
        return True

    def execute_with_retry(
        self,
        action_name: str,
        action_func: Callable[[], Any],
    ) -> Any:
        """Executes an action with exponential backoff on transient network or locator errors."""
        last_exception = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return action_func()
            except Exception as exc:
                last_exception = exc
                delay = self.backoff_sec * (2 ** (attempt - 1))
                logger.warning(
                    f"[{action_name}] Attempt {attempt}/{self.max_retries} failed: {exc}. Retrying in {delay}s..."
                )
                time.sleep(delay)

        raise RuntimeError(f"Action {action_name!r} failed after {self.max_retries} attempts.") from last_exception

    def process_task_batch(
        self,
        tasks: List[Dict[str, Any]],
        task_executor: Callable[[Dict[str, Any]], bool],
    ) -> Dict[str, int]:
        """Iterates through tasks, skipping already completed ones and updating checkpoints."""
        self.is_running = True
        start_index = self.checkpoint_manager.get_resume_index()
        processed_count = 0
        skipped_count = 0

        logger.info(f"[Batch Runner] Resuming execution from index {start_index} of {len(tasks)} tasks.")

        for idx in range(start_index, len(tasks)):
            if not self.is_running:
                logger.info("[Batch Runner] Execution paused gracefully.")
                break

            task = tasks[idx]
            task_id = str(task.get("id", f"task_{idx}"))

            if self.checkpoint_manager.is_task_completed(task_id):
                skipped_count += 1
                continue

            # Execute single task safely
            success = task_executor(task)
            if success:
                self.checkpoint_manager.save_checkpoint(task_id=task_id, index=idx, status="RUNNING")
                processed_count += 1
            else:
                logger.error(f"[Batch Runner] Task {task_id} failed. Execution halted for inspection.")
                break

        return {"processed": processed_count, "skipped": skipped_count}

    def stop(self) -> None:
        self.is_running = False
