#!/usr/bin/env python3
"""
Weather Alert Evaluator for Anna, TX
Reads NWS scraped data and outputs a message ONLY when conditions are met.
Silent by default. Designed for hourly cron execution.
"""
import json
import hashlib
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

BASE_DIR = Path.home() / "Developer" / "weather-agent"
DATA_DIR = BASE_DIR / "data"
STATE_FILE = BASE_DIR / "alert-state.json"
LOG_FILE = BASE_DIR / "logs" / "alert-evaluator.log"
TZ = ZoneInfo("America/Chicago")


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{ts}] {msg}"
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Cleanup old daily keys (> 7 days)
    cutoff = (datetime.now(TZ) - timedelta(days=7)).strftime("%Y-%m-%d")
    keys_to_remove = [k for k in state if k.startswith(("morning_", "evening_")) and k.split("_")[1] < cutoff]
    for k in keys_to_remove:
        del state[k]
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def get_data():
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    data_file = DATA_DIR / f"{today}.json"
    if not data_file.exists():
        log(f"Data file missing: {data_file}")
        return None
    try:
        with open(data_file) as f:
            return json.load(f)
    except Exception as e:
        log(f"Failed to parse data file: {e}")
        return None


def parse_wind(wind_str):
    if not wind_str:
        return 0
    nums = re.findall(r'(\d+)', str(wind_str))
    if nums:
        return max(int(n) for n in nums)
    return 0


def is_severe_hourly(hour):
    short = hour.get("short", "").lower()
    precip = hour.get("precip")
    wind = parse_wind(hour.get("wind", ""))
    
    # Only trigger for explicit severe language, not "slight chance" or "chance"
    # Must contain "severe" or "hail" or "tornado" explicitly
    if "severe" in short or "hail" in short or "tornado" in short:
        return True
    
    # Very high winds (sustained or gusts)
    if wind >= 50:
        return True
    
    # High precip + strong storm language (not "slight chance")
    if precip is not None and precip != "":
        try:
            p = int(precip)
            if p >= 70 and ("storm" in short and "slight chance" not in short and "chance" not in short):
                return True
        except (ValueError, TypeError):
            pass
    return False


def get_next_hours(hourly, hours):
    now = datetime.now(TZ)
    result = []
    for h in hourly:
        t = h.get("time", "")
        try:
            ht = datetime.fromisoformat(t)
            if now <= ht <= now + timedelta(hours=hours):
                result.append(h)
        except Exception:
            continue
    return result


def hash_conditions(items, keys):
    parts = []
    for item in items:
        for k in keys:
            parts.append(str(item.get(k, "")))
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


def fmt_time(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%I:%M %p")
    except Exception:
        return iso_str


def _is_night_period(name):
    return name == "Tonight" or name.endswith("Night")


def compose_morning(data):
    lines = []
    lines.append("Morning Weather Brief - Anna, TX")
    lines.append("")

    forecast = data.get("forecast", [])
    alerts = data.get("alerts", [])
    afd = data.get("afd", {})

    # Find daytime period (first non-night period)
    today = None
    for p in forecast:
        if not _is_night_period(p.get("name", "")):
            today = p
            break

    # Find tonight period (first night period after today)
    tonight = None
    found_today = False
    for p in forecast:
        if p == today:
            found_today = True
            continue
        if found_today and _is_night_period(p.get("name", "")):
            tonight = p
            break

    if today:
        lines.append(f"Today: {today.get('name', 'N/A')} - {today.get('temp', 'N/A')} deg {today.get('temp_unit', 'F')}, {today.get('short', 'N/A')}")
        if today.get('wind'):
            lines.append(f"Wind: {today.get('wind_dir', '')} {today.get('wind', '')}")
        if today.get('precip') not in (None, ""):
            lines.append(f"Precipitation: {today.get('precip')}%")

    if tonight:
        lines.append("")
        lines.append(f"Tonight: {tonight.get('name', 'N/A')} - {tonight.get('temp', 'N/A')} deg {today.get('temp_unit', 'F')}, {tonight.get('short', 'N/A')}")

    lines.append("")
    if alerts:
        lines.append(f"Active Alerts ({len(alerts)}):")
        for a in alerts:
            lines.append(f"- {a.get('event', 'N/A')} ({a.get('severity', 'N/A')}): {a.get('headline', 'No details')}")
    else:
        lines.append("No active alerts.")

    # Include raw AFD key messages (agent filters via skill guidance)
    if afd and afd.get("text"):
        text = afd["text"]
        if ".KEY MESSAGES..." in text:
            start = text.find(".KEY MESSAGES...")
            end = text.find("&&", start)
            if end == -1:
                end = start + 800
            snippet = text[start:end].replace(".KEY MESSAGES...", "").strip()
            lines.append("")
            lines.append("AFD Key Messages:")
            lines.append(snippet[:600] + ("..." if len(snippet) > 600 else ""))

    return "\n".join(lines)


def compose_evening(data):
    lines = []
    lines.append("Evening Outlook - Anna, TX")
    lines.append("")

    forecast = data.get("forecast", [])
    afd = data.get("afd", {})
    upcoming = forecast[2:5] if len(forecast) > 2 else []

    if upcoming:
        lines.append("Next few days:")
        for p in upcoming:
            lines.append(f"- {p.get('name', 'N/A')}: {p.get('temp', 'N/A')} deg {p.get('temp_unit', 'F')}, {p.get('short', 'N/A')}, precip {p.get('precip', 'N/A')}%")

    sig = []
    for p in forecast:
        short = p.get("short", "").lower()
        if any(k in short for k in ["severe", "thunderstorm", "heavy rain", "tornado", "hail"]):
            sig.append(p)
        elif p.get("precip") not in (None, ""):
            try:
                if int(p.get("precip")) >= 50:
                    sig.append(p)
            except (ValueError, TypeError):
                pass

    if sig:
        lines.append("")
        lines.append("Significant events:")
        for p in sig[:3]:
            lines.append(f"- {p.get('name', 'N/A')}: {p.get('short', 'N/A')} ({p.get('precip', 'N/A')}% precip)")

    # Include raw AFD long term outlook (agent filters via skill guidance)
    if afd and afd.get("text"):
        text = afd["text"]
        if ".LONG TERM..." in text:
            start = text.find(".LONG TERM...")
            end = text.find("&&", start)
            if end == -1:
                end = start + 600
            snippet = text[start:end].replace(".LONG TERM...", "").strip()
            lines.append("")
            lines.append("AFD Long Term Outlook:")
            lines.append(snippet[:600] + ("..." if len(snippet) > 600 else ""))

    return "\n".join(lines)


def compose_severe(data, severe_alerts, severe_hourly):
    lines = []
    lines.append("SEVERE WEATHER ALERT - Anna, TX")
    lines.append("")

    if severe_alerts:
        lines.append(f"Active severe alerts ({len(severe_alerts)}):")
        for a in severe_alerts:
            lines.append(f"- {a.get('event', 'N/A')} ({a.get('severity', 'N/A')})")
            if a.get("instruction"):
                lines.append(f"  Action: {a.get('instruction')}")
            elif a.get("description"):
                lines.append(f"  Details: {a.get('description')[:200]}")

    if severe_hourly:
        lines.append("")
        lines.append("Severe conditions expected in next 3 hours:")
        for h in severe_hourly[:4]:
            time_str = fmt_time(h.get("time", ""))
            lines.append(f"- {time_str}: {h.get('short', 'N/A')}, {h.get('temp', 'N/A')} deg {h.get('temp_unit', 'F')}, wind {h.get('wind_dir', '')} {h.get('wind', '')}")

    return "\n".join(lines)


def compose_imminent(data, imminent_hours):
    lines = []
    lines.append("Weather Update - Next Hour - Anna, TX")
    lines.append("")

    for h in imminent_hours[:4]:
        time_str = fmt_time(h.get("time", ""))
        lines.append(f"{time_str}: {h.get('short', 'N/A')}")
        lines.append(f"  Temp: {h.get('temp', 'N/A')} deg {h.get('temp_unit', 'F')} | Precip: {h.get('precip', 'N/A')}% | Humidity: {h.get('humidity', 'N/A')}%")
        lines.append(f"  Wind: {h.get('wind_dir', '')} {h.get('wind', '')}")
        lines.append("")

    return "\n".join(lines)


def main():
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(TZ)
    state = load_state()
    data = get_data()

    if not data:
        log("No data available.")
        return

    date_str = now.strftime("%Y-%m-%d")
    output = None

    # 1. Morning brief (7 AM hour)
    if now.hour == 7:
        key = f"morning_{date_str}"
        if not state.get(key):
            output = compose_morning(data)
            state[key] = True
            log("Triggered morning brief")

    # 2. Evening outlook (7 PM hour)
    elif now.hour == 19:
        key = f"evening_{date_str}"
        if not state.get(key):
            output = compose_evening(data)
            state[key] = True
            log("Triggered evening outlook")

    # 3. Severe alert (any hour) - only if no scheduled brief already sent this run
    if output is None:
        alerts = data.get("alerts", [])
        severe_alerts = [a for a in alerts if a.get("severity") in ("Severe", "Extreme")]
        hourly = data.get("hourly", [])
        severe_hourly = [h for h in get_next_hours(hourly, 3) if is_severe_hourly(h)]

        if severe_alerts or severe_hourly:
            current_hash = hash_conditions(severe_alerts + severe_hourly, ["event", "time", "short", "severity"])
            if state.get("last_severe_hash") != current_hash:
                output = compose_severe(data, severe_alerts, severe_hourly)
                state["last_severe_hash"] = current_hash
                state["last_severe_time"] = datetime.now(timezone.utc).isoformat()
                log(f"Triggered severe alert (hash {current_hash})")

    # 4. Imminent alert (any hour) - only if nothing else triggered
    if output is None:
        hourly = data.get("hourly", [])
        next_hour = get_next_hours(hourly, 1)

        imminent = []
        for h in next_hour:
            precip = h.get("precip")
            wind = parse_wind(h.get("wind", ""))

            # Quantitative triggers only — no keyword guessing
            has_precip = False
            if precip is not None and precip != "":
                try:
                    has_precip = int(precip) > 30
                except (ValueError, TypeError):
                    pass
            
            has_wind = wind >= 30

            if has_precip or has_wind:
                imminent.append(h)

        if imminent:
            current_hash = hash_conditions(imminent, ["time", "temp", "short", "precip"])
            if state.get("last_imminent_hash") != current_hash:
                output = compose_imminent(data, imminent)
                state["last_imminent_hash"] = current_hash
                state["last_imminent_time"] = datetime.now(timezone.utc).isoformat()
                log(f"Triggered imminent alert (hash {current_hash})")

    save_state(state)

    if output:
        print(output)
    else:
        log("No conditions met. Silent.")


if __name__ == "__main__":
    main()
