#!/usr/bin/env python3
"""mPING (Meteorological Phenomena Identification Near the Ground) data fetcher.
Requires free API key from mping.ou.edu.
https://mping.ou.edu/api/index.html
"""
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import urlopen, Request

LAT, LON = 33.349, -96.548
HEADERS = {"User-Agent": "weather-scrape/1.0 (personal use)"}
MPING_API_KEY = os.environ.get("MPING_API_KEY", "")
MPING_ENABLED = bool(MPING_API_KEY)

def fetch_mping(lat=LAT, lon=LON, radius_miles=20, hours=24):
    """Fetch mPING reports within radius and last N hours.
    Uses mPING API v2 (requires API key set in MPING_API_KEY).
    """
    if not MPING_API_KEY:
        return []  # Silently skip if no key
    
    # Calculate time filter
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    obtime_gte = cutoff.strftime("%Y-%m-%d %H:%M:%S")
    
    # Build URL with filters
    params = urlencode({
        "obtime_gte": obtime_gte,
        "dist": round(radius_miles * 1609.344),
        "point": f"{lon},{lat}",
    })
    url = f"https://mping.ou.edu/mping/api/v2/reports?{params}"
    
    try:
        headers = {"Authorization": f"Token {MPING_API_KEY}"}
        req = Request(url, headers={**HEADERS, **headers})
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        reports = data.get("results", [])
    except Exception as e:
        return []
    
    filtered = []
    for r in reports:
        try:
            geom = r.get("geom", {})
            coords = geom.get("coordinates", [])
            if len(coords) >= 2:
                r_lon, r_lat = coords[0], coords[1]
            else:
                continue
            filtered.append({
                "time": r.get("obtime", ""),
                "type": r.get("description", "unknown"),
                "hail_size": r.get("hail_size_inches"),
                "lat": r_lat,
                "lon": r_lon,
                "city": r.get("city", ""),
                "state": r.get("state", ""),
            })
        except (KeyError, ValueError, TypeError):
            continue
    
    return filtered
