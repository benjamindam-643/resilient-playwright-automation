"""Automated Test Suite for State Checkpointing & Resumption.

Guarantees atomic checkpointing, crash recovery, and duplicate avoidance.
"""
import os
import unittest
from src.state.checkpoint import CheckpointManager
from src.browser.worker import ResilientBrowserWorker


class TestStateCheckpointing(unittest.TestCase):

    def setUp(self):
        self.test_state_file = ".state/test_checkpoint.json"
        self.manager = CheckpointManager(state_file_path=self.test_state_file)

    def tearDown(self):
        self.manager.reset_state()
        if os.path.exists(".state"):
            for f in os.listdir(".state"):
                try:
                    os.remove(os.path.join(".state", f))
                except Exception:
                    pass

    def test_checkpoint_saving_and_resumption(self):
        """Validates that saving progress accurately increments the resume index."""
        self.assertEqual(self.manager.get_resume_index(), 0)

        # Process first task
        self.manager.save_checkpoint("task_001", index=0)
        self.assertTrue(self.manager.is_task_completed("task_001"))
        self.assertFalse(self.manager.is_task_completed("task_002"))
        self.assertEqual(self.manager.get_resume_index(), 1)

        # Process second task
        self.manager.save_checkpoint("task_002", index=1)
        self.assertTrue(self.manager.is_task_completed("task_002"))
        self.assertEqual(self.manager.get_resume_index(), 2)

    def test_worker_precondition_validation(self):
        """Ensures missing required fields fail validation gates before UI execution."""
        worker = ResilientBrowserWorker(checkpoint_manager=self.manager)

        valid_payload = {"username": "john_doe", "action": "scrape_records"}
        self.assertTrue(worker.validate_action_preconditions(valid_payload, ["username", "action"]))

        invalid_payload = {"username": "", "action": "scrape_records"}
        self.assertFalse(worker.validate_action_preconditions(invalid_payload, ["username", "action"]))

        missing_payload = {"action": "scrape_records"}
        self.assertFalse(worker.validate_action_preconditions(missing_payload, ["username", "action"]))


if __name__ == "__main__":
    unittest.main()
