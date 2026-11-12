"""
Market data layer for real estate dashboard.

Sources:
  - OMI benchmarks: config/omi_benchmarks.json (Agenzia delle Entrate, H2 2024)
  - Idealista API (free developer tier — needs IDEALISTA_API_KEY + IDEALISTA_SECRET in env)
  - Nominatim (OpenStreetMap geocoding — no key required)
"""

from __future__ import annotations
import json
import os
import time
import threading
from pathlib import Path
import requests

# ── OMI benchmarks — loaded from config, not hardcoded ──────────────────────
_OMI_PATH = Path(__file__).resolve().parents[1] / "config" / "omi_benchmarks.json"
with open(_OMI_PATH) as _f:
    _OMI_RAW = json.load(_f)

OMI_BENCHMARKS: dict[str, dict] = {k: v for k, v in _OMI_RAW.items() if not k.startswith("_")}
FASCIA_LABELS: dict[str, str] = _OMI_RAW["_meta"]["zones"]

# ── City coordinates (lat, lng) for map rendering ───────────────────────────
CITY_COORDS: dict[str, tuple[float, float]] = {
    "Milano":  (45.4654,  9.1859),
    "Roma":    (41.9028, 12.4964),
    "Firenze": (43.7696, 11.2558),
    "Bologna": (44.4949, 11.3426),
    "Venezia": (45.4408, 12.3155),
    "Torino":  (45.0703,  7.6869),
    "Napoli":  (40.8518, 14.2681),
    "Genova":  (44.4056,  8.9463),
    "Palermo": (38.1157, 13.3615),
    "Bari":    (41.1171, 16.8719),
    "Catania": (37.5079, 15.0830),
    "Verona":  (45.4384, 10.9916),
    "Padova":  (45.4064, 11.8768),
    "Trieste": (45.6495, 13.7768),
    "Brescia": (45.5416, 10.2118),
    "Bergamo": (45.6983,  9.6773),
    "Modena":  (44.6471, 10.9252),
    "Parma":   (44.8015, 10.3279),
}


def get_omi_benchmark(city: str, fascia: str = "S") -> dict | None:
    """Return OMI price/rent benchmark for a city + zone. Returns None if not found."""
    data = OMI_BENCHMARKS.get(city, {}).get(fascia)
    if not data:
        return None
    sale_min, sale_max = data["sale"]
    rent_min, rent_max = data["rent"]
    return {
        "city": city,
        "fascia": fascia,
        "fascia_label": FASCIA_LABELS.get(fascia, fascia),
        "sale_min": sale_min,
        "sale_max": sale_max,
        "sale_mid": (sale_min + sale_max) // 2,
        "rent_min": rent_min,
        "rent_max": rent_max,
        "rent_mid": (rent_min + rent_max) / 2,
        "source": f"OMI — Agenzia delle Entrate ({_OMI_RAW['_meta']['edition']})",
    }


def list_cities() -> list[str]:
    return sorted(OMI_BENCHMARKS.keys())


def city_map_data(fascia: str = "S", ref_sqm: int = 70) -> list[dict]:
    """
    Return a list of dicts for all cities with lat/lng + yield metrics,
    ready for a Plotly/pydeck map.  ref_sqm is used to compute implied prices.
    """
    rows = []
    for city, (lat, lng) in CITY_COORDS.items():
        b = get_omi_benchmark(city, fascia)
        if not b:
            continue
        gross_yield = b["rent_mid"] * 12 / b["sale_mid"] * 100 if b["sale_mid"] > 0 else 0
        rows.append({
            "city":          city,
            "lat":           lat,
            "lon":           lng,
            "gross_yield":   round(gross_yield, 2),
            "sale_mid":      b["sale_mid"],
            "rent_mid":      b["rent_mid"],
            "implied_price": b["sale_mid"] * ref_sqm,
            "implied_rent":  round(b["rent_mid"] * ref_sqm),
        })
    return rows


# ── Nominatim geocoding ──────────────────────────────────────────────────────

def geocode_city(city: str, country: str = "Italy") -> tuple[float, float] | tuple[None, str]:
    """
    Return (lat, lng) on success.
    Return (None, reason) on failure — reason: 'timeout', 'not_found', or 'error'.
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

IDEALISTA_AUTH_URL   = "https://api.idealista.com/oauth/authorize"
IDEALISTA_SEARCH_URL = "https://api.idealista.com/3.5/it/search"

_token_cache: dict = {}
_token_lock = threading.Lock()


def _get_idealista_token() -> str | None:
    api_key    = os.getenv("IDEALISTA_API_KEY")
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
        _token_cache["token"]      = data["access_token"]
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
    Returns (listings, error_code) — error_code None on success, or one of:
    'no_credentials', 'auth_error', 'rate_limited', 'timeout', 'network_error', 'api_error'.
    """
    token = _get_idealista_token()
    if not token:
        return [], "no_credentials"

    try:
        resp = requests.post(
            IDEALISTA_SEARCH_URL,
            headers={"Authorization": f"Bearer {token}"},
            data={
                "operation":    operation,
                "propertyType": "homes",
                "center":       f"{lat},{lng}",
                "distance":     radius_m,
                "maxItems":     max_items,
                "numPage":      1,
                "country":      "it",
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
    prices_per_sqm, raw_prices = [], []
    for listing in listings:
        price = listing.get("price")
        size  = listing.get(sqm_key)
        if price and size and size > 0:
            prices_per_sqm.append(price / size)
            raw_prices.append(price)
    if not prices_per_sqm:
        return None
    prices_per_sqm.sort()
    sorted_prices = sorted(raw_prices)
    n = len(prices_per_sqm)
    median_psqm  = (prices_per_sqm[(n - 1) // 2] + prices_per_sqm[n // 2]) / 2
    median_price = (sorted_prices[(n - 1) // 2]   + sorted_prices[n // 2]) / 2
    return {
        "count":                n,
        "price_per_sqm_median": median_psqm,
        "price_per_sqm_min":    prices_per_sqm[0],
        "price_per_sqm_max":    prices_per_sqm[-1],
        "price_median":         median_price,
    }
