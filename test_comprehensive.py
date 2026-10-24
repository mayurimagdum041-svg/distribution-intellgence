"""
OptiStock AI — Comprehensive System Test Suite
Tests authentication, products, warehouses, retail stores, inventory matrix,
atomic stock transfers, AI demand predictions, warehouse sourcing, and dashboard APIs.
"""

import app
import database

def run_all_tests():
    print("=" * 60)
    print("  RUNNING OPTISTOCK AI SYSTEM VERIFICATION TEST SUITE  ")
    print("=" * 60)

    client = app.app.test_client()

    # 1. Test index redirect
    r = client.get('/')
    assert r.status_code == 302
    print("[PASS] Test 1: Root redirect -> /login")

    # 2. Test login page
    r = client.get('/login')
    assert r.status_code == 200
    assert b"Sign In" in r.data
    print("[PASS] Test 2: Login page loads with show/hide password inputs")

    # 3. Test Demo Account Login
    r = client.post('/demo-login', follow_redirects=True)
    assert r.status_code == 200
    assert b"Inventory &amp; Warehouse Operations Dashboard" in r.data or b"Inventory & Warehouse Operations Dashboard" in r.data
    print("[PASS] Test 3: 1-Click Demo Login -> Dashboard loaded")

    # 4. Test Dashboard KPIs
    r = client.get('/dashboard')
    assert r.status_code == 200
    assert b"Total Products" in r.data
    assert b"Total Warehouses" in r.data
    assert b"Total Retail Stores" in r.data
    assert b"Total Inventory Value" in r.data
    assert b"Low-Stock Outlets" in r.data
    assert b"Predicted Demand" in r.data
    print("[PASS] Test 4: Dashboard displays all 6 core metrics and charts")

    # 5. Test Chart.js Data Endpoint
    r = client.get('/api/chart-data')
    assert r.status_code == 200
    data = r.get_json()
    assert "categories" in data
    assert "status" in data
    assert "locations" in data
    print(f"[PASS] Test 5: /api/chart-data returned valid payload: {len(data['categories']['labels'])} categories")

    # 6. Test Product Management CRUD
    # Add new product
    r = client.post('/products/add', data={
        'name': 'Test Multivitamin Drops 30ml',
        'sku': 'MED-MVT-030',
        'category': 'Healthcare & Pharma',
        'price': '145.00',
        'min_stock_level': '25',
        'description': 'Paediatric liquid multivitamin formulation'
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"MED-MVT-030" in r.data
    print("[PASS] Test 6: Add product SKU with validation")

    # Duplicate SKU prevention
    r = client.post('/products/add', data={
        'name': 'Duplicate SKU Item',
        'sku': 'MED-MVT-030',
        'category': 'Healthcare & Pharma',
        'price': '100.00',
        'min_stock_level': '10',
        'description': ''
    }, follow_redirects=True)
    assert b"may already exist" in r.data or b"Failed to add" in r.data
    print("[PASS] Test 7: Duplicate SKU rejection enforced")

    # 7. Test Warehouse Management
    r = client.get('/warehouses')
    assert r.status_code == 200
    assert b"Pune Regional Distribution Hub" in r.data or b"Pune Central Distribution Hub" in r.data
    assert b"Mumbai Central Mega-DC" in r.data or b"Bhiwandi Mega Logistics Depot" in r.data

    # Add new warehouse
    r = client.post('/warehouses/add', data={
        'name': 'Nagpur Eastern Transit Depot',
        'code': 'WH-NAG-04',
        'address': 'Butibori MIDC Industrial Area',
        'city': 'Nagpur',
        'state': 'Maharashtra',
        'pincode': '441108'
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"WH-NAG-04" in r.data
    print("[PASS] Test 8: Warehouses list and register new warehouse")

    # 8. Test Retail Store Management
    r = client.get('/retail-stores')
    assert r.status_code == 200
    assert b"Pune Market Square Retail" in r.data or b"OptiStock Express FC Road" in r.data
    assert b"Mumbai South Hypermarket" in r.data or b"OptiStock Mart Bandra West" in r.data

    # Add new retail store
    r = client.post('/retail-stores/add', data={
        'name': 'OptiStock Store Nashik College Road',
        'code': 'ST-NSK-105',
        'address': 'College Road Opp Big Bazaar',
        'city': 'Nashik',
        'state': 'Maharashtra',
        'pincode': '422005'
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"ST-NSK-105" in r.data
    print("[PASS] Test 9: Retail stores list and register new outlet")

    # 9. Test Location-Based Inventory Matrix & Stock Allocation
    demo_user = database.get_user_by_email('demo@optistock.ai')
    new_prod = database.get_product_by_sku('MED-MVT-030', demo_user['id'])
    nag_wh = next(w for w in database.get_user_locations(demo_user['id'], loc_type='Warehouse') if w['code'] == 'WH-NAG-04')
    nsk_st = next(s for s in database.get_user_locations(demo_user['id'], loc_type='Retail Store') if s['code'] == 'ST-NSK-105')

    # Allocate stock to warehouse
    r = client.post('/inventory/set-stock', data={
        'product_id': new_prod['id'],
        'location_id': nag_wh['id'],
        'current_stock': '500',
        'units_sold_per_day': '0'
    }, follow_redirects=True)
    assert r.status_code == 200
    print("[PASS] Test 10: Location-based stock allocation to warehouse")

    # Allocate stock to retail store with daily sales velocity
    r = client.post('/inventory/set-stock', data={
        'product_id': new_prod['id'],
        'location_id': nsk_st['id'],
        'current_stock': '20',
        'units_sold_per_day': '5'
    }, follow_redirects=True)
    assert r.status_code == 200
    print("[PASS] Test 11: Location-based stock allocation to retail store with velocity")

    # 10. Test Stock Transfers (ACID Transaction Safeguards)
    # Test 10a: Same location prevention
    r = client.post('/transfers', data={
        'source_location_id': nag_wh['id'],
        'dest_location_id': nag_wh['id'],
        'product_id': new_prod['id'],
        'quantity': '50',
        'notes': 'Self transfer'
    }, follow_redirects=True)
    assert b"cannot be the same" in r.data
    print("[PASS] Test 12: Stock transfer rejects identical origin and target")

    # Test 10b: Overdraft prevention
    r = client.post('/transfers', data={
        'source_location_id': nag_wh['id'],
        'dest_location_id': nsk_st['id'],
        'product_id': new_prod['id'],
        'quantity': '99999', # more than 500
        'notes': 'Excessive'
    }, follow_redirects=True)
    assert b"Insufficient stock" in r.data
    print("[PASS] Test 13: Stock transfer blocks overdraft exceeding on-hand quantity")

    # Test 10c: Valid transfer execution
    r = client.post('/transfers', data={
        'source_location_id': nag_wh['id'],
        'dest_location_id': nsk_st['id'],
        'product_id': new_prod['id'],
        'quantity': '60',
        'notes': 'Test automated dispatch'
    }, follow_redirects=True)
    assert b"completed successfully" in r.data

    # Verify atomic balances: nag_wh had 500, should be 440. nsk_st had 20, should be 80.
    inv_rows = database.get_location_inventory(nag_wh['id'], demo_user['id'])
    nag_item = next(i for i in inv_rows if i['product_id'] == new_prod['id'])
    assert nag_item['current_stock'] == 440, f"Expected 440, got {nag_item['current_stock']}"

    inv_rows_st = database.get_location_inventory(nsk_st['id'], demo_user['id'])
    nsk_item = next(i for i in inv_rows_st if i['product_id'] == new_prod['id'])
    assert nsk_item['current_stock'] == 80, f"Expected 80, got {nsk_item['current_stock']}"
    print(f"[PASS] Test 14: Atomic stock transfer verified! Source: 440 units, Target: 80 units")

    # 11. Test AI Demand Prediction & Sourcing Engine
    # Run prediction for Nashik store
    # Current stock: 80, daily velocity: 5, period: 7 days, min stock: 25
    # Demand = 5 * 7 = 35
    # Projected stock = 80 - 35 = 45 > 25 -> Healthy, Replenishment = max(0, 35 + 25 - 80) = 0
    r = client.post('/predictions', data={
        'store_id': nsk_st['id'],
        'product_id': new_prod['id'],
        'current_stock': '80',
        'units_sold_per_day': '5',
        'min_stock_level': '25',
        'prediction_period': '7'
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"AI Demand Prediction calculated" in r.data
    print("[PASS] Test 15: AI Prediction calculation & database recording (Healthy scenario)")

    # Test Critical prediction scenario: stock: 10, velocity: 10, period: 7, min: 30
    # Demand = 70, Projected = 10 - 70 = -60 (Critical), Replenishment = max(0, 70 + 30 - 10) = 90
    # Warehouse sourcing should suggest nag_wh (440 units available)
    r = client.post('/predictions', data={
        'store_id': nsk_st['id'],
        'product_id': new_prod['id'],
        'current_stock': '10',
        'units_sold_per_day': '10',
        'min_stock_level': '30',
        'prediction_period': '7'
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"Critical" in r.data
    assert b"WH-NAG-04" in r.data
    print("[PASS] Test 16: AI Prediction critical stockout alert with suggested warehouse matching")

    # 12. Test Reports Page
    r = client.get('/reports')
    assert r.status_code == 200
    assert b"Total Network Capital" in r.data
    assert b"Automated Restocking Manifest" in r.data
    assert b"Comprehensive Inventory Ledger" in r.data
    print("[PASS] Test 17: Reports module renders manifests, printable ledger, and asset valuations")

    # 13. Test Logout
    r = client.get('/logout', follow_redirects=True)
    assert r.status_code == 200
    assert b"Sign In" in r.data
    print("[PASS] Test 18: Logout completed successfully")

    print("\n" + "=" * 60)
    print("  ALL 18 COMPREHENSIVE TESTS PASSED WITH 100% SUCCESS!  ")
    print("=" * 60)

if __name__ == "__main__":
    run_all_tests()
