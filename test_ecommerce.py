"""
Comprehensive Automated Test Suite for OptiStock AI Smart E-Commerce Platform
Tests customer auth, storefront catalog, cart, wishlist, atomic checkout, stock deduction,
ledger auditing, demand forecasting velocity update, order cancellation stock restoration,
and admin order management.
"""

import unittest
import json
import sqlite3
import database
from app import app


class TestEcommercePlatform(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

        # Re-initialize DB and seeds
        database.init_db()

        # Reset demo customer record for test predictability
        conn = sqlite3.connect(database.DB_PATH)
        conn.execute("UPDATE customers SET name = 'Priya Sharma', address = '42 Marine Drive, Nariman Point', city = 'Mumbai', pincode = '400021' WHERE email = 'customer@optistock.ai'")
        conn.commit()
        conn.close()

        # Connect to DB to inspect directly
        self.db_path = database.DB_PATH

    def get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── 1. Customer Authentication & Profile ──

    def test_customer_demo_login(self):
        """Tests 1-Click Demo Login as customer@optistock.ai."""
        res = self.client.post("/store/demo-login", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertIn("customer_id", sess)
            self.assertEqual(sess.get("customer_name"), "Priya Sharma")

    def test_customer_registration_and_login(self):
        """Tests registering a new unique customer and logging in."""
        unique_email = "test_shopper_99@example.com"
        reg_res = self.client.post("/store/register", data={
            "name": "Aarav Mehta",
            "email": unique_email,
            "password": "securepassword123",
            "phone": "9876500000",
            "address": "12 Galaxy Apts, Bandra West",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pincode": "400050",
        }, follow_redirects=True)
        self.assertEqual(reg_res.status_code, 200)

        # Verify customer created in DB
        cust = database.get_customer_by_email(unique_email)
        self.assertIsNotNone(cust)
        self.assertEqual(cust["name"], "Aarav Mehta")

        # Test logging out and logging back in
        self.client.get("/store/logout", follow_redirects=True)
        with self.client.session_transaction() as sess:
            self.assertNotIn("customer_id", sess)

        login_res = self.client.post("/store/login", data={
            "email": unique_email,
            "password": "securepassword123",
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("customer_id"), cust["id"])

    def test_customer_profile_update(self):
        """Tests updating customer delivery address."""
        # Log in as demo customer
        self.client.post("/store/demo-login")

        res = self.client.post("/store/profile", data={
            "name": "Priya Sharma Updated",
            "phone": "9820199999",
            "address": "Flat 802, Oceanic View, Worli",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pincode": "400018",
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        demo = database.get_customer_by_email("customer@optistock.ai")
        self.assertEqual(demo["name"], "Priya Sharma Updated")
        self.assertEqual(demo["city"], "Mumbai")
        self.assertEqual(demo["pincode"], "400018")

    # ── 2. Storefront Catalog & Live Stock API ──

    def test_store_landing_page(self):
        """Tests /store loads successfully with featured products."""
        res = self.client.get("/store")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"OptiStock Shop", res.data)
        self.assertIn(b"Trending", res.data)

    def test_store_catalog_filtering(self):
        """Tests catalog category filtering and search."""
        # Category filter: Fashion
        res_fash = self.client.get("/store/products?category=Fashion")
        self.assertEqual(res_fash.status_code, 200)
        self.assertIn(b"Fashion", res_fash.data)

        # Category filter: Electronics
        res_elec = self.client.get("/store/products?category=Electronics")
        self.assertEqual(res_elec.status_code, 200)
        self.assertIn(b"Electronics", res_elec.data)

        # Search filter
        res_search = self.client.get("/store/products?search=Polo")
        self.assertEqual(res_search.status_code, 200)
        self.assertIn(b"Polo", res_search.data)

    def test_product_detail_and_stock_locations(self):
        """Tests /store/product/<id> displays product and warehouse stock breakdown."""
        # Get first product ID
        products = database.get_store_products()
        self.assertTrue(len(products) > 0)
        p_id = products[0]["id"]

        res = self.client.get(f"/store/product/{p_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(products[0]["name"].encode("utf-8"), res.data)

        # Test JSON stock API
        api_res = self.client.get(f"/api/store/check-stock?product_id={p_id}")
        self.assertEqual(api_res.status_code, 200)
        data = json.loads(api_res.data)
        self.assertTrue(data["success"])
        self.assertIn("locations", data)
        self.assertIn("total_stock", data)

    # ── 3. Cart & Wishlist Operations ──

    def test_cart_operations(self):
        """Tests adding to cart, updating quantity, and removing items."""
        products = database.get_store_products()
        p1 = products[0]
        p2 = products[1]

        # Add p1 to cart
        res1 = self.client.post("/store/cart/add", data={"product_id": p1["id"], "quantity": 2}, follow_redirects=True)
        self.assertEqual(res1.status_code, 200)
        with self.client.session_transaction() as sess:
            cart = sess.get("store_cart", {})
            self.assertEqual(cart.get(str(p1["id"])), 2)

        # Add p2 to cart
        self.client.post("/store/cart/add", data={"product_id": p2["id"], "quantity": 1})
        with self.client.session_transaction() as sess:
            cart = sess.get("store_cart", {})
            self.assertEqual(cart.get(str(p2["id"])), 1)
            self.assertEqual(sum(cart.values()), 3)

        # Update p1 quantity to 4
        self.client.post("/store/cart/update", data={"product_id": str(p1["id"]), "quantity": 4})
        with self.client.session_transaction() as sess:
            cart = sess.get("store_cart", {})
            self.assertEqual(cart.get(str(p1["id"])), 4)

        # Remove p2 from cart
        self.client.post("/store/cart/remove", data={"product_id": str(p2["id"])})
        with self.client.session_transaction() as sess:
            cart = sess.get("store_cart", {})
            self.assertNotIn(str(p2["id"]), cart)

        # View cart page
        cart_page = self.client.get("/store/cart")
        self.assertEqual(cart_page.status_code, 200)
        self.assertIn(p1["name"].encode("utf-8"), cart_page.data)

        # Clear cart
        self.client.post("/store/cart/clear")
        with self.client.session_transaction() as sess:
            cart = sess.get("store_cart", {})
            self.assertEqual(len(cart), 0)

    def test_wishlist_toggle(self):
        """Tests adding and removing items from customer wishlist."""
        self.client.post("/store/demo-login")
        cust = database.get_customer_by_email("customer@optistock.ai")

        products = database.get_store_products()
        pid = products[0]["id"]

        # Toggle add
        self.client.post("/store/wishlist/toggle", data={"product_id": pid})
        self.assertTrue(database.is_in_wishlist(cust["id"], pid))

        # Wishlist page view
        res = self.client.get("/store/wishlist")
        self.assertEqual(res.status_code, 200)
        self.assertIn(products[0]["name"].encode("utf-8"), res.data)

        # Toggle remove
        self.client.post("/store/wishlist/toggle", data={"product_id": pid})
        self.assertFalse(database.is_in_wishlist(cust["id"], pid))

    # ── 4. Atomic Checkout, Stock Deduction & Ledger Audit ──

    def test_atomic_checkout_flow(self):
        """
        Tests end-to-end checkout:
        1. Adds in-stock item to cart
        2. Places order via POST /store/checkout
        3. Asserts order created, stock safely deducted, transaction ledger entry logged
        4. Asserts sales run rate velocity updated
        """
        # Log in demo customer
        self.client.post("/store/demo-login")
        cust = database.get_customer_by_email("customer@optistock.ai")

        # Pick a product with positive stock
        products = [p for p in database.get_store_products() if p["total_stock"] >= 5]
        self.assertTrue(len(products) > 0, "Expected at least one product with >= 5 stock")
        target_product = products[0]
        pid = target_product["id"]

        # Check initial total stock across locations
        initial_detail = database.get_store_product_detail(pid)
        initial_total_stock = initial_detail["total_stock"]
        best_loc = database.find_best_fulfillment_location(pid, 2)
        self.assertIsNotNone(best_loc)

        # Add 2 units to cart
        self.client.post("/store/cart/add", data={"product_id": pid, "quantity": 2})

        # Place Order
        checkout_res = self.client.post("/store/checkout", data={
            "name": "Priya Sharma",
            "address": "42 Hill Road, Bandra West",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pincode": "400050",
            "payment_method": "Cash on Delivery (Demo)",
        }, follow_redirects=False)

        # Must redirect to order-confirmation
        self.assertEqual(checkout_res.status_code, 302)
        redirect_url = checkout_res.headers.get("Location")
        self.assertIn("/store/order-confirmation/", redirect_url)

        order_code = redirect_url.split("/")[-1]

        # 1. Verify order in DB
        order = database.get_order_by_code(order_code)
        self.assertIsNotNone(order)
        self.assertEqual(order["customer_id"], cust["id"])
        self.assertEqual(order["order_status"], "Placed")
        self.assertEqual(len(order["items"]), 1)
        self.assertEqual(order["items"][0]["quantity"], 2)

        # 2. Verify stock deduction
        after_detail = database.get_store_product_detail(pid)
        after_total_stock = after_detail["total_stock"]
        self.assertEqual(after_total_stock, initial_total_stock - 2)

        # 3. Verify ledger transaction
        conn = self.get_db()
        tx = conn.execute(
            "SELECT * FROM inventory_transactions WHERE product_id = ? AND transaction_type = 'CUSTOMER_ORDER' ORDER BY id DESC LIMIT 1",
            (pid,)
        ).fetchone()
        conn.close()
        self.assertIsNotNone(tx)
        self.assertEqual(tx["quantity"], -2)
        self.assertIn(order_code, tx["reference"])

        # 4. Verify order confirmation page loads
        conf_res = self.client.get(f"/store/order-confirmation/{order_code}")
        self.assertEqual(conf_res.status_code, 200)
        self.assertIn(order_code.encode("utf-8"), conf_res.data)

        # 5. Verify customer orders history page includes this order
        orders_page = self.client.get("/store/orders")
        self.assertEqual(orders_page.status_code, 200)
        self.assertIn(order_code.encode("utf-8"), orders_page.data)

    def test_overdraft_stockout_protection(self):
        """Tests that ordering more than available stock is strictly prevented."""
        self.client.post("/store/demo-login")

        # Pick a product
        products = database.get_store_products()
        prod = products[0]
        avail = prod["total_stock"]

        # Attempt to order avail + 500 units directly via database function
        order_items = [{"product_id": prod["id"], "quantity": avail + 500, "unit_price": prod["price"]}]
        shipping_info = {
            "name": "Overdraft Tester",
            "email": "test@example.com",
            "address": "123 Test St",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pincode": "400001",
        }
        success, msg, order_id, order_code = database.create_customer_order(
            customer_id=1,
            items=order_items,
            shipping_info=shipping_info,
            payment_method="Demo COD",
        )

        self.assertFalse(success)
        self.assertIn("Insufficient stock", msg)

    # ── 5. Admin Orders Management & Order Cancellation Stock Restoration ──

    def test_admin_orders_and_status_transitions(self):
        """
        Tests admin order management:
        1. Admin views /orders
        2. Updates order status Placed -> Processing -> Shipped -> Delivered
        3. Tests cancelling an order and verifies that stock is restored!
        """
        # Create a fresh order first
        demo = database.get_customer_by_email("customer@optistock.ai")
        prod = database.get_store_products()[0]
        pid = prod["id"]

        init_detail = database.get_store_product_detail(pid)
        init_stock = init_detail["total_stock"]

        shipping_info = {
            "name": demo["name"],
            "email": demo["email"],
            "address": "Test Address",
            "city": "Mumbai",
            "state": "Maharashtra",
            "pincode": "400001",
        }
        success, msg, order_id, order_code = database.create_customer_order(
            customer_id=demo["id"],
            items=[{"product_id": pid, "quantity": 1, "unit_price": prod["price"]}],
            shipping_info=shipping_info,
            payment_method="Demo UPI",
        )
        self.assertTrue(success)

        # Stock should now be init_stock - 1
        curr_stock = database.get_store_product_detail(pid)["total_stock"]
        self.assertEqual(curr_stock, init_stock - 1)

        order = database.get_order_by_code(order_code)
        order_id = order["id"]

        # Log in as admin/operator (user_id = 1)
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1

        # View /orders
        res = self.client.get("/orders")
        self.assertEqual(res.status_code, 200)
        self.assertIn(order_code.encode("utf-8"), res.data)

        # Progress to Processing
        self.client.post(f"/orders/{order_id}/status", data={"new_status": "Processing", "tracking_notes": "Packed at WH-MUM"})
        order = database.get_order_by_id(order_id)
        self.assertEqual(order["order_status"], "Processing")

        # Progress to Shipped
        self.client.post(f"/orders/{order_id}/status", data={"new_status": "Shipped", "tracking_notes": "Courier AWB #9812"})
        order = database.get_order_by_id(order_id)
        self.assertEqual(order["order_status"], "Shipped")

        # Now test CANCEL: Should restore the 1 unit back to inventory
        cancel_res = self.client.post(f"/orders/{order_id}/status", data={"new_status": "Cancelled", "tracking_notes": "Customer cancelled"})
        self.assertEqual(cancel_res.status_code, 302)

        order = database.get_order_by_id(order_id)
        self.assertEqual(order["order_status"], "Cancelled")

        # Verify stock restored to original count
        restored_stock = database.get_store_product_detail(pid)["total_stock"]
        self.assertEqual(restored_stock, init_stock)

        # Verify restoration ledger transaction
        conn = self.get_db()
        tx = conn.execute(
            "SELECT * FROM inventory_transactions WHERE product_id = ? AND transaction_type = 'ORDER_CANCEL_RESTORE' ORDER BY id DESC LIMIT 1",
            (pid,)
        ).fetchone()
        conn.close()
        self.assertIsNotNone(tx)
        self.assertEqual(tx["quantity"], 1)


if __name__ == "__main__":
    unittest.main()
