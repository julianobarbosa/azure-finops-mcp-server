"""Unit tests for refactored budget operations."""

from datetime import date, datetime
from unittest.mock import MagicMock, Mock

import pytest

from azure_finops_mcp_server.helpers.budget_operations_refactored import (
    analyze_budget_efficiency,
    calculate_budget_summary,
    calculate_usage_percentage,
    determine_budget_status,
    extract_current_spend,
    extract_forecast_spend,
    extract_time_period,
    generate_budget_alerts,
    generate_efficiency_recommendations,
    process_budget_detail,
)


class TestBudgetProcessing:
    """Test budget processing functions."""

    def test_calculate_usage_percentage(self):
        """Test usage percentage calculation."""
        assert calculate_usage_percentage(50, 100) == 50.0
        assert calculate_usage_percentage(75, 100) == 75.0
        assert calculate_usage_percentage(120, 100) == 120.0
        assert calculate_usage_percentage(0, 100) == 0.0
        assert calculate_usage_percentage(50, 0) == 0.0  # Division by zero handling

    def test_determine_budget_status(self):
        """Test budget status determination."""
        assert determine_budget_status(0) == "OK"
        assert determine_budget_status(50) == "OK"
        assert determine_budget_status(74.9) == "OK"
        assert determine_budget_status(75) == "WARNING"
        assert determine_budget_status(89.9) == "WARNING"
        assert determine_budget_status(90) == "CRITICAL"
        assert determine_budget_status(99.9) == "CRITICAL"
        assert determine_budget_status(100) == "EXCEEDED"
        assert determine_budget_status(150) == "EXCEEDED"

    def test_extract_time_period(self):
        """Test time period extraction from budget."""
        # Budget with time period
        budget = Mock()
        budget.time_period = Mock()
        budget.time_period.start_date = datetime(2024, 1, 1)
        budget.time_period.end_date = datetime(2024, 12, 31)

        result = extract_time_period(budget)
        assert result["start_date"] == "2024-01-01T00:00:00"
        assert result["end_date"] == "2024-12-31T00:00:00"

        # Budget without time period
        budget_no_period = Mock()
        budget_no_period.time_period = None

        result = extract_time_period(budget_no_period)
        assert result["start_date"] is None
        assert result["end_date"] is None

    def test_extract_current_spend(self):
        """Test current spend extraction."""
        # Budget with current spend
        budget = Mock()
        budget.current_spend = Mock()
        budget.current_spend.amount = 500.50
        budget.current_spend.unit = "USD"

        result = extract_current_spend(budget)
        assert result["amount"] == 500.50
        assert result["unit"] == "USD"

        # Budget without current spend
        budget_no_spend = Mock(spec=[])
        result = extract_current_spend(budget_no_spend)
        assert result["amount"] == 0
        assert result["unit"] == "USD"

    def test_extract_forecast_spend(self):
        """Test forecast spend extraction."""
        # Budget with forecast
        budget = Mock()
        budget.forecast_spend = Mock()
        budget.forecast_spend.amount = 1200.75
        budget.forecast_spend.unit = "USD"

        result = extract_forecast_spend(budget)
        assert result["amount"] == 1200.75
        assert result["unit"] == "USD"

        # Budget without forecast
        budget_no_forecast = Mock(spec=[])
        result = extract_forecast_spend(budget_no_forecast)
        assert result is None


class TestBudgetAlerts:
    """Test budget alert generation."""

    def test_generate_budget_alerts_exceeded(self):
        """Test alert generation for exceeded budget."""
        budget_detail = {"name": "TestBudget", "percentage_used": 120, "status": "EXCEEDED", "forecast_percentage": 130}

        alerts = generate_budget_alerts(budget_detail)
        assert len(alerts) == 2
        assert "has been exceeded (120%)" in alerts[0]
        assert "forecasted to exceed by 30.0%" in alerts[1]

    def test_generate_budget_alerts_critical(self):
        """Test alert generation for critical budget."""
        budget_detail = {"name": "TestBudget", "percentage_used": 95, "status": "CRITICAL"}

        alerts = generate_budget_alerts(budget_detail)
        assert len(alerts) == 1
        assert "critical level (95%)" in alerts[0]

    def test_generate_budget_alerts_ok(self):
        """Test no alerts for OK budget."""
        budget_detail = {"name": "TestBudget", "percentage_used": 50, "status": "OK"}

        alerts = generate_budget_alerts(budget_detail)
        assert len(alerts) == 0


class TestBudgetSummary:
    """Test budget summary calculations."""

    def test_calculate_budget_summary(self):
        """Test summary calculation for multiple budgets."""
        budgets = [
            {"amount": 1000, "current_spend": {"amount": 500}, "status": "OK"},
            {"amount": 2000, "current_spend": {"amount": 1900}, "status": "CRITICAL"},
            {"amount": 500, "current_spend": {"amount": 600}, "status": "EXCEEDED"},
        ]

        summary = calculate_budget_summary(budgets)

        assert summary["total_budgets"] == 3
        assert summary["total_budget_amount"] == 3500
        assert summary["total_current_spend"] == 3000
        assert summary["overall_percentage"] == pytest.approx(85.71, 0.01)
        assert summary["budgets_exceeded"] == 1
        assert summary["budgets_critical"] == 1
        assert summary["budgets_warning"] == 0
        assert summary["budgets_ok"] == 1


class TestBudgetEfficiency:
    """Test budget efficiency analysis functions."""

    def test_analyze_budget_efficiency(self):
        """Test budget efficiency analysis."""
        budgets = [
            {"amount": 1000, "current_spend": {"amount": 300}, "percentage_used": 30},  # Underutilized
            {"amount": 2000, "current_spend": {"amount": 1500}, "percentage_used": 75},  # Efficiently used
            {"amount": 500, "current_spend": {"amount": 480}, "percentage_used": 96},  # Near limit
            {"amount": 1500, "current_spend": {"amount": 1600}, "percentage_used": 106.67},  # Exceeded
        ]

        analysis = analyze_budget_efficiency(budgets)

        assert analysis["total_allocated"] == 5000
        assert analysis["total_used"] == 3880
        assert analysis["efficiency_rate"] == 77.6
        assert analysis["underutilized_budgets"] == 1
        assert analysis["efficiently_used_budgets"] == 1
        assert analysis["near_limit_budgets"] == 1
        assert analysis["exceeded_budgets"] == 1

    def test_analyze_budget_efficiency_empty(self):
        """Test efficiency analysis with no budgets."""
        analysis = analyze_budget_efficiency([])
        assert "message" in analysis
        assert analysis["message"] == "No budgets to analyze"

    def test_generate_efficiency_recommendations(self):
        """Test efficiency recommendation generation."""
        underutilized = [{"amount": 1000, "current_spend": {"amount": 300}}]
        efficiently_used = []
        near_limit = [{"amount": 500, "current_spend": {"amount": 480}}]
        exceeded = [{"amount": 1500, "current_spend": {"amount": 1600}}]

        recommendations = generate_efficiency_recommendations(underutilized, efficiently_used, near_limit, exceeded)

        assert len(recommendations) >= 2
        assert any("reallocating" in r for r in recommendations)
        assert any("overspend" in r for r in recommendations)
