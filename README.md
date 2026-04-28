# Weather Data Updater for Anna, TX

This repo only updates local weather data for Anna, Texas. Hermes owns reading that data, deciding whether anything should be sent, and writing the forecast or alert report through the `weather` skill.

## Live Scripts

| Script | Purpose |
|--------|---------|
| `weather_scrape.py` | Fetches no-key weather sources and updates `data/YYYY-MM-DD.json`. |
| `weather_data.py` | Read-only CLI for Hermes to inspect the latest data. |
| `nws.py` | NWS AFD, alerts, forecast, hourly forecast, and alert polygons. |
| `cwop.py` | Nearby NWS station observations. |
| `rainviewer.py` | RainViewer radar tile metadata. |
| `spc.py` | SPC mesoscale discussions, watches, convective outlooks, and PDS watches. |
| `mping.py` | Optional mPING support. Disabled because it requires an API key. |

`alert_evaluator.py` and `weather-digest.py` are legacy scripts. They should not be part of the live automation path.

## Live Automation

### Data Updater

- Runs from launchd every 15 minutes
- Stores to `data/YYYY-MM-DD.json` (gitignored)
- Deduplicates by content hash
- Auto-cleans files older than 7 days
- Refuses to overwrite the current file if core NWS forecast/hourly data is missing

### Hermes Reader

Hermes cron runs the `weather` skill. The skill reads the latest data with:

```bash
python3 ~/Developer/weather-agent/weather_data.py --for-hermes
```

Hermes should send:
- a concise forecast at 7 AM America/Chicago
- weather alerts when active NWS alerts are present
- `[SILENT]` when there is nothing to report

## Data Structure

Each day's JSON contains:
- `fetched_at` — last scrape timestamp
- `source_status` — basic status for each data source
- `afd` — Area Forecast Discussion from NWS Fort Worth
- `alerts` — active NWS alerts for the Anna, TX point
- `alert_polygons` — geometry for active alerts
- `forecast` — 7-day forecast periods
- `hourly` — next 24 hours of hourly data
- `cwop_stations` — nearby station observations
- `rainviewer` — latest radar tile metadata
- `spc` — SPC mesoscale discussions, watches, convective outlooks, and PDS watches
- `mping_reports` — optional crowdsourced reports if mPING is enabled

## API Keys

NWS, nearby station observations, and RainViewer do not require API keys.

mPING requires a free key from `mping.ou.edu`, so it is disabled by default. Leave it disabled unless you explicitly want that source.

## Schedulers

Activate the launchd scraper:

```bash
launchctl bootout gui/$(id -u)/com.sethrose.weather-scrape 2>/dev/null; sleep 1
launchctl load ~/Library/LaunchAgents/com.sethrose.weather-scrape.plist
```

Check Hermes cron separately:

```bash
hermes cron list
```

## Runtime Files

The following are excluded from git:
- `data/`
- `logs/`
- `alert-state.json`
- `__pycache__/`
- `.DS_Store`
