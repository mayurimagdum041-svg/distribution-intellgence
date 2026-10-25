"""
OptiStock AI — Expired & Spoiled Products Module Verification Test Suite
Tests:
1. Authentication & Route Accessibility
2. Metrics & Aggregation Calculation
3. Sellable Stock Deduction & Isolation Verification
4. Inventory Ledger Audit Logging (SPOILAGE_DEDUCT & SPOILAGE_RESTORE)
5. Spoilage Lifecycle Transitions (Pending Disposal -> Disposed / Returned)
6. Filtering & Search API
7. Rollback & Stock Restoration
"""

import unittest
import json
import database
from app import app


class TestExpiredSpoiledProducts(unittest.TestCase):

    def setUp(self):
        self.app = app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()

        database.init_db()
        self.demo_user = database.get_user_by_email("demo@optistock.ai")
        self.assertIsNotNone(self.demo_user, "Demo user must exist in database")
        self.user_id = self.demo_user["id"]

    def login_demo_user(self):
        """Helper to create an authenticated session."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_id
            sess["user_email"] = self.demo_user["email"]
            sess["user_name"] = self.demo_user["name"]

    def test_01_unauthenticated_access_redirects(self):
        """Unauthenticated requests to /expired-spoiled must redirect to login."""
        response = self.client.get("/expired-spoiled", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_02_expired_spoiled_page_loads(self):
        """Authenticated access to /expired-spoiled returns 200 with cards and elements."""
        self.login_demo_user()
        response = self.client.get("/expired-spoiled")
        self.assertEqual(response.status_code, 200)

        html = response.data.decode("utf-8")
        self.assertIn("Expired &amp; Spoiled Products", html)
        self.assertIn("Total Affected Products", html)
        self.assertIn("Affected Quantity (Units)", html)
        self.assertIn("Total Estimated Financial Loss", html)
        self.assertIn("Pending Disposal", html)
        self.assertIn("Disposed", html)
        self.assertIn("Returned", html)
        self.assertIn("recordSpoilageModal", html)

    def test_03_api_product_stock_at_location(self):
        """Verifies the dynamic JSON API for stock and pricing lookup."""
        self.login_demo_user()
        prods = database.get_products_by_user(self.user_id)
        locs = database.get_locations_by_user(self.user_id)
        self.assertTrue(len(prods) > 0)
        self.assertTrue(len(locs) > 0)

        p_id = prods[0]["id"]
        l_id = locs[0]["id"]

        resp = self.client.get(f"/api/product-stock-at-location?product_id={p_id}&location_id={l_id}")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data)
        self.assertTrue(data["success"])
        self.assertIn("current_stock", data["data"])
        self.assertIn("unit_price", data["data"])

    def test_04_record_spoilage_deducts_sellable_stock_atomically(self):
        """
        Critical Requirement: Recording an expired/spoiled incident must immediately
        deduct units from inventory.current_stock, protecting sellable stock.
        """
        # Find a product with positive stock
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT product_id, location_id, current_stock 
            FROM inventory 
            WHERE user_id = ? AND current_stock >= 10
            LIMIT 1
        """, (self.user_id,))
        row = cursor.fetchone()
        conn.close()

        self.assertIsNotNone(row, "Must find inventory with >= 10 units for testing deduction")
        p_id = row["product_id"]
        l_id = row["location_id"]
        initial_stock = row["current_stock"]

        deduct_qty = 5
        success, msg, rec_id = database.record_spoilage(
            user_id=self.user_id,
            product_id=p_id,
            location_id=l_id,
            quantity=deduct_qty,
            reason="Expired",
            expiry_date="2026-10-24",
            notes="Test automated unit test deduction",
            status="Pending Disposal"
        )
        self.assertTrue(success, f"Failed to record spoilage: {msg}")
        self.assertIsNotNone(rec_id)

        # Verify stock was deducted in database
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT current_stock FROM inventory WHERE user_id = ? AND product_id = ? AND location_id = ?",
                       (self.user_id, p_id, l_id))
        after_stock = cursor.fetchone()["current_stock"]
        self.assertEqual(after_stock, initial_stock - deduct_qty)

        # Verify audit ledger entry
        cursor.execute("""
            SELECT transaction_type, quantity, balance_after 
            FROM inventory_transactions 
            WHERE user_id = ? AND product_id = ? AND location_id = ? AND transaction_type = 'SPOILAGE_DEDUCT'
            ORDER BY id DESC LIMIT 1
        """, (self.user_id, p_id, l_id))
        audit = cursor.fetchone()
        self.assertIsNotNone(audit)
        self.assertEqual(audit["quantity"], -deduct_qty)
        self.assertEqual(audit["balance_after"], after_stock)

        # Clean up / Roll back test record with stock restoration
        del_success, del_msg = database.delete_spoilage_record(self.user_id, rec_id, restore_stock=True)
        self.assertTrue(del_success)

        # Verify stock restored
        cursor.execute("SELECT current_stock FROM inventory WHERE user_id = ? AND product_id = ? AND location_id = ?",
                       (self.user_id, p_id, l_id))
        restored_stock = cursor.fetchone()["current_stock"]
        self.assertEqual(restored_stock, initial_stock)
        conn.close()

    def test_05_prevent_over_deduction(self):
        """Recording spoilage with quantity exceeding available stock must be rejected."""
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT product_id, location_id, current_stock 
            FROM inventory 
            WHERE user_id = ?
            LIMIT 1
        """, (self.user_id,))
        row = cursor.fetchone()
        conn.close()

        p_id = row["product_id"]
        l_id = row["location_id"]
        stock = row["current_stock"]

        excessive_qty = stock + 99999
        success, msg, rec_id = database.record_spoilage(
            user_id=self.user_id,
            product_id=p_id,
            location_id=l_id,
            quantity=excessive_qty,
            reason="Temperature Abuse / Spoilage",
            status="Pending Disposal"
        )
        self.assertFalse(success)
        self.assertIn("Insufficient sellable stock", msg)

    def test_06_update_spoilage_status(self):
        """Verifies transitioning status between Pending Disposal, Disposed, and Returned."""
        records = database.get_spoilage_records(self.user_id)
        self.assertTrue(len(records) > 0)
        rec = records[0]

        # Update to Disposed
        success, msg = database.update_spoilage_status(self.user_id, rec["id"], "Disposed", notes="Disposed via contractor")
        self.assertTrue(success)

        # Check DB
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT status, disposed_at FROM spoilage_records WHERE id = ?", (rec["id"],))
        updated = cursor.fetchone()
        self.assertEqual(updated["status"], "Disposed")
        self.assertIsNotNone(updated["disposed_at"])

        # Update to Returned
        success2, msg2 = database.update_spoilage_status(self.user_id, rec["id"], "Returned", notes="Vendor credit requested")
        self.assertTrue(success2)
        cursor.execute("SELECT status FROM spoilage_records WHERE id = ?", (rec["id"],))
        self.assertEqual(cursor.fetchone()["status"], "Returned")
        conn.close()

    def test_07_filtering_spoilage_records(self):
        """Verifies search, status, and reason filters in get_spoilage_records."""
        all_recs = database.get_spoilage_records(self.user_id)

        # Filter by Disposed
        disposed_recs = database.get_spoilage_records(self.user_id, status="Disposed")
        for r in disposed_recs:
            self.assertEqual(r["status"], "Disposed")

        # Filter by Reason
        expired_recs = database.get_spoilage_records(self.user_id, reason="Expired")
        for r in expired_recs:
            self.assertEqual(r["reason"], "Expired")

        # Search query matching 'SPL-'
        search_recs = database.get_spoilage_records(self.user_id, search="SPL-")
        self.assertTrue(len(search_recs) > 0)

    def test_08_web_post_record_and_update_lifecycle(self):
        """Full end-to-end HTTP POST flow testing form submission and status transition."""
        self.login_demo_user()

        # Find inventory
        conn = database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT product_id, location_id, current_stock FROM inventory WHERE user_id = ? AND current_stock >= 5 LIMIT 1", (self.user_id,))
        inv = cursor.fetchone()
        conn.close()

        # Submit new incident via HTTP POST
        post_data = {
            "product_id": str(inv["product_id"]),
            "location_id": str(inv["location_id"]),
            "quantity": "2",
            "reason": "Damaged in Transit",
            "expiry_date": "2026-11-01",
            "unit_price": "75.00",
            "status": "Pending Disposal",
            "notes": "End-to-end integration test"
        }
        resp = self.client.post("/expired-spoiled/record", data=post_data, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("recorded", resp.data.decode("utf-8").lower())

        # Fetch newly created record
        recs = database.get_spoilage_records(self.user_id, search="End-to-end integration test")
        self.assertTrue(len(recs) > 0)
        new_rec = recs[0]
        self.assertEqual(new_rec["quantity"], 2)
        self.assertEqual(new_rec["status"], "Pending Disposal")

        # Transition status via HTTP POST
        update_data = {
            "record_id": str(new_rec["id"]),
            "status": "Disposed",
            "notes": "Marked disposed via test"
        }
        resp2 = self.client.post("/expired-spoiled/update-status", data=update_data, follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)

        # Delete with stock restoration via HTTP POST
        del_data = {
            "record_id": str(new_rec["id"]),
            "restore_stock": "1"
        }
        resp3 = self.client.post("/expired-spoiled/delete", data=del_data, follow_redirects=True)
        self.assertEqual(resp3.status_code, 200)


if __name__ == "__main__":
    unittest.main()
