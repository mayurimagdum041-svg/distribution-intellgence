"""
OptiStock AI - Automation Workflows Engine
Implements:
1. Auto-Replenishment (Safety stock, ROP, suggested order, duplicate prevention, manager approval)
2. Expiry Rescue (FEFO shelf-life scan, store absorption capacity, transit check, safe transfers)
3. Distribution Optimization (Multi-warehouse comparison, ranked alternatives, sample data classification)
4. Delivery Monitoring (Deadline verification, delayed-shipment alerts, checkpoint tracking)
5. Automated Alert Center (Deduplication, severity tiers, resolution workflows)
All workflows support dry_run mode, transaction safety, and comprehensive logging.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Tuple

from engine.automation_db import get_db_connection
from engine.data_loader import (
    PRODUCTS,
    WAREHOUSES,
    STORES,
    INITIAL_BATCHES,
    DISTANCE_KM,
    calculate_transport_cost_per_unit,
    get_transit_time_days,
)
from engine.inventory_optimizer import (
    analyze_store_inventory_health,
    analyze_warehouse_batches,
)

logger = logging.getLogger("optistock.automation.engine")


# ---------------------------------------------------------------------------
# Helper: Idempotency hashing for alerts and recommendations
# ---------------------------------------------------------------------------
def generate_idempotency_hash(*args) -> str:
    """Generates a reproducible SHA256 hex digest from variable string components."""
    content = "|".join(str(a) for a in args)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:32]


# ---------------------------------------------------------------------------
# Alert Helper: Create or retrieve existing active alert (prevents duplicate spam)
# ---------------------------------------------------------------------------
def create_alert(
    conn,
    alert_type: str,
    severity: str,
    entity_type: str,
    entity_id: str,
    title: str,
    message: str,
    recommended_action: str,
    dry_run: bool = False
) -> Optional[int]:
    """
    Creates an alert in the database if an open/acknowledged alert with the same
    idempotency hash does not already exist.
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    alert_hash = generate_idempotency_hash(alert_type, entity_type, entity_id)

    # Check for existing non-resolved alert
    existing = conn.execute("""
    SELECT id, status FROM alerts 
    WHERE idempotency_hash = ? AND status IN ('OPEN', 'ACKNOWLEDGED');
    """, (alert_hash,)).fetchone()

    if existing:
        logger.debug("Duplicate active alert skipped for hash %s (ID %s)", alert_hash, existing["id"])
        return None

    if dry_run:
        logger.info("[DRY-RUN] Would create alert: %s (%s) - %s", title, severity, message)
        return -1

    cursor = conn.execute("""
    INSERT INTO alerts (
        alert_type, severity, entity_type, entity_id, title, message,
        recommended_action, status, idempotency_hash, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?, ?);
    """, (
        alert_type, severity, entity_type, entity_id, title, message,
        recommended_action, alert_hash, now_iso, now_iso
    ))
    return cursor.lastrowid


# ---------------------------------------------------------------------------
# WORKFLOW 1: AUTO-REPLENISHMENT
# ---------------------------------------------------------------------------
def run_auto_replenishment(dry_run: bool = False, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    1. Evaluates all store-SKU inventory health against dynamic ROP & Safety Stock.
    2. Identifies stockout risks (Critical / Warning).
    3. Calculates suggested order quantity taking into account daily demand, lead time,
       safety stock, and minimum batch constraints.
    4. Creates PENDING_APPROVAL replenishment recommendations (skips duplicates).
    5. Never automatically places purchase orders or dispatches stock.
    """
    conn = get_db_connection(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    actions_generated = 0
    items_created = []

    try:
        store_health = analyze_store_inventory_health(horizon_days=3, service_level_pct=95.0)

        with conn:
            for rec in store_health:
                store_id = rec["store_id"]
                product_id = rec["product_id"]
                current_stock = rec["current_stock"]
                rop = rec["reorder_point"]
                risk_status = rec["risk_status"]

                # Only trigger for stores below ROP or in Critical/Warning status
                if risk_status not in ("Critical", "Warning") and current_stock >= rop:
                    continue

                # Idempotency key for pending recommendation
                rec_key = generate_idempotency_hash("REPLENISH", store_id, product_id)

                # Check if a pending recommendation already exists
                existing = conn.execute("""
                SELECT id, suggested_quantity, status FROM replenishment_requests
                WHERE idempotency_key = ? AND status = 'PENDING_APPROVAL';
                """, (rec_key,)).fetchone()

                if existing:
                    logger.debug("Pending replenishment request already active for %s - Product %s (ID %s)",
                                 store_id, product_id, existing["id"])
                    continue

                # Calculate suggested order quantity
                # Suggested = (Reorder Point - Current Stock) + (Lead Time Demand * 1.5)
                product_info = next((p for p in PRODUCTS if p["id"] == product_id), None)
                min_batch = product_info["min_batch_size"] if product_info else 10

                deficit = max(0.0, rop - current_stock)
                lead_time_buffer = rec["daily_demand"] * rec.get("lead_time_days", 1.0) * 1.5
                raw_suggested = deficit + lead_time_buffer
                # Round to nearest batch constraint
                suggested_quantity = max(min_batch, int(round(raw_suggested / 5.0) * 5))

                if dry_run:
                    actions_generated += 1
                    items_created.append({
                        "store_id": store_id,
                        "product_name": rec["product_name"],
                        "current_stock": current_stock,
                        "suggested_quantity": suggested_quantity,
                        "mode": "DRY_RUN"
                    })
                    continue

                # Insert recommendation requiring manager approval
                conn.execute("""
                INSERT INTO replenishment_requests (
                    store_id, store_name, product_id, product_name, category,
                    current_stock, daily_demand, safety_stock, reorder_point,
                    lead_time_days, suggested_quantity, risk_status, status,
                    idempotency_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_APPROVAL', ?, ?, ?);
                """, (
                    store_id, rec["store_name"], product_id, rec["product_name"],
                    rec["category"], current_stock, rec["daily_demand"],
                    rec["safety_stock"], rop, 1.0, suggested_quantity,
                    risk_status, rec_key, now_iso, now_iso
                ))

                # Create corresponding alert
                severity = "CRITICAL" if risk_status == "Critical" else "WARNING"
                create_alert(
                    conn=conn,
                    alert_type="LOW_STOCK" if risk_status == "Critical" else "URGENT_REPLENISHMENT",
                    severity=severity,
                    entity_type="STORE",
                    entity_id=f"{store_id}-{product_id}",
                    title=f"Low Stock Alert: {rec['product_name']} at {rec['store_name']}",
                    message=f"Current stock {current_stock} is below ROP ({rop}). Days of cover: {rec['days_of_cover']}d.",
                    recommended_action=f"Review and approve replenishment request of {suggested_quantity} units.",
                    dry_run=dry_run
                )

                actions_generated += 1
                items_created.append({
                    "store_id": store_id,
                    "store_name": rec["store_name"],
                    "product_name": rec["product_name"],
                    "current_stock": current_stock,
                    "reorder_point": rop,
                    "suggested_quantity": suggested_quantity,
                    "risk_status": risk_status,
                })

        return {
            "workflow": "auto_replenishment",
            "status": "SUCCESS" if not dry_run else "DRY_RUN",
            "actions_generated": actions_generated,
            "items": items_created,
            "dry_run": dry_run
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# WORKFLOW 2: EXPIRY RESCUE
# ---------------------------------------------------------------------------
def run_expiry_rescue(dry_run: bool = False, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    1. Scans warehouse batches nearing expiration (shelf life <= 7 days, priority <= 4 days).
    2. Identifies high-velocity destination stores within feasible road transit distance.
    3. Guarantees batch_expiry_days > transit_days + 1.0 so stock arrives fresh.
    4. Limits transfer quantity to store absorption capacity (daily_demand * remaining_life).
    5. Never transfers more than available batch stock.
    6. Stages transfer as PENDING_APPROVAL.
    """
    conn = get_db_connection(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    actions_generated = 0
    items_created = []

    try:
        warehouse_batches = analyze_warehouse_batches()
        store_health = analyze_store_inventory_health(horizon_days=3)

        # Map store daily demand by (product_id, store_id)
        store_demand_map = {
            (s["product_id"], s["store_id"]): s for s in store_health
        }

        with conn:
            for batch in warehouse_batches:
                expiry_days = batch["expiry_days"]
                available_qty = batch["quantity"]
                batch_id = batch["batch_id"]
                p_id = batch["product_id"]
                w_id = batch["warehouse_id"]

                # Scan batches approaching expiry (<= 7 days)
                if expiry_days > 7 or available_qty <= 0:
                    continue

                # Find eligible destination stores
                eligible_candidates = []
                for store in STORES:
                    s_id = store["id"]
                    transit_days = get_transit_time_days(w_id, s_id)

                    # Expiry constraint: Must arrive with usable shelf life
                    remaining_after_transit = expiry_days - transit_days
                    if remaining_after_transit <= 1.0:
                        continue  # Infeasible: will spoil in transit or on arrival

                    store_info = store_demand_map.get((p_id, s_id))
                    if not store_info or store_info["daily_demand"] <= 0:
                        continue

                    daily_demand = store_info["daily_demand"]
                    # Absorption capacity during remaining shelf life
                    absorption_cap = daily_demand * max(1.0, remaining_after_transit - 0.5)

                    eligible_candidates.append({
                        "store": store,
                        "transit_days": transit_days,
                        "remaining_after_transit": remaining_after_transit,
                        "daily_demand": daily_demand,
                        "absorption_capacity": absorption_cap,
                        "current_stock": store_info["current_stock"],
                    })

                if not eligible_candidates:
                    logger.debug("No viable stores found to absorb expiring batch %s (%sd remaining)", batch_id, expiry_days)
                    continue

                # Rank candidates by absorption capacity and shortest transit time
                eligible_candidates.sort(
                    key=lambda c: (-c["absorption_capacity"], c["transit_days"])
                )
                best_store = eligible_candidates[0]
                dest_store = best_store["store"]
                dest_id = dest_store["id"]

                # Safe transfer quantity calculation
                transfer_qty = min(
                    available_qty,
                    max(10.0, round(best_store["absorption_capacity"]))
                )
                transfer_qty = min(transfer_qty, available_qty)  # Strictly never exceed available stock!

                rescue_key = generate_idempotency_hash("RESCUE", batch_id, dest_id)

                # Check for existing pending rescue transfer
                existing = conn.execute("""
                SELECT id FROM expiry_rescue_transfers
                WHERE idempotency_key = ? AND status = 'PENDING_APPROVAL';
                """, (rescue_key,)).fetchone()

                if existing:
                    continue

                reason = (
                    f"Batch {batch_id} expires in {expiry_days}d at {batch['warehouse_name']}. "
                    f"Rerouting {transfer_qty} units to {dest_store['name']} (transit {best_store['transit_days']}d, "
                    f"store demand {best_store['daily_demand']} units/d can liquidate stock before expiry)."
                )

                if dry_run:
                    actions_generated += 1
                    items_created.append({
                        "batch_id": batch_id,
                        "destination_store": dest_store["name"],
                        "transfer_quantity": transfer_qty,
                        "expiry_days": expiry_days,
                        "mode": "DRY_RUN"
                    })
                    continue

                conn.execute("""
                INSERT INTO expiry_rescue_transfers (
                    batch_id, product_id, product_name, category,
                    source_warehouse_id, source_warehouse_name,
                    destination_store_id, destination_store_name,
                    available_batch_quantity, transfer_quantity,
                    batch_expiry_days, transit_time_days,
                    remaining_shelf_life_days, store_daily_demand,
                    reason, status, idempotency_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_APPROVAL', ?, ?, ?);
                """, (
                    batch_id, p_id, batch["product_name"], batch["category"],
                    w_id, batch["warehouse_name"],
                    dest_id, dest_store["name"],
                    available_qty, transfer_qty,
                    expiry_days, best_store["transit_days"],
                    round(best_store["remaining_after_transit"], 1),
                    best_store["daily_demand"],
                    reason, rescue_key, now_iso, now_iso
                ))

                # Create Alert
                severity = "CRITICAL" if expiry_days <= 3 else "WARNING"
                create_alert(
                    conn=conn,
                    alert_type="EXPIRY_RISK",
                    severity=severity,
                    entity_type="WAREHOUSE_BATCH",
                    entity_id=batch_id,
                    title=f"Expiring Lot Alert: {batch['product_name']} ({batch_id})",
                    message=f"{available_qty} units expire in {expiry_days} days at {batch['warehouse_name']}.",
                    recommended_action=f"Approve urgent FEFO rescue transfer of {transfer_qty} units to {dest_store['name']}.",
                    dry_run=dry_run
                )

                actions_generated += 1
                items_created.append({
                    "batch_id": batch_id,
                    "product_name": batch["product_name"],
                    "source_warehouse": batch["warehouse_name"],
                    "destination_store": dest_store["name"],
                    "transfer_quantity": transfer_qty,
                    "expiry_days": expiry_days,
                    "reason": reason
                })

        return {
            "workflow": "expiry_rescue",
            "status": "SUCCESS" if not dry_run else "DRY_RUN",
            "actions_generated": actions_generated,
            "items": items_created,
            "dry_run": dry_run
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# WORKFLOW 3: DISTRIBUTION OPTIMIZATION
# ---------------------------------------------------------------------------
def run_distribution_optimization(dry_run: bool = False, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    1. Scans stores needing replenishment.
    2. Compares all eligible supply warehouses based on available stock, road distance,
       transit duration, estimated freight cost per unit, and store demand urgency.
    3. Generates ranked recommendations (Rank 1, Rank 2, Rank 3) with decision rationales.
    4. Clearly tags generated data as 'SIMULATED_SAMPLE' to distinguish from real GPS/WMS.
    """
    conn = get_db_connection(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    actions_generated = 0
    items_created = []

    try:
        store_health = analyze_store_inventory_health(horizon_days=3)
        batches = analyze_warehouse_batches()

        # Compute stock by (product_id, warehouse_id)
        wh_stock_map = {}
        for b in batches:
            key = (b["product_id"], b["warehouse_id"])
            wh_stock_map[key] = wh_stock_map.get(key, 0.0) + b["quantity"]

        with conn:
            # Mark previous active recommendations as superseded if not dry run
            if not dry_run:
                conn.execute("UPDATE distribution_recommendations SET status = 'SUPERSEDED' WHERE status = 'ACTIVE';")

            for rec in store_health:
                if rec["risk_status"] not in ("Critical", "Warning"):
                    continue

                store_id = rec["store_id"]
                product_id = rec["product_id"]
                deficit = rec["net_replenishment_needed"]
                if deficit <= 0:
                    continue

                candidate_warehouses = []
                for wh in WAREHOUSES:
                    w_id = wh["id"]
                    stock_avail = wh_stock_map.get((product_id, w_id), 0.0)
                    if stock_avail <= 0:
                        continue

                    dist_km = DISTANCE_KM.get((w_id, store_id), 250.0)
                    transit_days = get_transit_time_days(w_id, store_id)
                    unit_cost = calculate_transport_cost_per_unit(w_id, store_id, product_id)
                    total_est_freight = round(unit_cost * min(deficit, stock_avail), 2)

                    # Scoring formula: Lower cost & distance is better, higher available stock is better
                    score = (dist_km * 0.4) + (unit_cost * 15.0) - (min(stock_avail, deficit) * 0.2)

                    candidate_warehouses.append({
                        "warehouse": wh,
                        "stock_available": stock_avail,
                        "distance_km": dist_km,
                        "transit_days": transit_days,
                        "unit_cost": unit_cost,
                        "total_freight_est": total_est_freight,
                        "score": score
                    })

                if not candidate_warehouses:
                    continue

                # Sort candidates by score (lowest score = highest rank)
                candidate_warehouses.sort(key=lambda x: x["score"])

                for rank, cand in enumerate(candidate_warehouses[:3], start=1):
                    wh = cand["warehouse"]
                    rationale = (
                        f"Rank {rank}: {wh['name']} has {cand['stock_available']} units available. "
                        f"Route distance is {cand['distance_km']} km (transit {cand['transit_days']}d) "
                        f"at estimated freight Rs {cand['unit_cost']}/unit (Total Est: Rs {cand['total_freight_est']})."
                    )

                    if dry_run:
                        actions_generated += 1
                        items_created.append({
                            "store": rec["store_name"],
                            "product": rec["product_name"],
                            "warehouse": wh["name"],
                            "rank": rank,
                            "mode": "DRY_RUN"
                        })
                        continue

                    conn.execute("""
                    INSERT INTO distribution_recommendations (
                        store_id, store_name, product_id, product_name,
                        recommended_warehouse_id, recommended_warehouse_name,
                        warehouse_rank, stock_available, distance_km,
                        transit_days, unit_transport_cost, total_freight_est,
                        urgency_score, data_classification, rationale, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SIMULATED_SAMPLE', ?, 'ACTIVE', ?);
                    """, (
                        store_id, rec["store_name"], product_id, rec["product_name"],
                        wh["id"], wh["name"], rank, cand["stock_available"],
                        cand["distance_km"], cand["transit_days"], cand["unit_cost"],
                        cand["total_freight_est"], rec["risk_status"], rationale, now_iso
                    ))

                    actions_generated += 1
                    items_created.append({
                        "store_name": rec["store_name"],
                        "product_name": rec["product_name"],
                        "warehouse_name": wh["name"],
                        "rank": rank,
                        "rationale": rationale
                    })

        return {
            "workflow": "distribution_optimization",
            "status": "SUCCESS" if not dry_run else "DRY_RUN",
            "actions_generated": actions_generated,
            "items": items_created,
            "data_classification": "SIMULATED_SAMPLE",
            "dry_run": dry_run
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# WORKFLOW 4: DELIVERY MONITORING
# ---------------------------------------------------------------------------
def run_delivery_monitoring(dry_run: bool = False, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    1. Checks all active dispatches against scheduled delivery deadlines.
    2. Calculates delays in minutes when expected delivery window has passed.
    3. Generates delayed-shipment alerts with severity proportional to delay duration.
    4. Explicitly tags tracking source as ROAD_MANIFEST_CHECKPOINT (no live GPS claimed).
    """
    conn = get_db_connection(db_path)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    actions_generated = 0
    items_created = []

    try:
        with conn:
            shipments = conn.execute("""
            SELECT * FROM delivery_shipments 
            WHERE status IN ('IN_TRANSIT', 'DISPATCHED', 'DELAYED');
            """).fetchall()

            for s in shipments:
                shipment_code = s["shipment_code"]
                try:
                    exp_time = datetime.fromisoformat(s["expected_delivery_at"].replace("Z", "+00:00"))
                except Exception:
                    continue

                # Check if deadline is passed
                if now > exp_time:
                    delay_minutes = int((now - exp_time).total_seconds() / 60)
                    delay_reason = s["delay_reason"] or "Highway transit delay past scheduled delivery window"

                    if dry_run:
                        actions_generated += 1
                        items_created.append({
                            "shipment_code": shipment_code,
                            "delay_minutes": delay_minutes,
                            "mode": "DRY_RUN"
                        })
                        continue

                    # Update status in delivery_shipments table
                    conn.execute("""
                    UPDATE delivery_shipments 
                    SET status = 'DELAYED', delay_minutes = ?, delay_reason = ?, updated_at = ?
                    WHERE shipment_code = ?;
                    """, (delay_minutes, delay_reason, now_iso, shipment_code))

                    # Create delayed shipment alert
                    severity = "CRITICAL" if delay_minutes >= 120 else "WARNING"
                    create_alert(
                        conn=conn,
                        alert_type="DELAYED_SHIPMENT",
                        severity=severity,
                        entity_type="SHIPMENT",
                        entity_id=shipment_code,
                        title=f"Delivery Delayed: {shipment_code} to {s['destination_city']}",
                        message=(
                            f"Shipment {shipment_code} carrying {s['quantity']} units of {s['product_name']} "
                            f"is delayed by {delay_minutes} mins (Driver: {s['assigned_driver']}, Vehicle: {s['vehicle_no']}). "
                            f"Tracking source: Checkpoint update."
                        ),
                        recommended_action=f"Contact driver {s['assigned_driver']} or notify store manager at {s['destination_city']}.",
                        dry_run=dry_run
                    )

                    actions_generated += 1
                    items_created.append({
                        "shipment_code": shipment_code,
                        "destination_city": s["destination_city"],
                        "driver": s["assigned_driver"],
                        "vehicle_no": s["vehicle_no"],
                        "delay_minutes": delay_minutes,
                        "severity": severity
                    })

        return {
            "workflow": "delivery_monitoring",
            "status": "SUCCESS" if not dry_run else "DRY_RUN",
            "actions_generated": actions_generated,
            "items": items_created,
            "dry_run": dry_run
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# WORKFLOW EXECUTION RUNNER & LOGGER
# ---------------------------------------------------------------------------
WORKFLOW_RUNNERS = {
    "auto_replenishment": run_auto_replenishment,
    "expiry_rescue": run_expiry_rescue,
    "distribution_optimization": run_distribution_optimization,
    "delivery_monitoring": run_delivery_monitoring,
}


def execute_workflow(workflow_id: str, dry_run: bool = False, db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Executes a single workflow with performance timing, error handling,
    execution logging, and database state updates.
    """
    if workflow_id not in WORKFLOW_RUNNERS:
        return {"error": f"Unknown workflow id: {workflow_id}"}

    conn = get_db_connection(db_path)
    started_at = datetime.now(timezone.utc)
    started_iso = started_at.isoformat()

    cfg = conn.execute("SELECT * FROM automation_configs WHERE id = ?;", (workflow_id,)).fetchone()
    wf_name = cfg["name"] if cfg else workflow_id
    runner = WORKFLOW_RUNNERS[workflow_id]

    status = "SUCCESS"
    error_msg = None
    actions_count = 0
    result_data = {}

    try:
        result_data = runner(dry_run=dry_run, db_path=db_path)
        actions_count = result_data.get("actions_generated", 0)
        status = "DRY_RUN" if dry_run else "SUCCESS"
    except Exception as exc:
        logger.exception("Workflow %s failed with exception: %s", workflow_id, exc)
        status = "ERROR"
        error_msg = str(exc)
        result_data = {"error": str(exc)}
    finally:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)

        with conn:
            # Log execution history
            conn.execute("""
            INSERT INTO automation_execution_logs (
                workflow_id, workflow_name, started_at, finished_at,
                duration_ms, status, actions_generated, error_message, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                workflow_id, wf_name, started_iso, finished_at.isoformat(),
                duration_ms, status, actions_count, error_msg,
                json.dumps(result_data.get("items", []))[:2000]
            ))

            if not dry_run:
                # Update next run calculation
                interval = cfg["interval_seconds"] if cfg else 300
                next_run = (finished_at + timedelta(seconds=interval)).isoformat()

                conn.execute("""
                UPDATE automation_configs 
                SET last_run_at = ?, next_run_at = ?, last_status = ?, last_error = ?,
                    actions_count = actions_count + ?, updated_at = ?
                WHERE id = ?;
                """, (
                    finished_at.isoformat(), next_run, status, error_msg,
                    actions_count, finished_at.isoformat(), workflow_id
                ))

        conn.close()

    result_data["workflow_id"] = workflow_id
    result_data["workflow_name"] = wf_name
    result_data["duration_ms"] = duration_ms
    result_data["status"] = status
    if error_msg:
        result_data["error"] = error_msg
    return result_data


# ---------------------------------------------------------------------------
# MANAGER APPROVAL ACTIONS
# ---------------------------------------------------------------------------
def approve_replenishment(request_id: int, manager_name: str, notes: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Approves a replenishment recommendation. Required before purchasing/dispatch."""
    conn = get_db_connection(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            row = conn.execute("SELECT * FROM replenishment_requests WHERE id = ?;", (request_id,)).fetchone()
            if not row:
                return {"error": "Replenishment request not found", "success": False}
            if row["status"] != "PENDING_APPROVAL":
                return {"error": f"Request is already {row['status']}", "success": False}

            conn.execute("""
            UPDATE replenishment_requests 
            SET status = 'APPROVED', approved_by = ?, approved_at = ?, manager_notes = ?, updated_at = ?
            WHERE id = ?;
            """, (manager_name, now_iso, notes or "Approved by Manager", now_iso, request_id))

            # Mark associated alert as RESOLVED
            conn.execute("""
            UPDATE alerts 
            SET status = 'RESOLVED', resolved_by = ?, resolved_at = ?, updated_at = ?
            WHERE entity_id = ? AND alert_type IN ('LOW_STOCK', 'URGENT_REPLENISHMENT');
            """, (manager_name, now_iso, now_iso, f"{row['store_id']}-{row['product_id']}"))

        return {"success": True, "message": f"Replenishment request #{request_id} approved by {manager_name}."}
    finally:
        conn.close()


def reject_replenishment(request_id: int, manager_name: str, reason: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Rejects a replenishment recommendation."""
    conn = get_db_connection(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            row = conn.execute("SELECT * FROM replenishment_requests WHERE id = ?;", (request_id,)).fetchone()
            if not row:
                return {"error": "Replenishment request not found", "success": False}

            conn.execute("""
            UPDATE replenishment_requests 
            SET status = 'REJECTED', approved_by = ?, approved_at = ?, manager_notes = ?, updated_at = ?
            WHERE id = ?;
            """, (manager_name, now_iso, reason or "Rejected by Manager", now_iso, request_id))
        return {"success": True, "message": f"Replenishment request #{request_id} rejected."}
    finally:
        conn.close()


def approve_expiry_rescue(transfer_id: int, manager_name: str, notes: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Approves an expiry rescue transfer recommendation."""
    conn = get_db_connection(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            row = conn.execute("SELECT * FROM expiry_rescue_transfers WHERE id = ?;", (transfer_id,)).fetchone()
            if not row:
                return {"error": "Transfer request not found", "success": False}
            if row["status"] != "PENDING_APPROVAL":
                return {"error": f"Transfer is already {row['status']}", "success": False}

            conn.execute("""
            UPDATE expiry_rescue_transfers 
            SET status = 'APPROVED', approved_by = ?, approved_at = ?, manager_notes = ?, updated_at = ?
            WHERE id = ?;
            """, (manager_name, now_iso, notes or "Transfer Approved", now_iso, transfer_id))

            # Mark associated alert as RESOLVED
            conn.execute("""
            UPDATE alerts 
            SET status = 'RESOLVED', resolved_by = ?, resolved_at = ?, updated_at = ?
            WHERE entity_id = ? AND alert_type = 'EXPIRY_RISK';
            """, (manager_name, now_iso, now_iso, row["batch_id"]))

        return {"success": True, "message": f"Expiry rescue transfer #{transfer_id} approved by {manager_name}."}
    finally:
        conn.close()


def reject_expiry_rescue(transfer_id: int, manager_name: str, reason: Optional[str] = None, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Rejects an expiry rescue transfer."""
    conn = get_db_connection(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            row = conn.execute("SELECT * FROM expiry_rescue_transfers WHERE id = ?;", (transfer_id,)).fetchone()
            if not row:
                return {"error": "Transfer request not found", "success": False}

            conn.execute("""
            UPDATE expiry_rescue_transfers 
            SET status = 'REJECTED', approved_by = ?, approved_at = ?, manager_notes = ?, updated_at = ?
            WHERE id = ?;
            """, (manager_name, now_iso, reason or "Transfer Rejected", now_iso, transfer_id))
        return {"success": True, "message": f"Expiry rescue transfer #{transfer_id} rejected."}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# ALERT CENTER ACTIONS
# ---------------------------------------------------------------------------
def resolve_alert(alert_id: int, user_name: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Marks an alert as RESOLVED."""
    conn = get_db_connection(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            conn.execute("""
            UPDATE alerts 
            SET status = 'RESOLVED', resolved_by = ?, resolved_at = ?, updated_at = ?
            WHERE id = ?;
            """, (user_name, now_iso, now_iso, alert_id))
        return {"success": True, "message": f"Alert #{alert_id} resolved by {user_name}."}
    finally:
        conn.close()


def acknowledge_alert(alert_id: int, user_name: str, db_path: Optional[str] = None) -> Dict[str, Any]:
    """Marks an alert as ACKNOWLEDGED."""
    conn = get_db_connection(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        with conn:
            conn.execute("""
            UPDATE alerts 
            SET status = 'ACKNOWLEDGED', acknowledged_by = ?, acknowledged_at = ?, updated_at = ?
            WHERE id = ?;
            """, (user_name, now_iso, now_iso, alert_id))
        return {"success": True, "message": f"Alert #{alert_id} acknowledged by {user_name}."}
    finally:
        conn.close()
