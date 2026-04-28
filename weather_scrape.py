#!/usr/bin/env python3
"""Main weather scraper - orchestrates all data sources.
Imports from modular source files: nws.py, cwop.py, mping.py
"""
import json
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Import from modular sources
from nws import get_afd, get_alerts, get_forecast, get_hourly, get_alert_polygons
from cwop import get_cwop_stations
from mping import fetch_mping, MPING_ENABLED, MPING_API_KEY

BSE_DIR = Path.home() / "Developer" / "weather-agent"
DATA_DIR = BSE_DIR / "data"
LOG_FILE = BSE_DIR / "logs" / "weather-scrape.log"
TZ = __import__('zoneinfo').ZoneInfo("America/Chicago")
RETENTION_DAYS = 7

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def content_hash(afd, alerts, forecast, hourly, cwop_stations=None, mping_reports=None):
    """Hash the meaningful data to detect duplicates."""
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
    # Add CWOP stations
    if cwop_stations:
        for s in cwop_stations[:3]:
            parts.append(str(s.get("temp", "")))
            parts.append(str(s.get("humidity", "")))
    # Add mPING reports
    if mping_reports:
        for r in mping_reports:
            parts.append(r.get("time", ""))
            parts.append(r.get("type", ""))
            parts.append(str(r.get("hail_size", "")))
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
    
    # Fetch from all sources
    afd = get_afd()
    alerts = get_alerts()
    forecast = get_forecast()
    hourly = get_hourly()
    cwop_stations = get_cwop_stations()
    
    mping_reports = []
    if MPING_ENABLED and MPING_API_KEY:
        mping_reports = fetch_mping()
    elif MPING_ENABLED:
        log("[mPING] Enabled but no API key set. Skipping.")
    
    new_hash = content_hash(afd, alerts, forecast, hourly, cwop_stations, mping_reports)
    
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
        "location": {"lat": 33.349, "lon": -96.548, "name": "Anna, TX"},
        "afd": afd,
        "alerts": alerts,
        "forecast": forecast,
        "hourly": hourly,
        "cwop_updated": datetime.now(timezone.utc).isoformat(),
        "cwop_stations": cwop_stations,
    }
    
    if mping_reports:
        payload["mping_updated"] = datetime.now(timezone.utc).isoformat()
        payload["mping_reports"] = mping_reports
    
    with open(data_file, "w") as f:
        json.dump(payload, f, indent=2)
    
    log(f"Saved {data_file}  alerts={len(alerts)} forecast={len(forecast)} hourly={len(hourly)} cwop={len(cwop_stations)} mping={len(mping_reports)}")
    cleanup_old()

if __name__ == "__main__":
    main()
