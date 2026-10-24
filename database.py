"""
OptiStock AI — FMCG Distribution Intelligence & Smart Inventory Management System
Database Layer: Schema, SQLite Transactions, FMCG Geo-Locations, Shipment Lifecycle,
Idempotent Audit Ledger, and Real-Time Analytics
"""

import sqlite3
import os
import json
import math
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "optistock.db"))
if not os.access(os.path.dirname(os.path.abspath(DB_PATH)), os.W_OK):
    DB_PATH = os.path.join("/tmp", "optistock.db")


def get_db():
    """Returns SQLite connection with dict-like row access and PRAGMA foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """Calculates great-circle distance between two GPS coordinates in kilometers."""
    try:
        r = 6371.0  # Earth radius in km
        phi1 = math.radians(float(lat1))
        phi2 = math.radians(float(lat2))
        delta_phi = math.radians(float(lat2) - float(lat1))
        delta_lambda = math.radians(float(lon2) - float(lon1))

        a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        return round(r * c, 1)
    except (TypeError, ValueError):
        return 50.0


def init_db():
    """Initializes tables, indexes, constraints, and seeds FMCG demo dataset."""
    conn = get_db()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # 2. Products Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            sku TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL DEFAULT 0.0,
            min_stock_level INTEGER NOT NULL DEFAULT 0,
            description TEXT,
            weight_kg REAL DEFAULT 1.0,
            shelf_life_days INTEGER DEFAULT 365,
            is_demo INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, sku)
        );
    """)

    # 3. Locations Table (Warehouses, Distributors, Retailers with Coordinates & Capacity)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL, -- 'Warehouse', 'Distributor', 'Retailer'
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            state TEXT NOT NULL,
            pincode TEXT NOT NULL,
            lat REAL NOT NULL DEFAULT 18.5204,
            lng REAL NOT NULL DEFAULT 73.8567,
            capacity_units INTEGER NOT NULL DEFAULT 10000,
            operating_cost_per_day REAL DEFAULT 0.0,
            is_demo INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, code)
        );
    """)

    # 4. Inventory Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            location_id INTEGER NOT NULL,
            current_stock INTEGER NOT NULL DEFAULT 0,
            units_sold_per_day INTEGER NOT NULL DEFAULT 0,
            is_demo INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
            UNIQUE(user_id, product_id, location_id)
        );
    """)

    # 5. Shipments Table (Interactive Map Tracking & Lifecycle)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shipments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            shipment_code TEXT NOT NULL,
            source_location_id INTEGER NOT NULL,
            dest_location_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT NOT NULL, -- 'In Transit', 'Delivered', 'Delayed', 'Cancelled', 'Planned'
            dispatch_date TIMESTAMP,
            expected_delivery_date TIMESTAMP,
            actual_delivery_date TIMESTAMP,
            distance_km REAL DEFAULT 0.0,
            estimated_duration_min INTEGER DEFAULT 0,
            current_lat REAL,
            current_lng REAL,
            route_geometry TEXT, -- JSON array of [lat, lng] points
            notes TEXT,
            is_demo INTEGER DEFAULT 0,
            idempotency_key TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (source_location_id) REFERENCES locations(id) ON DELETE CASCADE,
            FOREIGN KEY (dest_location_id) REFERENCES locations(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );
    """)

    # 6. Inventory Transactions Audit Ledger
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            shipment_id INTEGER,
            product_id INTEGER NOT NULL,
            location_id INTEGER NOT NULL,
            transaction_type TEXT NOT NULL, -- 'DISPATCH_DEDUCT', 'DELIVERY_CREDIT', 'CANCEL_RESTORE', 'MANUAL_ADJUSTMENT'
            quantity INTEGER NOT NULL,
            balance_after INTEGER NOT NULL,
            reference TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE SET NULL,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE
        );
    """)

    # 7. Smart Alerts Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            alert_type TEXT NOT NULL, -- 'LOW_STOCK', 'CAPACITY_LIMIT', 'DELAYED_SHIPMENT', 'STOCKOUT_RISK', 'EXCESS_INVENTORY'
            severity TEXT NOT NULL, -- 'CRITICAL', 'WARNING', 'INFO'
            location_id INTEGER,
            product_id INTEGER,
            shipment_id INTEGER,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_resolved INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE
        );
    """)

    # 8. Predictions Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            store_id INTEGER NOT NULL,
            current_stock INTEGER NOT NULL,
            units_sold_per_day INTEGER NOT NULL,
            min_stock_level INTEGER NOT NULL,
            prediction_period INTEGER NOT NULL,
            predicted_demand INTEGER NOT NULL,
            projected_stock INTEGER NOT NULL,
            recommended_replenishment INTEGER NOT NULL,
            stock_status TEXT NOT NULL,
            suggested_warehouse_id INTEGER,
            available_warehouse_stock INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
            FOREIGN KEY (store_id) REFERENCES locations(id) ON DELETE CASCADE,
            FOREIGN KEY (suggested_warehouse_id) REFERENCES locations(id) ON DELETE SET NULL
        );
    """)

    conn.commit()

    # Seed Default Demo User if not exists
    cursor.execute("SELECT id FROM users WHERE email = ?", ("demo@optistock.ai",))
    demo_user = cursor.fetchone()

    if not demo_user:
        hashed_pw = generate_password_hash("password123")
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Amit Sharma", "demo@optistock.ai", hashed_pw)
        )
        demo_user_id = cursor.lastrowid
        seed_fmcg_demo_data(demo_user_id, conn)

    conn.commit()
    conn.close()


def seed_fmcg_demo_data(user_id, conn):
    """Seeds realistic FMCG network across Maharashtra & Gujarat for demonstration."""
    cursor = conn.cursor()

    # 1. FMCG Products Catalog
    fmcg_products = [
        ("Fresh Pasteurised Milk (1L)", "DAIRY-MLK-01", "Perishable Dairy", 54.0, 50, "Cold chain fresh pasteurised whole milk", 1.0, 6),
        ("Artisanal Greek Yogurt (400g)", "DAIRY-YGT-02", "Perishable Dairy", 85.0, 30, "Probiotic Greek yogurt tub", 0.4, 14),
        ("Farm Fresh Malai Paneer (500g)", "DAIRY-PNR-03", "Perishable Dairy", 160.0, 25, "Vacuum packed fresh cottage cheese", 0.5, 10),
        ("Cold-Pressed Orange Juice (1L)", "BEV-OJC-04", "Perishable Dairy", 120.0, 20, "100% pure cold pressed juice", 1.0, 21),
        ("Whole Wheat Brown Bread (400g)", "BKRY-BRD-05", "Bakery & Snacks", 45.0, 40, "Fiber-rich whole wheat daily bread", 0.4, 7),
        ("Digestive Fibre Biscuits (300g)", "SNK-BSC-06", "Bakery & Snacks", 60.0, 35, "Baked whole grain biscuits", 0.3, 120),
        ("Rich Tomato Ketchup (1kg)", "GROC-KCH-07", "Bakery & Snacks", 130.0, 20, "Classic tangy tomato ketchup glass bottle", 1.0, 180),
        ("Refined Sunflower Cooking Oil (5L)", "GROC-OIL-09", "Ambient Groceries", 690.0, 15, "Fortified sunflower oil can", 4.6, 365),
        ("Royal Basmati Rice (5kg Bag)", "GROC-RCE-10", "Ambient Groceries", 499.0, 20, "Long grain aged premium basmati", 5.0, 365),
        ("Advanced Laundry Detergent (2kg)", "HCARE-DTG-12", "Ambient Groceries", 280.0, 15, "Enzyme active laundry washing powder", 2.0, 365),
    ]

    for p in fmcg_products:
        cursor.execute("""
            INSERT OR IGNORE INTO products (user_id, name, sku, category, price, min_stock_level, description, weight_kg, shelf_life_days, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (user_id, *p))

    # 2. Locations: Warehouses, Distributors, Retailers
    locations = [
        # Warehouses (Blue)
        ("WH-MUM", "Mumbai Central Mega-DC", "Warehouse", "Plot 12, Kurla Industrial Estate", "Mumbai", "Maharashtra", "400070", 19.0760, 72.8777, 25000, 24000),
        ("WH-PUN", "Pune Regional Distribution Hub", "Warehouse", "Plot 45, Chakan MIDC Phase 2", "Pune", "Maharashtra", "410501", 18.5204, 73.8567, 18000, 18000),
        ("WH-AHM", "Ahmedabad Logistics Hub", "Warehouse", "Sarkhej-Bavla Road, Sanand Industrial Zone", "Ahmedabad", "Gujarat", "382210", 23.0225, 72.5714, 20000, 16500),
        ("WH-SUR", "Surat Coastal Depot", "Warehouse", "Hazira Port Industrial Corridor", "Surat", "Gujarat", "394270", 21.1702, 72.8311, 14000, 12000),

        # Distributors (Purple)
        ("DIS-THN", "Thane Regional Stockist", "Distributor", "Kolshet Road Logistics Park", "Thane", "Maharashtra", "400607", 19.2183, 72.9781, 10000, 8500),
        ("DIS-PUN", "Pune Metro Wholesalers", "Distributor", "Hadapsar Industrial Estate", "Pune", "Maharashtra", "411028", 18.5089, 73.9260, 12000, 9200),
        ("DIS-VAD", "Vadodara Supply Partners", "Distributor", "Makarpura GIDC Area", "Vadodara", "Gujarat", "390010", 22.3072, 73.1812, 9000, 7800),

        # Retailers (Orange)
        ("RET-MUM-S", "Mumbai South Hypermarket", "Retailer", "Colaba Causeway Main Blvd", "Mumbai", "Maharashtra", "400005", 18.9388, 72.8354, 4500, 5000),
        ("RET-MUM-N", "Mumbai North Supercenter", "Retailer", "SV Road, Borivali West", "Mumbai", "Maharashtra", "400092", 19.1860, 72.8485, 4000, 4800),
        ("RET-PUN-M", "Pune Market Square Retail", "Retailer", "FC Road, Deccan Gymkhana", "Pune", "Maharashtra", "411004", 18.5314, 73.8446, 3500, 4200),
        ("RET-PUN-W", "Pune West Mart", "Retailer", "Baner High Street Junction", "Pune", "Maharashtra", "411045", 18.5590, 73.7868, 3000, 3800),
        ("RET-NSH", "Nashik Fresh Direct", "Retailer", "College Road, Opp Big Bazaar", "Nashik", "Maharashtra", "422005", 19.9975, 73.7898, 3200, 3500),
        ("RET-KOL", "Kolhapur Agro Mart", "Retailer", "Rajarampuri 3rd Lane", "Kolhapur", "Maharashtra", "416008", 16.7050, 74.2433, 2800, 3200),
        ("RET-SUR-R", "Surat City Supermarket", "Retailer", "Ghod Dod Road", "Surat", "Gujarat", "395007", 21.1959, 72.8193, 3500, 3900),
    ]

    for loc in locations:
        cursor.execute("""
            INSERT OR IGNORE INTO locations (user_id, code, name, type, address, city, state, pincode, lat, lng, capacity_units, operating_cost_per_day, is_demo)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """, (user_id, *loc))

    # Fetch IDs
    cursor.execute("SELECT id, code FROM locations WHERE user_id = ?", (user_id,))
    loc_map = {r["code"]: r["id"] for r in cursor.fetchall()}

    cursor.execute("SELECT id, sku FROM products WHERE user_id = ?", (user_id,))
    prod_map = {r["sku"]: r["id"] for r in cursor.fetchall()}

    # 3. Seed Stock at Locations
    stock_seeds = [
        # Mumbai Mega-DC
        ("WH-MUM", "DAIRY-MLK-01", 3500, 0),
        ("WH-MUM", "DAIRY-YGT-02", 1800, 0),
        ("WH-MUM", "DAIRY-PNR-03", 1200, 0),
        ("WH-MUM", "GROC-OIL-09", 2500, 0),
        ("WH-MUM", "GROC-RCE-10", 3000, 0),
        ("WH-MUM", "HCARE-DTG-12", 2200, 0),

        # Pune Hub
        ("WH-PUN", "DAIRY-MLK-01", 2400, 0),
        ("WH-PUN", "BKRY-BRD-05", 1500, 0),
        ("WH-PUN", "SNK-BSC-06", 2000, 0),
        ("WH-PUN", "GROC-KCH-07", 1200, 0),
        ("WH-PUN", "GROC-OIL-09", 1800, 0),

        # Ahmedabad Hub
        ("WH-AHM", "GROC-OIL-09", 4000, 0),
        ("WH-AHM", "GROC-RCE-10", 3500, 0),
        ("WH-AHM", "SNK-BSC-06", 2500, 0),

        # Thane Distributor
        ("DIS-THN", "DAIRY-MLK-01", 800, 0),
        ("DIS-THN", "GROC-OIL-09", 450, 0),
        ("DIS-THN", "BKRY-BRD-05", 350, 0),

        # Pune Distributor
        ("DIS-PUN", "DAIRY-MLK-01", 650, 0),
        ("DIS-PUN", "SNK-BSC-06", 500, 0),

        # Vadodara Distributor
        ("DIS-VAD", "GROC-OIL-09", 600, 0),
        ("DIS-VAD", "GROC-RCE-10", 500, 0),

        # Retail Stores (Fast moving retail with velocity)
        ("RET-MUM-S", "DAIRY-MLK-01", 45, 25),    # Critical: 45 - 25*7 = -130
        ("RET-MUM-S", "GROC-OIL-09", 120, 10),    # Healthy
        ("RET-MUM-S", "BKRY-BRD-05", 30, 8),     # Low stock

        ("RET-MUM-N", "DAIRY-MLK-01", 80, 20),    # Critical: 80 - 140 = -60
        ("RET-MUM-N", "SNK-BSC-06", 150, 12),    # Healthy

        ("RET-PUN-M", "DAIRY-MLK-01", 35, 18),    # Critical
        ("RET-PUN-M", "DAIRY-PNR-03", 20, 6),     # Critical
        ("RET-PUN-M", "GROC-OIL-09", 90, 8),      # Healthy

        ("RET-PUN-W", "BKRY-BRD-05", 25, 7),     # Low stock
        ("RET-PUN-W", "DAIRY-MLK-01", 60, 12),    # Low stock

        ("RET-NSH", "GROC-RCE-10", 40, 5),        # Healthy
        ("RET-NSH", "DAIRY-MLK-01", 20, 10),      # Critical

        ("RET-KOL", "GROC-OIL-09", 35, 6),        # Low stock
        ("RET-KOL", "DAIRY-MLK-01", 15, 8),       # Critical

        ("RET-SUR-R", "GROC-OIL-09", 70, 7),      # Healthy
        ("RET-SUR-R", "SNK-BSC-06", 85, 9),       # Healthy
    ]

    for loc_code, sku, qty, vel in stock_seeds:
        l_id = loc_map.get(loc_code)
        p_id = prod_map.get(sku)
        if l_id and p_id:
            cursor.execute("""
                INSERT OR REPLACE INTO inventory (user_id, product_id, location_id, current_stock, units_sold_per_day, is_demo)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (user_id, p_id, l_id, qty, vel))

    # 4. Seed Shipments with Diverse Statuses & Coordinates for Map Visualization
    now = datetime.now()
    demo_shipments = [
        # 1. In Transit (Blue animated line, moving vehicle)
        {
            "code": "SHP-20261024-001",
            "src": "WH-MUM",
            "dst": "DIS-THN",
            "sku": "DAIRY-MLK-01",
            "qty": 400,
            "status": "In Transit",
            "dispatch": (now - timedelta(hours=3)).isoformat(),
            "expected": (now + timedelta(hours=2)).isoformat(),
            "notes": "Urgent cold-chain replenishment for Thane morning supply",
        },
        # 2. In Transit (Blue animated line, moving vehicle)
        {
            "code": "SHP-20261024-002",
            "src": "WH-PUN",
            "dst": "RET-PUN-M",
            "sku": "BKRY-BRD-05",
            "qty": 250,
            "status": "In Transit",
            "dispatch": (now - timedelta(hours=1)).isoformat(),
            "expected": (now + timedelta(hours=1)).isoformat(),
            "notes": "Daily fresh bakery store distribution",
        },
        # 3. Delivered (Green route line)
        {
            "code": "SHP-20261023-003",
            "src": "WH-MUM",
            "dst": "RET-MUM-S",
            "sku": "GROC-OIL-09",
            "qty": 180,
            "status": "Delivered",
            "dispatch": (now - timedelta(days=1, hours=5)).isoformat(),
            "expected": (now - timedelta(days=1, hours=1)).isoformat(),
            "actual": (now - timedelta(days=1)).isoformat(),
            "notes": "Cooking oil bulk shelf stock completed successfully",
        },
        # 4. Delivered (Green route line)
        {
            "code": "SHP-20261023-004",
            "src": "WH-AHM",
            "dst": "DIS-VAD",
            "sku": "GROC-RCE-10",
            "qty": 500,
            "status": "Delivered",
            "dispatch": (now - timedelta(days=1, hours=8)).isoformat(),
            "expected": (now - timedelta(days=1, hours=3)).isoformat(),
            "actual": (now - timedelta(days=1, hours=2)).isoformat(),
            "notes": "Inter-district distributor bulk transfer",
        },
        # 5. Delayed (Red route line)
        {
            "code": "SHP-20261024-005",
            "src": "WH-PUN",
            "dst": "RET-KOL",
            "sku": "DAIRY-MLK-01",
            "qty": 300,
            "status": "Delayed",
            "dispatch": (now - timedelta(hours=14)).isoformat(),
            "expected": (now - timedelta(hours=4)).isoformat(), # Expected 4 hours ago!
            "notes": "Heavy fog and highway detour on NH48 corridor",
        },
        # 6. Planned (Dashed route line)
        {
            "code": "SHP-20261025-006",
            "src": "WH-SUR",
            "dst": "RET-SUR-R",
            "sku": "SNK-BSC-06",
            "qty": 200,
            "status": "Planned",
            "dispatch": (now + timedelta(days=1)).isoformat(),
            "expected": (now + timedelta(days=1, hours=4)).isoformat(),
            "notes": "Scheduled weekly restocking manifest",
        },
    ]

    for s in demo_shipments:
        s_id = loc_map.get(s["src"])
        d_id = loc_map.get(s["dst"])
        p_id = prod_map.get(s["sku"])

        if s_id and d_id and p_id:
            # Fetch coords for distance & path
            cursor.execute("SELECT lat, lng FROM locations WHERE id = ?", (s_id,))
            s_row = cursor.fetchone()
            cursor.execute("SELECT lat, lng FROM locations WHERE id = ?", (d_id,))
            d_row = cursor.fetchone()

            dist = calculate_haversine_distance(s_row["lat"], s_row["lng"], d_row["lat"], d_row["lng"])
            duration_min = int(dist * 1.5)  # approx 40 km/h avg logistics speed

            # Linear interpolated path (source -> mid -> dest)
            mid_lat = (s_row["lat"] + d_row["lat"]) / 2.0
            mid_lng = (s_row["lng"] + d_row["lng"]) / 2.0
            route_geo = json.dumps([
                [s_row["lat"], s_row["lng"]],
                [round(mid_lat, 4), round(mid_lng, 4)],
                [d_row["lat"], d_row["lng"]]
            ])

            # Current vehicle position simulation
            curr_lat = mid_lat
            curr_lng = mid_lng

            cursor.execute("""
                INSERT OR IGNORE INTO shipments (
                    user_id, shipment_code, source_location_id, dest_location_id,
                    product_id, quantity, status, dispatch_date, expected_delivery_date,
                    actual_delivery_date, distance_km, estimated_duration_min,
                    current_lat, current_lng, route_geometry, notes, is_demo, idempotency_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                user_id, s["code"], s_id, d_id, p_id, s["qty"], s["status"],
                s["dispatch"], s["expected"], s.get("actual"), dist, duration_min,
                curr_lat, curr_lng, route_geo, s["notes"], f"DEMO-{s['code']}"
            ))

    # 5. Seed Initial Smart Alerts
    cursor.execute("""
        INSERT OR IGNORE INTO alerts (user_id, alert_type, severity, title, message)
        VALUES 
            (?, 'LOW_STOCK', 'CRITICAL', 'Critical Stockout at Mumbai South', 'Fresh Pasteurised Milk (1L) has 45 units remaining with run rate of 25 units/day. Depletion in 1.8 days.'),
            (?, 'DELAYED_SHIPMENT', 'CRITICAL', 'Shipment SHP-20261024-005 Delayed', 'Pune to Kolhapur transit delayed by 4 hours due to highway congestion.'),
            (?, 'CAPACITY_LIMIT', 'WARNING', 'Mumbai Central Mega-DC at 88% Capacity', 'Storage utilization reached 22,000 / 25,000 units. Transfer buffer low.'),
            (?, 'STOCKOUT_RISK', 'WARNING', 'Low Safety Floor at Pune Market Square', 'Farm Fresh Malai Paneer below safety threshold (20 units on hand).')
    """, (user_id, user_id, user_id, user_id))


def reset_demo_data(user_id):
    """Resets only DEMO records (is_demo=1) and repopulates clean demo data without touching user data."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM shipments WHERE user_id = ? AND is_demo = 1", (user_id,))
    cursor.execute("DELETE FROM inventory WHERE user_id = ? AND is_demo = 1", (user_id,))
    cursor.execute("DELETE FROM locations WHERE user_id = ? AND is_demo = 1", (user_id,))
    cursor.execute("DELETE FROM products WHERE user_id = ? AND is_demo = 1", (user_id,))
    cursor.execute("DELETE FROM alerts WHERE user_id = ?", (user_id,))

    conn.commit()
    seed_fmcg_demo_data(user_id, conn)
    conn.commit()
    conn.close()
    return True


# ─────────────────────────────────────────────────────────────
# USER AUTHENTICATION
# ─────────────────────────────────────────────────────────────

def get_user_by_email(email):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(email) = LOWER(?)", (email.strip(),))
    user = cursor.fetchone()
    conn.close()
    return user


def get_user_by_id(user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user


def create_user(name, email, password_hash):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name.strip(), email.strip().lower(), password_hash)
        )
        conn.commit()
        user_id = cursor.lastrowid
        seed_fmcg_demo_data(user_id, conn)
        conn.commit()
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


# ─────────────────────────────────────────────────────────────
# PRODUCTS CRUD
# ─────────────────────────────────────────────────────────────

def get_user_products(user_id, search=None, category=None):
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT 
            p.*,
            COALESCE(SUM(i.current_stock), 0) AS total_stock,
            COALESCE(SUM(i.current_stock * p.price), 0.0) AS total_value,
            COUNT(DISTINCT i.location_id) AS location_count
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id AND i.user_id = p.user_id
        WHERE p.user_id = ?
    """
    params = [user_id]

    if search:
        query += " AND (p.name LIKE ? OR p.sku LIKE ? OR p.category LIKE ?)"
        term = f"%{search.strip()}%"
        params.extend([term, term, term])

    if category and category.lower() != "all":
        query += " AND p.category = ?"
        params.append(category)

    query += " GROUP BY p.id ORDER BY p.name ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_product_by_id(product_id, user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            p.*,
            COALESCE(SUM(i.current_stock), 0) AS total_stock,
            COALESCE(SUM(i.current_stock * p.price), 0.0) AS total_value
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id AND i.user_id = p.user_id
        WHERE p.id = ? AND p.user_id = ?
        GROUP BY p.id
    """, (product_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def get_product_by_sku(sku, user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE UPPER(sku) = UPPER(?) AND user_id = ?", (sku.strip(), user_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_product(user_id, name, sku, category, price, min_stock_level, description="", weight_kg=1.0, shelf_life_days=365):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO products (user_id, name, sku, category, price, min_stock_level, description, weight_kg, shelf_life_days, is_demo)
            VALUES (?, ?, UPPER(?), ?, ?, ?, ?, ?, ?, 0)
        """, (user_id, name.strip(), sku.strip(), category.strip(), float(price), int(min_stock_level), description.strip(), float(weight_kg), int(shelf_life_days)))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def update_product(product_id, user_id, name, sku, category, price, min_stock_level, description="", weight_kg=1.0, shelf_life_days=365):
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE products SET
                name = ?, sku = UPPER(?), category = ?,
                price = ?, min_stock_level = ?, description = ?,
                weight_kg = ?, shelf_life_days = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        """, (name.strip(), sku.strip(), category.strip(), float(price), int(min_stock_level), description.strip(), float(weight_kg), int(shelf_life_days), product_id, user_id))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0
    except sqlite3.IntegrityError:
        conn.close()
        return False


def delete_product(product_id, user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ? AND user_id = ?", (product_id, user_id))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


# ─────────────────────────────────────────────────────────────
# LOCATIONS CRUD (WAREHOUSE, DISTRIBUTOR, RETAILER)
# ─────────────────────────────────────────────────────────────

def get_locations(user_id, loc_type=None, city=None, search=None):
    """Fetches locations with total stock, utilization %, and active shipments counts."""
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT 
            l.*,
            COALESCE(SUM(i.current_stock), 0) AS total_stock,
            COALESCE(SUM(i.current_stock), 0) AS total_items,
            COALESCE(SUM(i.current_stock * p.price), 0.0) AS total_valuation,
            COUNT(DISTINCT i.product_id) AS distinct_skus,
            ROUND(MIN(100.0, (CAST(COALESCE(SUM(i.current_stock), 0) AS REAL) / MAX(1, l.capacity_units)) * 100.0), 1) AS utilization_pct,
            (SELECT COUNT(*) FROM shipments s WHERE s.source_location_id = l.id AND s.status = 'In Transit') AS outgoing_shipments,
            (SELECT COUNT(*) FROM shipments s WHERE s.dest_location_id = l.id AND s.status = 'In Transit') AS incoming_shipments
        FROM locations l
        LEFT JOIN inventory i ON l.id = i.location_id AND i.user_id = l.user_id
        LEFT JOIN products p ON i.product_id = p.id AND p.user_id = l.user_id
        WHERE l.user_id = ?
    """
    params = [user_id]

    if loc_type and loc_type.lower() != "all":
        # Handle aliases
        if loc_type.lower() in ("store", "retail", "retail store", "retailer"):
            query += " AND l.type = 'Retailer'"
        else:
            query += " AND l.type = ?"
            params.append(loc_type)

    if city and city.lower() != "all":
        query += " AND l.city = ?"
        params.append(city)

    if search:
        query += " AND (l.name LIKE ? OR l.code LIKE ? OR l.city LIKE ? OR l.address LIKE ?)"
        term = f"%{search.strip()}%"
        params.extend([term, term, term, term])

    query += " GROUP BY l.id ORDER BY l.type ASC, l.name ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


get_user_locations = get_locations


def get_location_by_id(location_id, user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            l.*,
            COALESCE(SUM(i.current_stock), 0) AS total_stock,
            COALESCE(SUM(i.current_stock), 0) AS total_items,
            COALESCE(SUM(i.current_stock * p.price), 0.0) AS total_valuation,
            COUNT(DISTINCT i.product_id) AS distinct_skus,
            ROUND(MIN(100.0, (CAST(COALESCE(SUM(i.current_stock), 0) AS REAL) / MAX(1, l.capacity_units)) * 100.0), 1) AS utilization_pct
        FROM locations l
        LEFT JOIN inventory i ON l.id = i.location_id AND i.user_id = l.user_id
        LEFT JOIN products p ON i.product_id = p.id AND p.user_id = l.user_id
        WHERE l.id = ? AND l.user_id = ?
        GROUP BY l.id
    """, (location_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def add_location(user_id, code, name, loc_type, address, city, state, pincode, lat=18.5204, lng=73.8567, capacity=10000, operating_cost=0.0):
    conn = get_db()
    cursor = conn.cursor()
    # Normalize type
    t_clean = loc_type.strip().title()
    if t_clean in ("Retail Store", "Store"):
        t_clean = "Retailer"
    elif t_clean in ("Wh", "Distribution Center"):
        t_clean = "Warehouse"

    try:
        cursor.execute("""
            INSERT INTO locations (user_id, code, name, type, address, city, state, pincode, lat, lng, capacity_units, operating_cost_per_day, is_demo)
            VALUES (?, UPPER(?), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (user_id, code.strip(), name.strip(), t_clean, address.strip(), city.strip(), state.strip(), pincode.strip(), float(lat), float(lng), int(capacity), float(operating_cost)))
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id
    except sqlite3.IntegrityError:
        conn.close()
        return None


def update_location(location_id, user_id, code, name, loc_type, address, city, state, pincode, lat=None, lng=None, capacity=None):
    conn = get_db()
    cursor = conn.cursor()
    t_clean = loc_type.strip().title()
    if t_clean in ("Retail Store", "Store"):
        t_clean = "Retailer"

    try:
        cursor.execute("""
            UPDATE locations SET
                code = UPPER(?), name = ?, type = ?,
                address = ?, city = ?, state = ?, pincode = ?,
                lat = COALESCE(?, lat), lng = COALESCE(?, lng),
                capacity_units = COALESCE(?, capacity_units)
            WHERE id = ? AND user_id = ?
        """, (code.strip(), name.strip(), t_clean, address.strip(), city.strip(), state.strip(), pincode.strip(), lat, lng, capacity, location_id, user_id))
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0
    except sqlite3.IntegrityError:
        conn.close()
        return False


def delete_location(location_id, user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM locations WHERE id = ? AND user_id = ?", (location_id, user_id))
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected > 0


def get_location_popup_data(location_id, user_id):
    """
    Returns rich telemetry data required by map marker popups:
    - Available stock, incoming stock, outgoing stock
    - Stored products breakdown
    - Capacity utilization %
    - Recent deliveries (last 5)
    - Pending shipments
    """
    conn = get_db()
    cursor = conn.cursor()

    loc = get_location_by_id(location_id, user_id)
    if not loc:
        conn.close()
        return None

    # Stored products
    cursor.execute("""
        SELECT 
            i.current_stock, i.units_sold_per_day,
            p.id AS product_id, p.name, p.sku, p.category, p.price, p.min_stock_level,
            (i.current_stock * p.price) AS valuation
        FROM inventory i
        JOIN products p ON i.product_id = p.id AND p.user_id = i.user_id
        WHERE i.location_id = ? AND i.user_id = ? AND i.current_stock > 0
        ORDER BY i.current_stock DESC
    """, (location_id, user_id))
    products_stored = [dict(r) for r in cursor.fetchall()]

    # Incoming stock in transit
    cursor.execute("""
        SELECT COALESCE(SUM(quantity), 0) AS incoming
        FROM shipments 
        WHERE dest_location_id = ? AND user_id = ? AND status IN ('In Transit', 'Delayed')
    """, (location_id, user_id))
    incoming_stock = cursor.fetchone()["incoming"]

    # Outgoing stock in transit
    cursor.execute("""
        SELECT COALESCE(SUM(quantity), 0) AS outgoing
        FROM shipments 
        WHERE source_location_id = ? AND user_id = ? AND status IN ('In Transit', 'Delayed')
    """, (location_id, user_id))
    outgoing_stock = cursor.fetchone()["outgoing"]

    # Recent deliveries (last 5)
    cursor.execute("""
        SELECT 
            s.*, p.name AS product_name, p.sku AS product_sku,
            src.name AS source_name, src.type AS source_type
        FROM shipments s
        JOIN products p ON s.product_id = p.id AND p.user_id = s.user_id
        JOIN locations src ON s.source_location_id = src.id AND src.user_id = s.user_id
        WHERE s.dest_location_id = ? AND s.user_id = ? AND s.status = 'Delivered'
        ORDER BY s.actual_delivery_date DESC
        LIMIT 5
    """, (location_id, user_id))
    recent_deliveries = [dict(r) for r in cursor.fetchall()]

    # Pending orders / shipments
    cursor.execute("""
        SELECT 
            s.*, p.name AS product_name, p.sku AS product_sku,
            src.name AS source_name, dst.name AS dest_name
        FROM shipments s
        JOIN products p ON s.product_id = p.id AND p.user_id = s.user_id
        JOIN locations src ON s.source_location_id = src.id AND src.user_id = s.user_id
        JOIN locations dst ON s.dest_location_id = dst.id AND dst.user_id = s.user_id
        WHERE (s.source_location_id = ? OR s.dest_location_id = ?) 
          AND s.user_id = ? 
          AND s.status IN ('In Transit', 'Delayed', 'Planned')
        ORDER BY s.created_at DESC
        LIMIT 5
    """, (location_id, location_id, user_id))
    pending_orders = [dict(r) for r in cursor.fetchall()]

    conn.close()

    loc["incoming_stock"] = incoming_stock
    loc["outgoing_stock"] = outgoing_stock
    loc["products_stored"] = products_stored
    loc["stored_products"] = products_stored
    loc["recent_deliveries"] = recent_deliveries
    loc["pending_orders"] = pending_orders

    return loc


# ─────────────────────────────────────────────────────────────
# INVENTORY MATRIX CRUD
# ─────────────────────────────────────────────────────────────

def get_location_inventory(location_id, user_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            i.*,
            p.name AS product_name,
            p.sku AS product_sku,
            p.category AS product_category,
            p.price AS product_price,
            p.min_stock_level,
            (i.current_stock * p.price) AS total_val,
            l.name AS location_name,
            l.code AS location_code,
            l.type AS location_type,
            l.lat, l.lng
        FROM inventory i
        JOIN products p ON i.product_id = p.id AND p.user_id = i.user_id
        JOIN locations l ON i.location_id = l.id AND l.user_id = i.user_id
        WHERE i.location_id = ? AND i.user_id = ?
        ORDER BY p.name ASC
    """, (location_id, user_id))
    rows = cursor.fetchall()
    conn.close()

    items = []
    for r in rows:
        d = dict(r)
        pred = calculate_prediction(d["current_stock"], d["units_sold_per_day"], 7, d["min_stock_level"])
        d.update(pred)
        items.append(d)
    return items


def get_all_inventory_records(user_id, location_id=None, city=None, loc_type=None, search=None):
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT 
            i.*,
            p.name AS product_name,
            p.sku AS product_sku,
            p.category AS product_category,
            p.price AS product_price,
            p.min_stock_level,
            (i.current_stock * p.price) AS inventory_value,
            l.name AS location_name,
            l.code AS location_code,
            l.type AS location_type,
            l.city AS location_city,
            l.state AS location_state,
            l.lat, l.lng
        FROM inventory i
        JOIN products p ON i.product_id = p.id AND p.user_id = i.user_id
        JOIN locations l ON i.location_id = l.id AND l.user_id = i.user_id
        WHERE i.user_id = ?
    """
    params = [user_id]

    if location_id:
        query += " AND i.location_id = ?"
        params.append(location_id)

    if loc_type and loc_type.lower() != "all":
        if loc_type.lower() in ("store", "retail store", "retailer"):
            query += " AND l.type = 'Retailer'"
        else:
            query += " AND l.type = ?"
            params.append(loc_type)

    if city and city.lower() != "all":
        query += " AND l.city = ?"
        params.append(city)

    if search:
        query += " AND (p.name LIKE ? OR p.sku LIKE ? OR l.name LIKE ? OR l.code LIKE ?)"
        term = f"%{search.strip()}%"
        params.extend([term, term, term, term])

    query += " ORDER BY l.name ASC, p.name ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    result = []
    for r in rows:
        d = dict(r)
        pred = calculate_prediction(d["current_stock"], d["units_sold_per_day"], 7, d["min_stock_level"])
        d.update(pred)
        result.append(d)
    return result


def set_inventory_stock(user_id, product_id, location_id, current_stock, units_sold_per_day=0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO inventory (user_id, product_id, location_id, current_stock, units_sold_per_day, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, product_id, location_id) DO UPDATE SET
            current_stock = excluded.current_stock,
            units_sold_per_day = excluded.units_sold_per_day,
            updated_at = CURRENT_TIMESTAMP
    """, (user_id, product_id, location_id, int(current_stock), int(units_sold_per_day)))
    conn.commit()
    conn.close()
    return True


# ─────────────────────────────────────────────────────────────
# SHIPMENT LIFECYCLE & ATOMIC INVENTORY MOVEMENTS
# ─────────────────────────────────────────────────────────────

def get_shipments(user_id, status=None, search=None):
    conn = get_db()
    cursor = conn.cursor()

    query = """
        SELECT 
            s.*,
            s.shipment_code AS transfer_code,
            p.name AS product_name,
            p.sku AS product_sku,
            p.price AS product_price,
            (s.quantity * p.price) AS shipment_value,
            (s.quantity * p.price) AS transfer_value,
            src.name AS source_name,
            src.code AS source_code,
            src.type AS source_type,
            src.city AS source_city,
            src.lat AS source_lat,
            src.lng AS source_lng,
            dst.name AS dest_name,
            dst.code AS dest_code,
            dst.type AS dest_type,
            dst.city AS dest_city,
            dst.lat AS dest_lat,
            dst.lng AS dest_lng
        FROM shipments s
        JOIN products p ON s.product_id = p.id AND p.user_id = s.user_id
        JOIN locations src ON s.source_location_id = src.id AND src.user_id = s.user_id
        JOIN locations dst ON s.dest_location_id = dst.id AND dst.user_id = s.user_id
        WHERE s.user_id = ?
    """
    params = [user_id]

    if status and status.lower() != "all":
        query += " AND s.status = ?"
        params.append(status)

    if search:
        query += " AND (s.shipment_code LIKE ? OR p.name LIKE ? OR p.sku LIKE ? OR src.name LIKE ? OR dst.name LIKE ?)"
        term = f"%{search.strip()}%"
        params.extend([term, term, term, term, term])

    query += " ORDER BY s.created_at DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    result = []
    now = datetime.now()

    for r in rows:
        d = dict(r)
        # Parse route geometry JSON
        if d.get("route_geometry"):
            try:
                d["geometry"] = json.loads(d["route_geometry"])
            except Exception:
                d["geometry"] = [[d["source_lat"], d["source_lng"]], [d["dest_lat"], d["dest_lng"]]]
        else:
            d["geometry"] = [[d["source_lat"], d["source_lng"]], [d["dest_lat"], d["dest_lng"]]]

        # Dynamic vehicle transit progression simulation for moving truck icons
        if d["status"] in ("In Transit", "Delayed") and d.get("dispatch_date"):
            try:
                disp_dt = datetime.fromisoformat(d["dispatch_date"])
                exp_dt = datetime.fromisoformat(d["expected_delivery_date"]) if d.get("expected_delivery_date") else disp_dt + timedelta(hours=4)
                total_sec = max(1, (exp_dt - disp_dt).total_seconds())
                elapsed_sec = (now - disp_dt).total_seconds()
                progress = min(0.92, max(0.08, elapsed_sec / total_sec))
            except Exception:
                progress = 0.5

            # Interpolate vehicle GPS position
            d["vehicle_lat"] = round(d["source_lat"] + (d["dest_lat"] - d["source_lat"]) * progress, 4)
            d["vehicle_lng"] = round(d["source_lng"] + (d["dest_lng"] - d["source_lng"]) * progress, 4)
            d["progress_pct"] = int(progress * 100)
        else:
            d["vehicle_lat"] = d["dest_lat"] if d["status"] == "Delivered" else d["source_lat"]
            d["vehicle_lng"] = d["dest_lng"] if d["status"] == "Delivered" else d["source_lng"]
            d["progress_pct"] = 100 if d["status"] == "Delivered" else 0

        # Status badge color
        if d["status"] == "Delivered":
            d["route_color"] = "#10b981" # Green
            d["status_badge"] = "status-healthy"
        elif d["status"] == "In Transit":
            d["route_color"] = "#3b82f6" # Blue
            d["status_badge"] = "badge-warehouse"
        elif d["status"] == "Delayed":
            d["route_color"] = "#ef4444" # Red
            d["status_badge"] = "status-critical"
        elif d["status"] == "Cancelled":
            d["route_color"] = "#64748b" # Gray
            d["status_badge"] = "badge"
        else:
            d["route_color"] = "#a855f7" # Purple/Dashed Planned
            d["status_badge"] = "badge-store"

        result.append(d)

    return result


def get_shipment_by_id(shipment_id, user_id):
    shipments = get_shipments(user_id)
    for s in shipments:
        if s["id"] == shipment_id:
            return s
    return None


def create_shipment(user_id, source_id, dest_id, product_id, quantity, status="In Transit", dispatch_date=None, expected_date=None, notes=None, idempotency_key=None):
    """
    Dispatches a shipment and atomically updates inventory:
    1. Validates source != dest
    2. Validates quantity > 0
    3. Checks source location has sufficient available inventory
    4. Deducts quantity from source inventory
    5. Saves shipment record with route coordinates
    6. Logs DISPATCH_DEDUCT in audit ledger
    """
    if source_id == dest_id:
        return False, "Origin facility and destination facility cannot be identical."

    try:
        qty = int(quantity)
        if qty <= 0:
            return False, "Shipment quantity must be a positive integer greater than zero."
    except (ValueError, TypeError):
        return False, "Invalid shipment quantity provided."

    conn = get_db()
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN IMMEDIATE TRANSACTION;")

        # Idempotency check
        if idempotency_key:
            cursor.execute("SELECT id FROM shipments WHERE user_id = ? AND idempotency_key = ?", (user_id, idempotency_key))
            if cursor.fetchone():
                conn.rollback()
                conn.close()
                return False, "Duplicate operation detected. This shipment has already been recorded."

        # Verify source inventory availability
        cursor.execute("""
            SELECT current_stock FROM inventory 
            WHERE user_id = ? AND product_id = ? AND location_id = ?
        """, (user_id, product_id, source_id))
        source_row = cursor.fetchone()
        source_stock = source_row["current_stock"] if source_row else 0

        if source_stock < qty:
            conn.rollback()
            conn.close()
            return False, f"Insufficient stock at source facility. On-hand: {source_stock} units, Requested dispatch: {qty} units."

        # Fetch coordinates for distance & duration calculation
        cursor.execute("SELECT lat, lng FROM locations WHERE id = ?", (source_id,))
        s_coords = cursor.fetchone()
        cursor.execute("SELECT lat, lng FROM locations WHERE id = ?", (dest_id,))
        d_coords = cursor.fetchone()

        dist_km = calculate_haversine_distance(s_coords["lat"], s_coords["lng"], d_coords["lat"], d_coords["lng"])
        duration_min = int(dist_km * 1.5)

        # Route geometry points
        mid_lat = (s_coords["lat"] + d_coords["lat"]) / 2.0
        mid_lng = (s_coords["lng"] + d_coords["lng"]) / 2.0
        route_geo = json.dumps([
            [s_coords["lat"], s_coords["lng"]],
            [round(mid_lat, 4), round(mid_lng, 4)],
            [d_coords["lat"], d_coords["lng"]]
        ])

        now = datetime.now()
        disp_dt = dispatch_date or now.isoformat()
        exp_dt = expected_date or (now + timedelta(minutes=duration_min + 60)).isoformat()

        # Deduct from source inventory
        new_source_stock = source_stock - qty
        cursor.execute("""
            UPDATE inventory 
            SET current_stock = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND product_id = ? AND location_id = ?
        """, (new_source_stock, user_id, product_id, source_id))

        # Generate unique shipment code
        cursor.execute("SELECT COUNT(*) AS total FROM shipments WHERE user_id = ?", (user_id,))
        seq = cursor.fetchone()["total"] + 1
        shipment_code = f"SHP-{now.strftime('%Y%m%d')}-{seq:04d}"

        # Insert shipment
        cursor.execute("""
            INSERT INTO shipments (
                user_id, shipment_code, source_location_id, dest_location_id,
                product_id, quantity, status, dispatch_date, expected_delivery_date,
                distance_km, estimated_duration_min, current_lat, current_lng,
                route_geometry, notes, idempotency_key, is_demo
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            user_id, shipment_code, source_id, dest_id,
            product_id, qty, status, disp_dt, exp_dt,
            dist_km, duration_min, s_coords["lat"], s_coords["lng"],
            route_geo, notes.strip() if notes else None, idempotency_key
        ))
        new_shipment_id = cursor.lastrowid

        # Audit ledger record
        cursor.execute("""
            INSERT INTO inventory_transactions (user_id, shipment_id, product_id, location_id, transaction_type, quantity, balance_after, reference)
            VALUES (?, ?, ?, ?, 'DISPATCH_DEDUCT', ?, ?, ?)
        """, (user_id, new_shipment_id, product_id, source_id, -qty, new_source_stock, f"Dispatched via {shipment_code}"))

        conn.commit()
        conn.close()
        return True, f"Shipment {shipment_code} ({qty} units) successfully dispatched! Route active on map."

    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Failed to dispatch shipment: {str(e)}"


def confirm_delivery(shipment_id, user_id, confirmed_quantity=None):
    """
    Confirms shipment delivery:
    1. Verifies shipment is currently 'In Transit' or 'Delayed'
    2. Credits confirmed quantity to destination inventory
    3. Sets status to 'Delivered' and stamps actual_delivery_date
    4. Logs DELIVERY_CREDIT in audit ledger
    5. Prevents duplicate credit
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN IMMEDIATE TRANSACTION;")

        cursor.execute("SELECT * FROM shipments WHERE id = ? AND user_id = ?", (shipment_id, user_id))
        shipment = cursor.fetchone()

        if not shipment:
            conn.rollback()
            conn.close()
            return False, "Shipment not found."

        if shipment["status"] == "Delivered":
            conn.rollback()
            conn.close()
            return False, "This shipment has already been confirmed as Delivered."

        if shipment["status"] == "Cancelled":
            conn.rollback()
            conn.close()
            return False, "Cannot confirm delivery of a cancelled shipment."

        qty_to_credit = int(confirmed_quantity) if confirmed_quantity is not None else shipment["quantity"]
        dest_id = shipment["dest_location_id"]
        product_id = shipment["product_id"]

        # Fetch current destination stock
        cursor.execute("""
            SELECT current_stock FROM inventory 
            WHERE user_id = ? AND product_id = ? AND location_id = ?
        """, (user_id, product_id, dest_id))
        dest_row = cursor.fetchone()
        dest_stock = dest_row["current_stock"] if dest_row else 0
        new_dest_stock = dest_stock + qty_to_credit

        # Upsert destination inventory
        cursor.execute("""
            INSERT INTO inventory (user_id, product_id, location_id, current_stock, units_sold_per_day, updated_at)
            VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, product_id, location_id) DO UPDATE SET
                current_stock = current_stock + excluded.current_stock,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, product_id, dest_id, qty_to_credit))

        now_str = datetime.now().isoformat()

        # Update shipment status
        cursor.execute("""
            UPDATE shipments SET
                status = 'Delivered',
                actual_delivery_date = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        """, (now_str, shipment_id, user_id))

        # Audit ledger
        cursor.execute("""
            INSERT INTO inventory_transactions (user_id, shipment_id, product_id, location_id, transaction_type, quantity, balance_after, reference)
            VALUES (?, ?, ?, ?, 'DELIVERY_CREDIT', ?, ?, ?)
        """, (user_id, shipment_id, product_id, dest_id, qty_to_credit, new_dest_stock, f"Delivered via {shipment['shipment_code']}"))

        conn.commit()
        conn.close()
        return True, f"Delivery confirmed! {qty_to_credit} units credited to destination inventory."

    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Failed to confirm delivery: {str(e)}"


def cancel_shipment(shipment_id, user_id, reason="Cancelled by user"):
    """
    Cancels a shipment and safely restores source inventory:
    1. Verifies shipment is in 'In Transit' or 'Delayed' or 'Planned'
    2. Restores dispatched quantity back to source inventory
    3. Sets status to 'Cancelled'
    4. Logs CANCEL_RESTORE in audit ledger
    """
    conn = get_db()
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN IMMEDIATE TRANSACTION;")

        cursor.execute("SELECT * FROM shipments WHERE id = ? AND user_id = ?", (shipment_id, user_id))
        shipment = cursor.fetchone()

        if not shipment:
            conn.rollback()
            conn.close()
            return False, "Shipment record not found."

        if shipment["status"] == "Delivered":
            conn.rollback()
            conn.close()
            return False, "Delivered shipments cannot be cancelled."

        if shipment["status"] == "Cancelled":
            conn.rollback()
            conn.close()
            return False, "Shipment is already cancelled."

        # If it was in transit or delayed, inventory was deducted, so restore it!
        if shipment["status"] in ("In Transit", "Delayed"):
            qty = shipment["quantity"]
            src_id = shipment["source_location_id"]
            prod_id = shipment["product_id"]

            cursor.execute("""
                UPDATE inventory 
                SET current_stock = current_stock + ?, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND product_id = ? AND location_id = ?
            """, (qty, user_id, prod_id, src_id))

            cursor.execute("SELECT current_stock FROM inventory WHERE user_id = ? AND product_id = ? AND location_id = ?", (user_id, prod_id, src_id))
            balance = cursor.fetchone()["current_stock"]

            cursor.execute("""
                INSERT INTO inventory_transactions (user_id, shipment_id, product_id, location_id, transaction_type, quantity, balance_after, reference)
                VALUES (?, ?, ?, ?, 'CANCEL_RESTORE', ?, ?, ?)
            """, (user_id, shipment_id, prod_id, src_id, qty, balance, f"Restored from cancelled {shipment['shipment_code']} - {reason}"))

        cursor.execute("""
            UPDATE shipments SET
                status = 'Cancelled',
                notes = COALESCE(notes || ' | ', '') || ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
        """, (f"Cancelled: {reason}", shipment_id, user_id))

        conn.commit()
        conn.close()
        return True, f"Shipment {shipment['shipment_code']} cancelled. Stock safely restored to source."

    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Cancellation failed: {str(e)}"


def transfer_stock(user_id, source_id, dest_id, product_id, quantity, notes=""):
    """
    Executes an atomic transfer between source and destination:
    1. Validates source != dest
    2. Validates available stock >= quantity
    3. Atomically deducts from source, credits destination
    4. Records in shipments (status='Delivered') and inventory_transactions audit ledger
    """
    try:
        s_id = int(source_id)
        d_id = int(dest_id)
        p_id = int(product_id)
        qty = int(quantity)
    except (ValueError, TypeError):
        return False, "Invalid location, product, or quantity values."

    if s_id == d_id:
        return False, "Source and destination locations cannot be the same."

    if qty <= 0:
        return False, "Transfer quantity must be greater than zero."

    conn = get_db()
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN IMMEDIATE TRANSACTION;")

        cursor.execute("""
            SELECT current_stock FROM inventory 
            WHERE user_id = ? AND product_id = ? AND location_id = ?
        """, (user_id, p_id, s_id))
        src_row = cursor.fetchone()
        src_stock = src_row["current_stock"] if src_row else 0

        if src_stock < qty:
            conn.rollback()
            conn.close()
            return False, f"Insufficient stock at source location. Available: {src_stock}, requested: {qty}."

        # Deduct from source
        new_source_stock = src_stock - qty
        cursor.execute("""
            UPDATE inventory 
            SET current_stock = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND product_id = ? AND location_id = ?
        """, (new_source_stock, user_id, p_id, s_id))

        # Credit to destination
        cursor.execute("""
            INSERT INTO inventory (user_id, product_id, location_id, current_stock, units_sold_per_day, updated_at)
            VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, product_id, location_id) DO UPDATE SET
                current_stock = current_stock + excluded.current_stock,
                updated_at = CURRENT_TIMESTAMP
        """, (user_id, p_id, d_id, qty))

        cursor.execute("SELECT current_stock FROM inventory WHERE user_id = ? AND product_id = ? AND location_id = ?", (user_id, p_id, d_id))
        dest_stock = cursor.fetchone()["current_stock"]

        # Coordinates & route
        cursor.execute("SELECT lat, lng FROM locations WHERE id = ?", (s_id,))
        s_coords = cursor.fetchone() or {"lat": 18.5204, "lng": 73.8567}
        cursor.execute("SELECT lat, lng FROM locations WHERE id = ?", (d_id,))
        d_coords = cursor.fetchone() or {"lat": 18.5204, "lng": 73.8567}

        dist_km = calculate_haversine_distance(s_coords["lat"], s_coords["lng"], d_coords["lat"], d_coords["lng"])
        route_geo = json.dumps([
            [s_coords["lat"], s_coords["lng"]],
            [d_coords["lat"], d_coords["lng"]]
        ])

        now = datetime.now()
        cursor.execute("SELECT COUNT(*) AS total FROM shipments WHERE user_id = ?", (user_id,))
        seq = cursor.fetchone()["total"] + 1
        transfer_code = f"TRF-{now.strftime('%Y%m%d')}-{seq:04d}"

        # Insert shipment record
        cursor.execute("""
            INSERT INTO shipments (
                user_id, shipment_code, source_location_id, dest_location_id,
                product_id, quantity, status, dispatch_date, expected_delivery_date,
                actual_delivery_date, distance_km, estimated_duration_min,
                current_lat, current_lng, route_geometry, notes, is_demo
            ) VALUES (?, ?, ?, ?, ?, ?, 'Delivered', ?, ?, ?, ?, 0, ?, ?, ?, ?, 0)
        """, (
            user_id, transfer_code, s_id, d_id,
            p_id, qty, now.isoformat(), now.isoformat(),
            now.isoformat(), dist_km, d_coords["lat"], d_coords["lng"],
            route_geo, notes.strip() if notes else "Direct inter-facility stock transfer"
        ))
        trf_id = cursor.lastrowid

        # Insert audit ledger records
        cursor.execute("""
            INSERT INTO inventory_transactions (user_id, shipment_id, product_id, location_id, transaction_type, quantity, balance_after, reference)
            VALUES (?, ?, ?, ?, 'TRANSFER_OUT', ?, ?, ?)
        """, (user_id, trf_id, p_id, s_id, -qty, new_source_stock, f"Transferred to {d_id} via {transfer_code}"))

        cursor.execute("""
            INSERT INTO inventory_transactions (user_id, shipment_id, product_id, location_id, transaction_type, quantity, balance_after, reference)
            VALUES (?, ?, ?, ?, 'TRANSFER_IN', ?, ?, ?)
        """, (user_id, trf_id, p_id, d_id, qty, dest_stock, f"Received from {s_id} via {transfer_code}"))

        conn.commit()
        conn.close()
        return True, f"Stock transfer completed successfully! {qty} units moved ({transfer_code})."

    except Exception as e:
        conn.rollback()
        conn.close()
        return False, f"Transfer failed: {str(e)}"


# ─────────────────────────────────────────────────────────────
# DEMAND PREDICTION ENGINE
# ─────────────────────────────────────────────────────────────

def calculate_prediction(current_stock, units_sold_per_day, prediction_period, min_stock_level):
    try:
        curr = int(current_stock)
        vel = int(units_sold_per_day)
        period = int(prediction_period)
        min_stock = int(min_stock_level)
    except (ValueError, TypeError):
        curr, vel, period, min_stock = 0, 0, 7, 0

    predicted_demand = vel * period
    projected_stock = curr - predicted_demand
    recommended_replenishment = max(0, predicted_demand + min_stock - curr)

    if projected_stock < 0:
        status = "Critical"
        badge = "status-critical"
        msg = f"Projected Stockout! Stock will be depleted in {(curr / vel):.1f} days." if vel > 0 else "Stockout Risk."
    elif projected_stock <= min_stock:
        status = "Low Stock"
        badge = "status-low"
        msg = "Projected stock approaches or falls below minimum safety buffer."
    else:
        status = "Healthy"
        badge = "status-healthy"
        msg = "Optimal inventory runway across the selected forecast horizon."

    return {
        "predicted_demand": predicted_demand,
        "projected_stock": projected_stock,
        "expected_remaining_stock": projected_stock,
        "recommended_replenishment": recommended_replenishment,
        "recommended_restock": recommended_replenishment,
        "status": status,
        "status_badge": badge,
        "status_message": msg,
        "days_of_coverage": round(curr / vel, 1) if vel > 0 else 999.0,
        "min_stock_level": min_stock,
        "current_stock": curr,
        "units_sold_per_day": vel,
        "prediction_period": period
    }


def find_suggested_warehouse(user_id, product_id, needed_quantity):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            l.id, l.name, l.code, l.city, l.state,
            i.current_stock AS available_stock
        FROM inventory i
        JOIN locations l ON i.location_id = l.id AND l.user_id = i.user_id
        WHERE i.user_id = ? 
          AND i.product_id = ? 
          AND l.type = 'Warehouse'
          AND i.current_stock > 0
        ORDER BY i.current_stock DESC
    """, (user_id, product_id))
    warehouses = [dict(r) for r in cursor.fetchall()]
    conn.close()

    if not warehouses:
        return {
            "warehouse": None,
            "available_stock": 0,
            "shortage": needed_quantity,
            "has_sufficient": False,
            "message": "Shortage: No warehouse stock available across all distribution hubs."
        }

    sufficient = [w for w in warehouses if w["available_stock"] >= needed_quantity]
    selected = sufficient[0] if sufficient else warehouses[0]

    shortage = max(0, needed_quantity - selected["available_stock"])
    has_sufficient = selected["available_stock"] >= needed_quantity

    if has_sufficient:
        msg = f"Sufficient Stock: {selected['name']} ({selected['city']}) has {selected['available_stock']} units available."
    else:
        msg = f"Partial Availability: {selected['name']} has {selected['available_stock']} units (Shortage of {shortage} units)."

    return {
        "warehouse": selected,
        "available_stock": selected["available_stock"],
        "shortage": shortage,
        "has_sufficient": has_sufficient,
        "message": msg
    }


def save_prediction(user_id, product_id, store_id, current_stock, units_sold_per_day, min_stock_level, prediction_period, pred_result, wh_result):
    conn = get_db()
    cursor = conn.cursor()
    wh_id = wh_result["warehouse"]["id"] if wh_result.get("warehouse") else None
    wh_stock = wh_result.get("available_stock", 0)

    cursor.execute("""
        INSERT INTO predictions (
            user_id, product_id, store_id, current_stock, units_sold_per_day,
            min_stock_level, prediction_period, predicted_demand, projected_stock,
            recommended_replenishment, stock_status, suggested_warehouse_id, available_warehouse_stock
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id, product_id, store_id, current_stock, units_sold_per_day,
        min_stock_level, prediction_period, pred_result["predicted_demand"],
        pred_result["projected_stock"], pred_result["recommended_replenishment"],
        pred_result["status"], wh_id, wh_stock
    ))
    conn.commit()
    pred_id = cursor.lastrowid
    conn.close()
    return pred_id


def get_recent_predictions(user_id, limit=20):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            pr.*,
            p.name AS product_name, p.sku AS product_sku, p.category AS product_category, p.price AS product_price,
            s.name AS store_name, s.code AS store_code, s.city AS store_city,
            wh.name AS warehouse_name, wh.code AS warehouse_code, wh.city AS warehouse_city
        FROM predictions pr
        JOIN products p ON pr.product_id = p.id AND p.user_id = pr.user_id
        JOIN locations s ON pr.store_id = s.id AND s.user_id = pr.user_id
        LEFT JOIN locations wh ON pr.suggested_warehouse_id = wh.id AND wh.user_id = pr.user_id
        WHERE pr.user_id = ?
        ORDER BY pr.created_at DESC
        LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─────────────────────────────────────────────────────────────
# FMCG ANALYTICS & SMART ALERTS
# ─────────────────────────────────────────────────────────────

def get_fmcg_dashboard_metrics(user_id):
    """
    Calculates all 10 key metric cards and analytics data:
    1. Total inventory across locations
    2. Number of warehouses
    3. Active distributors
    4. Retailers served
    5. Shipments in transit
    6. Successfully delivered shipments
    7. Delayed shipments
    8. Low-stock products
    9. Total dispatched units
    10. Total delivered units
    """
    conn = get_db()
    cursor = conn.cursor()

    # Total inventory
    cursor.execute("SELECT COALESCE(SUM(current_stock), 0) AS total_inv, COALESCE(SUM(current_stock * p.price), 0.0) AS total_val FROM inventory i JOIN products p ON i.product_id = p.id AND p.user_id = i.user_id WHERE i.user_id = ?", (user_id,))
    inv_row = cursor.fetchone()
    total_inventory = inv_row["total_inv"]
    total_inventory_value = inv_row["total_val"]

    # Product count
    cursor.execute("SELECT COUNT(*) AS total FROM products WHERE user_id = ?", (user_id,))
    total_products = cursor.fetchone()["total"]

    # Facility counts
    cursor.execute("SELECT COUNT(*) AS total FROM locations WHERE user_id = ? AND type = 'Warehouse'", (user_id,))
    total_warehouses = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM locations WHERE user_id = ? AND type = 'Distributor'", (user_id,))
    active_distributors = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM locations WHERE user_id = ? AND type = 'Retailer'", (user_id,))
    retailers_served = cursor.fetchone()["total"]
    total_retail_stores = retailers_served

    # Predicted demand across retail outlets (7-day forecast run)
    cursor.execute("SELECT COALESCE(SUM(units_sold_per_day * 7), 0) AS pred_demand FROM inventory WHERE user_id = ?", (user_id,))
    predicted_demand = cursor.fetchone()["pred_demand"]

    # Store inventory health & replenishment deficit analysis
    cursor.execute("""
        SELECT 
            i.current_stock, i.units_sold_per_day,
            p.name AS product_name, p.sku AS product_sku, p.price, p.min_stock_level,
            l.name AS store_name, l.code AS store_code
        FROM inventory i
        JOIN products p ON i.product_id = p.id AND p.user_id = i.user_id
        JOIN locations l ON i.location_id = l.id AND l.user_id = i.user_id
        WHERE i.user_id = ? AND l.type = 'Retailer'
    """, (user_id,))
    store_inv_rows = cursor.fetchall()

    status_counts = {"Healthy": 0, "Low Stock": 0, "Critical": 0}
    deficit_items = []

    for row in store_inv_rows:
        curr = row["current_stock"]
        vel = row["units_sold_per_day"] or 0
        min_lvl = row["min_stock_level"] or 0
        proj = curr - (vel * 7)
        replenish = max(0, (vel * 7) + min_lvl - curr)

        if proj < 0:
            st = "Critical"
            badge = "status-critical"
        elif proj <= min_lvl:
            st = "Low Stock"
            badge = "status-low"
        else:
            st = "Healthy"
            badge = "status-healthy"

        status_counts[st] += 1

        if st in ("Critical", "Low Stock") or curr <= min_lvl:
            deficit_items.append({
                "store_name": row["store_name"],
                "store_code": row["store_code"],
                "product_name": row["product_name"],
                "product_sku": row["product_sku"],
                "current_stock": curr,
                "units_sold_per_day": vel,
                "projected_stock": proj,
                "recommended_replenishment": replenish,
                "status": st,
                "status_badge": badge
            })

    # Recent stock transfers
    cursor.execute("""
        SELECT 
            s.shipment_code AS transfer_code,
            s.created_at,
            p.name AS product_name,
            src.code AS source_code,
            dst.code AS dest_code,
            s.quantity,
            s.status
        FROM shipments s
        JOIN products p ON s.product_id = p.id AND p.user_id = s.user_id
        JOIN locations src ON s.source_location_id = src.id AND src.user_id = s.user_id
        JOIN locations dst ON s.dest_location_id = dst.id AND dst.user_id = s.user_id
        WHERE s.user_id = ?
        ORDER BY s.created_at DESC
        LIMIT 6
    """, (user_id,))
    recent_transfers = [dict(r) for r in cursor.fetchall()]

    # Shipment metrics
    cursor.execute("SELECT COUNT(*) AS total FROM shipments WHERE user_id = ? AND status = 'In Transit'", (user_id,))
    shipments_in_transit = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM shipments WHERE user_id = ? AND status = 'Delivered'", (user_id,))
    delivered_shipments = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) AS total FROM shipments WHERE user_id = ? AND status = 'Delayed'", (user_id,))
    delayed_shipments = cursor.fetchone()["total"]

    cursor.execute("SELECT COALESCE(SUM(quantity), 0) AS dispatched FROM shipments WHERE user_id = ? AND status IN ('In Transit', 'Delivered', 'Delayed')", (user_id,))
    total_dispatched_units = cursor.fetchone()["dispatched"]

    cursor.execute("SELECT COALESCE(SUM(quantity), 0) AS delivered FROM shipments WHERE user_id = ? AND status = 'Delivered'", (user_id,))
    total_delivered_units = cursor.fetchone()["delivered"]

    # Low-stock count
    cursor.execute("""
        SELECT COUNT(*) AS low_count
        FROM inventory i
        JOIN products p ON i.product_id = p.id AND p.user_id = i.user_id
        WHERE i.user_id = ? AND i.current_stock <= p.min_stock_level
    """, (user_id,))
    low_stock_products = cursor.fetchone()["low_count"]

    # Chart 1: Inventory by Location (Top 7)
    cursor.execute("""
        SELECT l.name, l.code, l.type, COALESCE(SUM(i.current_stock), 0) AS total_stock
        FROM locations l
        LEFT JOIN inventory i ON l.id = i.location_id AND i.user_id = l.user_id
        WHERE l.user_id = ?
        GROUP BY l.id
        ORDER BY total_stock DESC
        LIMIT 7
    """, (user_id,))
    loc_stock_rows = cursor.fetchall()
    loc_chart = {
        "labels": [f"{r['code']}" for r in loc_stock_rows],
        "values": [r["total_stock"] for r in loc_stock_rows]
    }

    # Chart 2: Product-wise stock distribution
    cursor.execute("""
        SELECT p.name, p.sku, COALESCE(SUM(i.current_stock), 0) AS stock
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id AND i.user_id = p.user_id
        WHERE p.user_id = ?
        GROUP BY p.id
        ORDER BY stock DESC
        LIMIT 6
    """, (user_id,))
    prod_stock_rows = cursor.fetchall()
    prod_chart = {
        "labels": [r["sku"] for r in prod_stock_rows],
        "values": [r["stock"] for r in prod_stock_rows]
    }

    # Chart 3: Shipment Status breakdown
    shipment_status_chart = {
        "labels": ["Delivered", "In Transit", "Delayed", "Planned"],
        "values": [
            delivered_shipments,
            shipments_in_transit,
            delayed_shipments,
            0
        ]
    }

    # Location type valuation breakdown
    cursor.execute("""
        SELECT l.type, COALESCE(SUM(i.current_stock * p.price), 0.0) AS val
        FROM locations l
        LEFT JOIN inventory i ON l.id = i.location_id AND i.user_id = l.user_id
        LEFT JOIN products p ON i.product_id = p.id AND p.user_id = l.user_id
        WHERE l.user_id = ?
        GROUP BY l.type
    """, (user_id,))
    type_val_rows = cursor.fetchall()
    location_type_valuation = {r["type"]: r["val"] for r in type_val_rows}
    if "Retailer" in location_type_valuation and "Retail Store" not in location_type_valuation:
        location_type_valuation["Retail Store"] = location_type_valuation["Retailer"]
    if "Warehouse" not in location_type_valuation:
        location_type_valuation["Warehouse"] = 0.0
    if "Retail Store" not in location_type_valuation:
        location_type_valuation["Retail Store"] = 0.0

    # Delivery success rate %
    total_completed = delivered_shipments + delayed_shipments
    success_rate = round((delivered_shipments / total_completed * 100.0), 1) if total_completed > 0 else 100.0

    conn.close()

    return {
        "total_products": total_products,
        "total_inventory": total_inventory,
        "total_inventory_value": total_inventory_value,
        "total_warehouses": total_warehouses,
        "total_retail_stores": total_retail_stores,
        "active_distributors": active_distributors,
        "retailers_served": retailers_served,
        "shipments_in_transit": shipments_in_transit,
        "delivered_shipments": delivered_shipments,
        "delayed_shipments": delayed_shipments,
        "low_stock_products": low_stock_products,
        "total_dispatched_units": total_dispatched_units,
        "total_delivered_units": total_delivered_units,
        "success_rate": success_rate,
        "predicted_demand": predicted_demand,
        "status_counts": status_counts,
        "deficit_items": deficit_items,
        "recent_transfers": recent_transfers,
        "location_type_valuation": location_type_valuation,
        "charts": {
            "locations": loc_chart,
            "products": prod_chart,
            "shipments": shipment_status_chart
        }
    }


def get_replenishment_manifest(user_id):
    """Fetches all retail store inventory records that require restocking."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 
            i.*,
            p.name AS product_name, p.sku AS product_sku, p.category AS product_category,
            p.price AS product_price, p.min_stock_level,
            l.name AS location_name, l.code AS location_code, l.city AS location_city,
            l.type AS location_type
        FROM inventory i
        JOIN products p ON i.product_id = p.id AND p.user_id = i.user_id
        JOIN locations l ON i.location_id = l.id AND l.user_id = i.user_id
        WHERE i.user_id = ? AND l.type = 'Retailer'
        ORDER BY l.name ASC, p.name ASC
    """, (user_id,))
    rows = cursor.fetchall()
    conn.close()

    manifest = []
    for r in rows:
        d = dict(r)
        pred = calculate_prediction(d["current_stock"], d["units_sold_per_day"], 7, d["min_stock_level"])
        d.update(pred)
        if d["recommended_replenishment"] > 0 or d["status"] in ("Critical", "Low Stock"):
            manifest.append(d)
    return manifest


get_dashboard_metrics = get_fmcg_dashboard_metrics


def get_chart_data(user_id):
    """Provides Chart.js payload for category valuations, stock health, and location breakdown."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT p.category, COALESCE(SUM(i.current_stock * p.price), 0.0) AS valuation
        FROM products p
        LEFT JOIN inventory i ON p.id = i.product_id AND i.user_id = p.user_id
        WHERE p.user_id = ?
        GROUP BY p.category
        ORDER BY valuation DESC
    """, (user_id,))
    cat_rows = cursor.fetchall()
    categories_data = {
        "labels": [r["category"] for r in cat_rows] if cat_rows else ["General FMCG"],
        "values": [round(r["valuation"], 2) for r in cat_rows] if cat_rows else [0]
    }

    metrics = get_fmcg_dashboard_metrics(user_id)
    status_data = {
        "labels": ["Healthy", "Low Stock", "Critical"],
        "counts": [
            metrics["status_counts"]["Healthy"],
            metrics["status_counts"]["Low Stock"],
            metrics["status_counts"]["Critical"]
        ]
    }

    cursor.execute("""
        SELECT l.code, COALESCE(SUM(i.current_stock), 0) AS total_stock
        FROM locations l
        LEFT JOIN inventory i ON l.id = i.location_id AND i.user_id = l.user_id
        WHERE l.user_id = ?
        GROUP BY l.id
        ORDER BY total_stock DESC
        LIMIT 7
    """, (user_id,))
    loc_rows = cursor.fetchall()
    locations_data = {
        "labels": [r["code"] for r in loc_rows],
        "values": [r["total_stock"] for r in loc_rows]
    }

    conn.close()
    return {
        "categories": categories_data,
        "status": status_data,
        "locations": locations_data
    }


def get_smart_alerts(user_id):
    """Generates and returns prioritized real-time inventory and delivery alerts."""
    conn = get_db()
    cursor = conn.cursor()

    # Sync delayed shipments automatically if current time > expected_delivery_date
    now_str = datetime.now().isoformat()
    cursor.execute("""
        UPDATE shipments 
        SET status = 'Delayed', updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ? AND status = 'In Transit' AND expected_delivery_date < ?
    """, (user_id, now_str))
    conn.commit()

    # Low stock alerts from inventory
    cursor.execute("""
        SELECT 
            i.current_stock, p.name AS product_name, p.sku, p.min_stock_level,
            l.name AS location_name, l.code AS location_code, l.lat, l.lng, l.type AS location_type
        FROM inventory i
        JOIN products p ON i.product_id = p.id AND p.user_id = i.user_id
        JOIN locations l ON i.location_id = l.id AND l.user_id = i.user_id
        WHERE i.user_id = ? AND i.current_stock <= p.min_stock_level
        ORDER BY (i.current_stock - p.min_stock_level) ASC
        LIMIT 6
    """, (user_id,))
    low_stocks = cursor.fetchall()

    alerts = []
    for r in low_stocks:
        sev = "CRITICAL" if r["current_stock"] == 0 else "WARNING"
        alerts.append({
            "type": "LOW_STOCK",
            "severity": sev,
            "title": f"Stock Alert: {r['location_name']}",
            "message": f"{r['product_name']} ({r['sku']}) is at {r['current_stock']} units (Safety floor: {r['min_stock_level']}).",
            "lat": r["lat"],
            "lng": r["lng"],
            "location_code": r["location_code"]
        })

    # Delayed shipment alerts
    cursor.execute("""
        SELECT 
            s.shipment_code, s.quantity, p.name AS product_name,
            src.name AS source_name, dst.name AS dest_name, dst.lat, dst.lng, dst.code AS dest_code
        FROM shipments s
        JOIN products p ON s.product_id = p.id AND p.user_id = s.user_id
        JOIN locations src ON s.source_location_id = src.id AND src.user_id = s.user_id
        JOIN locations dst ON s.dest_location_id = dst.id AND dst.user_id = s.user_id
        WHERE s.user_id = ? AND s.status = 'Delayed'
        LIMIT 4
    """, (user_id,))
    delayed = cursor.fetchall()
    for d in delayed:
        alerts.append({
            "type": "DELAYED_SHIPMENT",
            "severity": "CRITICAL",
            "title": f"Transit Delay: {d['shipment_code']}",
            "message": f"{d['product_name']} ({d['quantity']} units) from {d['source_name']} to {d['dest_name']} is delayed.",
            "lat": d["lat"],
            "lng": d["lng"],
            "location_code": d["dest_code"]
        })

    conn.close()
    return alerts
