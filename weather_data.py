#!/usr/bin/env python3
"""Read the latest scraper output for Hermes or humans.

This script does not fetch weather data. `weather_scrape.py` owns updates.
"""
import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
TZ = ZoneInfo("America/Chicago")


def load_today():
    now = datetime.now(TZ)
    data_file = DATA_DIR / f"{now:%Y-%m-%d}.json"
    if not data_file.exists():
        return data_file, None
    with open(data_file) as f:
        return data_file, json.load(f)


def parse_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def freshness(data, max_age_minutes):
    fetched_at = parse_timestamp(data.get("fetched_at"))
    if not fetched_at:
        return {"fresh": False, "age_minutes": None, "reason": "missing fetched_at"}
    age = datetime.now(fetched_at.tzinfo) - fetched_at
    return {
        "fresh": age <= timedelta(minutes=max_age_minutes),
        "age_minutes": round(age.total_seconds() / 60, 1),
        "reason": None,
    }


def compact_for_hermes(data_file, data, max_age_minutes):
    now = datetime.now(TZ)
    if data is None:
        return {
            "status": "missing",
            "now_local": now.isoformat(),
            "data_file": str(data_file),
            "message": "No weather data file exists for today.",
        }

    fresh = freshness(data, max_age_minutes)
    return {
        "status": "fresh" if fresh["fresh"] else "stale",
        "now_local": now.isoformat(),
        "hour_local": now.hour,
        "data_file": str(data_file),
        "freshness": fresh,
        "location": data.get("location", {}),
        "source_status": data.get("source_status", {}),
        "fetched_at": data.get("fetched_at"),
        "alerts": data.get("alerts", []),
        "alert_polygons": data.get("alert_polygons", []),
        "forecast": data.get("forecast", []),
        "hourly": data.get("hourly", []),
        "afd": data.get("afd", {}),
        "cwop_stations": data.get("cwop_stations", []),
        "rainviewer": data.get("rainviewer"),
        "spc": data.get("spc", {}),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--for-hermes", action="store_true", help="Output compact JSON for the Hermes weather skill.")
    parser.add_argument("--max-age-minutes", type=int, default=75)
    args = parser.parse_args()

    data_file, data = load_today()
    if args.for_hermes:
        print(json.dumps(compact_for_hermes(data_file, data, args.max_age_minutes), indent=2))
    elif data is None:
        raise SystemExit(f"No weather data file exists for today: {data_file}")
    else:
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
