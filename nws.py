#!/usr/bin/env python3
"""NWS (National Weather Service) data fetcher.
All functions use the free, public NWS API (no API key required).
"""
import json
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
