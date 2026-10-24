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

## 🏃 Quick Start

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/OptiStock-AI.git
cd OptiStock-AI

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

# Install dependencies
pip install flask numpy pandas scikit-learn scipy

# Run the app
python app.py
```

Then open: **http://127.0.0.1:5000/simple**

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
