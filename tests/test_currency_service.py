import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.services.currency_service import (
    fetch_exchange_rates,
    get_supported_currencies,
    SUPPORTED_CURRENCIES,
    _cache,
)

client = TestClient(app)

def test_supported_currencies_endpoint():
    response = client.get("/api/v1/currency/supported")
    assert response.status_code == 200
    data = response.json()
    assert "currencies" in data
    assert data["base_currency"] == "USD"
    codes = [c["code"] for c in data["currencies"]]
    assert "USD" in codes
    assert "INR" in codes
    assert "EUR" in codes
    assert "GBP" in codes

def test_currency_rates_usd_only():
    response = client.get("/api/v1/currency/rates?base=USD&quotes=USD")
    assert response.status_code == 200
    data = response.json()
    assert data["base"] == "USD"
    assert data["rates"]["USD"] == 1.0

def test_currency_rates_endpoint():
    response = client.get("/api/v1/currency/rates?base=USD&quotes=INR,EUR,GBP")
    assert response.status_code == 200
    data = response.json()
    assert data["base"] == "USD"
    assert "INR" in data["rates"]
    assert "EUR" in data["rates"]
    assert "GBP" in data["rates"]
    assert data["rates"]["USD"] == 1.0
    assert data["rates"]["INR"] > 0

def test_currency_service_cache():
    # Calling it twice should return cached rate
    res1 = fetch_exchange_rates(base="USD", quotes=["EUR", "INR"])
    assert "INR" in res1.rates
    res2 = fetch_exchange_rates(base="USD", quotes=["EUR", "INR"])
    assert res2.is_cached is True

def test_cost_calculation_inr_conversion():
    # Test 1 & 2: 270 USD converted with INR rate
    rates_resp = fetch_exchange_rates(base="USD", quotes=["INR"])
    inr_rate = rates_resp.rates["INR"]
    assert inr_rate > 0
    usd_amount = 270.0
    converted_inr = usd_amount * inr_rate
    assert converted_inr > 20000  # 270 * 85+ is > 20,000

def test_cost_calculation_eur_conversion():
    # Test 4: INR -> EUR conversion logic
    rates_resp = fetch_exchange_rates(base="USD", quotes=["EUR"])
    eur_rate = rates_resp.rates["EUR"]
    assert 0.5 < eur_rate < 1.5
    usd_amount = 270.0
    converted_eur = usd_amount * eur_rate
    assert 100 < converted_eur < 500

def test_non_currency_metrics_unaffected():
    # Test 8 & 9: Verify CPU % and Memory % remain intact numeric metrics
    response = client.get("/api/v1/cost/summary")
    assert response.status_code == 200
    data = response.json()
    assert "estimated_monthly_spend_usd" in data
    assert data["estimated_monthly_spend_usd"] == 270.0
    # Resources have utilization scores as pure percentages
    for res in data["top_cost_resources"]:
        assert isinstance(res["utilization_score"], (int, float))
        assert "monthly_spend_usd" in res
        assert res["monthly_spend_usd"] > 0
