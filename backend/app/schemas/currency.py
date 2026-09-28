"""
Currency Schemas & Pydantic Data Models.
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class CurrencyMetadata(BaseModel):
    code: str
    name: str
    symbol: str
    locale: str
    decimal_digits: int = 2


class ExchangeRateItem(BaseModel):
    quote: str
    rate: float
    date: str


class ExchangeRatesResponse(BaseModel):
    base: str = "USD"
    rates: Dict[str, float]
    rate_date: str
    source: str = "Frankfurter"
    is_cached: bool = False
    fetched_at: datetime


class SupportedCurrenciesResponse(BaseModel):
    base_currency: str = "USD"
    currencies: List[CurrencyMetadata]
