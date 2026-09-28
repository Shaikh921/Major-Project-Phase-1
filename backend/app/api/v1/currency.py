"""
Currency API Router.

Provides exchange rate queries and supported currency catalog for runtime display conversion.
"""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException, status

from backend.app.schemas.currency import (
    ExchangeRatesResponse,
    SupportedCurrenciesResponse,
)
from backend.app.services.currency_service import (
    fetch_exchange_rates,
    get_supported_currencies,
)

router = APIRouter(prefix="/currency", tags=["Currency Conversion"])


@router.get("/supported", response_model=SupportedCurrenciesResponse)
def get_supported():
    """Returns the list of supported display currencies with symbol and formatting metadata."""
    return get_supported_currencies()


@router.get("/rates", response_model=ExchangeRatesResponse)
def get_rates(
    base: str = Query("USD", description="Base currency code (must be USD)"),
    quotes: Optional[str] = Query(None, description="Comma-separated quote currency codes (e.g. INR,EUR,GBP)"),
):
    """
    Returns live or cached exchange rates from Frankfurter API v2 for USD to quote currencies.
    """
    if base.upper() != "USD":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Base currency must be USD.",
        )
    
    quote_list = [q.strip() for q in quotes.split(",")] if quotes else None
    return fetch_exchange_rates(base=base, quotes=quote_list)
