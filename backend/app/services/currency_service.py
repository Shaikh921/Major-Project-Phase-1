"""
Currency Service for Real-Time Exchange Rates with In-Memory Caching.

Integrates with Frankfurter API v2 to provide live USD exchange rates
for localized SRE cost display without altering base USD calculations.
"""

import json
import logging
import threading
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from backend.app.schemas.currency import (
    CurrencyMetadata,
    ExchangeRatesResponse,
    SupportedCurrenciesResponse,
)

logger = logging.getLogger(__name__)

FRANKFURTER_API_BASE = "https://api.frankfurter.dev/v2"
DEFAULT_CACHE_TTL_SECONDS = 3600  # 1 Hour

SUPPORTED_CURRENCIES: List[CurrencyMetadata] = [
    CurrencyMetadata(code="USD", name="US Dollar", symbol="$", locale="en-US", decimal_digits=2),
    CurrencyMetadata(code="INR", name="Indian Rupee", symbol="₹", locale="en-IN", decimal_digits=2),
    CurrencyMetadata(code="EUR", name="Euro", symbol="€", locale="de-DE", decimal_digits=2),
    CurrencyMetadata(code="GBP", name="British Pound", symbol="£", locale="en-GB", decimal_digits=2),
    CurrencyMetadata(code="JPY", name="Japanese Yen", symbol="¥", locale="ja-JP", decimal_digits=0),
    CurrencyMetadata(code="CAD", name="Canadian Dollar", symbol="CA$", locale="en-CA", decimal_digits=2),
    CurrencyMetadata(code="AUD", name="Australian Dollar", symbol="A$", locale="en-AU", decimal_digits=2),
    CurrencyMetadata(code="SGD", name="Singapore Dollar", symbol="S$", locale="en-SG", decimal_digits=2),
    CurrencyMetadata(code="AED", name="UAE Dirham", symbol="AED", locale="ar-AE", decimal_digits=2),
    CurrencyMetadata(code="CHF", name="Swiss Franc", symbol="CHF", locale="de-CH", decimal_digits=2),
]

SUPPORTED_CODES = {c.code for c in SUPPORTED_CURRENCIES}


DEFAULT_FALLBACK_RATES: Dict[str, float] = {
    "USD": 1.0,
    "INR": 86.5,
    "EUR": 0.92,
    "GBP": 0.78,
    "JPY": 152.0,
    "CAD": 1.38,
    "AUD": 1.54,
    "SGD": 1.34,
    "AED": 3.67,
    "CHF": 0.89,
}


class CurrencyRateCache:
    """Thread-safe in-memory cache for exchange rates."""

    def __init__(self, ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS):
        self._lock = threading.Lock()
        self._rates: Dict[str, float] = dict(DEFAULT_FALLBACK_RATES)
        self._rate_date: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self._fetched_at: Optional[datetime] = None
        self._ttl = timedelta(seconds=ttl_seconds)

    def is_fresh(self) -> bool:
        with self._lock:
            if not self._fetched_at:
                return False
            return (datetime.now(timezone.utc) - self._fetched_at) < self._ttl

    def get_rates(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "rates": dict(self._rates),
                "rate_date": self._rate_date,
                "fetched_at": self._fetched_at or datetime.now(timezone.utc),
                "is_cached": self._fetched_at is not None,
            }

    def set_rates(self, rates: Dict[str, float], rate_date: str):
        with self._lock:
            self._rates.update(rates)
            self._rates["USD"] = 1.0
            self._rate_date = rate_date
            self._fetched_at = datetime.now(timezone.utc)


_cache = CurrencyRateCache()


def get_supported_currencies() -> SupportedCurrenciesResponse:
    """Returns metadata for all supported display currencies."""
    return SupportedCurrenciesResponse(
        base_currency="USD",
        currencies=SUPPORTED_CURRENCIES,
    )


def fetch_exchange_rates(
    base: str = "USD",
    quotes: Optional[List[str]] = None,
) -> ExchangeRatesResponse:
    """
    Fetches exchange rates from Frankfurter v2 with in-memory caching and fallback.
    """
    normalized_base = (base or "USD").upper().strip()
    if normalized_base != "USD":
        raise ValueError("Base currency must be USD")

    requested_quotes = [q.upper().strip() for q in (quotes or list(SUPPORTED_CODES)) if q.strip()]

    # 1. Return fresh cached rates if available
    if _cache.is_fresh():
        cache_data = _cache.get_rates()
        all_cached = cache_data["rates"]
        # Check if all requested quotes are in cache
        if all(q in all_cached for q in requested_quotes):
            filtered = {q: all_cached[q] for q in requested_quotes if q in all_cached}
            filtered["USD"] = 1.0
            return ExchangeRatesResponse(
                base="USD",
                rates=filtered,
                rate_date=cache_data["rate_date"],
                source="Frankfurter (Cache)",
                is_cached=True,
                fetched_at=cache_data["fetched_at"],
            )

    # 2. Query Frankfurter API v2
    quotes_param = ",".join(requested_quotes)
    url = f"{FRANKFURTER_API_BASE}/rates?base=USD&quotes={quotes_param}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "CloudOps-Intel/3.0.0 (SRE Command Center)"},
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                raw = response.read().decode("utf-8")
                data = json.loads(raw)
                # Frankfurter v2 returns a list of items: [{"date": "...", "base": "USD", "quote": "INR", "rate": 95.8}, ...]
                parsed_rates: Dict[str, float] = {"USD": 1.0}
                latest_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

                if isinstance(data, list):
                    for item in data:
                        q = item.get("quote")
                        r = item.get("rate")
                        if q and r is not None:
                            parsed_rates[q] = float(r)
                            latest_date = item.get("date", latest_date)
                elif isinstance(data, dict):
                    # Fallback dict format if API returns object
                    rates_dict = data.get("rates", {})
                    for q, r in rates_dict.items():
                        parsed_rates[q] = float(r)
                    latest_date = data.get("date", latest_date)

                _cache.set_rates(parsed_rates, latest_date)
                now_utc = datetime.now(timezone.utc)

                filtered = {q: parsed_rates[q] for q in requested_quotes if q in parsed_rates}
                filtered["USD"] = 1.0
                return ExchangeRatesResponse(
                    base="USD",
                    rates=filtered,
                    rate_date=latest_date,
                    source="Frankfurter",
                    is_cached=False,
                    fetched_at=now_utc,
                )

    except Exception as exc:
        logger.warning("Failed to fetch rates from Frankfurter API: %s. Using fallback cache.", exc)

    # 3. Fallback: Return stale cache if available, or base USD
    cache_data = _cache.get_rates()
    cached_rates = cache_data["rates"]
    filtered_fallback = {q: cached_rates.get(q, 1.0) for q in requested_quotes if q in cached_rates}
    filtered_fallback["USD"] = 1.0

    return ExchangeRatesResponse(
        base="USD",
        rates=filtered_fallback,
        rate_date=cache_data["rate_date"],
        source="Frankfurter (Fallback)",
        is_cached=True,
        fetched_at=cache_data["fetched_at"],
    )
