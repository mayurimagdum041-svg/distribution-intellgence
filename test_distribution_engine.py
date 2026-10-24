"""
OptiStock AI — Problem Statement 2 Verification Test Suite
Tests:
1. Distribution Intelligence & Inventory Optimization Engine endpoint (/distribution-engine)
2. Supply Chain Efficiency Demonstration Metrics (Stockout Rate, Transport Costs, Wastage Prevention, Fill Rate)
3. Explicitly Stated Optimization Model Assumptions
4. Multi-Constraint 4-Tuple Recommendations (Which Product -> Which Location in What Quantity from Which Warehouse)
5. JSON API (/api/distribution/plan)
6. 1-Click Single Allocation Execution (/api/distribution/execute)
7. 1-Click Batch Plan Execution (/api/distribution/batch-execute)
"""

import app
import database

def run_distribution_engine_tests():
    print("=" * 70)
    print(" RUNNING PROBLEM STATEMENT 2: DISTRIBUTION INTELLIGENCE VERIFICATION ")
    print("=" * 70)

    client = app.app.test_client()

    # 1. Authenticate with demo account
    r = client.post('/demo-login', follow_redirects=True)
    assert r.status_code == 200
    demo_user = database.get_user_by_email('demo@optistock.ai')
    assert demo_user is not None
    user_id = demo_user['id']
    print("[PASS] Test 1: Authenticated with Demo Account")

    # 2. Test GET /distribution-engine Console page
    r = client.get('/distribution-engine')
    assert r.status_code == 200
    assert b"Distribution Intelligence &amp; Inventory Optimization Engine" in r.data or b"Distribution Intelligence & Inventory Optimization Engine" in r.data
    assert b"PROBLEM STATEMENT 2" in r.data
    # Efficiency metrics
    assert b"Stockout Incidence Rate" in r.data
    assert b"Transport Cost / Unit" in r.data
    assert b"Perishable Spoilage Risk" in r.data
    assert b"Network Order Fill Rate" in r.data
    # Stated assumptions
    assert b"Freight Transport Rate" in r.data
    assert b"FEFO Shelf Life Threshold" in r.data
    assert b"Haversine" in r.data or b"Geodesic Distance" in r.data
    print("[PASS] Test 2: /distribution-engine loaded with Problem Statement 2 KPIs, 4 efficiency cards, and stated assumptions")

    # 3. Test GET /api/distribution/plan
    r = client.get('/api/distribution/plan')
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    plan = data["plan"]
    assert "recommendations" in plan
    assert "summary" in plan
    assert "efficiency_metrics" in plan
    assert "assumptions" in plan

    recs = plan["recommendations"]
    assert len(recs) >= 5, f"Expected at least 5 recommendations, found {len(recs)}"

    # Validate 4-tuple recommendation attributes on every recommendation
    for rec in recs:
        assert "product_id" in rec and "product_name" in rec and "product_sku" in rec
        assert "source_id" in rec and "source_name" in rec and "source_code" in rec
        assert "dest_id" in rec and "dest_name" in rec and "dest_code" in rec
        assert "recommended_quantity" in rec and rec["recommended_quantity"] > 0
        assert "distance_km" in rec and rec["distance_km"] >= 0
        assert "freight_cost" in rec and rec["freight_cost"] >= 150.0
        assert "optimization_score" in rec and rec["optimization_score"] > 0
        assert "shelf_life_days" in rec

    top = recs[0]
    print(f"[PASS] Test 3: /api/distribution/plan returned {len(recs)} actionable 4-tuple recommendations (Top: {top['product_sku']} -> {top['dest_code']} from {top['source_code']}, Score: {top['optimization_score']}%)")

    # 4. Test 1-Click Single Recommendation Execution (/api/distribution/execute)
    first_rec = recs[0]
    src_id = first_rec["source_id"]
    dst_id = first_rec["dest_id"]
    p_id = first_rec["product_id"]
    qty_to_send = min(10, first_rec["recommended_quantity"])

    # Source stock before dispatch
    conn = database.get_db()
    c = conn.cursor()
    c.execute("SELECT current_stock FROM inventory WHERE user_id = ? AND location_id = ? AND product_id = ?", (user_id, src_id, p_id))
    stock_pre = c.fetchone()["current_stock"]
    conn.close()

    r = client.post('/api/distribution/execute', json={
        'source_id': src_id,
        'dest_id': dst_id,
        'product_id': p_id,
        'quantity': qty_to_send,
        'notes': 'Unit test single recommendation dispatch'
    })
    assert r.status_code == 200
    res = r.get_json()
    assert res["success"] is True

    # Source stock after dispatch
    conn = database.get_db()
    c = conn.cursor()
    c.execute("SELECT current_stock FROM inventory WHERE user_id = ? AND location_id = ? AND product_id = ?", (user_id, src_id, p_id))
    stock_post = c.fetchone()["current_stock"]
    conn.close()

    assert stock_post == stock_pre - qty_to_send
    print(f"[PASS] Test 4: 1-Click single dispatch executed atomically! Stock deducted: {stock_pre} -> {stock_post}")

    # 5. Test 1-Click Batch Execution (/api/distribution/batch-execute)
    r = client.post('/api/distribution/batch-execute', json={'min_score': 85.0})
    assert r.status_code == 200
    batch_res = r.get_json()
    assert batch_res["success"] is True
    assert "result" in batch_res
    print(f"[PASS] Test 5: 1-Click batch dispatch executed! Dispatched: {batch_res['result']['dispatched_count']} shipments, Units: {batch_res['result']['units_moved']}")

    print("\n" + "=" * 70)
    print(" ALL 5 PROBLEM STATEMENT 2 DISTRIBUTION ENGINE TESTS PASSED (100%)! ")
    print("=" * 70)

if __name__ == "__main__":
    run_distribution_engine_tests()
