"""
OptiStock AI - Background Automation Scheduler
Provides multi-worker safe, resilient periodic job execution.
Features:
- Distributed database mutex locking (safe for Render web workers & multi-process Gunicorn)
- Dynamic per-workflow interval checks and database-backed Enable/Disable flags
- Standalone runner mode (`python -m engine.automation_scheduler`) for Render background worker
- Optional in-process threading runner for single-container local deployments
- Graceful shutdown handling on SIGINT/SIGTERM
"""

import os
import time
import socket
import signal
import logging
import threading
from datetime import datetime, timezone, timedelta
from typing import Optional

from engine.automation_db import (
    init_db,
    get_db_connection,
    acquire_scheduler_lock,
    release_scheduler_lock,
)
from engine.automation_engine import execute_workflow

logger = logging.getLogger("optistock.automation.scheduler")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s")

LOCK_NAME = "OPTISTOCK_SCHEDULER_LEADER"
WORKER_IDENTIFIER = f"{socket.gethostname()}-{os.getpid()}"

# Global flag for graceful termination
_STOP_REQUESTED = False


def signal_handler(signum, frame):
    global _STOP_REQUESTED
    logger.info("Termination signal %s received. Stopping scheduler loop...", signum)
    _STOP_REQUESTED = True


def run_scheduler_tick(db_path: Optional[str] = None):
    """
    Performs a single evaluation pass:
    1. Attempts to acquire or renew the distributed leader lock.
    2. If lock acquired, checks all enabled workflows whose next_run_at <= now.
    3. Triggers execution and computes next scheduled time.
    """
    is_leader = acquire_scheduler_lock(
        lock_name=LOCK_NAME,
        worker_id=WORKER_IDENTIFIER,
        timeout_seconds=45,
        db_path=db_path
    )

    if not is_leader:
        logger.debug("Worker %s is follower (leader lock held by another process). Skipping tick.", WORKER_IDENTIFIER)
        return

    conn = get_db_connection(db_path)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    try:
        workflows = conn.execute("""
        SELECT * FROM automation_configs 
        WHERE enabled = 1;
        """).fetchall()

        for wf in workflows:
            wf_id = wf["id"]
            next_run_str = wf["next_run_at"]

            should_run = False
            if not next_run_str:
                should_run = True
            else:
                try:
                    next_run_dt = datetime.fromisoformat(next_run_str.replace("Z", "+00:00"))
                    if now >= next_run_dt:
                        should_run = True
                except Exception:
                    should_run = True

            if should_run:
                logger.info("Triggering scheduled run for workflow: %s (%s)", wf_id, wf["name"])
                # Execute workflow
                result = execute_workflow(workflow_id=wf_id, dry_run=False, db_path=db_path)
                logger.info("Workflow %s completed with status: %s (Actions: %s)",
                            wf_id, result.get("status"), result.get("actions_generated", 0))

    except Exception as e:
        logger.exception("Error during scheduler tick: %s", e)
    finally:
        conn.close()


def scheduler_worker_loop(db_path: Optional[str] = None, poll_interval_seconds: int = 15):
    """
    Main blocking loop for running the scheduler service.
    Polls every `poll_interval_seconds` seconds.
    """
    global _STOP_REQUESTED
    logger.info("OptiStock AI Automation Scheduler Worker started (ID: %s)", WORKER_IDENTIFIER)
    init_db(db_path)

    # Register OS signals for graceful shutdown
    try:
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    except Exception:
        # Some OS/threading contexts do not allow signal registration
        pass

    while not _STOP_REQUESTED:
        try:
            run_scheduler_tick(db_path=db_path)
        except Exception as exc:
            logger.error("Unhandled error in scheduler loop: %s", exc)

        # Sleep in small slices to respond promptly to stop requests
        for _ in range(poll_interval_seconds * 2):
            if _STOP_REQUESTED:
                break
            time.sleep(0.5)

    logger.info("Scheduler worker stopping. Releasing leader lock...")
    try:
        release_scheduler_lock(LOCK_NAME, WORKER_IDENTIFIER, db_path=db_path)
    except Exception:
        pass
    logger.info("Scheduler worker stopped cleanly.")


# Thread reference for in-process mode
_in_process_thread: Optional[threading.Thread] = None


def start_in_process_scheduler(db_path: Optional[str] = None, poll_interval_seconds: int = 20) -> threading.Thread:
    """
    Starts the scheduler loop in a background daemon thread.
    Useful for local dev server or single-container web instances.
    """
    global _in_process_thread, _STOP_REQUESTED
    if _in_process_thread and _in_process_thread.is_alive():
        logger.info("In-process scheduler thread is already running.")
        return _in_process_thread

    _STOP_REQUESTED = False
    _in_process_thread = threading.Thread(
        target=scheduler_worker_loop,
        kwargs={"db_path": db_path, "poll_interval_seconds": poll_interval_seconds},
        name="OptiStockAutomationScheduler",
        daemon=True
    )
    _in_process_thread.start()
    logger.info("In-process automation scheduler thread started successfully.")
    return _in_process_thread


def stop_in_process_scheduler():
    """Stops the in-process background scheduler."""
    global _STOP_REQUESTED
    _STOP_REQUESTED = True


if __name__ == "__main__":
    # When executed directly as `python -m engine.automation_scheduler` (Render Background Worker)
    poll_sec = int(os.environ.get("SCHEDULER_POLL_INTERVAL", "15"))
    scheduler_worker_loop(poll_interval_seconds=poll_sec)
