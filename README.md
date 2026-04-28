# Weather Agent for Anna, TX

A lightweight, free weather monitoring stack for Anna, Texas using the National Weather Service API. No API keys required. Designed to run silently on macOS and only alert when conditions warrant it.

## What It Does

1. **Scraper** (`weather_scrape.py` / `com.sethrose.weather-scrape` launchd agent)
   - Fetches NWS data every 15 minutes
   - Stores to `data/YYYY-MM-DD.json`
   - Deduplicates by content hash
   - Auto-cleans files older than 7 days

2. **Alert Evaluator** (`alert_evaluator.py` / Hermes cron job)
   - Runs hourly
   - Checks for specific conditions:
     - **7 AM** → Morning brief (daily forecast)
     - **7 PM** → Evening 2-3 day outlook
     - **Any hour** → Severe weather in next 3 hours
     - **Any hour** → Rain/storms/wind in next 1 hour
   - Returns `[SILENT]` if nothing is happening → zero noise
   - Deduplicates alerts so you don't get spammed

3. **Manual Queries** (Hermes skill: `weather`)
   - Say "check the weather" or "what's the forecast"
   - Reads the latest scraped data and synthesizes a human-readable brief

## Installation

```bash
# Activate the scraper
launchctl bootout gui/$(id -u)/com.sethrose.weather-scrape 2>/dev/null; sleep 1
launchctl load ~/Library/LaunchAgents/com.sethrose.weather-scrape.plist

# The Hermes cron job is managed via `hermes cron`
# Job ID: 9cf0b5d63304
```

## Data Structure

Each day's JSON contains:
- `fetched_at` — last scrape timestamp
- `afd` — Area Forecast Discussion (full meteorologist reasoning)
- `alerts` — active NWS alerts for the Anna, TX point
- `forecast` — 7-day forecast periods
- `hourly` — next 24 hours of hourly data

## Why No API Keys?

The NWS (`api.weather.gov`) is a free, public service. No registration or key required. Just be polite with request frequency.

## Files

| File | Purpose |
|------|---------|
| `weather_scrape.py` | NWS data fetcher and storage |
| `alert_evaluator.py` | Conditional alert logic |
| `com.sethrose.weather-scrape.plist` | macOS launchd agent for scraper |
| `data/` | Daily JSON files (gitignored) |
| `logs/` | Runtime logs (gitignored) |
| `alert-state.json` | Deduplication state (gitignored) |
