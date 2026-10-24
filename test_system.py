import app
import database

def run_tests():
    client = app.app.test_client()

    # 1. Test index redirect
    r = client.get('/')
    assert r.status_code == 302
    print("Test 1: Index redirect -> OK")

    # 2. Test login page GET
    r = client.get('/login')
    assert r.status_code == 200
    assert b"Sign In" in r.data
    print("Test 2: Login page GET -> OK")

    # 3. Test Registration: Password mismatch
    r = client.post('/register', data={
        'name': 'Test User',
        'email': 'testuser@optistock.ai',
        'password': 'password123',
        'confirm_password': 'mismatchpassword'
    }, follow_redirects=True)
    assert b"Passwords do not match" in r.data
    print("Test 3: Registration password mismatch validation -> OK")

    # 4. Test Registration: Password too short
    r = client.post('/register', data={
        'name': 'Test User',
        'email': 'testuser@optistock.ai',
        'password': '123',
        'confirm_password': '123'
    }, follow_redirects=True)
    assert b"at least 6 characters" in r.data
    print("Test 4: Registration password length validation -> OK")

    # 5. Test Successful Registration
    r = client.post('/register', data={
        'name': 'Pooja Patil',
        'email': 'pooja@retailmart.in',
        'password': 'securepass123',
        'confirm_password': 'securepass123'
    }, follow_redirects=True)
    assert r.status_code == 200
    assert b"Welcome to OptiStock AI" in r.data or b"Pooja Patil" in r.data
    print("Test 5: Registration successful with automatic 3 starter items -> OK")

    # Verify starter items were loaded for Pooja
    user = database.get_user_by_email('pooja@retailmart.in')
    assert user is not None
    pooja_products = database.get_user_products(user['id'])
    assert len(pooja_products) == 3
    print(f"Test 6: Starter items verified for new user -> {len(pooja_products)} items loaded")

    # 6. Test Demo Login POST
    r = client.post('/demo-login', follow_redirects=True)
    assert r.status_code == 200
    assert b"Analytics &amp; Intelligence Dashboard" in r.data or b"Analytics & Intelligence Dashboard" in r.data
    print("Test 7: Demo login POST & Dashboard GET -> OK")

    # 7. Test Add Product with negative numbers (Validation)
    r = client.post('/add-product', data={
        'name': 'Faulty Item',
        'category': 'Electronics',
        'current_stock': '-10',
        'units_sold_per_day': '5',
        'price': '-100',
        'min_stock_level': '5',
        'prediction_period': '7'
    }, follow_redirects=True)
    assert b"must be non-negative" in r.data
    print("Test 8: Add product negative validation -> OK")

    # 8. Test Add Product Valid
    r = client.post('/add-product', data={
        'name': 'Premium Wireless Mouse',
        'category': 'Electronics',
        'current_stock': '75',
        'units_sold_per_day': '6',
        'price': '899.00',
        'min_stock_level': '20',
        'prediction_period': '15'
    }, follow_redirects=True)
    assert b"Premium Wireless Mouse" in r.data
    print("Test 9: Add product successful -> OK")

    # Find the newly added product
    demo_user = database.get_user_by_email('demo@optistock.ai')
    products = database.get_user_products(demo_user['id'])
    new_prod = next(p for p in products if p['name'] == 'Premium Wireless Mouse')
    assert new_prod['predicted_demand'] == 6 * 15 # 90
    assert new_prod['expected_remaining_stock'] == 75 - 90 # -15 -> Critical
    assert new_prod['status'] == 'Critical'
    assert new_prod['recommended_restock'] == max(0, 90 + 20 - 75) # 35
    print("Test 10: Product prediction calculated accurately in DB -> OK")

    # 9. Test Edit Product
    r = client.post(f"/edit-product/{new_prod['id']}", data={
        'name': 'Premium Wireless Mouse V2',
        'category': 'Electronics',
        'current_stock': '150', # increased stock
        'units_sold_per_day': '6',
        'price': '899.00',
        'min_stock_level': '20',
        'prediction_period': '15'
    }, follow_redirects=True)
    assert r.status_code == 200
    updated_prod = database.get_product_by_id(new_prod['id'], demo_user['id'])
    assert updated_prod['name'] == 'Premium Wireless Mouse V2'
    assert updated_prod['current_stock'] == 150
    # 150 - 90 = 60 > 20 -> Healthy
    assert updated_prod['status'] == 'Healthy'
    print("Test 11: Edit product and status recalculation -> OK")

    # 10. Test Delete Product
    r = client.post(f"/delete-product/{new_prod['id']}", follow_redirects=True)
    assert r.status_code == 200
    deleted_check = database.get_product_by_id(new_prod['id'], demo_user['id'])
    assert deleted_check is None
    print("Test 12: Delete product -> OK")

    # 11. Test Chart Data API
    r = client.get('/api/chart-data')
    assert r.status_code == 200
    json_data = r.get_json()
    assert len(json_data['comparison']['labels']) > 0
    assert len(json_data['status']['counts']) == 3
    assert len(json_data['categories']['labels']) > 0
    print("Test 13: Chart data verified -> OK")

    # 12. Test Logout
    r = client.get('/logout', follow_redirects=True)
    assert r.status_code == 200
    print("Test 14: Logout -> OK")

    print("\n==============================================")
    print("  ALL 14 ADVANCED TEST SUITES PASSED 100%!   ")
    print("==============================================")

if __name__ == "__main__":
    run_tests()
