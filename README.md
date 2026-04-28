# Anna TX Weather Agent

A local weather intelligence pipeline for Anna, Texas. It quietly refreshes rich weather data every 15 minutes, then Hermes reads that data to produce useful forecasts, storm briefings, and alert reports.

The design is intentionally simple:

1. `weather_scrape.py` updates local JSON data.
2. `weather_data.py` exposes the latest data to Hermes.
3. The Hermes `weather` skill decides what to say.
4. Hermes cron sends a 7 AM forecast, alert reports when needed, or `[SILENT]`.

No paid services are required. All core sources are free. mPING is optional and uses a free approved API key.

## What It Captures

### NWS Forecast Intelligence

- Area Forecast Discussion from NWS Fort Worth
- Active NWS alerts for the Anna, TX point
- Alert geometry when NWS provides it
- 7-day forecast periods
- Next 24 hours of hourly forecast data
- Point-grid details that normal forecasts do not expose cleanly:
  - thunder probability
  - quantitative precipitation forecast
  - wind gust potential
  - weather windows
  - coded hazards

### Local NWS Products

- Local Storm Reports from NWS Fort Worth
- Special Weather Statements
- Hazardous Weather Outlook when available

These give Hermes short-fuse detail and ground truth without making it parse the whole internet.

### SPC Severe Weather Context

- Mesoscale Discussions
- Tornado and Severe Thunderstorm Watches
- Convective Outlooks
- PDS Watches
- Nearby SPC storm reports filtered around Anna

This is the severe-weather layer that makes the briefing feel serious instead of generic.

### Radar

- Pulls RainViewer public radar metadata
- Converts Anna's lat/lon to the correct map tile
- Renders a city-level NEXRAD reflectivity map over a dark labeled basemap
- Frames Anna to the right so west-to-east storms have room on the image
- Keeps the storm layer slightly transparent so towns and roads stay readable
- Exposes the image path to Hermes

When the weather is requested through Telegram, Hermes can attach the radar image with:

```text
MEDIA:/Users/sethrose/Developer/weather-agent/data/radar/YYYY-MM-DD-latest-map.png
```

Hermes strips the `MEDIA:` line and sends the PNG as a native Telegram image.

### Nearby Observations

- Fetches nearby NWS station observations
- Stores temperature, dewpoint, humidity, wind, pressure, precipitation, and current conditions

### Nearby Town Timing Grid

- Stores 50 nearby town reference points around Anna
- Includes latitude, longitude, distance from Anna, bearing, and compass direction
- Includes a west-to-east storm-motion reference so Hermes can reason about upstream towns and rough timing
- Uses static Census Gazetteer-derived coordinates, so it adds no recurring API calls

### mPING Reports

- Optional crowdsourced ground reports from mPING
- Enabled when `MPING_API_KEY` is present in the runtime environment
- Captures nearby precipitation and hail reports for hyperlocal context

## Live Files

| File | Role |
|------|------|
| `weather_scrape.py` | Main updater. Fetches all data sources and writes `data/YYYY-MM-DD.json`. |
| `weather_data.py` | Read-only CLI for Hermes. Outputs compact JSON with freshness metadata. |
| `nws.py` | NWS API client for forecasts, alerts, grid details, and FWD local products. |
| `spc.py` | SPC RSS and storm report fetcher. |
| `rainviewer.py` | RainViewer radar tile metadata. |
| `radar_map.py` | Renders the Telegram-ready radar map from free public tiles. |
| `nearby_places.py` | Local town distance and storm-timing reference grid. |
| `cwop.py` | Nearby station observations via NWS. |
| `mping.py` | mPING API client, enabled by `MPING_API_KEY`. |

Legacy files:

- `alert_evaluator.py`
- `weather-digest.py`

Those are not part of the live automation path. Hermes now owns summarization and delivery through the `weather` skill.

## Automation Flow

```text
launchd
  every 15 minutes
  runs weather_scrape.py
    -> NWS forecast, alerts, grid details, local products
    -> SPC products and nearby storm reports
    -> RainViewer radar image
    -> nearby station observations
    -> nearby town timing grid
    -> optional mPING reports
    -> data/YYYY-MM-DD.json

Hermes cron
  hourly
  loads weather skill
  runs weather_data.py --for-hermes
    -> 7 AM forecast
    -> active alert report
    -> [SILENT] when nothing matters
```

## Data Contract

Each daily JSON file contains:

- `fetched_at` — UTC timestamp for the scrape
- `data_hash` — content hash used to skip unchanged writes
- `location` — Anna, TX lat/lon metadata
- `source_status` — per-source health summary
- `afd` — NWS Fort Worth Area Forecast Discussion
- `alerts` — active alerts for Anna
- `alert_polygons` — alert geometry and metadata
- `forecast` — 7-day NWS forecast periods
- `hourly` — next 24 hours
- `grid_details` — QPF, thunder probability, gusts, weather windows, and hazards
- `local_products` — FWD LSR/SPS/HWO products
- `cwop_stations` — nearby station observations
- `nearby_places` — nearby town lat/lon, distance, bearing, and storm-motion reference
- `rainviewer` — radar tile URL, raw tile path, and rendered map path
- `spc` — SPC discussions, watches, outlooks, PDS watches, and nearby storm reports
- `mping_reports` — nearby mPING reports when enabled

Hermes reads the compact version with:

```bash
python3 ~/Developer/weather-agent/weather_data.py --for-hermes
```

That command includes:

- `status`: `fresh`, `stale`, or `missing`
- `freshness.age_minutes`
- `hour_local`
- all high-signal forecast, severe, radar, observation, and report fields

## Scheduler Setup

The launchd scraper runs every 900 seconds:

```bash
launchctl bootout gui/$(id -u)/com.sethrose.weather-scrape 2>/dev/null; sleep 1
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.sethrose.weather-scrape.plist
launchctl kickstart -k gui/$(id -u)/com.sethrose.weather-scrape
```

Check it:

```bash
launchctl print gui/$(id -u)/com.sethrose.weather-scrape
tail -n 50 logs/weather-scrape.log
```

Hermes cron is managed separately:

```bash
hermes cron list
```

Current intended Hermes behavior:

- 7 AM America/Chicago: send a concise forecast
- Any hour with active alerts: send an alert-focused report
- Otherwise: return `[SILENT]`

## API Keys

No key required:

- NWS API
- NWS products
- SPC RSS feeds
- SPC storm reports
- RainViewer public radar metadata
- nearby station observations through NWS

Optional key:

- mPING requires `MPING_API_KEY`

Do not commit API keys. The key belongs in the local launchd environment.

## Runtime Files

Ignored by git:

- `data/`
- `logs/`
- `alert-state.json`
- `__pycache__/`
- `.DS_Store`

## Verification

Compile the scripts:

```bash
python3 -m py_compile weather_scrape.py weather_data.py nws.py spc.py rainviewer.py cwop.py mping.py
```

Run a scrape:

```bash
python3 weather_scrape.py
```

Inspect the Hermes contract:

```bash
python3 weather_data.py --for-hermes
```

Useful checks:

```bash
python3 weather_data.py --for-hermes | python3 -m json.tool
ls -lh data/radar/
tail -n 50 logs/weather-scrape.log
```

## Why This Is Good

This is not a generic weather bot. It combines point-specific NWS forecast data, forecaster reasoning, storm reports, SPC severe-weather context, radar imagery, nearby observations, and crowdsourced mPING reports into one compact local feed. Hermes gets enough detail to write a genuinely useful briefing, but the scraper stays boring, deterministic, and cheap.
