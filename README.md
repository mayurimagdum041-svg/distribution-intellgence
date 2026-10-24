# 📦 OptiStock AI
**Distribution Intelligence & Inventory Optimization Engine**

An AI-powered FMCG supply chain dashboard built with Flask, SciPy MILP, and ML demand forecasting.

## 🚀 Features
- **MILP Optimization** — SciPy HiGHS solver minimizes freight cost while preventing stockouts
- **FEFO Prioritization** — First-Expired-First-Out batch routing to reduce spoilage
- **ML Demand Forecasting** — Ridge Regression with confidence intervals
- **Interactive Dashboard** — Clean light-theme UI with Chart.js visualizations
- **Live Shipment Map** — Leaflet.js map showing warehouse → store routes across Maharashtra
- **What-If Simulator** — Demand shocks, fuel cost changes, warehouse shutdowns
- **Delivery Locations** — Pune, Satara, Kolhapur, Sangli, Karad and more
- **Autonomous Supply Chain Workflows** — Real-time automated replenishment, expiry rescue, distribution ranking, and SLA delivery tracking
- **Manager Approval Lifecycle** — Audit-logged approval gate for procurement and inter-store transfers with idempotency deduplication
- **Automated Alert Center** — Severity-prioritized notifications for stockouts, expiration risks, and delayed deliveries

---

## 🤖 Real-Time Automation System

OptiStock AI includes a production-grade background automation engine with multi-worker concurrency protection:

### 1. Auto-Replenishment Workflow
- Continuously audits retail store inventory against dynamic Reorder Points (ROP) using lead times, daily demand, and safety stock.
- Generates replenishment proposals with suggested order quantities and estimated costs.
- Enforces an idempotency hash to prevent duplicate pending orders.
- **Safety Guarantee**: Purchases, payments, or dispatches are never made automatically; manager authorization is required.

### 2. FEFO Expiry Rescue Workflow
- Scans warehouse inventory batches for short remaining shelf-life (< 15 days).
- Identifies optimal destination stores capable of absorbing the stock before expiration.
- Validates feasibility constraints: ensures shelf-life strictly exceeds transit time plus a 1.0-day buffer (`expiry > transit + 1.0`).
- Prevents transfers exceeding batch availability or destination capacity.

### 3. Distribution Optimization Workflow
- Evaluates candidate distribution centers for deficit stores using road distance matrices, freight tariff curves, and warehouse availability.
- Generates ranked sourcing options (Rank 1 Optimal, Rank 2 Alternate) with explainable rationales.
- Clearly flags simulated model estimates with `SIMULATED_SAMPLE` badges.

### 4. Delivery Monitoring Workflow
- Tracks dispatch manifest timestamps against SLA delivery deadlines.
- Automatically flags delayed shipments exceeding their expected delivery window.
- Checkpoint manifest auditing without false live GPS claims.

### 5. Automated Alert Center
- Database-backed alert management with deduplication.
- Prioritizes events across `CRITICAL`, `WARNING`, and `INFO` tiers.
- Provides recommended remediation steps with one-click **Acknowledge** and **Resolve** audit logging.

### 6. Automation Control Panel
- Web-based cockpit to monitor workflow states (`Enabled`, `Disabled`, `Error`), cadence, execution times, and action counters.
- Supports instant manual execution via **Run Now**.
- Features an isolated **Dry-Run Mode** for risk-free policy simulation without database writes.

---

## 🔐 Dedicated User Portals & Login Pages

OptiStock AI features dedicated, branded authentication pages for each user role with 4-digit PIN verification and direct workspace routing:

| User Role | Dedicated Login URL | Demo PIN | Workspace Access & Permissions |
|:---|:---|:---:|:---|
| **👑 Administrator** | [`/login/admin`](http://127.0.0.1:5000/login/admin) | `1111` | Executive command tower, SciPy HiGHS MILP optimizer, What-If simulator, automation engine & all reports |
| **🏭 Warehouse Manager** | [`/login/warehouse`](http://127.0.0.1:5000/login/warehouse) | `2222` | Batch shelf-life tracking (FEFO radar), cold-chain pallet storage, expiry rescue transfers, and outbound manifests |
| **🏪 Retail Store Manager** | [`/login/retail`](http://127.0.0.1:5000/login/retail) | `3333` | Store health, Days of Cover, Reorder Points (ROP), auto-replenishment requests, and ML demand forecasts |
| **🚚 Delivery Fleet Partner** | [`/login/delivery`](http://127.0.0.1:5000/login/delivery) | `4444` | Live dispatch route map, Pune-Kolhapur corridor stops, and road checkpoint SLA delivery tracker |
| **🌐 Portal Hub Gateway** | [`/login`](http://127.0.0.1:5000/login) | — | Main gateway displaying all 4 user portals with direct one-click selection |

---

## 🏃 Quick Start

```bash
# Clone the repo
git clone https://github.com/mayurimagdum041-svg/distribution-intellgence.git
cd OptiStock-AI

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install flask numpy pandas scikit-learn scipy

# Run automated tests
python -m unittest discover tests

# Run the app
python app.py
```

Then open: **http://127.0.0.1:5000/simple**

---

## 🧪 Testing the Automations

Run the complete test suite:
```bash
python -m unittest tests/test_automation.py -v
```

### Manual Workflow Verification via UI:
1. Navigate to **🤖 Automation** in the sidebar.
2. Check the **🧪 Dry Run** box on **Auto-Replenishment** and click **▶ Run Now**. Observe that rules evaluate without committing database records.
3. Uncheck Dry Run and click **▶ Run Now**.
4. Navigate to **📋 Approvals** to view generated replenishment proposals. Click **✓ Approve PO** or **✕ Reject**.
5. Navigate to **🔔 Alert Center** to view generated low stock and delivery delay alerts. Click **👁️ Ack** or **✓ Resolve**.

---

## ☁️ Hosting on Render & Multi-Worker Environments

### Concurrency & Scheduler Locking:
When hosted with multi-process WSGI servers (e.g. Gunicorn with multiple workers on Render), running background loops in every process causes duplicate execution.

OptiStock AI solves this with **database-backed leader election** using the `scheduler_locks` table. Only one worker can acquire the distributed mutex; standby workers automatically step down.

### Deployment Architecture Options on Render:

#### Option A: Unified Web Service (Default & Recommended)
- Start Command: `gunicorn app:app --workers 2 --bind 0.0.0.0:$PORT`
- Environment Variables:
  - `SCHEDULER_AUTOSTART=true`
  - `OPTISTOCK_DB_PATH=/var/data/optistock_automation.db` (attach a Render Persistent Disk)
- Leader election guarantees that only 1 of the 2 Gunicorn workers acts as the scheduler.

#### Option B: Dedicated Background Worker
If you prefer complete separation between web traffic and scheduled background tasks:
1. **Web Service**:
   - Environment Variable: `SCHEDULER_AUTOSTART=false`
   - Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT`
2. **Background Worker**:
   - Start Command: `python -m engine.automation_scheduler`
   - Shares the same persistent database volume.

## 🗂️ Project Structure
```
OptiStock-AI/
├── app.py                  # Flask app & API routes
├── engine/
│   ├── allocator.py        # MILP distribution solver
│   ├── forecaster.py       # ML demand forecaster
│   ├── inventory_optimizer.py
│   ├── data_loader.py
│   └── simulator.py        # What-If scenario engine
├── templates/
│   └── simple.html         # Main dashboard UI
├── static/
│   ├── simple.css          # Light theme styles
│   └── simple.js           # Dashboard logic + map
└── data/
    ├── products.csv
    ├── stores.csv
    ├── warehouses.csv
    └── sales_history_sample.csv
```

## 🌐 API Endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /simple` | Main dashboard |
| `GET /api/summary` | KPI summary |
| `GET /api/plan` | Optimized shipment plan |
| `GET /api/inventory/stores` | Store health & safety stock |
| `GET /api/inventory/warehouses` | Warehouse batch tracker |
| `GET /api/forecast` | ML demand forecast |
| `POST /api/scenario` | What-If simulation |
| `GET /api/network` | Supply chain topology |

## 🛠️ Tech Stack
- **Backend:** Python, Flask, SciPy, NumPy, Pandas, Scikit-learn
- **Frontend:** HTML5, CSS3, Vanilla JS, Chart.js, Leaflet.js
- **Optimization:** HiGHS MILP Solver via SciPy
- **Maps:** Leaflet.js + OpenStreetMap (no API key needed)
