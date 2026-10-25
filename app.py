"""
OptiStock AI — Smart Inventory & Warehouse Management System
FMCG Distribution Intelligence, Interactive Real-Time Map, and Logistics Gateway
"""

import os
import json
import urllib.request
import urllib.parse
from functools import wraps
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
from werkzeug.security import generate_password_hash, check_password_hash
import database

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "optistock-ai-secret-key-2026-secure")

# Initialize database on application start
database.init_db()


def login_required(f):
    """Protects routes requiring user authentication."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access your OptiStock AI workspace.", "warning")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


@app.context_processor
def inject_user_context():
    """Provides user session info to all Jinja templates."""
    user = None
    if "user_id" in session:
        user = database.get_user_by_id(session["user_id"])
    return {"current_user": user}


# ─────────────────────────────────────────────────────────────
# AUTHENTICATION ROUTES
# ─────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("inventory"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("inventory"))

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "error")
            return render_template("login.html", email=email)

        user = database.get_user_by_email(email)
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password. Please try again.", "error")
            return render_template("login.html", email=email)

        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        session["user_email"] = user["email"]

        flash(f"Welcome back, {user['name']}! Successfully signed in.", "success")
        next_page = request.args.get("next")
        if next_page and next_page.startswith("/"):
            return redirect(next_page)
        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/demo-login", methods=["POST"])
def demo_login():
    """1-Click Demo Login for immediate reviewer testing."""
    demo_user = database.get_user_by_email("demo@optistock.ai")
    if not demo_user:
        database.init_db()
        demo_user = database.get_user_by_email("demo@optistock.ai")

    if demo_user:
        session.clear()
        session["user_id"] = demo_user["id"]
        session["user_name"] = demo_user["name"]
        session["user_email"] = demo_user["email"]
        flash("Logged in with Demo Account! Welcome to OptiStock AI.", "success")
        return redirect(url_for("dashboard"))

    flash("Could not initialize demo account.", "error")
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        errors = []
        if not name:
            errors.append("Full Name is required.")
        if not email or "@" not in email:
            errors.append("A valid email address is required.")
        if not password or len(password) < 6:
            errors.append("Password must be at least 6 characters long.")
        if password != confirm_password:
            errors.append("Passwords do not match.")

        existing = database.get_user_by_email(email)
        if existing:
            errors.append("An account with this email already exists. Please log in.")

        if errors:
            for err in errors:
                flash(err, "error")
            return render_template("register.html", name=name, email=email)

        pw_hash = generate_password_hash(password)
        new_id = database.create_user(name, email, pw_hash)

        if new_id:
            session.clear()
            session["user_id"] = new_id
            session["user_name"] = name
            session["user_email"] = email
            flash("Account registered successfully! Welcome to OptiStock AI.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Registration failed. Please try again.", "error")
            return render_template("register.html", name=name, email=email)

    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for("login"))


# ─────────────────────────────────────────────────────────────
# FMCG DISTRIBUTION INTELLIGENCE & INTERACTIVE MAP CONSOLE
# ─────────────────────────────────────────────────────────────

@app.route("/inventory", methods=["GET"])
@login_required
def inventory():
    """Main interactive geographical map for real-time inventory movement & delivery tracking."""
    user_id = session["user_id"]

    # Filter parameters
    loc_type = request.args.get("type", "").strip()
    status_filter = request.args.get("status", "").strip()
    search = request.args.get("search", "").strip()

    locations = database.get_locations(user_id, loc_type=loc_type or None, search=search or None)
    shipments = database.get_shipments(user_id, status=status_filter or None, search=search or None)
    products = database.get_user_products(user_id)
    fmcg_metrics = database.get_fmcg_dashboard_metrics(user_id)
    alerts = database.get_smart_alerts(user_id)

    # All locations for dropdown pickers
    all_locations = database.get_locations(user_id)

    return render_template(
        "inventory.html",
        locations=locations,
        all_locations=all_locations,
        shipments=shipments,
        products=products,
        metrics=fmcg_metrics,
        alerts=alerts,
        selected_type=loc_type,
        selected_status=status_filter,
        search=search,
        page="inventory"
    )


# ─────────────────────────────────────────────────────────────
# REST APIS FOR REAL-TIME MAP & INVENTORY WORKFLOWS
# ─────────────────────────────────────────────────────────────

@app.route("/api/map-data")
@login_required
def api_map_data():
    """Provides complete real-time JSON for Leaflet.js markers, routes, and vehicle locations."""
    user_id = session["user_id"]
    status_filter = request.args.get("status")
    loc_type = request.args.get("type")
    search = request.args.get("search")

    locations = database.get_locations(user_id, loc_type=loc_type or None, search=search or None)
    shipments = database.get_shipments(user_id, status=status_filter or None, search=search or None)
    metrics = database.get_fmcg_dashboard_metrics(user_id)
    alerts = database.get_smart_alerts(user_id)

    return jsonify({
        "success": True,
        "locations": locations,
        "shipments": shipments,
        "metrics": metrics,
        "alerts": alerts
    })


@app.route("/api/location/<int:loc_id>/popup")
@login_required
def api_location_popup(loc_id):
    """Provides detailed telemetry when a user clicks any map marker."""
    user_id = session["user_id"]
    popup_data = database.get_location_popup_data(loc_id, user_id)
    if not popup_data:
        return jsonify({"success": False, "error": "Location not found"}), 404
    return jsonify({"success": True, "location": popup_data})


@app.route("/api/geocode")
@login_required
def api_geocode():
    """Geocodes an address using OpenStreetMap Nominatim with fallback coordinates."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"success": False, "error": "Query required"}), 400

    # Clean query
    encoded_q = urllib.parse.quote(query)
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={encoded_q}&countrycodes=in&limit=1"

    req = urllib.request.Request(url, headers={"User-Agent": "OptiStockAI-FMCG-Platform/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and len(data) > 0:
                return jsonify({
                    "success": True,
                    "lat": float(data[0]["lat"]),
                    "lng": float(data[0]["lon"]),
                    "display_name": data[0]["display_name"]
                })
    except Exception:
        pass

    # City-based heuristic fallback if network/geocoding blocks
    fallback_map = {
        "mumbai": (19.0760, 72.8777),
        "pune": (18.5204, 73.8567),
        "thane": (19.2183, 72.9781),
        "nashik": (19.9975, 73.7898),
        "kolhapur": (16.7050, 74.2433),
        "ahmedabad": (23.0225, 72.5714),
        "surat": (21.1702, 72.8311),
        "vadodara": (22.3072, 73.1812),
        "nagpur": (21.1458, 79.0882),
        "satara": (17.6805, 74.0183),
        "aurangabad": (19.8762, 75.3433),
    }

    q_lower = query.lower()
    for city, coords in fallback_map.items():
        if city in q_lower:
            return jsonify({
                "success": True,
                "lat": coords[0],
                "lng": coords[1],
                "display_name": f"{query} (Estimated {city.title()})"
            })

    # Default Maharashtra center
    return jsonify({
        "success": True,
        "lat": 18.5204,
        "lng": 73.8567,
        "display_name": f"{query} (Default Regional Center)"
    })


@app.route("/api/shipments/create", methods=["POST"])
@login_required
def api_shipment_create():
    """Dispatches a new shipment with atomic stock deduction and route drawing."""
    user_id = session["user_id"]
    data = request.get_json(silent=True) or request.form

    source_id = data.get("source_location_id")
    dest_id = data.get("dest_location_id")
    product_id = data.get("product_id")
    quantity = data.get("quantity")
    status = data.get("status", "In Transit")
    dispatch_date = data.get("dispatch_date")
    expected_date = data.get("expected_delivery_date")
    notes = data.get("notes")

    try:
        s_id = int(source_id)
        d_id = int(dest_id)
        p_id = int(product_id)
        qty = int(quantity)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid numerical parameters"}), 400

    success, msg = database.create_shipment(
        user_id, s_id, d_id, p_id, qty,
        status=status, dispatch_date=dispatch_date,
        expected_date=expected_date, notes=notes
    )

    if request.is_json:
        return jsonify({"success": success, "message": msg})
    else:
        flash(msg, "success" if success else "error")
        return redirect(url_for("inventory"))


@app.route("/api/shipments/<int:shipment_id>/deliver", methods=["POST"])
@login_required
def api_shipment_deliver(shipment_id):
    """Confirms shipment delivery and adds stock to destination inventory."""
    user_id = session["user_id"]
    data = request.get_json(silent=True) or request.form
    confirmed_qty = data.get("confirmed_quantity")

    qty_val = None
    if confirmed_qty:
        try:
            qty_val = int(confirmed_qty)
        except ValueError:
            qty_val = None

    success, msg = database.confirm_delivery(shipment_id, user_id, confirmed_quantity=qty_val)
    if request.is_json:
        return jsonify({"success": success, "message": msg})
    else:
        flash(msg, "success" if success else "error")
        return redirect(url_for("inventory"))


@app.route("/api/shipments/<int:shipment_id>/cancel", methods=["POST"])
@login_required
def api_shipment_cancel(shipment_id):
    """Cancels a shipment and safely restores stock to source inventory."""
    user_id = session["user_id"]
    data = request.get_json(silent=True) or request.form
    reason = data.get("reason", "Cancelled by operator")

    success, msg = database.cancel_shipment(shipment_id, user_id, reason=reason)
    if request.is_json:
        return jsonify({"success": success, "message": msg})
    else:
        flash(msg, "info" if success else "error")
        return redirect(url_for("inventory"))


@app.route("/api/locations/add", methods=["POST"])
@login_required
def api_location_add():
    """Adds a new Warehouse, Distributor, or Retailer with GPS coordinates."""
    user_id = session["user_id"]
    data = request.get_json(silent=True) or request.form

    name = data.get("name", "").strip()
    code = data.get("code", "").strip().upper()
    loc_type = data.get("type", "Warehouse").strip()
    address = data.get("address", "").strip()
    city = data.get("city", "").strip()
    state = data.get("state", "Maharashtra").strip()
    pincode = data.get("pincode", "400001").strip()
    lat = data.get("lat", 18.5204)
    lng = data.get("lng", 73.8567)
    capacity = data.get("capacity_units", 10000)

    if not name or not code or not city:
        if request.is_json:
            return jsonify({"success": False, "error": "Name, Code, and City are required"}), 400
        flash("Name, ID Code, and City are required.", "error")
        return redirect(url_for("inventory"))

    try:
        lat_val = float(lat)
        lng_val = float(lng)
        cap_val = int(capacity)
    except ValueError:
        lat_val, lng_val, cap_val = 18.5204, 73.8567, 10000

    new_id = database.add_location(
        user_id, code, name, loc_type, address, city, state, pincode,
        lat=lat_val, lng=lng_val, capacity=cap_val
    )

    if new_id:
        msg = f"{loc_type} '{name}' ({code}) pinned to map successfully!"
        if request.is_json:
            return jsonify({"success": True, "location_id": new_id, "message": msg})
        flash(msg, "success")
    else:
        msg = f"Failed to register facility. Code '{code}' may already exist."
        if request.is_json:
            return jsonify({"success": False, "error": msg}), 400
        flash(msg, "error")

    return redirect(url_for("inventory"))


@app.route("/api/reset-demo", methods=["POST"])
@login_required
def api_reset_demo():
    """Resets FMCG demo data without deleting user-created items."""
    user_id = session["user_id"]
    database.reset_demo_data(user_id)
    flash("FMCG Demo Data reset to default baseline! User records preserved.", "info")
    return redirect(url_for("inventory"))


@app.route("/api/fmcg-stats")
@login_required
def api_fmcg_stats():
    """Returns analytics data for Recharts / Chart.js graphs."""
    user_id = session["user_id"]
    return jsonify(database.get_fmcg_dashboard_metrics(user_id))


@app.route("/api/chart-data")
@login_required
def api_chart_data():
    """Provides Chart.js payload for Dashboard category & status graphs."""
    user_id = session["user_id"]
    return jsonify(database.get_chart_data(user_id))


@app.route("/inventory/set-stock", methods=["POST"])
@login_required
def inventory_set_stock():
    """Allocates or updates stock levels and sales velocity at a specific location."""
    user_id = session["user_id"]
    product_id = request.form.get("product_id")
    location_id = request.form.get("location_id")
    current_stock = request.form.get("current_stock", "0").strip()
    units_sold_per_day = request.form.get("units_sold_per_day", "0").strip()

    try:
        p_id = int(product_id)
        l_id = int(location_id)
        stock_val = int(current_stock)
        vel_val = int(units_sold_per_day)
    except (ValueError, TypeError):
        flash("Invalid numerical values for stock allocation.", "error")
        return redirect(url_for("inventory"))

    database.set_inventory_stock(user_id, p_id, l_id, stock_val, vel_val)
    flash("Stock level and velocity updated successfully!", "success")
    return redirect(url_for("inventory"))


# ─────────────────────────────────────────────────────────────
# PRESERVED WORKING MODULES
# ─────────────────────────────────────────────────────────────

@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session["user_id"]
    metrics = database.get_fmcg_dashboard_metrics(user_id)
    recent_shipments = database.get_shipments(user_id)[:5]
    alerts = database.get_smart_alerts(user_id)
    inventory_analytics = database.get_all_inventory_records(user_id)
    all_locations = database.get_locations(user_id)
    all_products = database.get_user_products(user_id)

    # Top forecast items with non-zero daily velocity
    forecast_items = [item for item in inventory_analytics if item.get("units_sold_per_day", 0) > 0][:4]
    if not forecast_items:
        forecast_items = inventory_analytics[:4]

    # Critical & Low stock risk items
    risk_items = [item for item in inventory_analytics if item.get("status") in ("Critical", "Low Stock")][:4]

    # Restock suggestions with warehouse sourcing recommendation
    restock_suggestions = []
    for item in risk_items[:3]:
        wh_suggestion = database.find_suggested_warehouse(user_id, item["product_id"], item["recommended_replenishment"])
        restock_suggestions.append({
            "item": item,
            "warehouse_suggestion": wh_suggestion
        })

    return render_template(
        "dashboard.html",
        metrics=metrics,
        recent_shipments=recent_shipments,
        alerts=alerts,
        inventory_analytics=inventory_analytics,
        all_locations=all_locations,
        all_products=all_products,
        forecast_items=forecast_items,
        risk_items=risk_items,
        restock_suggestions=restock_suggestions,
        page="dashboard"
    )


@app.route("/products", methods=["GET"])
@login_required
def products():
    user_id = session["user_id"]
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "").strip()

    all_products = database.get_user_products(user_id, search=search or None, category=category or None)
    categories = sorted(list(set(p["category"] for p in database.get_user_products(user_id))))

    return render_template(
        "products.html",
        products=all_products,
        categories=categories,
        search=search,
        selected_category=category,
        page="products"
    )


@app.route("/products/add", methods=["POST"])
@login_required
def add_product():
    user_id = session["user_id"]
    name = request.form.get("name", "").strip()
    sku = request.form.get("sku", "").strip().upper()
    category = request.form.get("category", "").strip()
    price = request.form.get("price", "0").strip()
    min_stock_level = request.form.get("min_stock_level", "0").strip()
    description = request.form.get("description", "").strip()
    redirect_target = request.form.get("redirect_to", "products")

    # Optional initial location stock allocation
    location_id = request.form.get("location_id")
    initial_stock = request.form.get("initial_stock")
    units_sold_per_day = request.form.get("units_sold_per_day", "0")

    try:
        price_val = float(price)
        min_stock_val = int(min_stock_level)
    except ValueError:
        flash("Invalid numerical values.", "error")
        return redirect(url_for(redirect_target if redirect_target in ("dashboard", "products") else "products"))

    new_id = database.add_product(user_id, name, sku, category, price_val, min_stock_val, description)
    if new_id:
        # If location and stock provided, allocate immediately
        if location_id and initial_stock:
            try:
                l_id = int(location_id)
                stock_val = int(initial_stock)
                vel_val = int(units_sold_per_day) if units_sold_per_day else 0
                database.set_inventory_stock(user_id, new_id, l_id, stock_val, vel_val)
            except (ValueError, TypeError):
                pass
        flash(f"Product '{name}' ({sku}) registered successfully!", "success")
    else:
        flash(f"Failed to add product. SKU '{sku}' may already exist.", "error")

    return redirect(url_for(redirect_target if redirect_target in ("dashboard", "products") else "products"))


@app.route("/products/edit/<int:product_id>", methods=["POST"])
@login_required
def edit_product(product_id):
    user_id = session["user_id"]
    name = request.form.get("name", "").strip()
    sku = request.form.get("sku", "").strip().upper()
    category = request.form.get("category", "").strip()
    price = request.form.get("price", "0").strip()
    min_stock_level = request.form.get("min_stock_level", "0").strip()
    description = request.form.get("description", "").strip()

    try:
        price_val = float(price)
        min_stock_val = int(min_stock_level)
    except ValueError:
        flash("Invalid numbers.", "error")
        return redirect(url_for("products"))

    database.update_product(product_id, user_id, name, sku, category, price_val, min_stock_val, description)
    flash(f"Product '{name}' updated!", "success")
    return redirect(url_for("products"))


@app.route("/products/delete/<int:product_id>", methods=["POST"])
@login_required
def delete_product(product_id):
    user_id = session["user_id"]
    database.delete_product(product_id, user_id)
    flash("Product removed.", "info")
    return redirect(url_for("products"))


@app.route("/warehouses")
@login_required
def warehouses():
    user_id = session["user_id"]
    all_warehouses = database.get_locations(user_id, loc_type="Warehouse")
    wh_id = request.args.get("id")
    selected_warehouse = None
    stored_inventory = []

    if wh_id:
        try:
            selected_warehouse = database.get_location_by_id(int(wh_id), user_id)
            if selected_warehouse:
                stored_inventory = database.get_location_inventory(int(wh_id), user_id)
        except (ValueError, TypeError):
            pass

    if not selected_warehouse and all_warehouses:
        selected_warehouse = all_warehouses[0]
        stored_inventory = database.get_location_inventory(selected_warehouse["id"], user_id)

    return render_template(
        "warehouses.html",
        warehouses=all_warehouses,
        selected_warehouse=selected_warehouse,
        stored_inventory=stored_inventory,
        page="warehouses"
    )


@app.route("/warehouses/add", methods=["POST"])
@login_required
def add_warehouse():
    user_id = session["user_id"]
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()
    address = request.form.get("address", "").strip()
    city = request.form.get("city", "").strip()
    state = request.form.get("state", "Maharashtra").strip()
    pincode = request.form.get("pincode", "").strip()

    if not name or not code or not city:
        flash("Name, ID Code, and City are required.", "error")
        return redirect(url_for("warehouses"))

    new_id = database.add_location(user_id, code, name, "Warehouse", address, city, state, pincode)
    if new_id:
        flash(f"Warehouse '{name}' ({code}) registered successfully!", "success")
    else:
        flash(f"Failed to add warehouse. Code '{code}' may already exist.", "error")
    return redirect(url_for("warehouses"))


@app.route("/warehouses/edit/<int:warehouse_id>", methods=["POST"])
@login_required
def edit_warehouse(warehouse_id):
    user_id = session["user_id"]
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()
    address = request.form.get("address", "").strip()
    city = request.form.get("city", "").strip()
    state = request.form.get("state", "Maharashtra").strip()
    pincode = request.form.get("pincode", "").strip()

    success = database.update_location(warehouse_id, user_id, code, name, "Warehouse", address, city, state, pincode)
    if success:
        flash(f"Warehouse '{name}' updated successfully!", "success")
    else:
        flash("Failed to update warehouse.", "error")
    return redirect(url_for("warehouses"))


@app.route("/warehouses/delete/<int:warehouse_id>", methods=["POST"])
@login_required
def delete_warehouse(warehouse_id):
    user_id = session["user_id"]
    database.delete_location(warehouse_id, user_id)
    flash("Warehouse removed successfully.", "info")
    return redirect(url_for("warehouses"))


@app.route("/retail-stores")
@login_required
def retail_stores():
    user_id = session["user_id"]
    all_stores = database.get_locations(user_id, loc_type="Retailer")
    store_id = request.args.get("id")
    selected_store = None
    store_inventory = []

    if store_id:
        try:
            selected_store = database.get_location_by_id(int(store_id), user_id)
            if selected_store:
                store_inventory = database.get_location_inventory(int(store_id), user_id)
        except (ValueError, TypeError):
            pass

    if not selected_store and all_stores:
        selected_store = all_stores[0]
        store_inventory = database.get_location_inventory(selected_store["id"], user_id)

    return render_template(
        "retail_stores.html",
        stores=all_stores,
        selected_store=selected_store,
        store_inventory=store_inventory,
        page="retail_stores"
    )


@app.route("/retail-stores/add", methods=["POST"])
@login_required
def add_retail_store():
    user_id = session["user_id"]
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()
    address = request.form.get("address", "").strip()
    city = request.form.get("city", "").strip()
    state = request.form.get("state", "Maharashtra").strip()
    pincode = request.form.get("pincode", "").strip()

    if not name or not code or not city:
        flash("Name, ID Code, and City are required.", "error")
        return redirect(url_for("retail_stores"))

    new_id = database.add_location(user_id, code, name, "Retailer", address, city, state, pincode)
    if new_id:
        flash(f"Retail store '{name}' ({code}) registered successfully!", "success")
    else:
        flash(f"Failed to add retail store. Code '{code}' may already exist.", "error")
    return redirect(url_for("retail_stores"))


@app.route("/retail-stores/edit/<int:store_id>", methods=["POST"])
@login_required
def edit_retail_store(store_id):
    user_id = session["user_id"]
    name = request.form.get("name", "").strip()
    code = request.form.get("code", "").strip().upper()
    address = request.form.get("address", "").strip()
    city = request.form.get("city", "").strip()
    state = request.form.get("state", "Maharashtra").strip()
    pincode = request.form.get("pincode", "").strip()

    success = database.update_location(store_id, user_id, code, name, "Retailer", address, city, state, pincode)
    if success:
        flash(f"Retail store '{name}' updated successfully!", "success")
    else:
        flash("Failed to update retail store.", "error")
    return redirect(url_for("retail_stores"))


@app.route("/retail-stores/delete/<int:store_id>", methods=["POST"])
@login_required
def delete_retail_store(store_id):
    user_id = session["user_id"]
    database.delete_location(store_id, user_id)
    flash("Retail store removed successfully.", "info")
    return redirect(url_for("retail_stores"))


@app.route("/transfers", methods=["GET", "POST"])
@login_required
def transfers():
    user_id = session["user_id"]

    if request.method == "POST":
        source_id = request.form.get("source_location_id")
        dest_id = request.form.get("dest_location_id")
        product_id = request.form.get("product_id")
        quantity = request.form.get("quantity", "0").strip()
        notes = request.form.get("notes", "").strip()

        success, msg = database.transfer_stock(user_id, source_id, dest_id, product_id, quantity, notes)
        if success:
            flash(msg, "success")
        else:
            flash(msg, "error")
        return redirect(url_for("transfers"))

    shipments = database.get_shipments(user_id)
    locations = database.get_locations(user_id)
    products = database.get_user_products(user_id)
    return render_template("transfers.html", transfers=shipments, locations=locations, products=products, page="transfers")


@app.route("/predictions", methods=["GET", "POST"])
@login_required
def predictions():
    user_id = session["user_id"]
    stores = database.get_locations(user_id, loc_type="Retailer")
    products = database.get_user_products(user_id)
    recent_predictions = database.get_recent_predictions(user_id)

    prediction_result = None
    warehouse_suggestion = None
    selected_store_id = None
    selected_product_id = None
    input_stock = 60
    input_velocity = 20
    input_min_stock = 50
    input_period = 7

    if request.method == "POST":
        store_id = request.form.get("store_id")
        product_id = request.form.get("product_id")
        current_stock = request.form.get("current_stock", "0").strip()
        units_sold_per_day = request.form.get("units_sold_per_day", "0").strip()
        min_stock_level = request.form.get("min_stock_level", "0").strip()
        prediction_period = request.form.get("prediction_period", "7").strip()

        try:
            s_id = int(store_id)
            p_id = int(product_id)
            stock_val = int(current_stock)
            vel_val = int(units_sold_per_day)
            min_val = int(min_stock_level)
            period_val = int(prediction_period)
        except (ValueError, TypeError):
            flash("Invalid input values.", "error")
            return redirect(url_for("predictions"))

        pred_res = database.calculate_prediction(stock_val, vel_val, period_val, min_val)
        wh_res = database.find_suggested_warehouse(user_id, p_id, pred_res["recommended_replenishment"])

        database.save_prediction(user_id, p_id, s_id, stock_val, vel_val, min_val, period_val, pred_res, wh_res)

        prediction_result = pred_res
        warehouse_suggestion = wh_res
        selected_store_id = s_id
        selected_product_id = p_id
        input_stock = stock_val
        input_velocity = vel_val
        input_min_stock = min_val
        input_period = period_val
        flash("AI Demand Prediction calculated!", "success")
        recent_predictions = database.get_recent_predictions(user_id)

    return render_template(
        "predictions.html",
        stores=stores,
        products=products,
        recent_predictions=recent_predictions,
        prediction_result=prediction_result,
        warehouse_suggestion=warehouse_suggestion,
        selected_store_id=selected_store_id,
        selected_product_id=selected_product_id,
        input_stock=input_stock,
        input_velocity=input_velocity,
        input_min_stock=input_min_stock,
        input_period=input_period,
        page="predictions"
    )


@app.route("/reports")
@login_required
def reports():
    user_id = session["user_id"]
    metrics = database.get_fmcg_dashboard_metrics(user_id)
    inventory_items = database.get_all_inventory_records(user_id)
    shipments = database.get_shipments(user_id)
    replenishment_manifest = database.get_replenishment_manifest(user_id)
    return render_template(
        "reports.html",
        metrics=metrics,
        inventory_items=inventory_items,
        replenishment_manifest=replenishment_manifest,
        shipments=shipments,
        page="reports"
    )


# ─────────────────────────────────────────────────────────────
# PROBLEM STATEMENT 2: DISTRIBUTION INTELLIGENCE & INVENTORY OPTIMIZATION ENGINE
# ─────────────────────────────────────────────────────────────

@app.route("/distribution-engine", methods=["GET"])
@login_required
def distribution_engine():
    """
    Problem Statement 2: AI-Powered Distribution Intelligence & Inventory Optimization Engine
    Multi-constraint allocation balancing demand, proximity, freight costs, and FEFO perishable shelf life.
    """
    user_id = session["user_id"]
    plan = database.get_distribution_optimization_plan(user_id)
    all_locations = database.get_locations(user_id)
    products = database.get_user_products(user_id)
    metrics = database.get_fmcg_dashboard_metrics(user_id)

    return render_template(
        "distribution_engine.html",
        recommendations=plan["recommendations"],
        summary=plan["summary"],
        efficiency_metrics=plan["efficiency_metrics"],
        assumptions=plan["assumptions"],
        all_locations=all_locations,
        products=products,
        metrics=metrics,
        page="distribution_engine"
    )


@app.route("/api/distribution/execute", methods=["POST"])
@login_required
def api_distribution_execute():
    """Executes a single recommended distribution allocation as an active shipment."""
    user_id = session["user_id"]
    data = request.get_json(silent=True) or request.form

    source_id = data.get("source_id")
    dest_id = data.get("dest_id")
    product_id = data.get("product_id")
    quantity = data.get("quantity")
    notes = data.get("notes")

    if not source_id or not dest_id or not product_id or not quantity:
        if request.is_json:
            return jsonify({"success": False, "error": "Missing required allocation parameters."}), 400
        flash("Missing required allocation parameters.", "error")
        return redirect(url_for("distribution_engine"))

    try:
        s_id = int(source_id)
        d_id = int(dest_id)
        p_id = int(product_id)
        qty = int(quantity)
    except (ValueError, TypeError):
        if request.is_json:
            return jsonify({"success": False, "error": "Invalid numerical parameters."}), 400
        flash("Invalid numerical parameters.", "error")
        return redirect(url_for("distribution_engine"))

    success, msg = database.execute_distribution_recommendation(user_id, s_id, d_id, p_id, qty, notes=notes)

    if success:
        if request.is_json:
            return jsonify({"success": True, "message": msg})
        flash(f"AI Allocation Dispatched: {msg}", "success")
    else:
        if request.is_json:
            return jsonify({"success": False, "error": msg}), 400
        flash(f"Dispatch failed: {msg}", "error")

    return redirect(url_for("distribution_engine"))


@app.route("/api/distribution/batch-execute", methods=["POST"])
@login_required
def api_distribution_batch_execute():
    """Batch-executes all high-confidence AI distribution recommendations."""
    user_id = session["user_id"]
    data = request.get_json(silent=True) or request.form
    min_score = float(data.get("min_score", 70.0))

    result = database.batch_execute_distribution_plan(user_id, min_score=min_score)

    msg = f"Dispatched {result['dispatched_count']} optimized shipments ({result['units_moved']} units, ₹{result['value_moved']:,.2f} inventory allocated)!"
    if result["errors"]:
        msg += f" ({len(result['errors'])} skipped due to source capacity)."

    if request.is_json:
        return jsonify({"success": True, "result": result, "message": msg})
    flash(msg, "success")
    return redirect(url_for("distribution_engine"))


@app.route("/api/distribution/plan", methods=["GET"])
@login_required
def api_distribution_plan():
    """Returns complete JSON optimization plan for charts, simulation, or third-party callers."""
    user_id = session["user_id"]
    plan = database.get_distribution_optimization_plan(user_id)
    return jsonify({"success": True, "plan": plan})


# ─────────────────────────────────────────────────────────────
# EXPIRED, SPOILED & DAMAGED PRODUCTS ROUTES
# ─────────────────────────────────────────────────────────────

@app.route("/expired-spoiled", methods=["GET"])
@login_required
def expired_spoiled():
    """
    Renders the Expired & Spoiled Products management dashboard:
    - Summary metrics (Affected products, Affected units, Estimated loss, status counts)
    - Records table with filtering by status, reason, facility, and search
    - Modal forms for recording new incidents and transitioning disposition status
    """
    user_id = session["user_id"]
    status_filter = request.args.get("status", "All")
    reason_filter = request.args.get("reason", "All")
    location_filter = request.args.get("location_id", "All")
    search_query = request.args.get("q", "").strip()

    records = database.get_spoilage_records(
        user_id=user_id,
        status=status_filter,
        reason=reason_filter,
        location_id=location_filter,
        search=search_query
    )
    metrics = database.get_spoilage_metrics(user_id)
    products = database.get_products_by_user(user_id)
    locations = database.get_locations_by_user(user_id)

    filters = {
        "status": status_filter,
        "reason": reason_filter,
        "location_id": location_filter,
        "search": search_query
    }

    return render_template(
        "expired_spoiled.html",
        page="expired_spoiled",
        records=records,
        metrics=metrics,
        products=products,
        locations=locations,
        filters=filters
    )


@app.route("/expired-spoiled/record", methods=["POST"])
@login_required
def record_spoilage_incident():
    """Records an incident of expired, spoiled, or damaged inventory."""
    user_id = session["user_id"]
    product_id = request.form.get("product_id")
    location_id = request.form.get("location_id")
    quantity = request.form.get("quantity")
    reason = request.form.get("reason", "Expired")
    expiry_date = request.form.get("expiry_date", "").strip() or None
    unit_price = request.form.get("unit_price")
    status = request.form.get("status", "Pending Disposal")
    notes = request.form.get("notes", "").strip()

    if not product_id or not location_id or not quantity:
        flash("Product, facility location, and quantity are mandatory fields.", "error")
        return redirect(url_for("expired_spoiled"))

    try:
        p_id = int(product_id)
        l_id = int(location_id)
        qty = int(quantity)
        u_price = float(unit_price) if unit_price and unit_price.strip() else None
    except (ValueError, TypeError):
        flash("Invalid numerical values provided.", "error")
        return redirect(url_for("expired_spoiled"))

    success, msg, rec_id = database.record_spoilage(
        user_id=user_id,
        product_id=p_id,
        location_id=l_id,
        quantity=qty,
        reason=reason,
        expiry_date=expiry_date,
        unit_price=u_price,
        notes=notes,
        status=status
    )

    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")

    return redirect(url_for("expired_spoiled"))


@app.route("/expired-spoiled/update-status", methods=["POST"])
@login_required
def update_spoilage_incident_status():
    """Updates disposition status (Pending Disposal -> Disposed or Returned)."""
    user_id = session["user_id"]
    record_id = request.form.get("record_id")
    new_status = request.form.get("status")
    notes = request.form.get("notes", "").strip()

    if not record_id or not new_status:
        flash("Missing incident record identifier or status parameter.", "error")
        return redirect(url_for("expired_spoiled"))

    try:
        r_id = int(record_id)
    except (ValueError, TypeError):
        flash("Invalid record identifier.", "error")
        return redirect(url_for("expired_spoiled"))

    success, msg = database.update_spoilage_status(user_id, r_id, new_status, notes=notes)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")

    return redirect(url_for("expired_spoiled"))


@app.route("/expired-spoiled/delete", methods=["POST"])
@login_required
def delete_spoilage_incident():
    """Deletes or rolls back a spoilage incident record."""
    user_id = session["user_id"]
    record_id = request.form.get("record_id")
    restore_stock = request.form.get("restore_stock") in ("1", "true", "on", True)

    try:
        r_id = int(record_id)
    except (ValueError, TypeError):
        flash("Invalid incident record identifier.", "error")
        return redirect(url_for("expired_spoiled"))

    success, msg = database.delete_spoilage_record(user_id, r_id, restore_stock=restore_stock)
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")

    return redirect(url_for("expired_spoiled"))


@app.route("/api/product-stock-at-location", methods=["GET"])
@login_required
def api_product_stock_at_location():
    """Returns available on-hand stock and unit pricing for selected location & product."""
    user_id = session["user_id"]
    product_id = request.args.get("product_id")
    location_id = request.args.get("location_id")

    if not product_id or not location_id:
        return jsonify({"success": False, "error": "Missing product_id or location_id."}), 400

    try:
        p_id = int(product_id)
        l_id = int(location_id)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid numerical parameters."}), 400

    info = database.get_product_stock_at_location(user_id, p_id, l_id)
    return jsonify({"success": True, "data": info})



if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
