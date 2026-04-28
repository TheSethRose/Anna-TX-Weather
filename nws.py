#!/usr/bin/env python3
"""NWS (National Weather Service) data fetcher.
All functions use the free, public NWS API (no API key required).
"""
import json
import re
from datetime import datetime, timezone
from urllib.request import urlopen, Request

LAT, LON = 33.349, -96.548
HEADERS = {"User-Agent": "weather-scrape/1.0 (personal use)"}

def fetch(url):
    """Fetch JSON from URL with proper headers."""
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_afd():
    """Get Area Forecast Discussion from NWS Fort Worth."""
    try:
        data = fetch("https://api.weather.gov/products/types/AFD/locations/FWD")
        if not data.get("@graph"):
            return None
        latest = data["@graph"][0]
        product_url = latest.get("@id")
        if not product_url:
            return None
        product = fetch(product_url)
        return {
            "issued": product.get("issuanceTime", ""),
            "title": product.get("productName", ""),
            "text": product.get("productText", ""),
        }
    except Exception as e:
        return None

def get_alerts():
    """Get active alerts for Anna, TX point."""
    try:
        data = fetch(f"https://api.weather.gov/alerts/active?point={LAT},{LON}")
        alerts = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            alerts.append({
                "event": props.get("event", ""),
                "severity": props.get("severity", ""),
                "urgency": props.get("urgency", ""),
                "headline": props.get("headline", ""),
                "description": props.get("description", ""),
                "instruction": props.get("instruction", ""),
                "effective": props.get("effective", ""),
                "expires": props.get("expires", ""),
            })
        return alerts
    except Exception as e:
        return []

def get_forecast():
    """Get 7-day forecast periods."""
    try:
        points = fetch(f"https://api.weather.gov/points/{LAT},{LON}")
        forecast_url = points["properties"]["forecast"]
        data = fetch(forecast_url)
        periods = []
        for p in data["properties"]["periods"][:7]:
            periods.append({
                "name": p.get("name", ""),
                "start": p.get("startTime", ""),
                "end": p.get("endTime", ""),
                "temp": p.get("temperature", ""),
                "temp_unit": p.get("temperatureUnit", ""),
                "wind": p.get("windSpeed", ""),
                "wind_dir": p.get("windDirection", ""),
                "forecast": p.get("detailedForecast", ""),
                "short": p.get("shortForecast", ""),
                "precip": p.get("probabilityOfPrecipitation", {}).get("value", ""),
            })
        return periods
    except Exception as e:
        return []

def get_hourly():
    """Get next 24 hours of hourly data."""
    try:
        points = fetch(f"https://api.weather.gov/points/{LAT},{LON}")
        hourly_url = points["properties"]["forecastHourly"]
        data = fetch(hourly_url)
        hours = []
        for p in data["properties"]["periods"][:24]:
            hours.append({
                "time": p.get("startTime", ""),
                "temp": p.get("temperature", ""),
                "temp_unit": p.get("temperatureUnit", ""),
                "wind": p.get("windSpeed", ""),
                "wind_dir": p.get("windDirection", ""),
                "short": p.get("shortForecast", ""),
                "precip": p.get("probabilityOfPrecipitation", {}).get("value", ""),
                "humidity": p.get("relativeHumidity", {}).get("value", ""),
                "dewpoint": p.get("dewpoint", {}).get("value", ""),
            })
        return hours
    except Exception as e:
        return []

def get_alert_polygons():
    """Get alert polygons (geographic shapes) for active alerts.
    Free, part of NWS API - no additional key needed.
    """
    try:
        data = fetch(f"https://api.weather.gov/alerts/active?point={LAT},{LON}")
        alerts_with_geom = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            geom = feature.get("geometry")
            alerts_with_geom.append({
                "event": props.get("event", ""),
                "severity": props.get("severity", ""),
                "headline": props.get("headline", ""),
                "geometry": geom,
            })
        return alerts_with_geom
    except Exception as e:
        return []

def _first_values(series, limit=12):
    values = (series or {}).get("values", [])
    return values[:limit]

def _mm_to_inches(value):
    if value is None:
        return None
    return round(float(value) / 25.4, 2)

def _kmh_to_mph(value):
    if value is None:
        return None
    return round(float(value) * 0.621371)

def get_grid_details():
    """Get point-specific grid details not present in the plain forecast."""
    try:
        points = fetch(f"https://api.weather.gov/points/{LAT},{LON}")
        grid_url = points["properties"]["forecastGridData"]
        data = fetch(grid_url)
        props = data.get("properties", {})

        qpf_values = _first_values(props.get("quantitativePrecipitation"), 8)
        thunder_values = _first_values(props.get("probabilityOfThunder"), 12)
        gust_values = _first_values(props.get("windGust"), 12)
        weather_values = _first_values(props.get("weather"), 8)
        hazards_values = _first_values(props.get("hazards"), 8)

        qpf_total = sum(float(v.get("value") or 0) for v in qpf_values[:4])
        max_thunder = max((v.get("value") or 0 for v in thunder_values), default=0)
        max_gust = max((v.get("value") or 0 for v in gust_values), default=0)

        return {
            "updated": props.get("updateTime", ""),
            "valid_times": props.get("validTimes", ""),
            "qpf_next_24h_inches": _mm_to_inches(qpf_total),
            "max_thunder_probability_24h": max_thunder,
            "max_wind_gust_mph_24h": _kmh_to_mph(max_gust),
            "qpf_windows": [
                {"validTime": v.get("validTime", ""), "inches": _mm_to_inches(v.get("value"))}
                for v in qpf_values[:6]
            ],
            "thunder_windows": thunder_values[:8],
            "weather_windows": weather_values,
            "hazards": hazards_values,
        }
    except Exception as e:
        return {}

def _condense_text(text, max_chars=1800):
    text = re.sub(r"\n{3,}", "\n\n", text or "").strip()
    return text[:max_chars].rstrip()

def _get_latest_products(product_code, limit=3):
    data = fetch(f"https://api.weather.gov/products/types/{product_code}/locations/FWD")
    products = []
    for item in data.get("@graph", [])[:limit]:
        product_url = item.get("@id")
        if not product_url:
            continue
        product = fetch(product_url)
        products.append({
            "id": item.get("id", ""),
            "code": product_code,
            "name": item.get("productName", ""),
            "issued": item.get("issuanceTime", ""),
            "text": _condense_text(product.get("productText", "")),
        })
    return products

def get_local_products():
    """Get recent FWD products that add detail without duplicating alerts."""
    products = {}
    for code, limit in {"LSR": 8, "SPS": 3, "HWO": 1}.items():
        try:
            products[code.lower()] = _get_latest_products(code, limit)
        except Exception:
            products[code.lower()] = []
    return products
