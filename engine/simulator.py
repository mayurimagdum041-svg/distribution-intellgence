"""
OptiStock AI - Scenario Simulator & What-If Stress-Testing Sandbox
Enables supply chain leaders to simulate demand spikes, fuel volatility,
warehouse disruptions, and policy benchmark comparisons.
"""

from typing import Dict, List, Any, Optional
from engine.allocator import allocator
from engine.data_loader import WAREHOUSES, PRODUCTS, STORES


class ScenarioSimulator:
    """
    Simulates operational stress tests and policy comparisons.
    """

    def __init__(self):
        pass

    def run_scenario(
        self,
        horizon_days: int = 3,
        demand_shock_pct: float = 0.0,
        fuel_multiplier: float = 1.0,
        disabled_warehouses: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a What-If scenario with custom operational shocks
        and returns comparative impact analytics.
        """
        disabled_warehouses = disabled_warehouses or []

        # Run AI Optimizer on the stressed network
        optimized_plan = allocator.solve(
            horizon_days=horizon_days,
            demand_shock_pct=demand_shock_pct,
            fuel_multiplier=fuel_multiplier,
            disabled_warehouses=disabled_warehouses,
        )

        # Baseline comparison calculations
        benchmark = optimized_plan["benchmark"]

        # Calculate Network Resilience Score (0 - 100)
        fulfillment = benchmark["fulfillment_rate_ai"]
        disruption_penalty = len(disabled_warehouses) * 12.0
        shock_penalty = max(0.0, demand_shock_pct * 0.25)
        resilience_score = max(10.0, min(100.0, round(fulfillment - disruption_penalty - shock_penalty, 1)))

        scenario_name = self._get_scenario_name(demand_shock_pct, fuel_multiplier, disabled_warehouses)

        return {
            "scenario_name": scenario_name,
            "horizon_days": horizon_days,
            "demand_shock_pct": demand_shock_pct,
            "fuel_multiplier": fuel_multiplier,
            "disabled_warehouses": disabled_warehouses,
            "disabled_warehouse_names": [
                w["name"] for w in WAREHOUSES if w["id"] in disabled_warehouses
            ],
            "resilience_score": resilience_score,
            "plan": optimized_plan,
            "summary_cards": {
                "units_shipped": optimized_plan["units_shipped"],
                "total_transport_cost": optimized_plan["total_transport_cost"],
                "unmet_units": optimized_plan["total_unmet_units"],
                "fulfillment_rate": benchmark["fulfillment_rate_ai"],
                "transport_savings": benchmark["transport_savings"],
                "spoilage_averted": benchmark["spoilage_averted_savings"],
                "total_benefit": benchmark["total_economic_benefit"],
            },
        }

    def _get_scenario_name(
        self, demand_shock: float, fuel_mult: float, disabled: List[str]
    ) -> str:
        parts = []
        if demand_shock > 0:
            parts.append(f"+{int(demand_shock)}% Demand Surge")
        elif demand_shock < 0:
            parts.append(f"{int(demand_shock)}% Demand Drop")

        if fuel_mult > 1.0:
            parts.append(f"+{int((fuel_mult - 1.0) * 100)}% Fuel Price Surge")

        if disabled:
            parts.append(f"{len(disabled)} Warehouse(s) Disrupted")

        return " & ".join(parts) if parts else "Standard Operational Baseline"


# Simulator singleton
simulator = ScenarioSimulator()
