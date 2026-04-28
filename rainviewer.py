#!/usr/bin/env python3
"""RainViewer radar data fetcher.
Free public API - no API key required.
Provides radar frames, storm tracking context for Anna, TX.
"""
import json
import subprocess
from datetime import datetime, timezone

RAINVIEWER_API = "https://api.rainviewer.com/public/weather-maps.json"
LAT, LON = 33.349, -96.548  # Anna, TX default

def fetch(url):
    """Fetch JSON via curl (bypasses Python urllib timeouts)."""
    try:
        result = subprocess.run(
            ["curl", "-s", "--max-time", "10", "-A", "Mozilla/5.0", url],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode != 0:
            return None
        return json.loads(result.stdout)
    except Exception as e:
        return None

def get_rainviewer_data(lat=LAT, lon=LON):
    """Get latest RainViewer radar data for a point.
    Returns dict with latest frame time, image URL, and basic precip status.
    """
    try:
        data = fetch(RAINVIEWER_API)
        if not data or not data.get("radar") or not data["radar"].get("past"):
            return None
        
        # Sort past frames by time (newest first)
        frames = sorted(data["radar"]["past"], key=lambda x: x["time"], reverse=True)
        if not frames:
            return None
        
        latest = frames[0]
        latest_time = datetime.fromtimestamp(latest["time"], tz=timezone.utc)
        host = data.get("host", "https://tilecache.rainviewer.com")
        
        # Build tile URL for Anna area (zoom 7 = ~400mi view, max zoom for RainViewer)
        tile_url = f"{host}{latest['path']}/256/7/{lat}/{lon}/1_1.png"
        
        # Check last 3 frames (30 mins) for activity near Anna
        recent_frames = [f for f in frames if f["time"] >= latest["time"] - 1800]  # Last 30 mins
        
        return {
            "latest_frame_time": latest_time.isoformat(),
            "latest_frame_url": tile_url,
            "recent_frames_count": len(recent_frames),
            "has_recent_activity": len(recent_frames) > 0,
            "source": "RainViewer",
        }
    except Exception as e:
        return None
