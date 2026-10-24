OPTISTOCK AI — DISTRIBUTION INTELLIGENCE & INVENTORY OPTIMIZATION

Requirements:
- Python 3.10 or newer recommended
- Internet connection only for Google Fonts and Chart.js CDN (the Flask app itself is local)

RUN ON WINDOWS / VS CODE:
1. Open the OptiStock-AI folder in VS Code.
2. Open Terminal > New Terminal.
3. Optional virtual environment:
   py -m venv venv
   .\venv\Scripts\Activate.ps1
4. Install dependencies:
   python -m pip install flask pandas scikit-learn
5. Run:
   python app.py
6. Open this address in your browser:
   http://127.0.0.1:5000

FILES:
- app.py: Flask routes, simulated data, forecast and allocation heuristic
- templates/index.html: dashboard layout
- static/style.css: dark responsive styling
- static/script.js: charts, tables, filters, navigation and CSV export

IMPORTANT ASSUMPTIONS:
- All inventory, demand, route costs, warehouse locations and expiry values are simulated.
- Demand is average daily demand multiplied by the selected planning horizon.
- Route costs are illustrative rupees per unit.
- Transit time is assumed to be at most one day.
- Stock expiring in one day or less is excluded from new allocation.
- The plan uses an explainable greedy allocation heuristic; it is not guaranteed to be globally optimal.
- The baseline comparison is a simple lowest-route-cost estimate and is not a fully constrained operational baseline.
- Forecasting is illustrative and uses a three-day moving average with small day-of-week adjustments. It is not trained or validated on real sales data.
- Dashboard savings are estimates from demo assumptions, not verified business savings.

For a production version, add real sales/inventory feeds, transit times, capacity constraints, supplier lead times, minimum order quantities, validated forecasts and a mathematical optimizer.
