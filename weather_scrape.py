#!/usr/bin/env python3
import json
import os
import hashlib
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path
from urllib.request import urlopen, Request

LAT, LON = 33.349, -96.548
BASE_DIR = Path.home() / "Developer" / "weather-agent"
DATA_DIR = BASE_DIR / "data"
LOG_FILE = BASE_DIR / "logs" / "weather-scrape.log"
HEADERS = {"User-Agent": "weather-scrape/1.0 (personal use)"}
TZ = ZoneInfo("America/Chicago")
RETENTION_DAYS = 7


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def fetch(url):
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_afd():
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
        log(f"AFD fetch error: {e}")
        return None


def get_alerts():
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
        log(f"Alerts fetch error: {e}")
        return []


def get_forecast():
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
        log(f"Forecast fetch error: {e}")
        return []


def get_hourly():
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
        log(f"Hourly fetch error: {e}")
        return []


def content_hash(afd, alerts, forecast, hourly):
    """Hash the meaningful data to detect duplicates."""
    # Use key mutable fields: AFD issued time, alert count + event names, forecast first period name+temp, hourly first 3 temps
    parts = []
    if afd:
        parts.append(afd.get("issued", ""))
    parts.append(str(len(alerts)))
    for a in alerts:
        parts.append(a.get("event", ""))
        parts.append(a.get("effective", ""))
    if forecast:
        parts.append(forecast[0].get("name", ""))
        parts.append(str(forecast[0].get("temp", "")))
    for h in hourly[:3]:
        parts.append(str(h.get("temp", "")))
        parts.append(str(h.get("precip", "")))
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def cleanup_old():
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    removed = 0
    for f in DATA_DIR.glob("*.json"):
        try:
            date_str = f.stem
            file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            if file_date < cutoff:
                f.unlink()
                removed += 1
        except Exception:
            continue
    if removed:
        log(f"Cleaned up {removed} old data file(s)")


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(TZ)
    date_str = now.strftime("%Y-%m-%d")
    data_file = DATA_DIR / f"{date_str}.json"

    afd = get_afd()
    alerts = get_alerts()
    forecast = get_forecast()
    hourly = get_hourly()

    new_hash = content_hash(afd, alerts, forecast, hourly)

    # Check if existing file has identical data
    if data_file.exists():
        try:
            with open(data_file) as f:
                existing = json.load(f)
            existing_hash = existing.get("data_hash", "")
            if existing_hash == new_hash:
                log(f"Data unchanged (hash {new_hash}). Skipping.")
                cleanup_old()
                return
        except Exception:
            pass

    log(f"Data changed (hash {new_hash}). Saving...")

    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "data_hash": new_hash,
        "location": {"lat": LAT, "lon": LON, "name": "Anna, TX"},
        "afd": afd,
        "alerts": alerts,
        "forecast": forecast,
        "hourly": hourly,
    }

    with open(data_file, "w") as f:
        json.dump(payload, f, indent=2)

    log(f"Saved {data_file}  alerts={len(alerts)} forecast={len(forecast)} hourly={len(hourly)}")
    cleanup_old()


if __name__ == "__main__":
    main()
