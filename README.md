# Weather Agent for Anna, TX

A lightweight, free weather monitoring stack for Anna, Texas using the National Weather Service API. No API keys required.

## Python Scripts

| Script | Purpose |
|--------|---------|
| `weather_scrape.py` | NWS data fetcher and storage. Fetches every 15 minutes via launchd agent. |
| `alert_evaluator.py` | Conditional alert logic. Runs hourly via Hermes cron job. |
| `weather-digest.py` | Weather digest generator. |

## What They Do

### 1. `weather_scrape.py`
- Fetches NWS data every 15 minutes
- Stores to `data/YYYY-MM-DD.json` (gitignored)
- Deduplicates by content hash
- Auto-cleans files older than 7 days

### 2. `alert_evaluator.py`
- Runs hourly
- Checks for specific conditions:
  - **7 AM** → Morning brief (daily forecast)
  - **7 PM** → Evening 2-3 day outlook
  - **Any hour** → Severe weather in next 3 hours
  - **Any hour** → Rain/storms/wind in next 1 hour
- Returns `[SILENT]` if nothing is happening → zero noise
- Deduplicates alerts so you don't get spammed

### 3. `weather-digest.py`
- Generates weather digests for delivery

## Data Structure

Each day's JSON (stored locally in `data/`, not in repo) contains:
- `fetched_at` — last scrape timestamp
- `afd` — Area Forecast Discussion (full meteorologist reasoning)
- `alerts` — active NWS alerts for the Anna, TX point
- `forecast` — 7-day forecast periods
- `hourly` — next 24 hours of hourly data

## Why No API Keys?

The NWS (`api.weather.gov`) is a free, public service. No registration or key required. Just be polite with request frequency.

## Local Setup

```bash
# Activate the scraper (runs every 15 minutes)
launchctl bootout gui/$(id -u)/com.sethrose.weather-scrape 2>/dev/null; sleep 1
launchctl load ~/Library/LaunchAgents/com.sethrose.weather-scrape.plist

# The Hermes cron job is managed via `hermes cron`
# Job ID: 9cf0b5d63304
```

## Git Ignore

The following are excluded from the repo (see `.gitignore`):
- `data/` — Daily JSON files
- `logs/` — Runtime logs
- `alert-state.json` — Deduplication state
- `__pycache__/` — Python cache
- `.DS_Store` — macOS metadata
