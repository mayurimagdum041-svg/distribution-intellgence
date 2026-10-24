"""
OptiStock AI - Distribution Intelligence & Inventory Optimization Engine
Flask Application & RESTful API Gateway
"""

import json
import os
from flask import Flask, render_template, jsonify, request
from engine.data_loader import (
    PRODUCTS,
    WAREHOUSES,
    STORES,
    INITIAL_BATCHES,
    DISTANCE_KM,
    calculate_transport_cost_per_unit,
    get_transit_time_days,
)
from engine.forecaster import forecaster
from engine.inventory_optimizer import (
    analyze_store_inventory_health,
    analyze_warehouse_batches,
    calculate_safety_stock,
)
from engine.allocator import allocator
from engine.simulator import simulator
from engine.automation_db import init_db, get_db_connection
from engine.automation_engine import (
    execute_workflow,
    approve_replenishment,
    reject_replenishment,
    approve_expiry_rescue,
    reject_expiry_rescue,
    resolve_alert,
    acknowledge_alert,
)
from engine.automation_scheduler import start_in_process_scheduler

app = Flask(__name__)

# Initialize database on startup
init_db()

# Auto-start in-process background scheduler (if enabled and not disabled for testing)
if os.environ.get("SCHEDULER_AUTOSTART", "1").lower() in ("1", "true", "yes"):
    if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        try:
            start_in_process_scheduler()
        except Exception as _e:
            app.logger.warning("Could not auto-start in-process scheduler: %s", _e)


@app.route("/")
def index():
    return render_template("simple.html")


# 4 User Roles & Profiles
USERS = {
    "admin": {
        "username": "admin",
        "name": "System Administrator",
        "role": "admin",
        "role_title": "Executive Admin",
        "badge": "👑 Administrator",
        "avatar": "AD",
        "color": "#2563eb",
        "allowed_sections": ["overview", "distribution", "inventory", "forecast", "whatif", "map"],
        "description": "Full access: Network-wide KPIs, SciPy MILP optimizer, simulations, and complete supply chain."
    },
    "warehouse": {
        "username": "warehouse",
        "name": "Pune Regional DC Head",
        "role": "warehouse",
        "role_title": "Warehouse Manager",
        "badge": "🏭 Warehouse Manager",
        "avatar": "WH",
        "color": "#d97706",
        "allowed_sections": ["inventory", "distribution", "map"],
        "description": "Lot-level tracking, cold-chain storage, FEFO expiry priorities, and outbound pallet dispatches."
    },
    "retail": {
        "username": "retail",
        "name": "Store Operations Head",
        "role": "retail",
        "role_title": "Retail Store Manager",
        "badge": "🏪 Retail Store Manager",
        "avatar": "RT",
        "color": "#16a34a",
        "allowed_sections": ["inventory", "distribution", "forecast"],
        "description": "Store stock levels, Days of Cover, Reorder Points (ROP), stockout alerts, and ML demand forecasts."
    },
    "delivery": {
        "username": "delivery",
        "name": "Maharashtra Corridor Fleet",
        "role": "delivery",
        "role_title": "Delivery Partner & Driver",
        "badge": "🚚 Delivery Fleet",
        "avatar": "DL",
        "color": "#7c3aed",
        "allowed_sections": ["map", "distribution"],
        "description": "Dispatch manifests, road transit routes, and delivery checkpoints for Pune, Satara, Kolhapur, Sangli, Karad."
    }
}

# Live in-memory delivery status tracker for stops
DELIVERY_STOPS = {
    "LOC-PUNE": {"city": "Pune", "status": "In Transit", "eta": "45 mins", "driver": "Rajesh Shinde", "vehicle": "MH-12-Q-4021"},
    "LOC-SATARA": {"city": "Satara", "status": "Dispatched", "eta": "2 hrs 10 mins", "driver": "Sachin Kadam", "vehicle": "MH-11-V-8812"},
    "LOC-KOLHAPUR": {"city": "Kolhapur", "status": "Out for Delivery", "eta": "3 hrs 30 mins", "driver": "Amit Patil", "vehicle": "MH-09-AA-1004"},
    "LOC-SANGLI": {"city": "Sangli", "status": "In Transit", "eta": "3 hrs 45 mins", "driver": "Sunil More", "vehicle": "MH-10-CX-9421"},
    "LOC-KARAD": {"city": "Karad", "status": "Scheduled", "eta": "2 hrs 40 mins", "driver": "Nitin Sawant", "vehicle": "MH-50-B-3100"},
}

@app.route("/simple")
def simple():
    """Light-theme, simplified dashboard for presentations and quick reviews."""
    return render_template("simple.html")


# 4-Digit Security PINs for Each Role
USER_PINS = {
    "admin": "1111",      # 👑 Admin PIN
    "warehouse": "2222",  # 🏭 Warehouse PIN
    "retail": "3333",     # 🏪 Retail PIN
    "delivery": "4444"    # 🚚 Delivery PIN
}

@app.route("/api/auth/verify-pin", methods=["POST"])
def api_verify_pin():
    """Validates the 4-digit PIN for the requested user role."""
    data = request.get_json(silent=True) or {}
    role = data.get("role")
    pin = str(data.get("pin", "")).strip()

    if role in USER_PINS and USER_PINS[role] == pin:
        user_info = dict(USERS[role])
        return jsonify({"success": True, "user": user_info})

    return jsonify({"success": False, "error": f"Invalid PIN for {role.capitalize() if role else 'user'}."}), 401


@app.route("/api/users")
def api_users():
    """Returns available user roles and profiles."""
    return jsonify({"users": list(USERS.values())})


@app.route("/api/delivery/stops", methods=["GET", "POST"])
def api_delivery_stops():
    """Get or update active delivery stops and their shipment progress."""
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        loc_id = data.get("loc_id")
        new_status = data.get("status")
        if loc_id in DELIVERY_STOPS and new_status:
            DELIVERY_STOPS[loc_id]["status"] = new_status
            return jsonify({"success": True, "stop": DELIVERY_STOPS[loc_id]})
        return jsonify({"error": "Invalid location or status"}), 400
    return jsonify(DELIVERY_STOPS)


@app.route("/api/meta")
def api_meta():
    """Returns static metadata: products, warehouses, stores, and model assumptions."""
    return jsonify({
        "products": PRODUCTS,
        "warehouses": WAREHOUSES,
        "stores": STORES,
        "assumptions": {
            "planning_horizons": [1, 3, 7, 14],
            "solver": "SciPy HiGHS Mixed-Integer Linear Programming (MILP)",
            "service_levels": [90.0, 95.0, 98.0, 99.0],
            "forecasting_model": "Autoregressive Ridge Regression with Lag & Promotion Features",
            "stockout_penalty_multiplier": "2.2x Retail Selling Price",
            "fefo_priority_window_days": 4,
            "transport_cost_structure": "Distance (km) * Fleet Rate (Cold-Chain Rs. 0.024/kg-km vs Ambient Rs. 0.014/kg-km) * Weight + Fixed Handling",
        }
    })


@app.route("/api/summary")
def api_summary():
    """Returns executive KPIs and financial summary for the default 3-day horizon."""
    try:
        horizon = int(request.args.get("days", 3))
    except (ValueError, TypeError):
        horizon = 3

    plan = allocator.solve(horizon_days=horizon)
    batches = analyze_warehouse_batches()
    stores = analyze_store_inventory_health(horizon_days=horizon)

    total_inventory_units = sum(b["quantity"] for b in batches)
    total_inventory_value = round(sum(b["inventory_value"] for b in batches), 2)
    critical_stockouts = sum(1 for s in stores if s["risk_status"] == "Critical")
    warning_stockouts = sum(1 for s in stores if s["risk_status"] == "Warning")
    urgent_batches = sum(1 for b in batches if b["status"] == "Urgent")

    b_mark = plan["benchmark"]

    return jsonify({
        "horizon_days": horizon,
        "total_inventory_units": total_inventory_units,
        "total_inventory_value": total_inventory_value,
        "warehouse_count": len(WAREHOUSES),
        "store_count": len(STORES),
        "product_count": len(PRODUCTS),
        "critical_stockouts": critical_stockouts,
        "warning_stockouts": warning_stockouts,
        "urgent_expiry_batches": urgent_batches,
        "shipment_count": plan["shipment_count"],
        "units_shipped": plan["units_shipped"],
        "total_unmet_units": plan["total_unmet_units"],
        "total_transport_cost": plan["total_transport_cost"],
        "baseline_transport_cost": b_mark["baseline_transport_cost"],
        "transport_savings": b_mark["transport_savings"],
        "transport_savings_pct": b_mark["transport_savings_pct"],
        "spoilage_averted_savings": b_mark["spoilage_averted_savings"],
        "total_economic_benefit": b_mark["total_economic_benefit"],
        "fulfillment_rate_ai": b_mark["fulfillment_rate_ai"],
        "fulfillment_rate_baseline": b_mark["fulfillment_rate_baseline"],
        "stockouts_prevented_units": b_mark["stockouts_prevented_units"],
    })


@app.route("/api/plan")
def api_plan():
    """Calculates and returns the optimized MILP distribution plan with explainable rationales."""
    try:
        horizon = int(request.args.get("days", 3))
    except (ValueError, TypeError):
        horizon = 3

    try:
        fuel_multiplier = float(request.args.get("fuel", 1.0))
    except (ValueError, TypeError):
        fuel_multiplier = 1.0

    try:
        demand_shock = float(request.args.get("shock", 0.0))
    except (ValueError, TypeError):
        demand_shock = 0.0

    disabled_raw = request.args.get("disabled", "")
    disabled_warehouses = [x.strip() for x in disabled_raw.split(",") if x.strip()]

    plan = allocator.solve(
        horizon_days=horizon,
        fuel_multiplier=fuel_multiplier,
        demand_shock_pct=demand_shock,
        disabled_warehouses=disabled_warehouses,
    )
    return jsonify(plan)


@app.route("/api/inventory/stores")
def api_store_inventory():
    """Returns store-level inventory health, safety stocks, ROP, and stockout risk."""
    try:
        horizon = int(request.args.get("days", 3))
    except (ValueError, TypeError):
        horizon = 3

    try:
        service_level = float(request.args.get("service_level", 95.0))
    except (ValueError, TypeError):
        service_level = 95.0

    try:
        demand_shock = float(request.args.get("shock", 0.0))
    except (ValueError, TypeError):
        demand_shock = 0.0

    records = analyze_store_inventory_health(
        horizon_days=horizon,
        service_level_pct=service_level,
        demand_shock_pct=demand_shock,
    )
    return jsonify(records)


@app.route("/api/inventory/warehouses")
def api_warehouse_inventory():
    """Returns warehouse batch inventory, shelf-life tracker, and spoilage risk."""
    records = analyze_warehouse_batches()
    return jsonify(records)


@app.route("/api/forecast")
def api_forecast():
    """Returns ML demand forecast, confidence intervals, and metrics for a store-SKU."""
    store_id = request.args.get("store_id", "ST-MUM-S")
    try:
        product_id = int(request.args.get("product_id", 1))
    except (ValueError, TypeError):
        product_id = 1

    try:
        horizon = int(request.args.get("days", 7))
    except (ValueError, TypeError):
        horizon = 7

    try:
        data = forecaster.forecast_store_sku(
            store_id=store_id,
            product_id=product_id,
            horizon_days=horizon,
        )
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/scenario", methods=["POST"])
def api_scenario():
    """Runs a What-If scenario simulation with custom operational shocks."""
    body = request.get_json(silent=True) or {}
    horizon = int(body.get("horizon_days", 3))
    demand_shock = float(body.get("demand_shock_pct", 0.0))
    fuel_multiplier = float(body.get("fuel_multiplier", 1.0))
    disabled = body.get("disabled_warehouses", [])

    result = simulator.run_scenario(
        horizon_days=horizon,
        demand_shock_pct=demand_shock,
        fuel_multiplier=fuel_multiplier,
        disabled_warehouses=disabled,
    )
    return jsonify(result)


@app.route("/api/network")
def api_network():
    """Returns network nodes and connection topology with distances and transit times."""
    nodes = []
    for w in WAREHOUSES:
        nodes.append({
            "id": w["id"],
            "name": w["name"],
            "type": "warehouse",
            "city": w["city"],
            "lat": w["lat"],
            "lng": w["lng"],
            "capacity": w["capacity_pallets"],
            "cold_chain": w["has_cold_chain"],
        })

    for s in STORES:
        nodes.append({
            "id": s["id"],
            "name": s["name"],
            "type": "store",
            "city": s["city"],
            "lat": s["lat"],
            "lng": s["lng"],
            "tier": s["tier"],
            "store_type": s["type"],
        })

    links = []
    for (w_id, s_id), dist in DISTANCE_KM.items():
        links.append({
            "source": w_id,
            "target": s_id,
            "distance_km": dist,
            "transit_days": get_transit_time_days(w_id, s_id),
        })

    return jsonify({"nodes": nodes, "links": links})


# ===========================================================================
# AUTOMATION CONTROL PANEL & WORKFLOW API GATEWAYS
# ===========================================================================

@app.route("/api/automation/status")
def api_automation_status():
    """Returns status, run statistics and configs for all automated workflows."""
    conn = get_db_connection()
    try:
        workflows = conn.execute("SELECT * FROM automation_configs ORDER BY id;").fetchall()
        wf_list = []
        for w in workflows:
            wf_list.append({
                "id": w["id"],
                "name": w["name"],
                "description": w["description"],
                "enabled": bool(w["enabled"]),
                "interval_seconds": w["interval_seconds"],
                "last_run_at": w["last_run_at"],
                "next_run_at": w["next_run_at"],
                "last_status": w["last_status"],
                "last_error": w["last_error"],
                "actions_count": w["actions_count"],
                "config": json.loads(w["config_json"] or "{}"),
            })

        # Summary statistics
        total_alerts = conn.execute("SELECT COUNT(*) as c FROM alerts WHERE status IN ('OPEN', 'ACKNOWLEDGED');").fetchone()["c"]
        pending_replenish = conn.execute("SELECT COUNT(*) as c FROM replenishment_requests WHERE status = 'PENDING_APPROVAL';").fetchone()["c"]
        pending_rescue = conn.execute("SELECT COUNT(*) as c FROM expiry_rescue_transfers WHERE status = 'PENDING_APPROVAL';").fetchone()["c"]
        delayed_deliveries = conn.execute("SELECT COUNT(*) as c FROM delivery_shipments WHERE status = 'DELAYED';").fetchone()["c"]

        return jsonify({
            "workflows": wf_list,
            "metrics": {
                "active_alerts": total_alerts,
                "pending_replenishments": pending_replenish,
                "pending_expiry_rescues": pending_rescue,
                "delayed_shipments": delayed_deliveries,
            }
        })
    finally:
        conn.close()


@app.route("/api/automation/toggle", methods=["POST"])
def api_automation_toggle():
    """Enables or disables an automation workflow."""
    body = request.get_json(silent=True) or {}
    workflow_id = body.get("workflow_id")
    enabled = int(bool(body.get("enabled", True)))

    if not workflow_id:
        return jsonify({"error": "workflow_id is required"}), 400

    conn = get_db_connection()
    try:
        with conn:
            cur = conn.execute("UPDATE automation_configs SET enabled = ?, updated_at = datetime('now') WHERE id = ?;", (enabled, workflow_id))
            if cur.rowcount == 0:
                return jsonify({"error": "Workflow not found"}), 404
        return jsonify({"success": True, "workflow_id": workflow_id, "enabled": bool(enabled)})
    finally:
        conn.close()


@app.route("/api/automation/run", methods=["POST"])
def api_automation_run():
    """Triggers immediate execution of a workflow (supports dry_run mode)."""
    body = request.get_json(silent=True) or {}
    workflow_id = body.get("workflow_id")
    dry_run = bool(body.get("dry_run", False))

    if not workflow_id:
        return jsonify({"error": "workflow_id is required"}), 400

    result = execute_workflow(workflow_id=workflow_id, dry_run=dry_run)
    return jsonify(result)


@app.route("/api/automation/history")
def api_automation_history():
    """Returns execution history logs for workflows."""
    wf_id = request.args.get("workflow_id")
    limit = int(request.args.get("limit", 30))

    conn = get_db_connection()
    try:
        if wf_id:
            rows = conn.execute("""
            SELECT * FROM automation_execution_logs 
            WHERE workflow_id = ? 
            ORDER BY started_at DESC LIMIT ?;
            """, (wf_id, limit)).fetchall()
        else:
            rows = conn.execute("""
            SELECT * FROM automation_execution_logs 
            ORDER BY started_at DESC LIMIT ?;
            """, (limit,)).fetchall()

        history = [dict(r) for r in rows]
        return jsonify({"history": history})
    finally:
        conn.close()


@app.route("/api/automation/replenishment")
def api_automation_replenishment():
    """Returns replenishment recommendations with status filter."""
    status = request.args.get("status", "PENDING_APPROVAL")
    conn = get_db_connection()
    try:
        if status and status != "all":
            rows = conn.execute("SELECT * FROM replenishment_requests WHERE status = ? ORDER BY id DESC;", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM replenishment_requests ORDER BY id DESC LIMIT 100;").fetchall()
        return jsonify({"requests": [dict(r) for r in rows]})
    finally:
        conn.close()


@app.route("/api/automation/replenishment/action", methods=["POST"])
def api_automation_replenishment_action():
    """Approves or rejects a replenishment recommendation (Manager action)."""
    body = request.get_json(silent=True) or {}
    request_id = body.get("request_id")
    action = (body.get("action") or "").lower()
    manager_name = body.get("manager_name") or "Supply Chain Manager"
    notes = body.get("notes")

    if not request_id or action not in ("approve", "reject"):
        return jsonify({"error": "request_id and valid action ('approve'|'reject') required"}), 400

    if action == "approve":
        result = approve_replenishment(request_id=request_id, manager_name=manager_name, notes=notes)
    else:
        result = reject_replenishment(request_id=request_id, manager_name=manager_name, reason=notes)

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@app.route("/api/automation/expiry-rescue")
def api_automation_expiry_rescue():
    """Returns expiry rescue recommendations."""
    status = request.args.get("status", "PENDING_APPROVAL")
    conn = get_db_connection()
    try:
        if status and status != "all":
            rows = conn.execute("SELECT * FROM expiry_rescue_transfers WHERE status = ? ORDER BY batch_expiry_days ASC;", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM expiry_rescue_transfers ORDER BY id DESC LIMIT 100;").fetchall()
        return jsonify({"transfers": [dict(r) for r in rows]})
    finally:
        conn.close()


@app.route("/api/automation/expiry-rescue/action", methods=["POST"])
def api_automation_expiry_rescue_action():
    """Approves or rejects an expiry rescue transfer (Manager action)."""
    body = request.get_json(silent=True) or {}
    transfer_id = body.get("transfer_id")
    action = (body.get("action") or "").lower()
    manager_name = body.get("manager_name") or "Warehouse Operations Lead"
    notes = body.get("notes")

    if not transfer_id or action not in ("approve", "reject"):
        return jsonify({"error": "transfer_id and valid action ('approve'|'reject') required"}), 400

    if action == "approve":
        result = approve_expiry_rescue(transfer_id=transfer_id, manager_name=manager_name, notes=notes)
    else:
        result = reject_expiry_rescue(transfer_id=transfer_id, manager_name=manager_name, reason=notes)

    status_code = 200 if result.get("success") else 400
    return jsonify(result), status_code


@app.route("/api/automation/distribution-options")
def api_automation_distribution_options():
    """Returns ranked candidate warehouses for stores needing inventory."""
    conn = get_db_connection()
    try:
        rows = conn.execute("""
        SELECT * FROM distribution_recommendations 
        WHERE status = 'ACTIVE' 
        ORDER BY store_name, product_name, warehouse_rank ASC;
        """).fetchall()
        return jsonify({
            "recommendations": [dict(r) for r in rows],
            "data_classification": "SIMULATED_SAMPLE",
            "note": "Warehouse rankings are calculated from road distances, cold-chain rate models, and simulated batch availability."
        })
    finally:
        conn.close()


@app.route("/api/automation/deliveries")
def api_automation_deliveries():
    """Returns active delivery shipments and delay monitoring status."""
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM delivery_shipments ORDER BY dispatched_at DESC;").fetchall()
        return jsonify({
            "shipments": [dict(r) for r in rows],
            "note": "Shipment milestones are logged via checkpoint manifest status. No live GPS hardware claimed."
        })
    finally:
        conn.close()


@app.route("/api/automation/alerts")
def api_automation_alerts():
    """Returns database-backed alerts with optional filtering."""
    status = request.args.get("status")
    severity = request.args.get("severity")
    alert_type = request.args.get("type")

    query = "SELECT * FROM alerts WHERE 1=1"
    params = []

    if status and status != "all":
        query += " AND status = ?"
        params.append(status)
    elif not status:
        query += " AND status IN ('OPEN', 'ACKNOWLEDGED')"

    if severity and severity != "all":
        query += " AND severity = ?"
        params.append(severity)

    if alert_type and alert_type != "all":
        query += " AND alert_type = ?"
        params.append(alert_type)

    query += " ORDER BY CASE severity WHEN 'CRITICAL' THEN 1 WHEN 'WARNING' THEN 2 ELSE 3 END, created_at DESC LIMIT 100;"

    conn = get_db_connection()
    try:
        rows = conn.execute(query, params).fetchall()
        counts = {
            "critical": conn.execute("SELECT COUNT(*) as c FROM alerts WHERE status IN ('OPEN', 'ACKNOWLEDGED') AND severity = 'CRITICAL';").fetchone()["c"],
            "warning": conn.execute("SELECT COUNT(*) as c FROM alerts WHERE status IN ('OPEN', 'ACKNOWLEDGED') AND severity = 'WARNING';").fetchone()["c"],
            "total_open": conn.execute("SELECT COUNT(*) as c FROM alerts WHERE status IN ('OPEN', 'ACKNOWLEDGED');").fetchone()["c"],
        }
        return jsonify({
            "alerts": [dict(r) for r in rows],
            "counts": counts
        })
    finally:
        conn.close()


@app.route("/api/automation/alerts/action", methods=["POST"])
def api_automation_alerts_action():
    """Acknowledges or resolves an alert."""
    body = request.get_json(silent=True) or {}
    alert_id = body.get("alert_id")
    action = (body.get("action") or "").lower()
    user_name = body.get("user_name") or "Duty Manager"

    if not alert_id or action not in ("acknowledge", "resolve"):
        return jsonify({"error": "alert_id and valid action ('acknowledge'|'resolve') required"}), 400

    if action == "acknowledge":
        result = acknowledge_alert(alert_id=alert_id, user_name=user_name)
    else:
        result = resolve_alert(alert_id=alert_id, user_name=user_name)

    return jsonify(result)


if __name__ == "__main__":
    print("=" * 70)
    print("OptiStock AI - Distribution Intelligence & Inventory Optimization Engine")
    print("Local Server starting at: http://127.0.0.1:5000")
    print("=" * 70)
    app.run(host="0.0.0.0", port=5000, debug=True)
