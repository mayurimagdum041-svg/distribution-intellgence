"""
OptiStock AI - Inventory Transactions Test Suite
Validates Stock In, Stock Out, stock availability enforcement, atomic persistence,
filtering queries, summary calculations, and authenticated API endpoints.
"""

import os
import tempfile
import unittest
from datetime import datetime, timezone

from app import app
from engine.automation_db import init_db, get_db_connection
from engine.data_loader import get_warehouse_stock, PRODUCTS, WAREHOUSES
from engine.inventory_transactions import (
    record_transaction,
    get_transactions,
    get_transaction_summary,
    generate_transaction_code,
)


class TestInventoryTransactions(unittest.TestCase):

    def setUp(self):
        # Create a dedicated temporary SQLite database for test isolation
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        init_db(self.temp_db_path)
        self.client = app.test_client()

    def tearDown(self):
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            try:
                os.remove(self.temp_db_path)
            except PermissionError:
                pass

    def test_generate_transaction_code(self):
        code_in = generate_transaction_code("STOCK_IN", db_path=self.temp_db_path)
        code_out = generate_transaction_code("STOCK_OUT", db_path=self.temp_db_path)
        self.assertTrue(code_in.startswith("TXN-IN-"))
        self.assertTrue(code_out.startswith("TXN-OUT-"))

    def test_stock_in_increases_inventory(self):
        wh_id = "WH-PUN"
        prod_id = 1  # Fresh Milk
        initial_stock = get_warehouse_stock(wh_id, prod_id)
        qty_to_add = 75

        res = record_transaction(
            data={
                "transaction_type": "STOCK_IN",
                "product_id": prod_id,
                "warehouse_id": wh_id,
                "quantity": qty_to_add,
                "partner_name": "Amul Dairy Cooperative Ltd.",
                "transaction_date": "2026-10-24",
                "notes": "Test incoming morning batch",
            },
            user_name="Test Warehouse Lead",
            user_role="warehouse",
            db_path=self.temp_db_path,
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["transaction_type"], "STOCK_IN")
        self.assertEqual(res["quantity"], qty_to_add)

        # Confirm warehouse stock increased exactly by qty_to_add
        updated_stock = get_warehouse_stock(wh_id, prod_id)
        self.assertEqual(updated_stock, initial_stock + qty_to_add)

        # Confirm persisted in SQLite database
        conn = get_db_connection(self.temp_db_path)
        try:
            row = conn.execute(
                "SELECT * FROM inventory_transactions WHERE transaction_code = ?",
                (res["transaction_code"],),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["transaction_type"], "STOCK_IN")
            self.assertEqual(row["quantity"], qty_to_add)
            self.assertEqual(row["performed_by"], "Test Warehouse Lead")
        finally:
            conn.close()

    def test_stock_out_decreases_inventory(self):
        wh_id = "WH-MUM"
        prod_id = 10  # Royal Basmati Rice
        initial_stock = get_warehouse_stock(wh_id, prod_id)
        self.assertGreater(initial_stock, 50, "Test assumption: Initial stock must be sufficient")
        qty_to_dispatch = 40

        res = record_transaction(
            data={
                "transaction_type": "STOCK_OUT",
                "product_id": prod_id,
                "warehouse_id": wh_id,
                "quantity": qty_to_dispatch,
                "partner_name": "Mumbai South Hypermarket",
                "transaction_date": "2026-10-24",
                "notes": "Store replenishment dispatch",
            },
            user_name="Test Retail Lead",
            user_role="retail",
            db_path=self.temp_db_path,
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["transaction_type"], "STOCK_OUT")

        # Confirm warehouse stock decreased exactly by qty_to_dispatch
        updated_stock = get_warehouse_stock(wh_id, prod_id)
        self.assertEqual(updated_stock, initial_stock - qty_to_dispatch)

        # Confirm persisted in SQLite database
        conn = get_db_connection(self.temp_db_path)
        try:
            row = conn.execute(
                "SELECT * FROM inventory_transactions WHERE transaction_code = ?",
                (res["transaction_code"],),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["transaction_type"], "STOCK_OUT")
            self.assertEqual(row["quantity"], qty_to_dispatch)
        finally:
            conn.close()

    def test_stock_out_prevents_over_dispatch(self):
        wh_id = "WH-SUR"
        prod_id = 1  # Fresh Milk
        current_stock = get_warehouse_stock(wh_id, prod_id)
        excess_qty = current_stock + 9999

        # Attempt to dispatch more than available
        with self.assertRaises(ValueError) as ctx:
            record_transaction(
                data={
                    "transaction_type": "STOCK_OUT",
                    "product_id": prod_id,
                    "warehouse_id": wh_id,
                    "quantity": excess_qty,
                    "partner_name": "Surat City Mart",
                    "transaction_date": "2026-10-24",
                },
                user_name="Test User",
                user_role="warehouse",
                db_path=self.temp_db_path,
            )

        self.assertIn("Insufficient stock", str(ctx.exception))
        # Ensure stock remained unchanged
        self.assertEqual(get_warehouse_stock(wh_id, prod_id), current_stock)

    def test_validation_rules(self):
        # 1. Invalid quantity <= 0
        with self.assertRaises(ValueError):
            record_transaction(
                data={
                    "transaction_type": "STOCK_IN",
                    "product_id": 1,
                    "warehouse_id": "WH-PUN",
                    "quantity": 0,
                    "partner_name": "Supplier",
                },
                db_path=self.temp_db_path,
            )

        # 2. Missing partner name
        with self.assertRaises(ValueError):
            record_transaction(
                data={
                    "transaction_type": "STOCK_IN",
                    "product_id": 1,
                    "warehouse_id": "WH-PUN",
                    "quantity": 20,
                    "partner_name": "",
                },
                db_path=self.temp_db_path,
            )

        # 3. Invalid warehouse ID
        with self.assertRaises(ValueError):
            record_transaction(
                data={
                    "transaction_type": "STOCK_IN",
                    "product_id": 1,
                    "warehouse_id": "WH-NONEXISTENT",
                    "quantity": 20,
                    "partner_name": "Supplier",
                },
                db_path=self.temp_db_path,
            )

        # 4. Invalid transaction type
        with self.assertRaises(ValueError):
            record_transaction(
                data={
                    "transaction_type": "INVALID_TYPE",
                    "product_id": 1,
                    "warehouse_id": "WH-PUN",
                    "quantity": 20,
                    "partner_name": "Supplier",
                },
                db_path=self.temp_db_path,
            )

    def test_get_transactions_and_filtering(self):
        # The seeded transactions should exist
        all_txns = get_transactions(db_path=self.temp_db_path)
        self.assertGreaterEqual(all_txns["total_count"], 4)

        # Filter by type STOCK_IN
        in_txns = get_transactions(filters={"type": "STOCK_IN"}, db_path=self.temp_db_path)
        for t in in_txns["transactions"]:
            self.assertEqual(t["transaction_type"], "STOCK_IN")

        # Filter by type STOCK_OUT
        out_txns = get_transactions(filters={"type": "STOCK_OUT"}, db_path=self.temp_db_path)
        for t in out_txns["transactions"]:
            self.assertEqual(t["transaction_type"], "STOCK_OUT")

        # Search filter
        search_res = get_transactions(filters={"search": "Basmati"}, db_path=self.temp_db_path)
        self.assertGreaterEqual(search_res["total_count"], 1)
        self.assertIn("Basmati", search_res["transactions"][0]["product_name"])

    def test_get_transaction_summary(self):
        summary = get_transaction_summary(db_path=self.temp_db_path)
        self.assertIn("total_transactions", summary)
        self.assertIn("stock_received", summary)
        self.assertIn("stock_dispatched", summary)
        self.assertIn("net_movement", summary)
        self.assertIn("recent_transactions", summary)
        self.assertGreaterEqual(summary["total_transactions"], 4)
        self.assertGreater(summary["stock_received"], 0)
        self.assertGreater(summary["stock_dispatched"], 0)

    def test_api_transactions_unauthenticated(self):
        # Without session or role headers, requests should be rejected with 401
        res = self.client.get("/api/transactions")
        self.assertEqual(res.status_code, 401)
        data = res.get_json()
        self.assertFalse(data["success"])

        res_post = self.client.post("/api/transactions", json={"transaction_type": "STOCK_IN"})
        self.assertEqual(res_post.status_code, 401)

    def test_api_transactions_authenticated(self):
        # Authenticated with session role
        with self.client.session_transaction() as sess:
            sess["user_role"] = "admin"
            sess["user_name"] = "System Administrator"

        # 1. GET transactions
        res_get = self.client.get("/api/transactions")
        self.assertEqual(res_get.status_code, 200)
        data = res_get.get_json()
        self.assertTrue(data["success"])
        self.assertIn("transactions", data)
        self.assertIn("summary", data)

        # 2. POST valid Stock In
        post_data = {
            "transaction_type": "STOCK_IN",
            "product_id": 2,
            "warehouse_id": "WH-PUN",
            "quantity": 30,
            "partner_name": "Mother Dairy Hub",
            "transaction_date": "2026-10-24",
            "notes": "API Unit Test Inbound",
        }
        res_post = self.client.post("/api/transactions", json=post_data)
        self.assertEqual(res_post.status_code, 201)
        created = res_post.get_json()
        self.assertTrue(created["success"])
        self.assertTrue(created["transaction_code"].startswith("TXN-IN-"))

        # 3. GET /api/transactions/next-code
        res_code = self.client.get("/api/transactions/next-code?type=STOCK_OUT")
        self.assertEqual(res_code.status_code, 200)
        self.assertTrue(res_code.get_json()["transaction_code"].startswith("TXN-OUT-"))

        # 4. GET /api/summary includes transactions data
        res_sum = self.client.get("/api/summary?days=3")
        self.assertEqual(res_sum.status_code, 200)
        sum_json = res_sum.get_json()
        self.assertIn("transactions", sum_json)
        self.assertIn("total_transactions", sum_json)
        self.assertIn("stock_received", sum_json)
        self.assertIn("stock_dispatched", sum_json)
        self.assertIn("recent_transactions", sum_json)


if __name__ == "__main__":
    unittest.main()
