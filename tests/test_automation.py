"""
OptiStock AI - Automated Workflows & Reliability Test Suite
Validates:
1. Auto-Replenishment (Safety stock, ROP, duplicate prevention, manager approval)
2. Expiry Rescue (FEFO shelf-life scan, transit feasibility constraint, stock bounds)
3. Distribution Optimization (Multi-warehouse comparison, ranked alternatives, sample tagging)
4. Delivery Monitoring (Deadline audit, delayed shipment detection, checkpoint notes)
5. Automated Alert Center (Deduplication, severity tiers, acknowledge & resolve)
6. Distributed Scheduler & Mutex Locking (Multi-worker race prevention)
7. Dry-Run Mode & Transaction Safety
"""

import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from engine.automation_db import (
    init_db,
    get_db_connection,
    acquire_scheduler_lock,
    release_scheduler_lock,
)
from engine.automation_engine import (
    run_auto_replenishment,
    run_expiry_rescue,
    run_distribution_optimization,
    run_delivery_monitoring,
    execute_workflow,
    approve_replenishment,
    reject_replenishment,
    approve_expiry_rescue,
    reject_expiry_rescue,
    resolve_alert,
    acknowledge_alert,
)


class TestAutomationSystem(unittest.TestCase):

    def setUp(self):
        # Create an isolated temporary SQLite database for each test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_automation.db")
        init_db(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    # -----------------------------------------------------------------------
    # Test 1: Database Initialization & Schema Integrity
    # -----------------------------------------------------------------------
    def test_database_initialization(self):
        conn = get_db_connection(self.db_path)
        try:
            # Check workflow configurations are seeded
            configs = conn.execute("SELECT id, name, enabled FROM automation_configs").fetchall()
            workflow_ids = [c["id"] for c in configs]
            self.assertIn("auto_replenishment", workflow_ids)
            self.assertIn("expiry_rescue", workflow_ids)
            self.assertIn("distribution_optimization", workflow_ids)
            self.assertIn("delivery_monitoring", workflow_ids)

            # Check initial seeded shipments exist
            shipment_cnt = conn.execute("SELECT COUNT(*) as cnt FROM delivery_shipments").fetchone()["cnt"]
            self.assertGreaterEqual(shipment_cnt, 5)
        finally:
            conn.close()

    # -----------------------------------------------------------------------
    # Test 2: Distributed Mutex Locking (Multi-Worker Safety)
    # -----------------------------------------------------------------------
    def test_distributed_scheduler_locking(self):
        lock_name = "TEST_LEADER_LOCK"
        worker_1 = "worker-alpha-101"
        worker_2 = "worker-beta-202"

        # Worker 1 acquires lock
        acquired_1 = acquire_scheduler_lock(lock_name, worker_1, timeout_seconds=10, db_path=self.db_path)
        self.assertTrue(acquired_1)

        # Worker 2 attempts to acquire same lock -> must fail
        acquired_2 = acquire_scheduler_lock(lock_name, worker_2, timeout_seconds=10, db_path=self.db_path)
        self.assertFalse(acquired_2)

        # Worker 1 releases lock
        release_scheduler_lock(lock_name, worker_1, db_path=self.db_path)

        # Worker 2 now acquires lock successfully
        acquired_2_retry = acquire_scheduler_lock(lock_name, worker_2, timeout_seconds=10, db_path=self.db_path)
        self.assertTrue(acquired_2_retry)

    # -----------------------------------------------------------------------
    # Test 3: Auto-Replenishment Workflow & Duplicate Prevention
    # -----------------------------------------------------------------------
    def test_auto_replenishment_workflow(self):
        # 1. Dry run execution
        dry_res = run_auto_replenishment(dry_run=True, db_path=self.db_path)
        self.assertEqual(dry_res["status"], "DRY_RUN")
        self.assertGreater(dry_res["actions_generated"], 0)

        # Confirm no actual records were written in dry run
        conn = get_db_connection(self.db_path)
        req_count = conn.execute("SELECT COUNT(*) as cnt FROM replenishment_requests").fetchone()["cnt"]
        self.assertEqual(req_count, 0)
        conn.close()

        # 2. Real execution
        real_res = run_auto_replenishment(dry_run=False, db_path=self.db_path)
        self.assertEqual(real_res["status"], "SUCCESS")
        self.assertGreater(real_res["actions_generated"], 0)

        conn = get_db_connection(self.db_path)
        requests = conn.execute("SELECT * FROM replenishment_requests WHERE status = 'PENDING_APPROVAL'").fetchall()
        self.assertGreater(len(requests), 0)
        first_req = requests[0]
        self.assertEqual(first_req["status"], "PENDING_APPROVAL")
        self.assertGreater(first_req["suggested_quantity"], 0)
        self.assertIsNone(first_req["approved_by"])  # NEVER auto-purchases without approval!
        conn.close()

        # 3. Duplicate Prevention: Run again immediately -> actions_generated must be 0 for pending items
        rerun_res = run_auto_replenishment(dry_run=False, db_path=self.db_path)
        self.assertEqual(rerun_res["actions_generated"], 0)

    # -----------------------------------------------------------------------
    # Test 4: Manager Approval & Rejection Lifecycle
    # -----------------------------------------------------------------------
    def test_replenishment_approval_lifecycle(self):
        run_auto_replenishment(dry_run=False, db_path=self.db_path)

        conn = get_db_connection(self.db_path)
        req = conn.execute("SELECT id FROM replenishment_requests LIMIT 1").fetchone()
        req_id = req["id"]
        conn.close()

        # Approve by manager
        app_res = approve_replenishment(req_id, manager_name="Rajesh Director", notes="Approved for peak weekend", db_path=self.db_path)
        self.assertTrue(app_res["success"])

        conn = get_db_connection(self.db_path)
        updated = conn.execute("SELECT * FROM replenishment_requests WHERE id = ?", (req_id,)).fetchone()
        self.assertEqual(updated["status"], "APPROVED")
        self.assertEqual(updated["approved_by"], "Rajesh Director")
        self.assertIn("peak weekend", updated["manager_notes"])
        conn.close()

        # Cannot approve twice
        double_app = approve_replenishment(req_id, manager_name="Another Manager", db_path=self.db_path)
        self.assertFalse(double_app["success"])

    # -----------------------------------------------------------------------
    # Test 5: Expiry Rescue Workflow & Transit Constraints
    # -----------------------------------------------------------------------
    def test_expiry_rescue_workflow(self):
        # Run expiry rescue
        res = run_expiry_rescue(dry_run=False, db_path=self.db_path)
        self.assertEqual(res["status"], "SUCCESS")

        conn = get_db_connection(self.db_path)
        transfers = conn.execute("SELECT * FROM expiry_rescue_transfers").fetchall()
        self.assertGreater(len(transfers), 0)

        for t in transfers:
            # Transit constraint: Must arrive with usable shelf life
            self.assertGreater(t["remaining_shelf_life_days"], 1.0)
            # Quantity constraint: Never exceed available batch quantity
            self.assertLessEqual(t["transfer_quantity"], t["available_batch_quantity"])
            # Status must require manager approval
            self.assertEqual(t["status"], "PENDING_APPROVAL")
            # Reason must be clearly explained
            self.assertTrue(len(t["reason"]) > 20)

        first_id = transfers[0]["id"]
        conn.close()

        # Manager approval test
        app_res = approve_expiry_rescue(first_id, manager_name="Warehouse Ops Lead", db_path=self.db_path)
        self.assertTrue(app_res["success"])

    # -----------------------------------------------------------------------
    # Test 6: Distribution Optimization & Sample Tagging
    # -----------------------------------------------------------------------
    def test_distribution_optimization_workflow(self):
        res = run_distribution_optimization(dry_run=False, db_path=self.db_path)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["data_classification"], "SIMULATED_SAMPLE")
        self.assertGreater(res["actions_generated"], 0)

        conn = get_db_connection(self.db_path)
        recs = conn.execute("SELECT * FROM distribution_recommendations WHERE status = 'ACTIVE'").fetchall()
        self.assertGreater(len(recs), 0)

        for r in recs:
            # Check ranking
            self.assertIn(r["warehouse_rank"], (1, 2, 3))
            self.assertGreater(r["stock_available"], 0)
            self.assertGreater(r["distance_km"], 0)
            self.assertGreater(r["unit_transport_cost"], 0)
            self.assertEqual(r["data_classification"], "SIMULATED_SAMPLE")
            self.assertTrue("Rank" in r["rationale"])
        conn.close()

    # -----------------------------------------------------------------------
    # Test 7: Delivery Monitoring & Delay Detection
    # -----------------------------------------------------------------------
    def test_delivery_monitoring_workflow(self):
        # We already seeded SHP-MH-802 with expected_delivery_at in the past
        res = run_delivery_monitoring(dry_run=False, db_path=self.db_path)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertGreater(res["actions_generated"], 0)

        conn = get_db_connection(self.db_path)
        delayed = conn.execute("SELECT * FROM delivery_shipments WHERE status = 'DELAYED'").fetchall()
        self.assertGreater(len(delayed), 0)

        first_delayed = delayed[0]
        self.assertGreater(first_delayed["delay_minutes"], 0)
        self.assertEqual(first_delayed["tracking_source"], "ROAD_MANIFEST_CHECKPOINT")

        # Alert must be created
        alert = conn.execute("SELECT * FROM alerts WHERE alert_type = 'DELAYED_SHIPMENT'").fetchone()
        self.assertIsNotNone(alert)
        self.assertIn(first_delayed["shipment_code"], alert["entity_id"])
        conn.close()

    # -----------------------------------------------------------------------
    # Test 8: Automated Alert Center Deduplication & Resolution
    # -----------------------------------------------------------------------
    def test_alert_center_deduplication_and_actions(self):
        # Run workflows to create alerts
        run_auto_replenishment(dry_run=False, db_path=self.db_path)
        run_delivery_monitoring(dry_run=False, db_path=self.db_path)

        conn = get_db_connection(self.db_path)
        initial_alerts = conn.execute("SELECT * FROM alerts WHERE status = 'OPEN'").fetchall()
        initial_count = len(initial_alerts)
        self.assertGreater(initial_count, 0)
        first_alert_id = initial_alerts[0]["id"]
        conn.close()

        # Re-running workflows must NOT duplicate alerts
        run_auto_replenishment(dry_run=False, db_path=self.db_path)
        run_delivery_monitoring(dry_run=False, db_path=self.db_path)

        conn = get_db_connection(self.db_path)
        post_rerun_count = conn.execute("SELECT COUNT(*) as cnt FROM alerts WHERE status = 'OPEN'").fetchone()["cnt"]
        self.assertEqual(initial_count, post_rerun_count)
        conn.close()

        # Acknowledge alert
        ack_res = acknowledge_alert(first_alert_id, user_name="Control Room Operator", db_path=self.db_path)
        self.assertTrue(ack_res["success"])

        # Resolve alert
        res_res = resolve_alert(first_alert_id, user_name="Dispatch Supervisor", db_path=self.db_path)
        self.assertTrue(res_res["success"])

        conn = get_db_connection(self.db_path)
        resolved = conn.execute("SELECT * FROM alerts WHERE id = ?", (first_alert_id,)).fetchone()
        self.assertEqual(resolved["status"], "RESOLVED")
        self.assertEqual(resolved["resolved_by"], "Dispatch Supervisor")
        conn.close()

    # -----------------------------------------------------------------------
    # Test 9: Execution History Logging
    # -----------------------------------------------------------------------
    def test_workflow_execution_history_logging(self):
        exec_res = execute_workflow("auto_replenishment", dry_run=False, db_path=self.db_path)
        self.assertEqual(exec_res["status"], "SUCCESS")
        self.assertGreaterEqual(exec_res["duration_ms"], 0)

        conn = get_db_connection(self.db_path)
        logs = conn.execute("SELECT * FROM automation_execution_logs WHERE workflow_id = 'auto_replenishment'").fetchall()
        self.assertGreater(len(logs), 0)
        first_log = logs[0]
        self.assertEqual(first_log["status"], "SUCCESS")
        self.assertIsNotNone(first_log["started_at"])
        self.assertIsNotNone(first_log["finished_at"])
        conn.close()

    # -----------------------------------------------------------------------
    # Test 10: Flask RESTful Automation Endpoints
    # -----------------------------------------------------------------------
    def test_flask_automation_api_endpoints(self):
        from app import app
        client = app.test_client()

        # 1. Status
        res = client.get("/api/automation/status")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("workflows", data)
        self.assertIn("metrics", data)

        # 2. Run Workflow (dry-run)
        res_run = client.post("/api/automation/run", json={"workflow_id": "auto_replenishment", "dry_run": True})
        self.assertEqual(res_run.status_code, 200)
        self.assertEqual(res_run.get_json()["status"], "DRY_RUN")

        # 3. Toggle Workflow
        res_tog = client.post("/api/automation/toggle", json={"workflow_id": "auto_replenishment", "enabled": False})
        self.assertEqual(res_tog.status_code, 200)
        self.assertFalse(res_tog.get_json()["enabled"])

        # Re-enable
        client.post("/api/automation/toggle", json={"workflow_id": "auto_replenishment", "enabled": True})

        # 4. History
        res_hist = client.get("/api/automation/history?limit=10")
        self.assertEqual(res_hist.status_code, 200)
        self.assertIn("history", res_hist.get_json())

        # 5. Replenishment endpoints
        res_rep = client.get("/api/automation/replenishment")
        self.assertEqual(res_rep.status_code, 200)
        self.assertIn("requests", res_rep.get_json())

        # 6. Expiry Rescue endpoints
        res_res = client.get("/api/automation/expiry-rescue")
        self.assertEqual(res_res.status_code, 200)
        self.assertIn("transfers", res_res.get_json())

        # 7. Distribution options endpoints
        res_dist = client.get("/api/automation/distribution-options")
        self.assertEqual(res_dist.status_code, 200)
        self.assertEqual(res_dist.get_json()["data_classification"], "SIMULATED_SAMPLE")

        # 8. Deliveries endpoints
        res_del = client.get("/api/automation/deliveries")
        self.assertEqual(res_del.status_code, 200)
        self.assertIn("shipments", res_del.get_json())

        # 9. Alerts endpoints
        res_alt = client.get("/api/automation/alerts")
        self.assertEqual(res_alt.status_code, 200)
        self.assertIn("alerts", res_alt.get_json())
        self.assertIn("counts", res_alt.get_json())


if __name__ == "__main__":
    unittest.main()
