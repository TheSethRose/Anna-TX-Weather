#!/usr/bin/env python3
"""CWOP (Citizen Weather Observer Program) data fetcher.
Fetches data from personal weather stations near Anna, TX.
Free, no API key required - uses NWS API.
"""
import json
from datetime import datetime, timezone
from urllib.request import urlopen, Request

LAT, LON = 33.349, -96.548
HEADERS = {"User-Agent": "weather-scrape/1.0 (personal use)"}
MAX_STATIONS = 5  # Number of nearest stations to fetch

def fetch(url):
    """Fetch JSON from URL with proper headers."""
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_nearby_stations():
    """Get list of weather stations near Anna, TX."""
    try:
        url = f"https://api.weather.gov/points/{LAT},{LON}/stations"
        data = fetch(url)
        stations = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            geom = feature.get("geometry", {})
            coords = geom.get("coordinates", [])
            lon, lat = coords[:2] if len(coords) >= 2 else (0, 0)
            stations.append({
                "id": props.get("stationIdentifier", ""),
                "name": props.get("name", ""),
                "lat": lat,
                "lon": lon,
                "distance": ((lat - LAT) ** 2 + (lon - LON) ** 2) ** 0.5,
            })
        # Sort by distance
        stations.sort(key=lambda x: x["distance"])
        return stations[:MAX_STATIONS]
    except Exception as e:
        return []

def get_station_observations(station_id):
    """Get latest observations from a station."""
    try:
        url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
        data = fetch(url)
        props = data.get("properties", {})
        return {
            "station_id": station_id,
            "timestamp": props.get("timestamp", ""),
            "temp": props.get("temperature", {}).get("value"),
            "dewpoint": props.get("dewpoint", {}).get("value"),
            "humidity": props.get("relativeHumidity", {}).get("value"),
            "wind_speed": props.get("windSpeed", {}).get("value"),
            "wind_dir": props.get("windDirection", {}).get("value"),
            "pressure": props.get("barometricPressure", {}).get("value"),
            "precip_1h": props.get("precipitationLastHour", {}).get("value"),
            "conditions": props.get("textDescription", ""),
        }
    except Exception as e:
        return None

def get_cwop_stations():
    """Get observations from nearest CWOP/personal weather stations.
    Returns list of station data with current observations.
    """
    stations = get_nearby_stations()
    observations = []
    for station in stations[:MAX_STATIONS]:
        obs = get_station_observations(station["id"])
        if obs:
            obs["name"] = station["name"]
            obs["lat"] = station["lat"]
            obs["lon"] = station["lon"]
            obs["distance"] = station["distance"]
            observations.append(obs)
    return observations
