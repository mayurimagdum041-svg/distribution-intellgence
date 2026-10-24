"""
OptiStock AI - Automation Database Layer
Provides transactional SQLite schema, migrations, connection management,
mutex locking for multi-worker safety, and repository helpers.
Compatible with local environments and persistent disk storage on Render.
"""

import os
import sqlite3
import json
import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

logger = logging.getLogger("optistock.automation.db")

# Default database path (can be overridden via environment variable)
DEFAULT_DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "optistock_automation.db"
)
DB_PATH = os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Returns a configured SQLite connection with foreign keys and Row factory enabled.
    Sets timeout to 30s to gracefully handle concurrent SQLite access.
    """
    path = db_path or DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")  # Write-Ahead Logging for high concurrency
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def init_db(db_path: Optional[str] = None):
    """
    Initializes all database tables, indexes, and default workflow configurations.
    Safe to call multiple times (idempotent).
    """
    target_path = db_path or DB_PATH
    conn = get_db_connection(target_path)
    try:
        with conn:
            # 1. Distributed Process Lock Table (ensures only 1 worker runs scheduler jobs)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_locks (
                lock_name TEXT PRIMARY KEY,
                locked_by TEXT NOT NULL,
                locked_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            );
            """)

            # 2. Automation Workflow Configurations
            conn.execute("""
            CREATE TABLE IF NOT EXISTS automation_configs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                enabled INTEGER NOT NULL DEFAULT 1,
                interval_seconds INTEGER NOT NULL DEFAULT 300,
                last_run_at TEXT,
                next_run_at TEXT,
                last_status TEXT DEFAULT 'IDLE',
                last_error TEXT,
                actions_count INTEGER DEFAULT 0,
                config_json TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 3. Execution History Logs
            conn.execute("""
            CREATE TABLE IF NOT EXISTS automation_execution_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                workflow_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_ms INTEGER,
                status TEXT NOT NULL,  -- 'SUCCESS', 'ERROR', 'DRY_RUN'
                actions_generated INTEGER DEFAULT 0,
                error_message TEXT,
                details_json TEXT DEFAULT '{}',
                FOREIGN KEY (workflow_id) REFERENCES automation_configs(id) ON DELETE CASCADE
            );
            """)

            # 4. Auto-Replenishment Recommendations (with Manager Approval requirement)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS replenishment_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id TEXT NOT NULL,
                store_name TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                category TEXT,
                current_stock REAL NOT NULL,
                daily_demand REAL NOT NULL,
                safety_stock REAL NOT NULL,
                reorder_point REAL NOT NULL,
                lead_time_days REAL NOT NULL DEFAULT 1.0,
                suggested_quantity REAL NOT NULL,
                risk_status TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',  -- 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'DISPATCHED'
                manager_notes TEXT,
                approved_by TEXT,
                approved_at TEXT,
                idempotency_key TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 5. Expiry Rescue Transfer Recommendations
            conn.execute("""
            CREATE TABLE IF NOT EXISTS expiry_rescue_transfers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                batch_id TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                category TEXT,
                source_warehouse_id TEXT NOT NULL,
                source_warehouse_name TEXT NOT NULL,
                destination_store_id TEXT NOT NULL,
                destination_store_name TEXT NOT NULL,
                available_batch_quantity REAL NOT NULL,
                transfer_quantity REAL NOT NULL,
                batch_expiry_days REAL NOT NULL,
                transit_time_days REAL NOT NULL,
                remaining_shelf_life_days REAL NOT NULL,
                store_daily_demand REAL NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',  -- 'PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'EXECUTED'
                manager_notes TEXT,
                approved_by TEXT,
                approved_at TEXT,
                idempotency_key TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 6. Distribution Warehouse Rankings & Recommendations
            conn.execute("""
            CREATE TABLE IF NOT EXISTS distribution_recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id TEXT NOT NULL,
                store_name TEXT NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                recommended_warehouse_id TEXT NOT NULL,
                recommended_warehouse_name TEXT NOT NULL,
                warehouse_rank INTEGER NOT NULL,
                stock_available REAL NOT NULL,
                distance_km REAL NOT NULL,
                transit_days REAL NOT NULL,
                unit_transport_cost REAL NOT NULL,
                total_freight_est REAL NOT NULL,
                urgency_score TEXT NOT NULL,
                data_classification TEXT NOT NULL DEFAULT 'SIMULATED_SAMPLE',
                rationale TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'ACTIVE',
                created_at TEXT NOT NULL
            );
            """)

            # 7. Delivery Shipments & Deadlines Monitor
            conn.execute("""
            CREATE TABLE IF NOT EXISTS delivery_shipments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shipment_code TEXT UNIQUE NOT NULL,
                origin_warehouse_id TEXT NOT NULL,
                destination_loc_id TEXT NOT NULL,
                destination_city TEXT NOT NULL,
                product_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                assigned_driver TEXT NOT NULL,
                vehicle_no TEXT NOT NULL,
                dispatched_at TEXT NOT NULL,
                expected_delivery_at TEXT NOT NULL,
                actual_delivery_at TEXT,
                status TEXT NOT NULL DEFAULT 'IN_TRANSIT',  -- 'DISPATCHED', 'IN_TRANSIT', 'DELIVERED', 'DELAYED'
                delay_minutes INTEGER DEFAULT 0,
                delay_reason TEXT,
                tracking_source TEXT NOT NULL DEFAULT 'ROAD_MANIFEST_CHECKPOINT',
                notes TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 8. Automated Alert Center (Deduplicated Alerts)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,  -- 'LOW_STOCK', 'EXPIRY_RISK', 'DELAYED_SHIPMENT', 'URGENT_REPLENISHMENT'
                severity TEXT NOT NULL,    -- 'CRITICAL', 'WARNING', 'INFO'
                entity_type TEXT NOT NULL, -- 'STORE', 'WAREHOUSE_BATCH', 'SHIPMENT', 'NETWORK'
                entity_id TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                recommended_action TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',  -- 'OPEN', 'ACKNOWLEDGED', 'RESOLVED'
                idempotency_hash TEXT NOT NULL,
                acknowledged_by TEXT,
                acknowledged_at TEXT,
                resolved_by TEXT,
                resolved_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """)

            # 9. Inventory Movement Transactions (Stock In / Stock Out Ledger)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS inventory_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_code TEXT UNIQUE NOT NULL,
                transaction_type TEXT NOT NULL,       -- 'STOCK_IN', 'STOCK_OUT'
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                sku TEXT,
                quantity INTEGER NOT NULL,
                warehouse_id TEXT NOT NULL,
                warehouse_name TEXT NOT NULL,
                partner_name TEXT NOT NULL,           -- Supplier (Stock In) or Store/Customer (Stock Out)
                transaction_date TEXT NOT NULL,       -- YYYY-MM-DD
                notes TEXT,
                performed_by TEXT NOT NULL,
                performed_by_role TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # Performance Indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_status_severity ON alerts(status, severity);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts_hash ON alerts(idempotency_hash);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_replenish_status ON replenishment_requests(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rescue_status ON expiry_rescue_transfers(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_shipments_status ON delivery_shipments(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_txn_date ON inventory_transactions(transaction_date);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_txn_type ON inventory_transactions(transaction_type);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_txn_warehouse ON inventory_transactions(warehouse_id);")

            # Seed Default Automation Workflow Configurations
            now_iso = datetime.now(timezone.utc).isoformat()
            default_workflows = [
                (
                    "auto_replenishment",
                    "Auto-Replenishment Engine",
                    "Monitors store stock vs statistical ROP, calculates order requirements, and stages manager-approval requests.",
                    1,
                    300,  # 5 minutes
                    json.dumps({"service_level_pct": 95.0, "min_order_buffer": 0.5}),
                    now_iso,
                    now_iso
                ),
                (
                    "expiry_rescue",
                    "FEFO Expiry Rescue Scanner",
                    "Scans warehouse lots nearing expiration and generates feasible store transfer allocations before spoilage.",
                    1,
                    600,  # 10 minutes
                    json.dumps({"shelf_life_threshold_days": 7, "priority_window_days": 4}),
                    now_iso,
                    now_iso
                ),
                (
                    "distribution_optimization",
                    "Distribution Corridors & Routing",
                    "Ranks candidate supply centers using stock, transit distance, freight costs, and demand priority.",
                    1,
                    900,  # 15 minutes
                    json.dumps({"fuel_multiplier": 1.0, "max_ranked_options": 3}),
                    now_iso,
                    now_iso
                ),
                (
                    "delivery_monitoring",
                    "Delivery Deadlines & Delay Monitor",
                    "Audits active dispatches against scheduled delivery windows and generates delayed-shipment alerts.",
                    1,
                    180,  # 3 minutes
                    json.dumps({"grace_period_minutes": 15}),
                    now_iso,
                    now_iso
                ),
            ]

            for wf in default_workflows:
                conn.execute("""
                INSERT OR IGNORE INTO automation_configs 
                (id, name, description, enabled, interval_seconds, config_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """, wf)

            # Seed sample initial shipments into delivery_shipments if table is empty
            count = conn.execute("SELECT COUNT(*) as cnt FROM delivery_shipments").fetchone()["cnt"]
            if count == 0:
                _seed_initial_shipments(conn, now_iso)

            # Seed sample initial verified inventory transactions if table is empty
            txn_count = conn.execute("SELECT COUNT(*) as cnt FROM inventory_transactions").fetchone()["cnt"]
            if txn_count == 0:
                _seed_initial_transactions(conn, now_iso)

        logger.info("Database initialized successfully at %s", target_path)
    finally:
        conn.close()


def _seed_initial_shipments(conn: sqlite3.Connection, now_iso: str):
    """Seeds active delivery manifests across Maharashtra distribution corridors."""
    from datetime import timedelta
    now = datetime.now(timezone.utc)
    sample_shipments = [
        (
            "SHP-MH-801", "WH-PUN", "LOC-PUNE", "Pune",
            "Fresh Pasteurised Milk (1L)", 80,
            "Rajesh Shinde", "MH-12-Q-4021",
            (now - timedelta(hours=1)).isoformat(),
            (now + timedelta(minutes=45)).isoformat(),
            "IN_TRANSIT", 0, None,
            "ROAD_MANIFEST_CHECKPOINT", "Corridor Pune City Express", now_iso, now_iso
        ),
        (
            "SHP-MH-802", "WH-PUN", "LOC-SATARA", "Satara",
            "Whole Wheat Brown Bread (400g)", 120,
            "Sachin Kadam", "MH-11-V-8812",
            (now - timedelta(hours=3, minutes=30)).isoformat(),
            (now - timedelta(minutes=30)).isoformat(),  # Already past deadline! -> DELAYED test case
            "DELAYED", 30, "Heavy traffic on NH-48 Khambatki Ghat",
            "ROAD_MANIFEST_CHECKPOINT", "Satara Highway Dispatch", now_iso, now_iso
        ),
        (
            "SHP-MH-803", "WH-PUN", "LOC-KOLHAPUR", "Kolhapur",
            "Farm Fresh Malai Paneer (500g)", 45,
            "Amit Patil", "MH-09-AA-1004",
            (now - timedelta(hours=2)).isoformat(),
            (now + timedelta(hours=1, minutes=30)).isoformat(),
            "IN_TRANSIT", 0, None,
            "ROAD_MANIFEST_CHECKPOINT", "Kolhapur Agro Dedicated Cold Van", now_iso, now_iso
        ),
        (
            "SHP-MH-804", "WH-PUN", "LOC-SANGLI", "Sangli",
            "Cold-Pressed Orange Juice (1L)", 60,
            "Sunil More", "MH-10-CX-9421",
            (now - timedelta(hours=1, minutes=15)).isoformat(),
            (now + timedelta(hours=2, minutes=30)).isoformat(),
            "IN_TRANSIT", 0, None,
            "ROAD_MANIFEST_CHECKPOINT", "Sangli Transit Hub", now_iso, now_iso
        ),
        (
            "SHP-MH-805", "WH-PUN", "LOC-KARAD", "Karad",
            "Artisanal Greek Yogurt (400g)", 35,
            "Nitin Sawant", "MH-50-B-3100",
            (now - timedelta(minutes=45)).isoformat(),
            (now + timedelta(hours=1, minutes=55)).isoformat(),
            "DISPATCHED", 0, None,
            "ROAD_MANIFEST_CHECKPOINT", "Karad Logistics Stop", now_iso, now_iso
        )
    ]
    for s in sample_shipments:
        conn.execute("""
        INSERT INTO delivery_shipments (
            shipment_code, origin_warehouse_id, destination_loc_id, destination_city,
            product_name, quantity, assigned_driver, vehicle_no,
            dispatched_at, expected_delivery_at, status, delay_minutes, delay_reason,
            tracking_source, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, s)


def _seed_initial_transactions(conn: sqlite3.Connection, now_iso: str):
    """Seeds verified initial inventory transactions (Stock In and Stock Out ledger records)."""
    sample_txns = [
        (
            "TXN-IN-20261023-0001", "STOCK_IN", 1, "Fresh Pasteurised Milk (1L)", "DAIRY-MLK-01",
            100, "WH-PUN", "Pune Regional Distribution Hub", "Amul Dairy Cooperative Ltd.",
            "2026-10-23", "Scheduled morning farm fresh intake batch", "Rajesh Warehouse Lead", "warehouse", now_iso
        ),
        (
            "TXN-IN-20261023-0002", "STOCK_IN", 10, "Royal Basmati Rice (5kg Bag)", "GROC-RCE-10",
            250, "WH-MUM", "Mumbai Central Mega-DC", "KRBL Milling & Agro Ltd.",
            "2026-10-23", "Bulk seasonal procurement receipt", "System Admin", "admin", now_iso
        ),
        (
            "TXN-OUT-20261024-0001", "STOCK_OUT", 2, "Artisanal Greek Yogurt (400g)", "DAIRY-YGT-02",
            50, "WH-PUN", "Pune Regional Distribution Hub", "Mumbai South Hypermarket",
            "2026-10-24", "Dispatched via Reefer Van MH-12-Q-4021", "Rajesh Warehouse Lead", "warehouse", now_iso
        ),
        (
            "TXN-OUT-20261024-0002", "STOCK_OUT", 5, "Whole Wheat Brown Bread (400g)", "BKRY-BRD-05",
            80, "WH-MUM", "Mumbai Central Mega-DC", "Thane Regional Stockist",
            "2026-10-24", "Express morning store replenishment", "Sneha Retail Dispatch", "retail", now_iso
        )
    ]
    for t in sample_txns:
        conn.execute("""
        INSERT INTO inventory_transactions (
            transaction_code, transaction_type, product_id, product_name, sku,
            quantity, warehouse_id, warehouse_name, partner_name,
            transaction_date, notes, performed_by, performed_by_role, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, t)


# Helper function to acquire distributed scheduler lock
def acquire_scheduler_lock(lock_name: str, worker_id: str, timeout_seconds: int = 60, db_path: Optional[str] = None) -> bool:
    """
    Acquires a process lock in the database to prevent duplicate execution across workers.
    Returns True if acquired, False otherwise.
    """
    conn = get_db_connection(db_path)
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    from datetime import timedelta
    expires_iso = (now + timedelta(seconds=timeout_seconds)).isoformat()

    try:
        with conn:
            # Clean expired locks
            conn.execute("DELETE FROM scheduler_locks WHERE expires_at < ?;", (now_iso,))
            # Try to insert or take over expired lock
            try:
                conn.execute("""
                INSERT INTO scheduler_locks (lock_name, locked_by, locked_at, expires_at)
                VALUES (?, ?, ?, ?);
                """, (lock_name, worker_id, now_iso, expires_iso))
                return True
            except sqlite3.IntegrityError:
                # Lock exists and has not expired
                return False
    finally:
        conn.close()


def release_scheduler_lock(lock_name: str, worker_id: str, db_path: Optional[str] = None):
    """Releases the scheduler lock."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("DELETE FROM scheduler_locks WHERE lock_name = ? AND locked_by = ?;", (lock_name, worker_id))
    finally:
        conn.close()
