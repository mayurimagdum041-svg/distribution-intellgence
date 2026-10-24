"""
OptiStock AI - FMCG Data Layer & Synthetic Realistic Dataset
Provides data structures, realistic network nodes (warehouses, stores),
product catalog, inventory batches with shelf life, distance matrices,
and synthetic 180-day store sales history for ML demand forecasting.
"""

import math
import random
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

# ---------------------------------------------------------
# 1. Product Catalog
# ---------------------------------------------------------
PRODUCTS = [
    # Perishable Dairy / Cold Chain (4 - 18 days shelf life)
    {
        "id": 1,
        "name": "Fresh Pasteurised Milk (1L)",
        "sku": "DAIRY-MLK-01",
        "category": "Perishable Dairy",
        "storage": "Cold Chain",
        "shelf_life_days": 6,
        "unit_cost": 32.0,
        "unit_price": 54.0,
        "weight_kg": 1.0,
        "min_batch_size": 20,
    },
    {
        "id": 2,
        "name": "Artisanal Greek Yogurt (400g)",
        "sku": "DAIRY-YGT-02",
        "category": "Perishable Dairy",
        "storage": "Cold Chain",
        "shelf_life_days": 14,
        "unit_cost": 45.0,
        "unit_price": 85.0,
        "weight_kg": 0.4,
        "min_batch_size": 15,
    },
    {
        "id": 3,
        "name": "Farm Fresh Malai Paneer (500g)",
        "sku": "DAIRY-PNR-03",
        "category": "Perishable Dairy",
        "storage": "Cold Chain",
        "shelf_life_days": 10,
        "unit_cost": 95.0,
        "unit_price": 160.0,
        "weight_kg": 0.5,
        "min_batch_size": 10,
    },
    {
        "id": 4,
        "name": "Cold-Pressed Orange Juice (1L)",
        "sku": "BEV-OJC-04",
        "category": "Perishable Dairy",
        "storage": "Cold Chain",
        "shelf_life_days": 21,
        "unit_cost": 65.0,
        "unit_price": 120.0,
        "weight_kg": 1.0,
        "min_batch_size": 12,
    },
    # Semi-Perishable Packaged Foods (30 - 120 days shelf life)
    {
        "id": 5,
        "name": "Whole Wheat Brown Bread (400g)",
        "sku": "BKRY-BRD-05",
        "category": "Bakery & Snacks",
        "storage": "Ambient Dry",
        "shelf_life_days": 7,
        "unit_cost": 22.0,
        "unit_price": 45.0,
        "weight_kg": 0.4,
        "min_batch_size": 25,
    },
    {
        "id": 6,
        "name": "Digestive Fibre Biscuits (300g)",
        "sku": "SNK-BSC-06",
        "category": "Bakery & Snacks",
        "storage": "Ambient Dry",
        "shelf_life_days": 120,
        "unit_cost": 28.0,
        "unit_price": 60.0,
        "weight_kg": 0.3,
        "min_batch_size": 20,
    },
    {
        "id": 7,
        "name": "Rich Tomato Ketchup (1kg)",
        "sku": "GROC-KCH-07",
        "category": "Bakery & Snacks",
        "storage": "Ambient Dry",
        "shelf_life_days": 180,
        "unit_cost": 68.0,
        "unit_price": 130.0,
        "weight_kg": 1.0,
        "min_batch_size": 10,
    },
    {
        "id": 8,
        "name": "Crunchy Peanut Butter (500g)",
        "sku": "GROC-PBT-08",
        "category": "Bakery & Snacks",
        "storage": "Ambient Dry",
        "shelf_life_days": 150,
        "unit_cost": 85.0,
        "unit_price": 175.0,
        "weight_kg": 0.5,
        "min_batch_size": 10,
    },
    # Ambient Groceries & Household Care (180 - 365 days shelf life)
    {
        "id": 9,
        "name": "Refined Sunflower Cooking Oil (5L)",
        "sku": "GROC-OIL-09",
        "category": "Ambient Groceries",
        "storage": "Ambient Dry",
        "shelf_life_days": 365,
        "unit_cost": 480.0,
        "unit_price": 690.0,
        "weight_kg": 4.6,
        "min_batch_size": 6,
    },
    {
        "id": 10,
        "name": "Royal Basmati Rice (5kg Bag)",
        "sku": "GROC-RCE-10",
        "category": "Ambient Groceries",
        "storage": "Ambient Dry",
        "shelf_life_days": 365,
        "unit_cost": 310.0,
        "unit_price": 499.0,
        "weight_kg": 5.0,
        "min_batch_size": 5,
    },
    {
        "id": 11,
        "name": "Citrus Surface Disinfectant (1L)",
        "sku": "HCARE-DSF-11",
        "category": "Ambient Groceries",
        "storage": "Ambient Dry",
        "shelf_life_days": 365,
        "unit_cost": 82.0,
        "unit_price": 165.0,
        "weight_kg": 1.0,
        "min_batch_size": 15,
    },
    {
        "id": 12,
        "name": "Advanced Laundry Detergent (2kg)",
        "sku": "HCARE-DTG-12",
        "category": "Ambient Groceries",
        "storage": "Ambient Dry",
        "shelf_life_days": 365,
        "unit_cost": 140.0,
        "unit_price": 280.0,
        "weight_kg": 2.0,
        "min_batch_size": 10,
    },
]

# ---------------------------------------------------------
# 2. Warehouses (Distribution Centers / Depots)
# ---------------------------------------------------------
WAREHOUSES = [
    {
        "id": "WH-MUM",
        "name": "Mumbai Central Mega-DC",
        "city": "Mumbai",
        "state": "Maharashtra",
        "type": "Primary CDC",
        "has_cold_chain": True,
        "capacity_pallets": 15000,
        "lat": 19.0760,
        "lng": 72.8777,
        "operating_cost_per_day": 24000,
    },
    {
        "id": "WH-PUN",
        "name": "Pune Regional Distribution Hub",
        "city": "Pune",
        "state": "Maharashtra",
        "type": "Regional RDC",
        "has_cold_chain": True,
        "capacity_pallets": 11000,
        "lat": 18.5204,
        "lng": 73.8567,
        "operating_cost_per_day": 18000,
    },
    {
        "id": "WH-AHM",
        "name": "Ahmedabad Logistics Hub",
        "city": "Ahmedabad",
        "state": "Gujarat",
        "type": "Regional RDC",
        "has_cold_chain": True,
        "capacity_pallets": 12500,
        "lat": 23.0225,
        "lng": 72.5714,
        "operating_cost_per_day": 16500,
    },
    {
        "id": "WH-SUR",
        "name": "Surat Coastal Depot",
        "city": "Surat",
        "state": "Gujarat",
        "type": "Secondary Transit Depot",
        "has_cold_chain": True,
        "capacity_pallets": 8000,
        "lat": 21.1702,
        "lng": 72.8311,
        "operating_cost_per_day": 12000,
    },
]

# ---------------------------------------------------------
# 3. Retail Stores & Regional Distributors
# ---------------------------------------------------------
STORES = [
    {
        "id": "ST-MUM-S",
        "name": "Mumbai South Hypermarket",
        "city": "Mumbai",
        "tier": "Tier-1",
        "type": "Hypermarket",
        "priority": "High",
        "lat": 18.9388,
        "lng": 72.8354,
        "demand_multiplier": 1.45,
    },
    {
        "id": "ST-MUM-N",
        "name": "Mumbai North Supercenter",
        "city": "Mumbai",
        "tier": "Tier-1",
        "type": "Supercenter",
        "priority": "High",
        "lat": 19.1860,
        "lng": 72.8485,
        "demand_multiplier": 1.30,
    },
    {
        "id": "ST-PUN-M",
        "name": "Pune Market Square Retail",
        "city": "Pune",
        "tier": "Tier-1",
        "type": "Supermarket",
        "priority": "High",
        "lat": 18.5314,
        "lng": 73.8446,
        "demand_multiplier": 1.25,
    },
    {
        "id": "ST-PUN-W",
        "name": "Pune West Mart",
        "city": "Pune",
        "tier": "Tier-1",
        "type": "Supermarket",
        "priority": "Medium",
        "lat": 18.5074,
        "lng": 73.8077,
        "demand_multiplier": 0.95,
    },
    {
        "id": "ST-THN",
        "name": "Thane Regional Stockist",
        "city": "Thane",
        "tier": "Tier-1",
        "type": "Distributor",
        "priority": "High",
        "lat": 19.2183,
        "lng": 72.9781,
        "demand_multiplier": 1.40,
    },
    {
        "id": "ST-NSH",
        "name": "Nashik Fresh Direct",
        "city": "Nashik",
        "tier": "Tier-2",
        "type": "Retail Store",
        "priority": "Medium",
        "lat": 19.9975,
        "lng": 73.7898,
        "demand_multiplier": 0.85,
    },
    {
        "id": "ST-KOL",
        "name": "Kolhapur Agro Mart",
        "city": "Kolhapur",
        "tier": "Tier-2",
        "type": "Retail Store",
        "priority": "Medium",
        "lat": 16.7050,
        "lng": 74.2433,
        "demand_multiplier": 0.80,
    },
    {
        "id": "ST-AHM-P",
        "name": "Ahmedabad Prime Superstore",
        "city": "Ahmedabad",
        "tier": "Tier-1",
        "type": "Hypermarket",
        "priority": "High",
        "lat": 23.0338,
        "lng": 72.5850,
        "demand_multiplier": 1.35,
    },
    {
        "id": "ST-SUR-R",
        "name": "Surat City Mart",
        "city": "Surat",
        "tier": "Tier-2",
        "type": "Supermarket",
        "priority": "Medium",
        "lat": 21.1959,
        "lng": 72.8193,
        "demand_multiplier": 0.90,
    },
    {
        "id": "ST-VAD",
        "name": "Vadodara Express Outlet",
        "city": "Vadodara",
        "tier": "Tier-2",
        "type": "Retail Store",
        "priority": "Low",
        "lat": 22.3072,
        "lng": 73.1812,
        "demand_multiplier": 0.70,
    },
]

# ---------------------------------------------------------
# 4. Road Distance Matrix (km) between Warehouses and Stores
# ---------------------------------------------------------
DISTANCE_KM = {
    # Mumbai Central DC
    ("WH-MUM", "ST-MUM-S"): 22,
    ("WH-MUM", "ST-MUM-N"): 18,
    ("WH-MUM", "ST-THN"): 32,
    ("WH-MUM", "ST-PUN-M"): 150,
    ("WH-MUM", "ST-PUN-W"): 145,
    ("WH-MUM", "ST-NSH"): 168,
    ("WH-MUM", "ST-KOL"): 375,
    ("WH-MUM", "ST-SUR-R"): 285,
    ("WH-MUM", "ST-AHM-P"): 525,
    ("WH-MUM", "ST-VAD"): 415,
    # Pune Regional Hub
    ("WH-PUN", "ST-MUM-S"): 155,
    ("WH-PUN", "ST-MUM-N"): 162,
    ("WH-PUN", "ST-THN"): 148,
    ("WH-PUN", "ST-PUN-M"): 12,
    ("WH-PUN", "ST-PUN-W"): 14,
    ("WH-PUN", "ST-NSH"): 210,
    ("WH-PUN", "ST-KOL"): 235,
    ("WH-PUN", "ST-SUR-R"): 410,
    ("WH-PUN", "ST-AHM-P"): 660,
    ("WH-PUN", "ST-VAD"): 540,
    # Ahmedabad Logistics Hub
    ("WH-AHM", "ST-MUM-S"): 530,
    ("WH-AHM", "ST-MUM-N"): 515,
    ("WH-AHM", "ST-THN"): 500,
    ("WH-AHM", "ST-PUN-M"): 660,
    ("WH-AHM", "ST-PUN-W"): 655,
    ("WH-AHM", "ST-NSH"): 475,
    ("WH-AHM", "ST-KOL"): 880,
    ("WH-AHM", "ST-SUR-R"): 265,
    ("WH-AHM", "ST-AHM-P"): 15,
    ("WH-AHM", "ST-VAD"): 110,
    # Surat Coastal Depot
    ("WH-SUR", "ST-MUM-S"): 290,
    ("WH-SUR", "ST-MUM-N"): 275,
    ("WH-SUR", "ST-THN"): 260,
    ("WH-SUR", "ST-PUN-M"): 415,
    ("WH-SUR", "ST-PUN-W"): 410,
    ("WH-SUR", "ST-NSH"): 240,
    ("WH-SUR", "ST-KOL"): 630,
    ("WH-SUR", "ST-SUR-R"): 12,
    ("WH-SUR", "ST-AHM-P"): 265,
    ("WH-SUR", "ST-VAD"): 155,
}

# ---------------------------------------------------------
# 5. Realistic Batch-Level Inventory
# ---------------------------------------------------------
# Each batch has specific days to expiry, current quantity, production date
INITIAL_BATCHES = [
    # Milk (Shelf life 6d)
    {"batch_id": "BAT-MLK-01", "product_id": 1, "warehouse_id": "WH-PUN", "quantity": 420, "expiry_days": 3, "mfg_date": "2026-10-21"},
    {"batch_id": "BAT-MLK-02", "product_id": 1, "warehouse_id": "WH-PUN", "quantity": 580, "expiry_days": 5, "mfg_date": "2026-10-23"},
    {"batch_id": "BAT-MLK-03", "product_id": 1, "warehouse_id": "WH-MUM", "quantity": 380, "expiry_days": 2, "mfg_date": "2026-10-20"}, # Urgent!
    {"batch_id": "BAT-MLK-04", "product_id": 1, "warehouse_id": "WH-MUM", "quantity": 650, "expiry_days": 5, "mfg_date": "2026-10-23"},
    {"batch_id": "BAT-MLK-05", "product_id": 1, "warehouse_id": "WH-SUR", "quantity": 260, "expiry_days": 4, "mfg_date": "2026-10-22"},
    {"batch_id": "BAT-MLK-06", "product_id": 1, "warehouse_id": "WH-AHM", "quantity": 490, "expiry_days": 4, "mfg_date": "2026-10-22"},

    # Greek Yogurt (Shelf life 14d)
    {"batch_id": "BAT-YGT-01", "product_id": 2, "warehouse_id": "WH-PUN", "quantity": 290, "expiry_days": 6, "mfg_date": "2026-10-16"},
    {"batch_id": "BAT-YGT-02", "product_id": 2, "warehouse_id": "WH-MUM", "quantity": 450, "expiry_days": 11, "mfg_date": "2026-10-21"},
    {"batch_id": "BAT-YGT-03", "product_id": 2, "warehouse_id": "WH-AHM", "quantity": 310, "expiry_days": 4, "mfg_date": "2026-10-14"}, # Watch
    {"batch_id": "BAT-YGT-04", "product_id": 2, "warehouse_id": "WH-SUR", "quantity": 180, "expiry_days": 9, "mfg_date": "2026-10-19"},

    # Malai Paneer (Shelf life 10d)
    {"batch_id": "BAT-PNR-01", "product_id": 3, "warehouse_id": "WH-PUN", "quantity": 240, "expiry_days": 3, "mfg_date": "2026-10-17"}, # Urgent!
    {"batch_id": "BAT-PNR-02", "product_id": 3, "warehouse_id": "WH-MUM", "quantity": 320, "expiry_days": 8, "mfg_date": "2026-10-22"},
    {"batch_id": "BAT-PNR-03", "product_id": 3, "warehouse_id": "WH-AHM", "quantity": 210, "expiry_days": 7, "mfg_date": "2026-10-21"},

    # Orange Juice (Shelf life 21d)
    {"batch_id": "BAT-OJC-01", "product_id": 4, "warehouse_id": "WH-PUN", "quantity": 350, "expiry_days": 16, "mfg_date": "2026-10-19"},
    {"batch_id": "BAT-OJC-02", "product_id": 4, "warehouse_id": "WH-MUM", "quantity": 480, "expiry_days": 18, "mfg_date": "2026-10-21"},
    {"batch_id": "BAT-OJC-03", "product_id": 4, "warehouse_id": "WH-AHM", "quantity": 280, "expiry_days": 8, "mfg_date": "2026-10-11"},
    {"batch_id": "BAT-OJC-04", "product_id": 4, "warehouse_id": "WH-SUR", "quantity": 220, "expiry_days": 14, "mfg_date": "2026-10-17"},

    # Brown Bread (Shelf life 7d)
    {"batch_id": "BAT-BRD-01", "product_id": 5, "warehouse_id": "WH-PUN", "quantity": 380, "expiry_days": 3, "mfg_date": "2026-10-20"},
    {"batch_id": "BAT-BRD-02", "product_id": 5, "warehouse_id": "WH-MUM", "quantity": 510, "expiry_days": 5, "mfg_date": "2026-10-22"},
    {"batch_id": "BAT-BRD-03", "product_id": 5, "warehouse_id": "WH-AHM", "quantity": 340, "expiry_days": 4, "mfg_date": "2026-10-21"},
    {"batch_id": "BAT-BRD-04", "product_id": 5, "warehouse_id": "WH-SUR", "quantity": 220, "expiry_days": 3, "mfg_date": "2026-10-20"},

    # Biscuits (Shelf life 120d)
    {"batch_id": "BAT-BSC-01", "product_id": 6, "warehouse_id": "WH-PUN", "quantity": 750, "expiry_days": 90, "mfg_date": "2026-09-24"},
    {"batch_id": "BAT-BSC-02", "product_id": 6, "warehouse_id": "WH-MUM", "quantity": 950, "expiry_days": 110, "mfg_date": "2026-10-14"},
    {"batch_id": "BAT-BSC-03", "product_id": 6, "warehouse_id": "WH-AHM", "quantity": 620, "expiry_days": 85, "mfg_date": "2026-09-19"},
    {"batch_id": "BAT-BSC-04", "product_id": 6, "warehouse_id": "WH-SUR", "quantity": 480, "expiry_days": 100, "mfg_date": "2026-10-04"},

    # Tomato Ketchup (Shelf life 180d)
    {"batch_id": "BAT-KCH-01", "product_id": 7, "warehouse_id": "WH-PUN", "quantity": 420, "expiry_days": 140, "mfg_date": "2026-09-14"},
    {"batch_id": "BAT-KCH-02", "product_id": 7, "warehouse_id": "WH-MUM", "quantity": 580, "expiry_days": 160, "mfg_date": "2026-10-04"},
    {"batch_id": "BAT-KCH-03", "product_id": 7, "warehouse_id": "WH-AHM", "quantity": 390, "expiry_days": 130, "mfg_date": "2026-09-04"},

    # Peanut Butter (Shelf life 150d)
    {"batch_id": "BAT-PBT-01", "product_id": 8, "warehouse_id": "WH-PUN", "quantity": 310, "expiry_days": 125, "mfg_date": "2026-09-29"},
    {"batch_id": "BAT-PBT-02", "product_id": 8, "warehouse_id": "WH-MUM", "quantity": 440, "expiry_days": 135, "mfg_date": "2026-10-09"},
    {"batch_id": "BAT-PBT-03", "product_id": 8, "warehouse_id": "WH-AHM", "quantity": 260, "expiry_days": 115, "mfg_date": "2026-09-19"},

    # Sunflower Oil (Shelf life 365d)
    {"batch_id": "BAT-OIL-01", "product_id": 9, "warehouse_id": "WH-PUN", "quantity": 520, "expiry_days": 290, "mfg_date": "2026-08-09"},
    {"batch_id": "BAT-OIL-02", "product_id": 9, "warehouse_id": "WH-MUM", "quantity": 780, "expiry_days": 320, "mfg_date": "2026-09-08"},
    {"batch_id": "BAT-OIL-03", "product_id": 9, "warehouse_id": "WH-AHM", "quantity": 640, "expiry_days": 305, "mfg_date": "2026-08-24"},
    {"batch_id": "BAT-OIL-04", "product_id": 9, "warehouse_id": "WH-SUR", "quantity": 410, "expiry_days": 280, "mfg_date": "2026-07-30"},

    # Basmati Rice 5kg (Shelf life 365d)
    {"batch_id": "BAT-RCE-01", "product_id": 10, "warehouse_id": "WH-PUN", "quantity": 460, "expiry_days": 310, "mfg_date": "2026-08-29"},
    {"batch_id": "BAT-RCE-02", "product_id": 10, "warehouse_id": "WH-MUM", "quantity": 680, "expiry_days": 340, "mfg_date": "2026-09-28"},
    {"batch_id": "BAT-RCE-03", "product_id": 10, "warehouse_id": "WH-AHM", "quantity": 520, "expiry_days": 300, "mfg_date": "2026-08-19"},

    # Surface Disinfectant (Shelf life 365d)
    {"batch_id": "BAT-DSF-01", "product_id": 11, "warehouse_id": "WH-PUN", "quantity": 380, "expiry_days": 330, "mfg_date": "2026-09-18"},
    {"batch_id": "BAT-DSF-02", "product_id": 11, "warehouse_id": "WH-MUM", "quantity": 540, "expiry_days": 350, "mfg_date": "2026-10-08"},
    {"batch_id": "BAT-DSF-03", "product_id": 11, "warehouse_id": "WH-SUR", "quantity": 290, "expiry_days": 315, "mfg_date": "2026-09-03"},

    # Laundry Detergent (Shelf life 365d)
    {"batch_id": "BAT-DTG-01", "product_id": 12, "warehouse_id": "WH-PUN", "quantity": 410, "expiry_days": 340, "mfg_date": "2026-09-28"},
    {"batch_id": "BAT-DTG-02", "product_id": 12, "warehouse_id": "WH-MUM", "quantity": 620, "expiry_days": 360, "mfg_date": "2026-10-18"},
    {"batch_id": "BAT-DTG-03", "product_id": 12, "warehouse_id": "WH-AHM", "quantity": 440, "expiry_days": 325, "mfg_date": "2026-09-13"},
]

# Base daily sales rates per product (average per store)
BASE_DAILY_SALES = {
    1: 42,  # Fresh Milk (High velocity staple)
    2: 18,  # Greek Yogurt
    3: 16,  # Malai Paneer
    4: 15,  # Orange Juice
    5: 35,  # Brown Bread (Daily staple)
    6: 28,  # Biscuits
    7: 12,  # Ketchup
    8: 10,  # Peanut Butter
    9: 14,  # Sunflower Oil
    10: 16, # Basmati Rice
    11: 15, # Disinfectant
    12: 18, # Laundry Detergent
}


def calculate_transport_cost_per_unit(warehouse_id: str, store_id: str, product_id: int, fuel_multiplier: float = 1.0) -> float:
    """
    Computes realistic freight cost per unit based on road distance,
    cold-chain vs ambient transport, vehicle fixed handling fee, and fuel index.
    """
    distance = DISTANCE_KM.get((warehouse_id, store_id), 300)
    product = next(p for p in PRODUCTS if p["id"] == product_id)
    is_cold_chain = (product["storage"] == "Cold Chain")

    # Rate per km per kg: cold-chain requires refrigerated reefer fleet
    rate_per_km_kg = 0.024 if is_cold_chain else 0.014
    weight = product["weight_kg"]
    variable_cost = distance * rate_per_km_kg * weight * fuel_multiplier

    # Fixed loading/handling and toll factor per unit
    fixed_handling = 0.85 if is_cold_chain else 0.45

    return round(variable_cost + fixed_handling, 2)


def get_transit_time_days(warehouse_id: str, store_id: str) -> float:
    """Estimates transit lead time based on road distance and logistics check-ins."""
    distance = DISTANCE_KM.get((warehouse_id, store_id), 300)
    if distance <= 60:
        return 0.5  # Intra-city / local transit (same day)
    elif distance <= 250:
        return 1.0  # Regional transit (1 day)
    else:
        return 1.5  # Long haul transit (1.5 days)


def generate_sales_history(days: int = 180) -> pd.DataFrame:
    """
    Generates 180 days of realistic daily historical sales data across all stores and products.
    Includes:
      - Weekly seasonality (Friday-Sunday lifts)
      - Bi-weekly promotional events on select SKUs
      - Store-level geographic multipliers
      - Random demand noise (Poisson/Gaussian)
    """
    rng = np.random.default_rng(seed=42)
    end_date = datetime(2026, 10, 24)
    start_date = end_date - timedelta(days=days - 1)
    dates = [start_date + timedelta(days=i) for i in range(days)]

    records = []
    for d in dates:
        day_of_week = d.weekday()  # 0=Mon, 6=Sun
        is_weekend = day_of_week in [4, 5, 6]  # Fri, Sat, Sun

        # Day-of-week demand multipliers
        dow_mult = 1.0
        if day_of_week == 0:  # Monday
            dow_mult = 0.92
        elif day_of_week in [1, 2]:  # Tue, Wed
            dow_mult = 0.88
        elif day_of_week == 3:  # Thu
            dow_mult = 0.98
        elif day_of_week == 4:  # Fri
            dow_mult = 1.15
        elif day_of_week == 5:  # Sat
            dow_mult = 1.30
        elif day_of_week == 6:  # Sun
            dow_mult = 1.22

        # Promotion calendar: promotional boost every 14 days for certain products
        day_index = (d - start_date).days
        promo_active_1 = (day_index % 14 in [11, 12, 13])  # Weekend promos on dairy
        promo_active_2 = (day_index % 21 in [18, 19, 20])  # Monthly promo on ambient

        for store in STORES:
            store_mult = store["demand_multiplier"]
            for prod in PRODUCTS:
                base = BASE_DAILY_SALES[prod["id"]]
                promo = False
                promo_boost = 1.0

                if prod["category"] == "Perishable Dairy" and promo_active_1:
                    promo = True
                    promo_boost = 1.35
                elif prod["category"] == "Ambient Groceries" and promo_active_2:
                    promo = True
                    promo_boost = 1.25

                mean_demand = base * store_mult * dow_mult * promo_boost
                # Draw demand with realistic Poisson / rounded Gaussian distribution
                daily_sales = int(max(0, rng.normal(loc=mean_demand, scale=math.sqrt(mean_demand) * 0.9)))

                records.append({
                    "date": d.strftime("%Y-%m-%d"),
                    "store_id": store["id"],
                    "store_name": store["name"],
                    "product_id": prod["id"],
                    "product_name": prod["name"],
                    "sku": prod["sku"],
                    "category": prod["category"],
                    "day_of_week": day_of_week,
                    "is_weekend": int(is_weekend),
                    "on_promotion": int(promo),
                    "sales_units": daily_sales,
                })

    return pd.DataFrame(records)


# Pre-computed cached sales history singleton
_CACHED_SALES_DF = None

def get_sales_history_df() -> pd.DataFrame:
    global _CACHED_SALES_DF
    if _CACHED_SALES_DF is None:
        _CACHED_SALES_DF = generate_sales_history(180)
    return _CACHED_SALES_DF


def get_warehouse_stock(warehouse_id: str, product_id: int) -> int:
    """Returns total on-hand batch quantity for a product in a warehouse."""
    return sum(
        b["quantity"]
        for b in INITIAL_BATCHES
        if b["warehouse_id"] == warehouse_id and b["product_id"] == product_id
    )


def debit_warehouse_batch(
    warehouse_id: str,
    product_id: int,
    quantity: int,
    batch_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Debits stock from warehouse batches using FEFO (First-Expired, First-Out) priority
    or a specific targeted batch.
    """
    remaining_to_debit = int(quantity)
    debited_batches = []

    # Filter eligible batches
    eligible = [
        b for b in INITIAL_BATCHES
        if b["warehouse_id"] == warehouse_id and b["product_id"] == product_id and b["quantity"] > 0
    ]

    if batch_id:
        target = [b for b in eligible if b["batch_id"] == batch_id]
        if target:
            eligible = target + [b for b in eligible if b["batch_id"] != batch_id]

    # Sort FEFO (lowest expiry_days first)
    eligible.sort(key=lambda x: x["expiry_days"])

    for b in eligible:
        if remaining_to_debit <= 0:
            break
        deduct = min(b["quantity"], remaining_to_debit)
        b["quantity"] -= deduct
        remaining_to_debit -= deduct
        debited_batches.append({
            "batch_id": b["batch_id"],
            "debited": deduct,
            "remaining": b["quantity"],
        })

    return {
        "warehouse_id": warehouse_id,
        "product_id": product_id,
        "total_debited": int(quantity) - remaining_to_debit,
        "unfulfilled": max(0, remaining_to_debit),
        "debited_batches": debited_batches,
    }


def credit_warehouse_batch(
    warehouse_id: str,
    product_id: int,
    quantity: int,
    expiry_days: Optional[int] = None,
    batch_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Credits received stock into warehouse inventory batches.
    If batch_id is specified or an existing batch matches, increases batch quantity.
    Otherwise creates a new batch entry in INITIAL_BATCHES.
    """
    qty = int(quantity)
    product = next((p for p in PRODUCTS if p["id"] == product_id), None)
    shelf_life = product["shelf_life_days"] if product else 30
    exp_days = expiry_days if expiry_days is not None else shelf_life

    matched_batch = None
    if batch_id:
        matched_batch = next((b for b in INITIAL_BATCHES if b.get("batch_id") == batch_id), None)

    if not matched_batch:
        # Check if there is an existing batch for this warehouse and product
        candidates = [
            b for b in INITIAL_BATCHES 
            if b["warehouse_id"] == warehouse_id and b["product_id"] == product_id
        ]
        if candidates:
            # Sort by highest expiry_days (newest batch)
            candidates.sort(key=lambda x: x["expiry_days"], reverse=True)
            matched_batch = candidates[0]

    if matched_batch:
        matched_batch["quantity"] += qty
        used_batch_id = matched_batch["batch_id"]
        current_batch_qty = matched_batch["quantity"]
    else:
        # Create a new batch entry
        today_str = datetime.now().strftime("%Y-%m-%d")
        sku_parts = product["sku"].split("-") if product and "-" in product["sku"] else ["", "GEN"]
        sku_code = sku_parts[1] if len(sku_parts) > 1 else "GEN"
        new_id = batch_id or f"BAT-{sku_code}-{len(INITIAL_BATCHES) + 1:02d}"
        new_batch = {
            "batch_id": new_id,
            "product_id": product_id,
            "warehouse_id": warehouse_id,
            "quantity": qty,
            "expiry_days": exp_days,
            "mfg_date": today_str
        }
        INITIAL_BATCHES.append(new_batch)
        used_batch_id = new_id
        current_batch_qty = qty

    return {
        "warehouse_id": warehouse_id,
        "product_id": product_id,
        "total_credited": qty,
        "batch_id": used_batch_id,
        "new_quantity": current_batch_qty,
        "total_warehouse_stock": get_warehouse_stock(warehouse_id, product_id)
    }


