from flask import Flask, render_template, jsonify, request
from datetime import date, timedelta
import random
import math

app = Flask(__name__)

# Demo data only. Replace with verified business data before real-world use.
PRODUCTS = [
    {"id": 1, "name": "Fresh Milk (1L)", "category": "Dairy", "shelf_life_days": 7, "unit_cost": 28},
    {"id": 2, "name": "Orange Juice (1L)", "category": "Beverages", "shelf_life_days": 45, "unit_cost": 55},
    {"id": 3, "name": "Digestive Biscuits", "category": "Snacks", "shelf_life_days": 180, "unit_cost": 22},
    {"id": 4, "name": "Cooking Oil (1L)", "category": "Grocery", "shelf_life_days": 365, "unit_cost": 115},
    {"id": 5, "name": "Yogurt Cup", "category": "Dairy", "shelf_life_days": 14, "unit_cost": 18},
]

WAREHOUSES = [
    {"id": "WH-PUN", "name": "Pune Central", "city": "Pune"},
    {"id": "WH-MUM", "name": "Mumbai Hub", "city": "Mumbai"},
    {"id": "WH-KOL", "name": "Kolhapur Depot", "city": "Kolhapur"},
]

STORES = [
    {"id": "ST-101", "name": "Market Square", "city": "Pune", "priority": "High"},
    {"id": "ST-102", "name": "Green Basket", "city": "Mumbai", "priority": "High"},
    {"id": "ST-103", "name": "City Mart", "city": "Kolhapur", "priority": "Medium"},
    {"id": "ST-104", "name": "Fresh Corner", "city": "Nashik", "priority": "Medium"},
    {"id": "ST-105", "name": "Daily Needs", "city": "Satara", "priority": "Low"},
]

# Inventory is by product and warehouse. Quantities and expiry dates are simulated.
INVENTORY = [
    {"product_id": 1, "warehouse_id": "WH-PUN", "quantity": 240, "expiry_days": 4},
    {"product_id": 1, "warehouse_id": "WH-MUM", "quantity": 170, "expiry_days": 6},
    {"product_id": 1, "warehouse_id": "WH-KOL", "quantity": 95, "expiry_days": 2},
    {"product_id": 2, "warehouse_id": "WH-PUN", "quantity": 180, "expiry_days": 28},
    {"product_id": 2, "warehouse_id": "WH-MUM", "quantity": 260, "expiry_days": 35},
    {"product_id": 2, "warehouse_id": "WH-KOL", "quantity": 110, "expiry_days": 20},
    {"product_id": 3, "warehouse_id": "WH-PUN", "quantity": 400, "expiry_days": 120},
    {"product_id": 3, "warehouse_id": "WH-MUM", "quantity": 250, "expiry_days": 150},
    {"product_id": 3, "warehouse_id": "WH-KOL", "quantity": 210, "expiry_days": 100},
    {"product_id": 4, "warehouse_id": "WH-PUN", "quantity": 300, "expiry_days": 240},
    {"product_id": 4, "warehouse_id": "WH-MUM", "quantity": 210, "expiry_days": 270},
    {"product_id": 4, "warehouse_id": "WH-KOL", "quantity": 160, "expiry_days": 200},
    {"product_id": 5, "warehouse_id": "WH-PUN", "quantity": 90, "expiry_days": 8},
    {"product_id": 5, "warehouse_id": "WH-MUM", "quantity": 130, "expiry_days": 10},
    {"product_id": 5, "warehouse_id": "WH-KOL", "quantity": 65, "expiry_days": 5},
]

# Average daily demand is intentionally simulated for the demo.
DAILY_DEMAND = {
    (1, "ST-101"): 22, (1, "ST-102"): 24, (1, "ST-103"): 18, (1, "ST-104"): 16, (1, "ST-105"): 12,
    (2, "ST-101"): 9, (2, "ST-102"): 15, (2, "ST-103"): 8, (2, "ST-104"): 10, (2, "ST-105"): 6,
    (3, "ST-101"): 18, (3, "ST-102"): 20, (3, "ST-103"): 14, (3, "ST-104"): 12, (3, "ST-105"): 10,
    (4, "ST-101"): 7, (4, "ST-102"): 8, (4, "ST-103"): 6, (4, "ST-104"): 5, (4, "ST-105"): 4,
    (5, "ST-101"): 14, (5, "ST-102"): 16, (5, "ST-103"): 12, (5, "ST-104"): 10, (5, "ST-105"): 8,
}

# Approximate shipping cost per unit from warehouse to store (₹).
DISTANCE_COST = {
    ("WH-PUN", "ST-101"): 1.2, ("WH-PUN", "ST-102"): 3.2, ("WH-PUN", "ST-103"): 2.5, ("WH-PUN", "ST-104"): 2.0, ("WH-PUN", "ST-105"): 1.4,
    ("WH-MUM", "ST-101"): 3.0, ("WH-MUM", "ST-102"): 1.1, ("WH-MUM", "ST-103"): 3.4, ("WH-MUM", "ST-104"): 2.4, ("WH-MUM", "ST-105"): 2.7,
    ("WH-KOL", "ST-101"): 2.6, ("WH-KOL", "ST-102"): 3.6, ("WH-KOL", "ST-103"): 1.0, ("WH-KOL", "ST-104"): 2.8, ("WH-KOL", "ST-105"): 1.8,
}

def get_product(product_id):
    return next(p for p in PRODUCTS if p["id"] == product_id)

def get_warehouse(warehouse_id):
    return next(w for w in WAREHOUSES if w["id"] == warehouse_id)

def get_store(store_id):
    return next(s for s in STORES if s["id"] == store_id)

def make_plan(horizon_days=3):
    """Greedy, explainable allocation: prioritize demand, lower transport cost,
    and stock with a shorter usable shelf life. This is a demo heuristic, not
    a globally optimal mathematical solver.
    """
    horizon_days = max(1, min(int(horizon_days), 14))
    remaining = {(i["product_id"], i["warehouse_id"]): i["quantity"] for i in INVENTORY}
    demand_left = {}
    for p in PRODUCTS:
        for s in STORES:
            daily = DAILY_DEMAND.get((p["id"], s["id"]), 0)
            demand_left[(p["id"], s["id"])] = daily * horizon_days

    shipments = []
    for p in PRODUCTS:
        product_id = p["id"]
        # Higher daily demand locations are handled first.
        store_order = sorted(STORES, key=lambda s: demand_left[(product_id, s["id"])], reverse=True)
        for store in store_order:
            key_demand = (product_id, store["id"])
            needed = demand_left[key_demand]
            if needed <= 0:
                continue
            # Prefer warehouses with a feasible shelf life, then lower cost,
            # then earlier expiry (FEFO). Demo transit time is assumed <= 1 day.
            candidates = []
            for inv in INVENTORY:
                if inv["product_id"] != product_id:
                    continue
                key_stock = (product_id, inv["warehouse_id"])
                qty = remaining.get(key_stock, 0)
                if qty <= 0 or inv["expiry_days"] <= 1:
                    continue
                cost = DISTANCE_COST.get((inv["warehouse_id"], store["id"]), 4.0)
                # Prefer shorter expiry when shelf life is adequate, then cost.
                candidates.append((inv["expiry_days"], cost, inv["warehouse_id"], qty))
            candidates.sort(key=lambda x: (x[0], x[1]))
            for expiry_days, cost, warehouse_id, available in candidates:
                if needed <= 0:
                    break
                send = min(needed, available)
                if send <= 0:
                    continue
                remaining[(product_id, warehouse_id)] -= send
                needed -= send
                shipments.append({
                    "product": p["name"],
                    "product_id": product_id,
                    "warehouse": get_warehouse(warehouse_id)["name"],
                    "warehouse_id": warehouse_id,
                    "store": store["name"],
                    "store_id": store["id"],
                    "city": store["city"],
                    "quantity": send,
                    "unit_transport_cost": round(cost, 2),
                    "transport_cost": round(send * cost, 2),
                    "expiry_days": expiry_days,
                    "reason": f"{send} units allocated from {get_warehouse(warehouse_id)['name']}; estimated demand over {horizon_days} days and transport cost considered."
                })
            demand_left[key_demand] = needed

    unmet = []
    for (product_id, store_id), qty in demand_left.items():
        if qty > 0:
            unmet.append({
                "product": get_product(product_id)["name"],
                "store": get_store(store_id)["name"],
                "city": get_store(store_id)["city"],
                "unmet_quantity": qty
            })

    total_transport = round(sum(x["transport_cost"] for x in shipments), 2)
    units_shipped = sum(x["quantity"] for x in shipments)
    total_unmet = sum(x["unmet_quantity"] for x in unmet)
    total_inventory = sum(x["quantity"] for x in INVENTORY)
    expiry_alerts = []
    for inv in INVENTORY:
        if inv["expiry_days"] <= 7:
            expiry_alerts.append({
                "product": get_product(inv["product_id"])["name"],
                "warehouse": get_warehouse(inv["warehouse_id"])["name"],
                "quantity": inv["quantity"],
                "expiry_days": inv["expiry_days"]
            })

    # Baseline: serve each store from the cheapest single warehouse for each product,
    # without FEFO prioritization. Used only as a simple comparison estimate.
    baseline_cost = 0
    for p in PRODUCTS:
        for s in STORES:
            need = DAILY_DEMAND.get((p["id"], s["id"]), 0) * horizon_days
            if need <= 0:
                continue
            costs = sorted(DISTANCE_COST.get((w["id"], s["id"]), 4.0) for w in WAREHOUSES)
            baseline_cost += need * costs[0]
    baseline_cost = round(baseline_cost, 2)
    savings = round(max(0, baseline_cost - total_transport), 2)
    return {
        "horizon_days": horizon_days,
        "shipments": shipments,
        "unmet": unmet,
        "total_transport_cost": total_transport,
        "baseline_transport_cost": baseline_cost,
        "estimated_savings": savings,
        "units_shipped": units_shipped,
        "total_unmet": total_unmet,
        "total_inventory": total_inventory,
        "expiry_alerts": expiry_alerts,
        "products": PRODUCTS,
        "warehouses": WAREHOUSES,
        "stores": STORES
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/summary")
def summary():
    plan = make_plan(3)
    return jsonify({
        "total_inventory": plan["total_inventory"],
        "warehouse_count": len(WAREHOUSES),
        "store_count": len(STORES),
        "product_count": len(PRODUCTS),
        "stockout_locations": len({x["store"] for x in plan["unmet"]}),
        "shipment_count": len(plan["shipments"]),
        "units_shipped": plan["units_shipped"],
        "transport_cost": plan["total_transport_cost"],
        "baseline_cost": plan["baseline_transport_cost"],
        "estimated_savings": plan["estimated_savings"],
        "expiry_alert_count": len(plan["expiry_alerts"])
    })

@app.route("/api/plan")
def api_plan():
    try:
        horizon = int(request.args.get("days", 3))
    except ValueError:
        horizon = 3
    return jsonify(make_plan(horizon))

@app.route("/api/inventory")
def inventory():
    result = []
    for inv in INVENTORY:
        p, w = get_product(inv["product_id"]), get_warehouse(inv["warehouse_id"])
        result.append({
            "product": p["name"], "category": p["category"],
            "warehouse": w["name"], "city": w["city"],
            "quantity": inv["quantity"], "expiry_days": inv["expiry_days"],
            "status": "Urgent" if inv["expiry_days"] <= 3 else ("Expiring soon" if inv["expiry_days"] <= 7 else "Healthy")
        })
    return jsonify(result)

@app.route("/api/forecast")
def forecast():
    # Simulated historical series + a simple moving-average forecast.
    # These are illustrative demo numbers, not actual sales predictions.
    rng = random.Random(17)
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    history = [sum(DAILY_DEMAND.get((p["id"], s["id"]), 0) for p in PRODUCTS for s in STORES) for _ in labels]
    history = [max(0, int(v * (0.88 + rng.random() * 0.24))) for v in history]
    moving_average = round(sum(history[-3:]) / 3)
    forecast_values = [round(moving_average * f) for f in (0.96, 1.02, 1.08, 1.04, 1.12, 1.18, 1.05)]
    return jsonify({"history_labels": labels, "history": history,
                    "forecast_labels": ["Next Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                    "forecast": forecast_values,
                    "method": "3-day moving average with illustrative day-of-week adjustment"})

@app.route("/api/products")
def products():
    return jsonify(PRODUCTS)

if __name__ == "__main__":
    app.run(debug=True)
