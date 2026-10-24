"""
OptiStock AI - Inventory Transactions Module
Handles permanent recording of Stock In (procurement/supplier receipt)
and Stock Out (dispatch/replenishment fulfillment) with atomic validation,
inventory batch updates, and audit trail ledger persistence.
"""

from datetime import datetime, timezone
import logging
import sqlite3
from typing import Dict, List, Any, Optional

from engine.automation_db import get_db_connection
from engine.data_loader import (
    PRODUCTS,
    WAREHOUSES,
    get_warehouse_stock,
    debit_warehouse_batch,
    credit_warehouse_batch,
)

logger = logging.getLogger("optistock.inventory_transactions")


def generate_transaction_code(txn_type: str, db_path: Optional[str] = None) -> str:
    """
    Generates a unique, human-readable transaction identifier.
    Format: TXN-IN-YYYYMMDD-XXXX or TXN-OUT-YYYYMMDD-XXXX
    """
    prefix = "IN" if txn_type.upper() in ("STOCK_IN", "IN") else "OUT"
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")

    conn = get_db_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT COUNT(*) FROM inventory_transactions
            WHERE transaction_code LIKE ?
            """,
            (f"TXN-{prefix}-{today_str}-%",),
        )
        count = cur.fetchone()[0] + 1
        return f"TXN-{prefix}-{today_str}-{count:04d}"
    finally:
        conn.close()


def record_transaction(
    data: Dict[str, Any],
    user_name: str = "System User",
    user_role: str = "warehouse",
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Records an inventory movement transaction (STOCK_IN or STOCK_OUT).
    Validates all required fields, enforces stock availability, updates
    warehouse batches, and commits transaction record atomically.
    """
    # 1. Validate Transaction Type
    raw_type = str(data.get("transaction_type", "")).strip().upper()
    if raw_type in ("STOCK_IN", "IN", "RECEIVED"):
        txn_type = "STOCK_IN"
    elif raw_type in ("STOCK_OUT", "OUT", "DISPATCHED"):
        txn_type = "STOCK_OUT"
    else:
        raise ValueError("Invalid transaction type. Must be 'STOCK_IN' or 'STOCK_OUT'.")

    # 2. Validate Product
    try:
        product_id = int(data.get("product_id"))
    except (TypeError, ValueError):
        raise ValueError("Valid product ID is required.")

    product = next((p for p in PRODUCTS if p["id"] == product_id), None)
    if not product:
        raise ValueError(f"Product with ID {product_id} not found in catalog.")

    product_name = product["name"]
    sku = product["sku"]

    # 3. Validate Quantity
    try:
        quantity = int(data.get("quantity"))
        if quantity <= 0:
            raise ValueError()
    except (TypeError, ValueError):
        raise ValueError("Quantity must be a positive integer greater than zero.")

    # 4. Validate Warehouse
    warehouse_id = str(data.get("warehouse_id", "")).strip()
    warehouse = next((w for w in WAREHOUSES if w["id"] == warehouse_id), None)
    if not warehouse:
        raise ValueError(f"Warehouse ID '{warehouse_id}' is invalid or not registered.")
    warehouse_name = warehouse["name"]

    # 5. Validate Partner Name (Supplier for Stock In, Store/Customer for Stock Out)
    partner_name = str(data.get("partner_name", "")).strip()
    if not partner_name:
        partner_label = "Supplier name" if txn_type == "STOCK_IN" else "Destination store/customer"
        raise ValueError(f"{partner_label} is required.")

    # 6. Validate Date
    txn_date = str(data.get("transaction_date", "")).strip()
    if not txn_date:
        txn_date = datetime.now().strftime("%Y-%m-%d")
    else:
        try:
            # Validate format YYYY-MM-DD
            datetime.strptime(txn_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Transaction date must be in YYYY-MM-DD format.")

    notes = str(data.get("notes", "")).strip()
    txn_code = str(data.get("transaction_code", "")).strip()
    if not txn_code:
        txn_code = generate_transaction_code(txn_type, db_path=db_path)

    # 7. Check Available Inventory on Stock Out
    current_avail = get_warehouse_stock(warehouse_id, product_id)
    if txn_type == "STOCK_OUT" and quantity > current_avail:
        raise ValueError(
            f"Insufficient stock at {warehouse_name}. "
            f"Available on-hand: {current_avail} units, requested dispatch: {quantity} units."
        )

    # 8. Apply In-Memory Batch Adjustments with Rollback Capability
    batch_res = None
    if txn_type == "STOCK_IN":
        batch_res = credit_warehouse_batch(
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=quantity,
            expiry_days=data.get("expiry_days"),
        )
    else:
        batch_res = debit_warehouse_batch(
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=quantity,
        )

    # 9. Atomic DB Commit
    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO inventory_transactions (
                    transaction_code, transaction_type, product_id, product_name, sku,
                    quantity, warehouse_id, warehouse_name, partner_name,
                    transaction_date, notes, performed_by, performed_by_role, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    txn_code,
                    txn_type,
                    product_id,
                    product_name,
                    sku,
                    quantity,
                    warehouse_id,
                    warehouse_name,
                    partner_name,
                    txn_date,
                    notes,
                    user_name or "System User",
                    user_role or "warehouse",
                    now_iso,
                ),
            )
    except Exception as e:
        # Revert in-memory adjustment on DB failure to preserve consistency
        if txn_type == "STOCK_IN":
            debit_warehouse_batch(warehouse_id, product_id, quantity)
        else:
            credit_warehouse_batch(warehouse_id, product_id, quantity)
        logger.error("Failed to commit inventory transaction to database: %s", str(e))
        raise RuntimeError(f"Database error while saving transaction: {str(e)}")
    finally:
        conn.close()

    updated_stock = get_warehouse_stock(warehouse_id, product_id)
    logger.info(
        "Recorded %s: %s | %d units of %s at %s. Updated Stock: %d",
        txn_type,
        txn_code,
        quantity,
        product_name,
        warehouse_name,
        updated_stock,
    )

    return {
        "success": True,
        "transaction_code": txn_code,
        "transaction_type": txn_type,
        "product_id": product_id,
        "product_name": product_name,
        "sku": sku,
        "quantity": quantity,
        "warehouse_id": warehouse_id,
        "warehouse_name": warehouse_name,
        "partner_name": partner_name,
        "transaction_date": txn_date,
        "notes": notes,
        "performed_by": user_name or "System User",
        "performed_by_role": user_role or "warehouse",
        "updated_warehouse_stock": updated_stock,
        "batch_details": batch_res,
        "created_at": now_iso,
    }


def get_transactions(
    filters: Optional[Dict[str, Any]] = None,
    limit: int = 100,
    offset: int = 0,
    db_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Retrieves filtered and paginated inventory transactions from SQLite.
    """
    filters = filters or {}
    conn = get_db_connection(db_path)
    try:
        where_clauses = []
        params = []

        # Filter by transaction type
        txn_type = filters.get("type", "").strip().upper()
        if txn_type and txn_type != "ALL":
            where_clauses.append("transaction_type = ?")
            params.append(txn_type)

        # Filter by warehouse
        warehouse_id = filters.get("warehouse_id", "").strip()
        if warehouse_id and warehouse_id != "ALL":
            where_clauses.append("warehouse_id = ?")
            params.append(warehouse_id)

        # Filter by date range
        start_date = filters.get("start_date", "").strip()
        if start_date:
            where_clauses.append("transaction_date >= ?")
            params.append(start_date)

        end_date = filters.get("end_date", "").strip()
        if end_date:
            where_clauses.append("transaction_date <= ?")
            params.append(end_date)

        # Search query matching code, product, partner, notes, user
        search_query = filters.get("search", "").strip()
        if search_query:
            term = f"%{search_query}%"
            where_clauses.append(
                """
                (transaction_code LIKE ? OR
                 product_name LIKE ? OR
                 sku LIKE ? OR
                 warehouse_name LIKE ? OR
                 partner_name LIKE ? OR
                 performed_by LIKE ? OR
                 notes LIKE ?)
                """
            )
            params.extend([term] * 7)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        # Total count query
        count_sql = f"SELECT COUNT(*) as total FROM inventory_transactions {where_sql}"
        total_count = conn.execute(count_sql, params).fetchone()["total"]

        # Fetch records
        query_sql = f"""
            SELECT * FROM inventory_transactions
            {where_sql}
            ORDER BY transaction_date DESC, id DESC
            LIMIT ? OFFSET ?
        """
        rows = conn.execute(query_sql, params + [limit, offset]).fetchall()

        transactions = [dict(row) for row in rows]
        return {
            "transactions": transactions,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }
    finally:
        conn.close()


def get_transaction_summary(db_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Computes key transaction metrics and recent movements for dashboard KPI cards.
    """
    conn = get_db_connection(db_path)
    try:
        # Totals and counts by type
        stats_sql = """
            SELECT 
                COUNT(*) as total_count,
                COALESCE(SUM(CASE WHEN transaction_type = 'STOCK_IN' THEN quantity ELSE 0 END), 0) as total_stock_in,
                COALESCE(SUM(CASE WHEN transaction_type = 'STOCK_OUT' THEN quantity ELSE 0 END), 0) as total_stock_out,
                COALESCE(SUM(CASE WHEN transaction_type = 'STOCK_IN' THEN 1 ELSE 0 END), 0) as count_stock_in,
                COALESCE(SUM(CASE WHEN transaction_type = 'STOCK_OUT' THEN 1 ELSE 0 END), 0) as count_stock_out
            FROM inventory_transactions
        """
        stat_row = conn.execute(stats_sql).fetchone()
        total_count = stat_row["total_count"]
        total_stock_in = stat_row["total_stock_in"]
        total_stock_out = stat_row["total_stock_out"]
        count_stock_in = stat_row["count_stock_in"]
        count_stock_out = stat_row["count_stock_out"]

        # Recent 5 transactions
        recent_sql = """
            SELECT * FROM inventory_transactions
            ORDER BY transaction_date DESC, id DESC
            LIMIT 5
        """
        recent_rows = conn.execute(recent_sql).fetchall()
        recent_transactions = [dict(row) for row in recent_rows]

        return {
            "total_transactions": total_count,
            "stock_received": int(total_stock_in),
            "stock_dispatched": int(total_stock_out),
            "net_movement": int(total_stock_in - total_stock_out),
            "count_stock_in": count_stock_in,
            "count_stock_out": count_stock_out,
            "recent_transactions": recent_transactions,
        }
    finally:
        conn.close()
