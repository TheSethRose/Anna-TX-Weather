#!/usr/bin/env python3
"""Main weather scraper - orchestrates all data sources.
Imports from modular source files: nws.py, cwop.py, mping.py, rainviewer.py
"""
import json
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

# Import from modular sources
from nws import get_afd, get_alerts, get_forecast, get_hourly, get_alert_polygons, get_grid_details, get_local_products
from cwop import get_cwop_stations
from mping import fetch_mping, MPING_ENABLED, MPING_API_KEY
from rainviewer import get_rainviewer_data
from spc import get_spc_products

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOG_FILE = BASE_DIR / "logs" / "weather-scrape.log"
TZ = __import__('zoneinfo').ZoneInfo("America/Chicago")
RETENTION_DAYS = 7


def download_file(url, path):
    if not url:
        return None
    req = Request(url, headers={"User-Agent": "weather-scrape/1.0 (personal use)"})
    try:
        with urlopen(req, timeout=20) as resp:
            if resp.status != 200:
                return None
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(resp.read())
            return str(path)
    except Exception:
        return None

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def content_hash(afd, alerts, forecast, hourly, cwop_stations=None, mping_reports=None, alert_polygons=None, rainviewer_data=None, spc_products=None, grid_details=None, local_products=None):
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
    # Add alert polygons
    if alert_polygons:
        for p in alert_polygons:
            parts.append(p.get("event", ""))
            parts.append(p.get("severity", ""))
    # Add RainViewer data
    if rainviewer_data:
        parts.append(rainviewer_data.get("latest_frame_time", ""))
        parts.append(str(rainviewer_data.get("has_recent_activity", "")))
    if spc_products:
        for feed in spc_products.values():
            if isinstance(feed, dict):
                parts.append(feed.get("updated", ""))
                parts.append(str(len(feed.get("items", []))))
    if grid_details:
        parts.append(str(grid_details.get("qpf_next_24h_inches", "")))
        parts.append(str(grid_details.get("max_thunder_probability_24h", "")))
        parts.append(str(grid_details.get("max_wind_gust_mph_24h", "")))
    if local_products:
        for products in local_products.values():
            for product in products[:2]:
                parts.append(product.get("issued", ""))
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
    grid_details = get_grid_details()
    local_products = get_local_products()
    cwop_stations = get_cwop_stations()
    alert_polygons = get_alert_polygons()
    rainviewer_data = get_rainviewer_data()
    if rainviewer_data:
        radar_path = download_file(
            rainviewer_data.get("latest_tile_url") or rainviewer_data.get("latest_frame_url"),
            DATA_DIR / "radar" / f"{date_str}-latest.png",
        )
        if radar_path:
            rainviewer_data["latest_image_path"] = radar_path
    spc_products = get_spc_products()
    source_status = {
        "afd": "ok" if afd else "empty",
        "alerts": "ok",
        "forecast": "ok" if forecast else "empty",
        "hourly": "ok" if hourly else "empty",
        "grid_details": "ok" if grid_details else "empty",
        "local_products": "ok" if local_products else "empty",
        "cwop": "ok" if cwop_stations else "empty",
        "alert_polygons": "ok",
        "rainviewer": "ok" if rainviewer_data else "empty",
        "spc": "ok" if spc_products else "empty",
        "mping": "disabled",
    }
    
    mping_reports = []
    if MPING_ENABLED and MPING_API_KEY:
        mping_reports = fetch_mping()
        source_status["mping"] = "ok" if mping_reports else "empty"
    elif MPING_ENABLED:
        log("[mPING] Enabled but no API key set. Skipping.")
        source_status["mping"] = "missing_api_key"

    if not forecast or not hourly:
        log("Core NWS forecast/hourly data missing. Refusing to overwrite current data file.")
        cleanup_old()
        return
    
    new_hash = content_hash(afd, alerts, forecast, hourly, cwop_stations, mping_reports, alert_polygons, rainviewer_data, spc_products, grid_details, local_products)
    
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
        "source_status": source_status,
        "afd": afd,
        "alerts": alerts,
        "forecast": forecast,
        "hourly": hourly,
        "grid_details": grid_details,
        "local_products": local_products,
        "cwop_updated": datetime.now(timezone.utc).isoformat(),
        "cwop_stations": cwop_stations,
        "alert_polygons": alert_polygons,
        "rainviewer": rainviewer_data,
        "spc": spc_products,
    }
    
    if mping_reports:
        payload["mping_updated"] = datetime.now(timezone.utc).isoformat()
        payload["mping_reports"] = mping_reports
    
    with open(data_file, "w") as f:
        json.dump(payload, f, indent=2)
    
    spc_count = sum(len(feed.get("items", [])) for feed in spc_products.values() if isinstance(feed, dict))
    local_count = sum(len(products) for products in local_products.values())
    log(f"Saved {data_file}  alerts={len(alerts)} forecast={len(forecast)} hourly={len(hourly)} grid={'Y' if grid_details else 'N'} local_products={local_count} cwop={len(cwop_stations)} mping={len(mping_reports)} alert_poly={len(alert_polygons)} rainviewer={'Y' if rainviewer_data else 'N'} spc={spc_count}")
    cleanup_old()

if __name__ == "__main__":
    main()
