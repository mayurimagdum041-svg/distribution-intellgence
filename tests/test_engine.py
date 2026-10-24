"""
OptiStock AI - Unit & Integration Test Suite
Validates Demand Forecaster, Safety Stock calculations, MILP Allocator,
Scenario Simulator, and Flask REST API endpoints.
"""

import unittest
from app import app
from engine.forecaster import forecaster
from engine.inventory_optimizer import calculate_safety_stock, analyze_store_inventory_health
from engine.allocator import allocator
from engine.simulator import simulator


class TestOptiStockEngine(unittest.TestCase):

    def setUp(self):
        self.client = app.test_client()

    def test_demand_forecaster(self):
        res = forecaster.forecast_store_sku("ST-MUM-S", 1, horizon_days=7)
        self.assertIn("metrics", res)
        self.assertIn("forecast", res)
        self.assertEqual(len(res["forecast"]), 7)
        self.assertGreater(res["total_predicted_demand"], 0)
        self.assertLess(res["metrics"]["mape_percent"], 40.0)

    def test_safety_stock_calculation(self):
        ss_info = calculate_safety_stock(daily_demand=40.0, demand_std=5.0, lead_time_days=1.0)
        self.assertGreater(ss_info["safety_stock"], 0)
        self.assertGreater(ss_info["reorder_point"], 40.0)

    def test_milp_allocator(self):
        plan = allocator.solve(horizon_days=3)
        self.assertEqual(plan["status"], "optimal")
        self.assertGreater(plan["units_shipped"], 0)
        self.assertGreater(plan["shipment_count"], 0)
        self.assertIn("benchmark", plan)
        self.assertGreater(plan["benchmark"]["total_economic_benefit"], 0)

    def test_scenario_simulator(self):
        sim = simulator.run_scenario(horizon_days=3, demand_shock_pct=20.0, disabled_warehouses=["WH-PUN"])
        self.assertIn("resilience_score", sim)
        self.assertGreater(sim["summary_cards"]["units_shipped"], 0)

    def test_api_endpoints(self):
        r_sum = self.client.get("/api/summary?days=3")
        self.assertEqual(r_sum.status_code, 200)
        sum_data = r_sum.get_json()
        self.assertIn("total_inventory_units", sum_data)

        r_plan = self.client.get("/api/plan?days=3")
        self.assertEqual(r_plan.status_code, 200)

        r_stores = self.client.get("/api/inventory/stores")
        self.assertEqual(r_stores.status_code, 200)

        r_wh = self.client.get("/api/inventory/warehouses")
        self.assertEqual(r_wh.status_code, 200)

        r_meta = self.client.get("/api/meta")
        self.assertEqual(r_meta.status_code, 200)


if __name__ == "__main__":
    unittest.main()
