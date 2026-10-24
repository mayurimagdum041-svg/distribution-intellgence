"""
OptiStock AI - Multi-Echelon Inventory Optimizer
Calculates dynamic Safety Stock (SS), Reorder Points (ROP), Days of Cover (DoC),
Stockout Risk scoring, and Batch Shelf-Life Spoilage Risk analysis.
"""

import math
from typing import Dict, List, Tuple, Any
from engine.data_loader import (
    PRODUCTS,
    WAREHOUSES,
    STORES,
    INITIAL_BATCHES,
    DISTANCE_KM,
    get_transit_time_days,
)
from engine.forecaster import forecaster


# Simulated initial store on-hand inventory levels (units in store backroom/shelves)
# Some stores have low stock to create realistic stockout risks!
INITIAL_STORE_STOCK = {
    # Milk: ST-MUM-S has only 30 units (urgent replenishment needed!), ST-PUN-M has 80
    (1, "ST-MUM-S"): 30, (1, "ST-MUM-N"): 45, (1, "ST-PUN-M"): 80, (1, "ST-PUN-W"): 50, (1, "ST-THN"): 35,
    (1, "ST-NSH"): 40, (1, "ST-KOL"): 25, (1, "ST-AHM-P"): 60, (1, "ST-SUR-R"): 35, (1, "ST-VAD"): 20,

    # Yogurt
    (2, "ST-MUM-S"): 25, (2, "ST-MUM-N"): 30, (2, "ST-PUN-M"): 40, (2, "ST-PUN-W"): 20, (2, "ST-THN"): 25,
    (2, "ST-NSH"): 15, (2, "ST-KOL"): 18, (2, "ST-AHM-P"): 35, (2, "ST-SUR-R"): 22, (2, "ST-VAD"): 15,

    # Paneer
    (3, "ST-MUM-S"): 18, (3, "ST-MUM-N"): 22, (3, "ST-PUN-M"): 30, (3, "ST-PUN-W"): 15, (3, "ST-THN"): 12,
    (3, "ST-NSH"): 14, (3, "ST-KOL"): 10, (3, "ST-AHM-P"): 25, (3, "ST-SUR-R"): 15, (3, "ST-VAD"): 10,

    # Orange Juice
    (4, "ST-MUM-S"): 20, (4, "ST-MUM-N"): 25, (4, "ST-PUN-M"): 35, (4, "ST-PUN-W"): 18, (4, "ST-THN"): 22,
    (4, "ST-NSH"): 12, (4, "ST-KOL"): 15, (4, "ST-AHM-P"): 30, (4, "ST-SUR-R"): 18, (4, "ST-VAD"): 12,

    # Brown Bread
    (5, "ST-MUM-S"): 35, (5, "ST-MUM-N"): 40, (5, "ST-PUN-M"): 50, (5, "ST-PUN-W"): 30, (5, "ST-THN"): 32,
    (5, "ST-NSH"): 25, (5, "ST-KOL"): 20, (5, "ST-AHM-P"): 45, (5, "ST-SUR-R"): 28, (5, "ST-VAD"): 18,

    # Biscuits
    (6, "ST-MUM-S"): 60, (6, "ST-MUM-N"): 75, (6, "ST-PUN-M"): 85, (6, "ST-PUN-W"): 50, (6, "ST-THN"): 55,
    (6, "ST-NSH"): 40, (6, "ST-KOL"): 35, (6, "ST-AHM-P"): 70, (6, "ST-SUR-R"): 45, (6, "ST-VAD"): 30,

    # Tomato Ketchup
    (7, "ST-MUM-S"): 25, (7, "ST-MUM-N"): 30, (7, "ST-PUN-M"): 35, (7, "ST-PUN-W"): 20, (7, "ST-THN"): 22,
    (7, "ST-NSH"): 15, (7, "ST-KOL"): 12, (7, "ST-AHM-P"): 28, (7, "ST-SUR-R"): 18, (7, "ST-VAD"): 12,

    # Peanut Butter
    (8, "ST-MUM-S"): 20, (8, "ST-MUM-N"): 22, (8, "ST-PUN-M"): 25, (8, "ST-PUN-W"): 15, (8, "ST-THN"): 18,
    (8, "ST-NSH"): 12, (8, "ST-KOL"): 10, (8, "ST-AHM-P"): 22, (8, "ST-SUR-R"): 14, (8, "ST-VAD"): 10,

    # Sunflower Oil
    (9, "ST-MUM-S"): 30, (9, "ST-MUM-N"): 35, (9, "ST-PUN-M"): 40, (9, "ST-PUN-W"): 25, (9, "ST-THN"): 28,
    (9, "ST-NSH"): 20, (9, "ST-KOL"): 18, (9, "ST-AHM-P"): 35, (9, "ST-SUR-R"): 22, (9, "ST-VAD"): 15,

    # Basmati Rice
    (10, "ST-MUM-S"): 35, (10, "ST-MUM-N"): 40, (10, "ST-PUN-M"): 45, (10, "ST-PUN-W"): 28, (10, "ST-THN"): 30,
    (10, "ST-NSH"): 22, (10, "ST-KOL"): 20, (10, "ST-AHM-P"): 38, (10, "ST-SUR-R"): 25, (10, "ST-VAD"): 18,

    # Disinfectant
    (11, "ST-MUM-S"): 28, (11, "ST-MUM-N"): 32, (11, "ST-PUN-M"): 35, (11, "ST-PUN-W"): 22, (11, "ST-THN"): 25,
    (11, "ST-NSH"): 18, (11, "ST-KOL"): 15, (11, "ST-AHM-P"): 30, (11, "ST-SUR-R"): 20, (11, "ST-VAD"): 14,

    # Laundry Detergent
    (12, "ST-MUM-S"): 32, (12, "ST-MUM-N"): 38, (12, "ST-PUN-M"): 42, (12, "ST-PUN-W"): 25, (12, "ST-THN"): 28,
    (12, "ST-NSH"): 20, (12, "ST-KOL"): 18, (12, "ST-AHM-P"): 35, (12, "ST-SUR-R"): 24, (12, "ST-VAD"): 16,
}


def calculate_safety_stock(
    daily_demand: float,
    demand_std: float,
    lead_time_days: float = 1.0,
    lead_time_std: float = 0.25,
    service_level_pct: float = 95.0
) -> Dict[str, float]:
    """
    Computes statistical safety stock and reorder point:
      SS = Z * sqrt( L * sigma_D^2 + D^2 * sigma_L^2 )
      ROP = (D * L) + SS
    """
    # Z-factor mapping
    z_map = {90.0: 1.282, 95.0: 1.645, 98.0: 2.054, 99.0: 2.326}
    z = z_map.get(service_level_pct, 1.645)

    variance_term = (lead_time_days * (demand_std ** 2)) + ((daily_demand ** 2) * (lead_time_std ** 2))
    ss = z * math.sqrt(max(variance_term, 0.1))
    rop = (daily_demand * lead_time_days) + ss

    return {
        "service_level_z": z,
        "lead_time_days": lead_time_days,
        "safety_stock": round(ss, 1),
        "reorder_point": round(rop, 1),
    }


def analyze_store_inventory_health(
    horizon_days: int = 3,
    service_level_pct: float = 95.0,
    demand_shock_pct: float = 0.0
) -> List[Dict[str, Any]]:
    """
    Evaluates every store-SKU combination for:
      - Current on-hand inventory
      - Safety stock requirement
      - Reorder point (ROP)
      - Days of cover (DoC)
      - Net replenishment demand needed
      - Stockout Risk Category: 'Critical', 'Warning', 'Healthy'
    """
    demand_estimates = forecaster.get_network_demand_estimates(
        horizon_days=horizon_days, demand_shock_pct=demand_shock_pct
    )

    records = []
    for store in STORES:
        s_id = store["id"]
        for prod in PRODUCTS:
            p_id = prod["id"]
            est = demand_estimates.get((p_id, s_id), {"total_demand": 30.0, "daily_rate": 10.0, "demand_std": 2.5})
            daily_demand = est["daily_rate"]
            total_horizon_demand = est["total_demand"]
            demand_std = est["demand_std"]

            # Assume average lead time to this store is ~1 day
            ss_info = calculate_safety_stock(
                daily_demand=daily_demand,
                demand_std=demand_std,
                lead_time_days=1.0,
                service_level_pct=service_level_pct
            )

            current_stock = INITIAL_STORE_STOCK.get((p_id, s_id), int(daily_demand * 1.5))
            ss = ss_info["safety_stock"]
            rop = ss_info["reorder_point"]

            days_of_cover = round(current_stock / daily_demand, 1) if daily_demand > 0 else 99.0

            # Stockout Risk Status
            if current_stock <= (daily_demand * 0.75):
                risk_status = "Critical"
                risk_color = "#ff7777"
            elif current_stock < rop:
                risk_status = "Warning"
                risk_color = "#ffb36b"
            else:
                risk_status = "Healthy"
                risk_color = "#a3e635"

            # Net replenishment demand needed for planning horizon:
            # We want Store Stock + Inbound Shipments >= Horizon Demand + Safety Stock
            target_stock = total_horizon_demand + (ss * 0.5)  # Buffer half safety stock into shipment target
            net_needed = max(0.0, target_stock - current_stock)

            records.append({
                "store_id": s_id,
                "store_name": store["name"],
                "city": store["city"],
                "tier": store["tier"],
                "product_id": p_id,
                "product_name": prod["name"],
                "sku": prod["sku"],
                "category": prod["category"],
                "current_stock": current_stock,
                "daily_demand": daily_demand,
                "horizon_demand": total_horizon_demand,
                "safety_stock": ss,
                "reorder_point": rop,
                "days_of_cover": days_of_cover,
                "net_replenishment_needed": round(net_needed, 1),
                "risk_status": risk_status,
                "risk_color": risk_color,
            })

    return records


def analyze_warehouse_batches(batches: List[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Evaluates batches at warehouses:
      - Days to expiry
      - Expiry Status: 'Urgent' (<=3d), 'Expiring soon' (<=7d), 'Healthy' (>7d)
      - Network absorption velocity (will it spoil before we can sell it?)
    """
    if batches is None:
        batches = INITIAL_BATCHES

    records = []
    # Compute total network daily demand per product
    daily_rates = forecaster.get_network_demand_estimates(horizon_days=3)
    product_network_demand = {}
    for (p_id, _), info in daily_rates.items():
        product_network_demand[p_id] = product_network_demand.get(p_id, 0.0) + info["daily_rate"]

    for b in batches:
        p = next(x for x in PRODUCTS if x["id"] == b["product_id"])
        w = next(x for x in WAREHOUSES if x["id"] == b["warehouse_id"])
        expiry_days = b["expiry_days"]
        qty = b["quantity"]

        net_daily = product_network_demand.get(p["id"], 50.0)
        days_to_absorb = round(qty / net_daily, 1) if net_daily > 0 else 99.0

        # High spoilage risk if days to absorb exceeds expiry days!
        is_spoilage_risk = (days_to_absorb > expiry_days)

        if expiry_days <= 3:
            status = "Urgent"
        elif expiry_days <= 7:
            status = "Expiring soon"
        else:
            status = "Healthy"

        records.append({
            "batch_id": b["batch_id"],
            "product_id": p["id"],
            "product_name": p["name"],
            "sku": p["sku"],
            "category": p["category"],
            "storage": p["storage"],
            "warehouse_id": w["id"],
            "warehouse_name": w["name"],
            "city": w["city"],
            "quantity": qty,
            "expiry_days": expiry_days,
            "status": status,
            "days_to_absorb": days_to_absorb,
            "is_spoilage_risk": is_spoilage_risk,
            "unit_cost": p["unit_cost"],
            "inventory_value": round(qty * p["unit_cost"], 2),
        })

    return records


def get_store_stock(product_id: int, store_id: str) -> int:
    """Returns the current on-hand stock for a store SKU."""
    return INITIAL_STORE_STOCK.get((product_id, store_id), 0)


def credit_store_stock(store_id: str, product_id: int, quantity: int) -> int:
    """
    Credits replenished units to the specified retail store.
    Updates the active stock level and returns the new balance.
    """
    key = (product_id, store_id)
    current = INITIAL_STORE_STOCK.get(key, 0)
    new_level = current + int(quantity)
    INITIAL_STORE_STOCK[key] = new_level
    return new_level


def debit_store_stock(store_id: str, product_id: int, quantity: int) -> int:
    """Debits units from the retail store (e.g. customer fulfillment)."""
    key = (product_id, store_id)
    current = INITIAL_STORE_STOCK.get(key, 0)
    new_level = max(0, current - int(quantity))
    INITIAL_STORE_STOCK[key] = new_level
    return new_level

