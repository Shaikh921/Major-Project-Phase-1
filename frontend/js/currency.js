/**
 * Centralized Currency Display & Conversion Engine for CloudOps Intel.
 * 
 * Manages display currency selection, live rate synchronization via Frankfurter backend proxy,
 * Intl.NumberFormat localized formatting, and localStorage preference persistence.
 */

export const SUPPORTED_CURRENCIES = [
  { code: "USD", name: "US Dollar", symbol: "$", locale: "en-US", decimal_digits: 2, defaultRate: 1.0 },
  { code: "INR", name: "Indian Rupee", symbol: "₹", locale: "en-IN", decimal_digits: 2, defaultRate: 86.50 },
  { code: "EUR", name: "Euro", symbol: "€", locale: "de-DE", decimal_digits: 2, defaultRate: 0.92 },
  { code: "GBP", name: "British Pound", symbol: "£", locale: "en-GB", decimal_digits: 2, defaultRate: 0.78 },
  { code: "JPY", name: "Japanese Yen", symbol: "¥", locale: "ja-JP", decimal_digits: 0, defaultRate: 152.0 },
  { code: "CAD", name: "Canadian Dollar", symbol: "CA$", locale: "en-CA", decimal_digits: 2, defaultRate: 1.38 },
  { code: "AUD", name: "Australian Dollar", symbol: "A$", locale: "en-AU", decimal_digits: 2, defaultRate: 1.52 },
  { code: "SGD", name: "Singapore Dollar", symbol: "S$", locale: "en-SG", decimal_digits: 2, defaultRate: 1.34 },
  { code: "AED", name: "UAE Dirham", symbol: "AED", locale: "ar-AE", decimal_digits: 2, defaultRate: 3.67 },
  { code: "CHF", name: "Swiss Franc", symbol: "CHF", locale: "de-CH", decimal_digits: 2, defaultRate: 0.88 },
];

const CURRENCY_MAP = new Map(SUPPORTED_CURRENCIES.map(c => [c.code, c]));
const DEFAULT_RATES = Object.fromEntries(SUPPORTED_CURRENCIES.map(c => [c.code, c.defaultRate]));

class CurrencyManager {
  constructor() {
    const saved = localStorage.getItem("cloudops_display_currency");
    this.displayCurrency = (saved && CURRENCY_MAP.has(saved)) ? saved : "USD";
    this.baseCurrency = "USD";
    this.rates = { ...DEFAULT_RATES, USD: 1.0 };
    this.rateDate = new Date().toISOString().split("T")[0];
    this.rateSource = "Frankfurter";
    this.isCached = false;
    this.listeners = new Set();
    this.inflightPromise = null;
  }

  getCurrencyMeta(code = this.displayCurrency) {
    return CURRENCY_MAP.get(code) || CURRENCY_MAP.get("USD");
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notify() {
    for (const listener of this.listeners) {
      try {
        listener(this);
      } catch (err) {
        console.error("Error in currency listener:", err);
      }
    }
  }

  async setDisplayCurrency(currencyCode) {
    const code = String(currencyCode || "USD").toUpperCase().trim();
    if (!CURRENCY_MAP.has(code)) {
      console.warn(`Unsupported currency: ${code}, falling back to USD`);
      this.displayCurrency = "USD";
    } else {
      this.displayCurrency = code;
    }

    localStorage.setItem("cloudops_display_currency", this.displayCurrency);

    // Immediately notify listeners so UI updates instantly with available rates
    this.notify();

    // Trigger background rate refresh
    if (this.displayCurrency !== "USD") {
      this.refreshRates([this.displayCurrency]);
    }
  }

  async refreshRates(quotes = null) {
    if (this.inflightPromise) {
      try {
        await this.inflightPromise;
      } catch {
        // ignore
      }
    }

    const quoteList = quotes || SUPPORTED_CURRENCIES.map(c => c.code);
    const queryParam = quoteList.join(",");
    const url = `/api/v1/currency/rates?base=USD&quotes=${encodeURIComponent(queryParam)}`;

    this.inflightPromise = (async () => {
      try {
        const resp = await fetch(url);
        if (resp.ok) {
          const data = await resp.json();
          if (data && data.rates) {
            this.rates = { ...this.rates, ...data.rates, USD: 1.0 };
            this.rateDate = data.rate_date || this.rateDate;
            this.rateSource = data.source || "Frankfurter";
            this.isCached = data.is_cached;
          }
        }
      } catch (err) {
        console.warn("Failed to fetch live exchange rates, keeping current rates", err);
      } finally {
        this.inflightPromise = null;
        this.notify();
      }
    })();

    return this.inflightPromise;
  }

  /**
   * Convert and format a base USD monetary value into the active display currency.
   * 
   * @param {number} amountUsd - Base monetary value in USD
   * @param {object} options - Optional overrides (currency, showCode, maxDecimals)
   * @returns {string} Localized formatted currency string (e.g. "$270.00", "₹23,355.00")
   */
  format(amountUsd, options = {}) {
    const num = Number(amountUsd);
    if (isNaN(num)) return "—";

    const targetCode = options.currency || this.displayCurrency;
    const meta = this.getCurrencyMeta(targetCode);
    const rate = this.rates[targetCode] || meta.defaultRate || 1.0;
    const convertedValue = num * rate;

    const decimals = options.maxDecimals !== undefined ? options.maxDecimals : meta.decimal_digits;

    try {
      const formatter = new Intl.NumberFormat(meta.locale, {
        style: "currency",
        currency: meta.code,
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });
      return formatter.format(convertedValue);
    } catch {
      return `${meta.symbol}${convertedValue.toFixed(decimals)}`;
    }
  }

  getRateMetadata() {
    const code = this.displayCurrency;
    const meta = this.getCurrencyMeta(code);
    const rate = this.rates[code] || meta.defaultRate || 1.0;
    return {
      baseCurrency: "USD",
      displayCurrency: code,
      rate: rate,
      rateFormatted: `1 USD = ${this.format(1, { currency: code })}`,
      rateDate: this.rateDate,
      source: this.rateSource,
      isConverted: code !== "USD",
    };
  }
}

export const currencyManager = new CurrencyManager();

// Pre-fetch initial rates on boot
currencyManager.refreshRates();
