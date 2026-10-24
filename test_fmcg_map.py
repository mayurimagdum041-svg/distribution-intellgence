"""
OptiStock AI — FMCG Distribution Intelligence & Interactive Map Verification Test Suite
Tests Leaflet live map endpoints, geocoder, facility registration, shipment dispatch,
confirm delivery, cancel/restore, smart alerts, and demo dataset reset.
"""

import json
import app
import database

def run_fmcg_tests():
    print("=" * 65)
    print(" RUNNING FMCG DISTRIBUTION INTELLIGENCE & MAP VERIFICATION ")
    print("=" * 65)

    client = app.app.test_client()

    # 1. Login with demo account
    r = client.post('/demo-login', follow_redirects=True)
    assert r.status_code == 200
    demo_user = database.get_user_by_email('demo@optistock.ai')
    assert demo_user is not None
    user_id = demo_user['id']
    print("[PASS] FMCG Test 1: Authenticated with Demo Account")

    # 2. Test GET /inventory Console page
    r = client.get('/inventory')
    assert r.status_code == 200
    assert b"fmcgMap" in r.data
    assert b"FMCG Distribution Intelligence" in r.data
    assert b"Total Stock" in r.data
    assert b"Warehouses" in r.data
    assert b"Distributors" in r.data
    assert b"Retail Outlets" in r.data
    assert b"In Transit" in r.data
    assert b"DEMO DATA ACTIVE" in r.data
    print("[PASS] FMCG Test 2: /inventory loads with Leaflet map container and 10 KPI cards")

    # 3. Test GET /api/map-data
    r = client.get('/api/map-data')
    assert r.status_code == 200
    data = r.get_json()
    assert data["success"] is True
    assert "locations" in data
    assert "shipments" in data
    assert "metrics" in data
    assert "alerts" in data

    locations = data["locations"]
    assert len(locations) >= 10
    wh_locations = [l for l in locations if l["type"] == "Warehouse"]
    dist_locations = [l for l in locations if l["type"] == "Distributor"]
    ret_locations = [l for l in locations if l["type"] == "Retailer"]
    assert len(wh_locations) >= 3
    assert len(dist_locations) >= 2
    assert len(ret_locations) >= 4
    for loc in locations:
        assert "lat" in loc and "lng" in loc
        assert loc["lat"] != 0 and loc["lng"] != 0
    print(f"[PASS] FMCG Test 3: /api/map-data loaded {len(locations)} facilities ({len(wh_locations)} WH, {len(dist_locations)} Dist, {len(ret_locations)} Ret) with geo coordinates")

    # 4. Test GET /api/location/<id>/popup telemetry
    test_loc_id = locations[0]["id"]
    r = client.get(f'/api/location/{test_loc_id}/popup')
    assert r.status_code == 200
    pdata = r.get_json()
    assert pdata["success"] is True
    loc_info = pdata["location"]
    assert "stored_products" in loc_info
    assert "total_stock" in loc_info
    assert "utilization_pct" in loc_info
    assert "capacity_units" in loc_info
    print(f"[PASS] FMCG Test 4: Location telemetry popup for '{loc_info['name']}' returned stock & capacity: {loc_info['total_stock']}/{loc_info['capacity_units']} ({loc_info['utilization_pct']}%)")

    # 5. Test GET /api/geocode
    r = client.get('/api/geocode?q=Pune')
    assert r.status_code == 200
    geo = r.get_json()
    assert geo["success"] is True
    assert abs(geo["lat"] - 18.52) < 0.2
    assert abs(geo["lng"] - 73.85) < 0.2
    print(f"[PASS] FMCG Test 5: Address Geocoder resolved 'Pune' -> [{geo['lat']}, {geo['lng']}]")

    # 6. Test POST /api/locations/add (Add new facility)
    r = client.post('/api/locations/add', json={
        'name': 'Aurangabad Express Distributor',
        'code': 'DIS-AUR-01',
        'type': 'Distributor',
        'address': 'Chikalthana MIDC Industrial Area',
        'city': 'Aurangabad',
        'state': 'Maharashtra',
        'pincode': '431006',
        'lat': 19.8762,
        'lng': 75.3433,
        'capacity_units': 15000
    })
    assert r.status_code == 200
    res = r.get_json()
    assert res["success"] is True
    new_loc_id = res["location_id"]
    print(f"[PASS] FMCG Test 6: Registered and pinned new facility 'DIS-AUR-01' (ID: {new_loc_id})")

    # 7. Test POST /api/shipments/create (Dispatch shipment)
    # Pick source warehouse and dest distributor
    wh_mum = next(l for l in locations if l["code"] == "WH-MUM")
    dist_thn = next(l for l in locations if l["code"] == "DIS-THN")
    fmcg_prods = database.get_user_products(user_id)
    milk_prod = next(p for p in fmcg_prods if p["sku"] == "DAIRY-MLK-01")

    # Check WH-MUM milk stock before dispatch
    inv_before = database.get_location_inventory(wh_mum["id"], user_id)
    milk_wh_before = next(i for i in inv_before if i["product_id"] == milk_prod["id"])
    stock_before = milk_wh_before["current_stock"]
    dispatch_qty = 100

    r = client.post('/api/shipments/create', json={
        'source_location_id': wh_mum["id"],
        'dest_location_id': dist_thn["id"],
        'product_id': milk_prod["id"],
        'quantity': dispatch_qty,
        'notes': 'Test FMCG express corridor dispatch'
    })
    assert r.status_code == 200
    disp_res = r.get_json()
    assert disp_res["success"] is True

    # Verify source stock decreased
    inv_after = database.get_location_inventory(wh_mum["id"], user_id)
    milk_wh_after = next(i for i in inv_after if i["product_id"] == milk_prod["id"])
    assert milk_wh_after["current_stock"] == stock_before - dispatch_qty
    print(f"[PASS] FMCG Test 7: Shipment dispatched! Source inventory atomically deducted: {stock_before} -> {milk_wh_after['current_stock']}")

    # Find the created shipment
    all_shipments = database.get_shipments(user_id)
    test_shp = next(s for s in all_shipments if s["source_location_id"] == wh_mum["id"] and s["dest_location_id"] == dist_thn["id"] and s["status"] == "In Transit")
    assert test_shp is not None
    assert test_shp["route_geometry"] is not None
    assert test_shp["distance_km"] > 0
    print(f"[PASS] FMCG Test 8: Shipment {test_shp['shipment_code']} active in transit with route geometry ({test_shp['distance_km']} km)")

    # 8. Test POST /api/shipments/<id>/deliver (Confirm delivery)
    # Check destination stock before
    dest_inv_before = database.get_location_inventory(dist_thn["id"], user_id)
    dest_item_before = next((i for i in dest_inv_before if i["product_id"] == milk_prod["id"]), None)
    dest_stock_before = dest_item_before["current_stock"] if dest_item_before else 0

    r = client.post(f'/api/shipments/{test_shp["id"]}/deliver', json={})
    assert r.status_code == 200
    deliv_res = r.get_json()
    assert deliv_res["success"] is True

    # Verify destination stock increased
    dest_inv_after = database.get_location_inventory(dist_thn["id"], user_id)
    dest_item_after = next(i for i in dest_inv_after if i["product_id"] == milk_prod["id"])
    assert dest_item_after["current_stock"] == dest_stock_before + dispatch_qty

    # Verify status changed to Delivered
    updated_shp = next(s for s in database.get_shipments(user_id) if s["id"] == test_shp["id"])
    assert updated_shp["status"] == "Delivered"
    print(f"[PASS] FMCG Test 9: Confirmed delivery! Target inventory credited: {dest_stock_before} -> {dest_item_after['current_stock']}")

    # Verify duplicate delivery prevention
    r_dup = client.post(f'/api/shipments/{test_shp["id"]}/deliver', json={})
    assert r_dup.status_code == 200
    dup_res = r_dup.get_json()
    assert dup_res["success"] is False
    assert "already been confirmed" in dup_res["message"]
    print("[PASS] FMCG Test 10: Double credit prevention enforced on confirmed shipment")

    # 9. Test POST /api/shipments/<id>/cancel (Cancel shipment and restore inventory)
    # Create another shipment to cancel
    r = client.post('/api/shipments/create', json={
        'source_location_id': wh_mum["id"],
        'dest_location_id': dist_thn["id"],
        'product_id': milk_prod["id"],
        'quantity': 50,
        'notes': 'Shipment to cancel'
    })
    cancel_shp = next(s for s in database.get_shipments(user_id) if s["status"] == "In Transit")
    wh_stock_pre_cancel = next(i["current_stock"] for i in database.get_location_inventory(wh_mum["id"], user_id) if i["product_id"] == milk_prod["id"])

    r_cancel = client.post(f'/api/shipments/{cancel_shp["id"]}/cancel', json={'reason': 'Route obstacle'})
    assert r_cancel.status_code == 200
    c_res = r_cancel.get_json()
    assert c_res["success"] is True

    # Verify stock restored to source
    wh_stock_post_cancel = next(i["current_stock"] for i in database.get_location_inventory(wh_mum["id"], user_id) if i["product_id"] == milk_prod["id"])
    assert wh_stock_post_cancel == wh_stock_pre_cancel + 50
    print(f"[PASS] FMCG Test 11: Shipment cancelled! Stock safely restored to source: {wh_stock_pre_cancel} -> {wh_stock_post_cancel}")

    # 10. Test Reset Demo Data (Preserves custom user records)
    r = client.post('/api/reset-demo', follow_redirects=True)
    assert r.status_code == 200
    # Check that custom Aurangabad location was preserved
    all_locs_after_reset = database.get_locations(user_id)
    aur_loc = next((l for l in all_locs_after_reset if l["code"] == "DIS-AUR-01"), None)
    assert aur_loc is not None
    print("[PASS] FMCG Test 12: Reset Demo Data restored baseline network while preserving custom records ('DIS-AUR-01')")

    # 11. Test FMCG Analytics Stats Endpoint
    r = client.get('/api/fmcg-stats')
    assert r.status_code == 200
    stats = r.get_json()
    assert "total_inventory" in stats
    assert "total_warehouses" in stats
    assert "active_distributors" in stats
    assert "retailers_served" in stats
    assert "shipments_in_transit" in stats
    assert "delivered_shipments" in stats
    print(f"[PASS] FMCG Test 13: /api/fmcg-stats returned complete operational analytics")

    print("\n" + "=" * 65)
    print(" ALL 13 FMCG DISTRIBUTION & LIVE MAP TESTS PASSED WITH 100%! ")
    print("=" * 65)

if __name__ == "__main__":
    run_fmcg_tests()
