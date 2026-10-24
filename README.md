# 🚚 OptiStock AI — FMCG Distribution Intelligence & Inventory Optimization Engine

A modern, professional enterprise web application designed for comprehensive warehouse network management, retail store inventory tracking, ACID-compliant stock transfers, rule-based AI demand forecasting, and **interactive geographical FMCG distribution tracking with real-time Leaflet.js maps**.

Built with **Python Flask**, **SQLite**, **Leaflet.js + OpenStreetMap**, **HTML5/CSS3 (Pitch Dark SaaS Theme)**, **JavaScript**, and **Chart.js**.

---

## 🌟 System Architecture & Core Modules

### 1. 🗺️ FMCG Distribution Intelligence & Interactive Live Map (`/inventory`)
- **Large Interactive Map**: Built using **Leaflet.js** and **OpenStreetMap** with custom vector markers:
  - **Warehouses**: 🔵 Blue warehouse pins (distribution hubs).
  - **Distributors**: 🟣 Purple location markers (regional stockists).
  - **Retailers**: 🟠 Orange storefront markers (POS supermarkets, hypermarkets, and marts).
  - **Delivery Vehicles**: 🚚 Moving truck markers with live position simulation along corridor transit routes.
- **Dynamic Route Flow & Color Coding**:
  - 🟢 **Green Solid Route Lines**: Successfully delivered shipments.
  - 🔵 **Blue Animated Route Lines**: Shipments currently in transit with directional flowing pulse.
  - 🔴 **Red Solid Route Lines**: Delayed shipments or corridor exception alerts.
  - ⚪ **Dashed Route Lines**: Planned upcoming delivery movements.
- **Rich Location Popups & Slide-Out Telemetry Drawer**:
  - Clicking any location marker displays name, type, capacity & utilization progress bar, total stock, incoming stock, outgoing stock, stored products list, and recent delivery history.
  - Click any marker to slide out the **Telemetry Drawer** for deeper operational inspection.
- **Smart Real-Time Alerts**:
  - Inventory safety floor breaches, capacity overloads (>85%), delayed shipments, and stockout warnings.
  - **Click-to-Pan (`flyTo`)**: Clicking any alert smoothly flies the map camera to the target facility marker with an animated radar pulse!
- **Facility Pinning & Address Geocoding**:
  - Register new Warehouses, Distributors, or Retailers.
  - Automatic address geocoding via OpenStreetMap Nominatim with local city heuristics.
  - **Interactive Click-to-Pin**: Click directly anywhere on the map to set precise latitude and longitude.

### 2. ⚡ Stock Movement & Atomic Delivery Tracking
- **Dispatch Shipment**:
  - Atomically validates and deducts available stock at the source location.
  - Calculates Haversine highway distance and estimated transit duration.
  - Generates route geometry and places an active animated transit route on the map.
- **Confirm Delivery**:
  - Atomically credits the confirmed quantity to the destination facility inventory.
  - Sets shipment status to `Delivered`, stamps actual delivery timestamp, and changes the route line to green.
  - Enforces strict idempotency to prevent duplicate inventory crediting.
- **Cancel / Fail Shipment**:
  - Safely restores deducted stock back to the origin facility.
  - Logs the restoration in the `inventory_transactions` audit ledger and sets status to `Cancelled`.
- **Audit Ledger**:
  - Tracks `DISPATCH_DEDUCT`, `DELIVERY_CREDIT`, `TRANSFER_OUT`, `TRANSFER_IN`, and `CANCEL_RESTORE` with balance after transaction.

### 3. 📊 10 FMCG KPI Metric Cards
1. **Total Stock**: Aggregate units stored across the entire distribution network.
2. **Total Valuation**: Capital valuation of inventory across all locations in Indian Rupees (`₹`).
3. **Warehouses**: Active central distribution hubs.
4. **Distributors**: Active regional transit stockists.
5. **Retail Outlets**: Active POS hypermarkets and supermarkets served.
6. **In Transit**: Active road shipments currently moving on distribution corridors.
7. **Delivered**: Completed shipments delivered to destinations.
8. **Delayed Shipments**: Corridor exceptions requiring logistics intervention.
9. **Low Stock Alerts**: Facilities where current stock breaches safety floor thresholds.
10. **Delivery Success Rate**: Overall completion rate percentage.

### 4. 🎨 Modern Pitch Dark SaaS UI
- **Pitch Dark Canvas**: Deep canvas (`#080c14` / `#070a12`), crisp high-contrast typography, electric blue (`#3b82f6`), royal purple (`#8b5cf6`), and emerald green (`#10b981`) accents.
- **Ambient Lighting**: Ambient radial glows, smooth card elevations, glowing action buttons, and responsive sidebar navigation.
- **Zero Raw Emojis**: Clean SVG icons across navigation, indicators, badges, and action buttons.

### 5. 🔐 Authentication & Session Security
- Registration and Login with secure password hashing (`werkzeug.security.generate_password_hash`).
- Password visibility toggle (SVG open/closed eye) on all password fields.
- Session-protected routes using `@login_required` decorators.
- Parameterized SQLite queries preventing SQL injection vulnerabilities.
- **1-Click Demo Login** button pre-configured with sample inventory data (`demo@optistock.ai` / `password123`).

### 6. 🧠 OptiStock AI Demand Prediction & Warehouse Sourcing
- Manual-input prediction form:
  - Product SKU, Retail Store, Current Stock, Velocity (units/day), Min Stock Floor, Prediction Period (7, 15, or 30 days).
- **Prediction Formulas**:
  $$\text{Predicted Demand} = \text{Units Sold Per Day} \times \text{Prediction Period}$$
  $$\text{Projected Stock} = \text{Current Stock} - \text{Predicted Demand}$$
  $$\text{Recommended Replenishment} = \max(0, \text{Predicted Demand} + \text{Minimum Stock Level} - \text{Current Stock})$$
- **Stock Status**:
  - **Critical**: Projected Stock $< 0$ (imminent stockout).
  - **Low Stock**: $0 \le \text{Projected Stock} \le \text{Minimum Stock Level}$ (safety buffer breached).
  - **Healthy**: Projected Stock $> \text{Minimum Stock Level}$ (optimal runway).
- **Suggested Warehouse Sourcing**:
  - Searches all warehouses holding inventory of this SKU and recommends fulfillment from the nearest hub with sufficient stock.

### 7. 📦 Preserved Core Modules
- **Products Catalog** (`/products`): Add, edit, search, filter, and delete product SKUs.
- **Warehouses Management** (`/warehouses`): View warehouse details, capacity, and stored SKUs.
- **Retail Stores Management** (`/retail-stores`): View retail store details, daily sales velocity, and restocking requirements.
- **Inter-Facility Stock Transfers** (`/transfers`): Direct ACID-compliant stock transfers between facilities.
- **Operational Reports** (`/reports`): Network capital breakdown, automated replenishment manifest, and printable inventory ledger.

---

## 🗄️ Database Schema (`optistock.db`)

SQLite database with 8 relational tables:
1. `users` — Authentication credentials and profiles
2. `products` — Master product catalog with SKU, category, price, min stock level, shelf life, and weight
3. `locations` — Warehouses, Distributors, and Retailers with coordinates (`lat`, `lng`), city, state, and capacity
4. `inventory` — Location-based stock tracking with `(user_id, product_id, location_id)` unique constraint
5. `shipments` — Shipment lifecycle records with route geometry, distance, duration, vehicle coordinates, and idempotency key
6. `inventory_transactions` — ACID audit ledger of all deductions, credits, transfers, and restoration movements
7. `alerts` — Prioritized alerts for stockouts, capacity limits, and shipment delays
8. `predictions` — Log of demand forecasting executions and suggested warehouses

---

## 💻 Instructions to Run in VS Code

### Step 1: Open Folder in VS Code
Open VS Code, press `Ctrl + O` (or `Cmd + O` on macOS), and select the folder:
```bash
cd c:\Users\HP\Downloads\OptiStock-AI
```

### Step 2: Open Terminal in VS Code
Press ``Ctrl + ` `` (backtick) or select **Terminal > New Terminal**.

### Step 3: Activate Virtual Environment
```powershell
# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Windows Command Prompt:
.\venv\Scripts\activate.bat
```

### Step 4: Install Dependencies (if needed)
```bash
pip install -r requirements.txt
```

### Step 5: Start the Web Application
```bash
python app.py
```

### Step 6: Access the Application
Open your browser and navigate to:
```
http://127.0.0.1:5000
```

---

## 🔑 Demo Account Credentials

For instant access:
- **Email**: `demo@optistock.ai`
- **Password**: `password123`
- *Or click **"1-Click Demo Login"** on the sign-in screen.*

---

## 🧪 Running Automated Test Suites

### 1. Run FMCG Live Map & Distribution Test Suite (13 Tests)
```bash
python test_fmcg_map.py
```

### 2. Run Comprehensive System Test Suite (18 Tests)
```bash
python test_comprehensive.py
```
