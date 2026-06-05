"""
Market data layer for real estate dashboard.

Sources:
  - OMI static benchmarks (Agenzia delle Entrate, public data, last update H2 2024)
  - Idealista API (free developer tier — needs IDEALISTA_API_KEY + IDEALISTA_SECRET in env)
  - Nominatim (OpenStreetMap geocoding — no key required)
"""

from __future__ import annotations
import os
import time
import threading
import requests

# ── OMI static benchmarks ────────────────────────────────────────────────────
# Source: Agenzia delle Entrate — Osservatorio del Mercato Immobiliare
# Tipologia: abitazioni civili (A), stato conservativo normale (N)
# Values: (sale_min, sale_max) €/sqm  |  (rent_min, rent_max) €/sqm/month
# Fascia: C=centro, S=semicentro, P=periferia

OMI_BENCHMARKS: dict[str, dict[str, dict]] = {
    "Milano": {
        "C": {"sale": (6500, 10500), "rent": (18, 28)},
        "S": {"sale": (4000, 7000),  "rent": (13, 20)},
        "P": {"sale": (2500, 4500),  "rent": (9, 14)},
    },
    "Roma": {
        "C": {"sale": (6000, 12000), "rent": (16, 26)},
        "S": {"sale": (3500, 6500),  "rent": (12, 18)},
        "P": {"sale": (2000, 4000),  "rent": (8, 13)},
    },
    "Firenze": {
        "C": {"sale": (4000, 7000),  "rent": (14, 22)},
        "S": {"sale": (2800, 4500),  "rent": (10, 16)},
        "P": {"sale": (1800, 3200),  "rent": (7, 12)},
    },
    "Bologna": {
        "C": {"sale": (3500, 5500),  "rent": (14, 20)},
        "S": {"sale": (2500, 4000),  "rent": (10, 15)},
        "P": {"sale": (1800, 3000),  "rent": (7, 12)},
    },
    "Venezia": {
        "C": {"sale": (4500, 8000),  "rent": (14, 22)},
        "S": {"sale": (3000, 5500),  "rent": (10, 16)},
        "P": {"sale": (1800, 3500),  "rent": (7, 12)},
    },
    "Torino": {
        "C": {"sale": (2500, 4500),  "rent": (10, 16)},
        "S": {"sale": (1800, 3200),  "rent": (8, 13)},
        "P": {"sale": (1200, 2500),  "rent": (6, 10)},
    },
    "Napoli": {
        "C": {"sale": (2500, 5000),  "rent": (8, 16)},
        "S": {"sale": (1500, 3000),  "rent": (6, 12)},
        "P": {"sale": (800, 2000),   "rent": (4, 8)},
    },
    "Genova": {
        "C": {"sale": (1800, 3500),  "rent": (8, 14)},
        "S": {"sale": (1200, 2500),  "rent": (6, 11)},
        "P": {"sale": (800, 1800),   "rent": (4, 8)},
    },
    "Palermo": {
        "C": {"sale": (1500, 3000),  "rent": (6, 12)},
        "S": {"sale": (1000, 2000),  "rent": (5, 9)},
        "P": {"sale": (600, 1500),   "rent": (3, 7)},
    },
    "Bari": {
        "C": {"sale": (1800, 3500),  "rent": (7, 13)},
        "S": {"sale": (1200, 2500),  "rent": (5, 10)},
        "P": {"sale": (700, 1600),   "rent": (3, 7)},
    },
    "Catania": {
        "C": {"sale": (1200, 2500),  "rent": (5, 10)},
        "S": {"sale": (800, 1800),   "rent": (4, 8)},
        "P": {"sale": (500, 1200),   "rent": (3, 6)},
    },
    "Verona": {
        "C": {"sale": (2500, 4500),  "rent": (10, 16)},
        "S": {"sale": (1800, 3200),  "rent": (8, 13)},
        "P": {"sale": (1200, 2400),  "rent": (6, 10)},
    },
    "Padova": {
        "C": {"sale": (2200, 4000),  "rent": (9, 15)},
        "S": {"sale": (1600, 2800),  "rent": (7, 12)},
        "P": {"sale": (1000, 2000),  "rent": (5, 9)},
    },
    "Trieste": {
        "C": {"sale": (1800, 3200),  "rent": (8, 13)},
        "S": {"sale": (1200, 2400),  "rent": (6, 10)},
        "P": {"sale": (800, 1800),   "rent": (4, 8)},
    },
    "Brescia": {
        "C": {"sale": (2000, 3800),  "rent": (9, 15)},
        "S": {"sale": (1500, 2800),  "rent": (7, 12)},
        "P": {"sale": (900, 2000),   "rent": (5, 9)},
    },
    "Bergamo": {
        "C": {"sale": (2200, 4000),  "rent": (9, 15)},
        "S": {"sale": (1600, 3000),  "rent": (7, 13)},
        "P": {"sale": (1000, 2200),  "rent": (5, 10)},
    },
    "Modena": {
        "C": {"sale": (2000, 3500),  "rent": (9, 14)},
        "S": {"sale": (1500, 2700),  "rent": (7, 11)},
        "P": {"sale": (1000, 2000),  "rent": (5, 9)},
    },
    "Parma": {
        "C": {"sale": (2000, 3500),  "rent": (9, 14)},
        "S": {"sale": (1500, 2700),  "rent": (7, 11)},
        "P": {"sale": (900, 1900),   "rent": (5, 9)},
    },
}

FASCIA_LABELS = {
    "C": "Centro",
    "S": "Semicentro",
    "P": "Periferia",
}


def get_omi_benchmark(city: str, fascia: str = "S") -> dict | None:
    """Return OMI price/rent benchmark for a city + zone. Returns None if not found."""
    match = OMI_BENCHMARKS.get(city, {}).get(fascia)
    if not match:
        return None
    return {
        "city": city,
        "fascia": fascia,
        "fascia_label": FASCIA_LABELS[fascia],
        "sale_min": match["sale"][0],
        "sale_max": match["sale"][1],
        "sale_mid": (match["sale"][0] + match["sale"][1]) // 2,
        "rent_min": match["rent"][0],
        "rent_max": match["rent"][1],
        "rent_mid": (match["rent"][0] + match["rent"][1]) / 2,
        "source": "OMI — Agenzia delle Entrate (H2 2024)",
    }


def list_cities() -> list[str]:
    return sorted(OMI_BENCHMARKS.keys())


# ── Nominatim geocoding ──────────────────────────────────────────────────────

def geocode_city(city: str, country: str = "Italy") -> tuple[float, float] | tuple[None, str]:
    """
    Return (lat, lng) on success.
    Return (None, reason) on failure — reason is 'timeout', 'not_found', or 'error'.
    """
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{city}, {country}", "format": "json", "limit": 1},
            headers={"User-Agent": "AIStudioAccademiaMilano-RealEstateDashboard/1.0"},
            timeout=5,
        )
        results = resp.json()
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
        return None, "not_found"
    except requests.exceptions.Timeout:
        return None, "timeout"
    except Exception:
        return None, "error"


# ── Idealista API ────────────────────────────────────────────────────────────

IDEALISTA_AUTH_URL = "https://api.idealista.com/oauth/authorize"
IDEALISTA_SEARCH_URL = "https://api.idealista.com/3.5/it/search"

_token_cache: dict = {}
_token_lock = threading.Lock()


def _get_idealista_token() -> str | None:
    api_key = os.getenv("IDEALISTA_API_KEY")
    api_secret = os.getenv("IDEALISTA_SECRET")
    if not api_key or not api_secret:
        return None

    with _token_lock:
        now = time.time()
        if _token_cache.get("expires_at", 0) > now + 60:
            return _token_cache["token"]

        try:
            resp = requests.post(
                IDEALISTA_AUTH_URL,
                auth=(api_key, api_secret),
                data={"grant_type": "client_credentials", "scope": "read"},
                timeout=6,
            )
        except requests.exceptions.RequestException:
            return None

        if resp.status_code != 200:
            return None
        data = resp.json()
        _token_cache["token"] = data["access_token"]
        _token_cache["expires_at"] = now + data.get("expires_in", 7200)
        return _token_cache["token"]


def _invalidate_token() -> None:
    with _token_lock:
        _token_cache.clear()


def search_idealista(
    lat: float,
    lng: float,
    operation: str = "sale",
    radius_m: int = 2000,
    max_items: int = 50,
) -> tuple[list[dict], str | None]:
    """
    Search Idealista listings near a coordinate.
    operation: 'sale' or 'rent'
    Returns (listings, error_code) — error_code is None on success,
    or one of: 'auth_error', 'rate_limited', 'timeout', 'network_error', 'api_error'.
    Requires IDEALISTA_API_KEY + IDEALISTA_SECRET env vars.
    """
    token = _get_idealista_token()
    if not token:
        return [], "no_credentials"

    try:
        resp = requests.post(
            IDEALISTA_SEARCH_URL,
            headers={"Authorization": f"Bearer {token}"},
            data={
                "operation": operation,
                "propertyType": "homes",
                "center": f"{lat},{lng}",
                "distance": radius_m,
                "maxItems": max_items,
                "numPage": 1,
                "country": "it",
            },
            timeout=8,
        )
    except requests.exceptions.Timeout:
        return [], "timeout"
    except requests.exceptions.RequestException:
        return [], "network_error"

    if resp.status_code == 401:
        _invalidate_token()
        return [], "auth_error"
    if resp.status_code == 429:
        return [], "rate_limited"
    if resp.status_code != 200:
        return [], "api_error"

    return resp.json().get("elementList", []), None


def summarise_listings(listings: list[dict], sqm_key: str = "size") -> dict | None:
    """Compute price/sqm stats from a list of Idealista listings."""
    if not listings:
        return None
    prices_per_sqm = []
    raw_prices = []
    for l in listings:
        price = l.get("price")
        size = l.get(sqm_key)
        if price and size and size > 0:
            prices_per_sqm.append(price / size)
            raw_prices.append(price)
    if not prices_per_sqm:
        return None
    prices_per_sqm.sort()
    sorted_prices = sorted(raw_prices)
    n = len(prices_per_sqm)
    # True median for both odd and even n
    median_psqm = (prices_per_sqm[(n - 1) // 2] + prices_per_sqm[n // 2]) / 2
    median_price = (sorted_prices[(n - 1) // 2] + sorted_prices[n // 2]) / 2
    return {
        "count": n,
        "price_per_sqm_median": median_psqm,
        "price_per_sqm_min": prices_per_sqm[0],
        "price_per_sqm_max": prices_per_sqm[-1],
        "price_median": median_price,
    }
