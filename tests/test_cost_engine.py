"""
Unit Tests for Cost Optimization & Rightsizing Engine (Module 3).
"""

from cost_engine.calculator import CostCalculator
from backend.app.services.cost_service import generate_fleet_cost_analysis, update_recommendation_status
from backend.app.schemas.cost import CostRecommendationAction
from tests.test_alert_engine import create_test_db


def test_cost_calculator_rightsizing():
    calc = CostCalculator()
    
    # Idle VM detection
    idle_rec = calc.evaluate_rightsizing(
        hostname="idle-vm-01",
        instance_type="c5.2xlarge",
        avg_cpu=2.5,
        peak_cpu=4.0,
        avg_memory=15.0,
        peak_memory=18.0,
    )
    assert idle_rec is not None
    assert idle_rec["recommendation_type"] == "IDLE_TERMINATION"
    assert idle_rec["estimated_monthly_savings_usd"] > 0

    # Over-provisioned downsizing
    downsize_rec = calc.evaluate_rightsizing(
        hostname="oversized-vm-01",
        instance_type="c5.2xlarge",
        avg_cpu=22.0,
        peak_cpu=35.0,
        avg_memory=30.0,
        peak_memory=40.0,
    )
    assert downsize_rec is not None
    assert downsize_rec["recommendation_type"] == "RIGHTSIZE_DOWN"
    assert downsize_rec["suggested_instance_type"] == "c5.large"


def test_cost_service_fleet_analysis():
    db = create_test_db()
    summary = generate_fleet_cost_analysis(db)
    assert summary.billing_status.startswith("Estimated")
    assert summary.currency == "USD"
    db.close()
