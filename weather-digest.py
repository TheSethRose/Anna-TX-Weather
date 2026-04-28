#!/usr/bin/env python3

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError

LAT, LON = 33.349, -96.548
OUT_DIR = Path.home() / "Developer" / "weather-agent" / "digests"
RAW_FEED = Path.home() / "Developer" / "weather-agent" / "weather-feed.jsonl"

HEADERS = {"User-Agent": "weather-digest/1.0 (personal use)"}


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
        return {"error": str(e)}


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
        return [{"error": str(e)}]


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
        return [{"error": str(e)}]


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
        return [{"error": str(e)}]


def build_prompt(afd, alerts, forecast, hourly):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    prompt = f"""You are a meteorologist writing a concise daily weather brief for Anna, Texas (Collin County).

Current time: {now}

---
AREA FORECAST DISCUSSION (NWS Fort Worth)
Issued: {afd.get('issued', 'N/A') if isinstance(afd, dict) else 'N/A'}
{afd.get('text', '') if isinstance(afd, dict) else str(afd)}

---
ACTIVE ALERTS ({len(alerts)} total)
"""
    if alerts and not any("error" in a for a in alerts):
        for a in alerts:
            prompt += f"""
Event: {a.get('event', 'N/A')}
Severity: {a.get('severity', 'N/A')}
Headline: {a.get('headline', 'N/A')}
Effective: {a.get('effective', 'N/A')} -> Expires: {a.get('expires', 'N/A')}
Description: {a.get('description', 'N/A')}
Instructions: {a.get('instruction', 'N/A')}
---
"""
    else:
        prompt += "No active alerts.\n"

    prompt += "\n7-DAY FORECAST\n"
    for p in forecast:
        if "error" in p:
            prompt += f"Error: {p['error']}\n"
            continue
        prompt += f"""
{p.get('name', 'N/A')}: {p.get('temp', 'N/A')}°{p.get('temp_unit', 'F')} | {p.get('short', 'N/A')}
Wind: {p.get('wind_dir', '')} {p.get('wind', '')} | Precip: {p.get('precip', 'N/A')}%
Detailed: {p.get('forecast', 'N/A')}
---
"""

    prompt += "\nNEXT 24 HOURS (Hourly)\n"
    for h in hourly:
        if "error" in h:
            prompt += f"Error: {h['error']}\n"
            continue
        t = h.get("time", "")
        try:
            dt = datetime.fromisoformat(t.replace("Z", "+00:00"))
            time_str = dt.strftime("%a %H:%M")
        except Exception:
            time_str = t
        prompt += f"{time_str}: {h.get('temp', 'N/A')}°{h.get('temp_unit', 'F')} | {h.get('short', 'N/A')} | precip {h.get('precip', 'N/A')}% | humidity {h.get('humidity', 'N/A')}%\n"

    prompt += """
---

Write a clear, concise daily weather brief in plain text. Cover:
1. Today's weather story (why it's doing what it's doing)
2. Any active alerts and what they mean for Anna specifically
3. Temperature trend and feel
4. Precipitation chances and timing
5. Wind conditions
6. Anything notable or unusual

Keep it to 2-3 short paragraphs. No bullet points unless listing alerts. No tables. Plain text, high school reading level. Be specific about timing.
"""
    return prompt


def hermes_forecast(prompt):
    hermes = None
    for path in ["hermes", "/opt/homebrew/bin/hermes", "/usr/local/bin/hermes"]:
        try:
            subprocess.run([path, "--version"], capture_output=True, timeout=5)
            hermes = path
            break
        except Exception:
            continue
    if not hermes:
        return "ERROR: hermes CLI not found in PATH."
    cmd = [hermes, "-z", prompt]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return result.stdout if result.returncode == 0 else f"ERROR (exit {result.returncode}): {result.stderr}"
    except Exception as e:
        return f"ERROR calling hermes: {e}"


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_FEED.parent.mkdir(parents=True, exist_ok=True)

    afd = get_afd()
    alerts = get_alerts()
    forecast = get_forecast()
    hourly = get_hourly()

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "afd": afd,
        "alerts": alerts,
        "forecast": forecast,
        "hourly": hourly,
    }
    with open(RAW_FEED, "a") as f:
        f.write(json.dumps(entry) + "\n")

    prompt = build_prompt(afd, alerts, forecast, hourly)
    forecast_text = hermes_forecast(prompt)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    digest_path = OUT_DIR / f"{date_str}-forecast.md"
    with open(digest_path, "w") as f:
        f.write(f"# Weather Brief — Anna, TX — {date_str}\n\n")
        f.write(forecast_text)
        f.write("\n\n---\n\n## Raw Data\n\n")
        f.write(f"**AFD Issued:** {afd.get('issued', 'N/A') if isinstance(afd, dict) else 'N/A'}\n\n")
        f.write(f"**Alerts:** {len(alerts)}\n\n")
        f.write(f"**Forecast periods:** {len(forecast)}\n\n")

    print(f"Saved digest to {digest_path}")
    print(f"Appended raw data to {RAW_FEED}")


if __name__ == "__main__":
    main()
