# Nepal Power Plants Dashboard

A fully self-contained Dash/Plotly web dashboard for Nepal's power plant and
transmission line licensing pipeline — **plus** an independent NEA
Operational Performance module (System Loss, Energy Balance, Financials,
Consumers/Sales Growth, etc.) and a statistical **Forecast Lab**, both fed
from their own Google Sheet.

- **Source (licensing data):** [www.doed.gov.np](https://www.doed.gov.np) —
  Department of Electricity Development
- **Source (operational data):** [www.nea.org.np](https://www.nea.org.np) —
  Nepal Electricity Authority
- **Live site:** https://www.neupanesandeep.com.np
- **Repo:** https://github.com/neupanesandeep500-glitch/Nepal-Power-Sector-Dashboard-
- **Author:** Er. Sandeep Neupane

> This is an independent, unofficial platform. It is not affiliated with or
> endorsed by DoED, NEA, or ERC.

---

## Table of Contents

1. [Key Features](#key-features)
2. [Architecture / File Structure](#architecture--file-structure)
3. [Requirements](#requirements)
4. [Local Setup (Environment Creation)](#local-setup-environment-creation)
5. [Environment Variables](#environment-variables)
6. [Data Sources](#data-sources)
   - [License Status Workbook](#1-license-status-workbook-doed)
   - [NEA Operational Data Workbook](#2-nea-operational-data-workbook-nea)
7. [GIS Data](#gis-data)
8. [Visitor Counter (Google Sheets persistence)](#visitor-counter-google-sheets-persistence)
9. [Google Analytics](#google-analytics)
10. [SEO](#seo)
11. [Admin Panel](#admin-panel)
12. [API Endpoints](#api-endpoints)
13. [Forecast Lab — Modeling Notes](#forecast-lab--modeling-notes)
14. [Deployment](#deployment)
15. [Troubleshooting](#troubleshooting)
16. [Recent Changes](#recent-changes)
17. [License](#license)

---

## Key Features

- **Zero-config GIS** — Nepal district/province boundaries and protected
  areas are bundled inline (`gis_bundled.py`, `nepal_*.geojson`) — no
  shapefile uploads or Drive syncs needed to get started.
- **Admin panel** at `/admin` for uploading workbooks, syncing Google
  Sheets, and managing branding (logo, flag, hero/category background
  images) — no redeploy needed to change data or theme.
- **8 main tabs**, two of them with their own sub-tabs:
  | Tab | Sub-tabs |
  |---|---|
  | 📊 Overview | — |
  | 📜 License Status | ⚡ Power Plants · 🔌 Transmission Line · 📋 GoN Studied Projects · 🚫 License Cancelled |
  | 📈 License Insights | 📈 Growth Trends · 📉 Comparative Charts · 🗂️ Data Table |
  | 🗺️ GIS Map | — |
  | 🏭 System Operational Performance (NEA) | System Loss, Financials, Energy/Peak, Consumers & Sales Growth, Transmission/Substation, Energy & Capacity Balance |
  | 🔬 NEA Forecast Lab | Single-parameter and stacked/composite forecasting |
  | 🎨 Custom Style | Chart theme, color scheme, fonts, grid/animation toggles |
  | 📄 Generate Report | One-click PDF report |
- **NEA Forecast Lab** — statsmodels-driven forecasting (Linear Regression /
  Holt Exponential Smoothing / Moving Average / ARIMA / SARIMA / Hybrid
  Linear+ARIMA) for any single parameter, plus **stacked/composite**
  scenarios that forecast each component independently and sum them into a
  total. Includes an automatic model-fallback chain and an anti-spike
  continuity correction so every history→forecast join is visually
  continuous (see [Forecast Lab — Modeling Notes](#forecast-lab--modeling-notes)).
- **Live ticker** with KPIs from both data sources, plus a live clock.
- **Visitor counter** that survives redeploys — persisted to a Google Sheet
  via a service account, independent of Render's ephemeral filesystem.
- **PDF report generation** — a multi-page report covering both the license
  pipeline and NEA operational figures.
- **SEO-ready** — meta description tag, `/sitemap.xml`, `/robots.txt`.
- **Google Analytics (GA4)** wired in alongside the durable visitor counter
  (GA is for analytics reporting only; it is not the displayed counter
  source).

## Architecture / File Structure

```
.
├── app.py                        # Main Dash application: layout, callbacks,
│                                  # all routes, chart builders, PDF report
├── NEA.py                        # NEA Operational Data + Forecast Lab —
│                                  # fully independent module: own Google
│                                  # Sheet, own parsing, own background sync,
│                                  # own forecasting (statsmodels)
├── data_engine.py                # License workbook loading, GIS engine,
│                                  # B.S. (Bikram Sambat) calendar helpers
├── server_state.py               # Shared app state (STATE), config
│                                  # persistence, background refresh loop,
│                                  # branding asset storage
├── coordinate_transform.py       # WGS-84 <-> Everest 1830 coordinate
│                                  # conversions for GIS layers
├── admin.py                      # /admin Flask blueprint (login, sheet
│                                  # sync, uploads, branding)
├── gis_bundled.py                # Inline bundled Nepal GIS data
├── gis_leaflet_map.py            # Leaflet map rendering helpers
├── gis_area_methods.py           # Spatial/area calculation helpers
├── visitor_counter.py            # Durable visitor counter (Google Sheet
│                                  # via service account) + background flush
├── nea_assets/
│   ├── nea_operational_dashboard_template.html  # NEA operational tab (Chart.js)
│   ├── nea_forecast_lab_template.html           # NEA Forecast Lab (Chart.js)
│   └── vendor/                   # Chart.js bundled locally (not from a CDN
│                                  # — see Troubleshooting)
├── nepal_boundary.geojson        # Country boundary
├── nepal_claimed_area.geojson    # Claimed territory overlay
├── nepal_districts.geojson       # District boundaries
├── nepal_localbodies.geojson     # Local body (palika) boundaries
├── nepal_protected_areas.geojson # Protected areas overlay
├── nepal_provinces.geojson       # Province boundaries
├── requirements.txt              # Python dependencies
└── data/                         # Created at runtime — workbooks, uploads,
                                   # nea_config.json, branding assets
```

## Requirements

- **Python 3.11** (recommended — matches the Docker image below;
  3.10–3.12 also work)
- `pip`
- Internet access at runtime for: Google Sheets sync (public CSV export —
  no auth needed for the license/NEA workbooks), the visitor counter's
  Google Sheets API call (needs a service account), and Google Analytics.

## Local Setup (Environment Creation)

```bash
# 1. Clone the repo
git clone https://github.com/neupanesandeep500-glitch/Nepal-Power-Sector-Dashboard-.git
cd Nepal-Power-Sector-Dashboard-

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) set environment variables for this session — see table below
export DEFAULT_SHEET_URL="https://docs.google.com/spreadsheets/d/..."
export NEA_SHEET_URL="https://docs.google.com/spreadsheets/d/..."
export ADMIN_PASSWORD="choose-a-strong-password"

# 5. Run locally
python app.py

# 6. Open a browser to
http://localhost:8050
# Admin panel:
http://localhost:8050/admin/login
```

Without any environment variables set, the app still starts cleanly — the
License Status tabs run on bundled/placeholder data until a workbook is
supplied, and the NEA tabs show "no data" until `NEA_SHEET_URL` (or the
admin panel's NEA Data Sync card) is set. GIS renders immediately from the
bundled boundary files regardless.

## Environment Variables

None of these are strictly required to boot the app — they configure data
sources, persistence, and integrations. Set them on your host (Render's
dashboard, a `.env` file with a loader, or your shell).

| Variable | Default | Description |
|---|---|---|
| `DEFAULT_SHEET_URL` | — | Google Sheet URL/ID for the **License Status** workbook, auto-synced on startup |
| `DEFAULT_GIS_DRIVE_URL` | — | Google Drive link for a higher-resolution GIS zip (optional — bundled GIS works without it) |
| `DEFAULT_PA_DRIVE_URL` | — | Google Drive link for a protected-areas zip (optional) |
| `DEFAULT_ASSETS_DRIVE_URL` | — | Google Drive link for bundled branding assets (logo/flag/hero), synced at bootstrap |
| `NEA_SHEET_URL` | placeholder | Google Sheet URL/ID for the **NEA Operational Data** workbook (11 required tabs — separate from the license workbook above) |
| `NEA_AUTO_REFRESH_HOURS` | `6` | Background refresh interval for the NEA sheet, in hours |
| `AUTO_REFRESH_HOURS` | `24` | Background refresh interval for the License Status sheet, in hours |
| `ADMIN_PASSWORD` | *(hardcoded in `admin.py` — override this)* | Password for `/admin`. **Always set this explicitly in production** — do not rely on the source default |
| `FLASK_SECRET_KEY` | random per-boot | Session/cookie encryption key. Set a fixed value in production so sessions (e.g. admin login) survive a process restart |
| `DATA_DIR` | `./data` | Path to persistent data storage — workbooks, uploads, and `nea_config.json` (the admin-saved NEA sheet URL, so it survives a restart without the env var) |
| `MAX_GIS_ZIP_MB` | `80` | Upload size cap for GIS zip files via the admin panel |
| `MAX_IMAGE_MB` | `10` | Upload size cap for branding images via the admin panel |
| `GA_MEASUREMENT_ID` | `G-DD12W6FLZ8` | Google Analytics 4 Measurement ID |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | — | **Required for the visitor counter to persist.** Full JSON key of a Google service account with edit access to the visitor-count Google Sheet (see [Visitor Counter](#visitor-counter-google-sheets-persistence)) |
| `VISITOR_SHEET_ID` | *(a default sheet ID in code)* | Google Sheet ID the visitor counter reads/writes |
| `VISITOR_SHEET_TAB` | `Website Visitor Counter` | Worksheet/tab name within that sheet |
| `VISITOR_COUNT_SEED` | `305` | Starting count if the sheet has no prior value |
| `VISITOR_FLUSH_INTERVAL` | `60` | Seconds between background flushes of the in-memory visitor count to the Google Sheet |
| `COUNTAPI_BASE` / `COUNTAPI_KEY` | set | Fallback counter service, used only if the Google Sheets path is unavailable |
| `PORT` | `8050` | Port the app listens on (Render sets this automatically) |

> **Note:** the License Status workbook and the NEA Operational Data
> workbook are two entirely separate Google Sheets, synced independently,
> on their own schedules, by their own code paths. Setting
> `DEFAULT_SHEET_URL` alone will **not** populate the NEA tabs — you need
> `NEA_SHEET_URL` (or the admin panel's "NEA Data Sync" card) for that.

## Data Sources

### 1. License Status Workbook (DoED)

**Option A — Admin Panel upload**
1. Go to `/admin/login`.
2. Upload an `.xlsx` workbook with columns such as:
   `project_name`, `type`, `status`, `capacity_mw`, `voltage_kv`,
   `line_length_km`, `district`, `province`, `promoter`, `latitude`,
   `longitude`, `license_date`, `cod` (commercial operation date, B.S.).

**Option B — Google Sheet sync**
1. Share the sheet as **"Anyone with the link can view."**
2. Paste the URL in the admin panel, or set `DEFAULT_SHEET_URL`.

**Option C — Local file**
Place `workbook.xlsx` in the `data/` folder before starting.

### 2. NEA Operational Data Workbook (NEA)

Feeds the **System Operational Performance** and **NEA Forecast Lab** tabs.
Set `NEA_SHEET_URL`, or paste the sheet URL/ID into the "NEA Data Sync" card
on `/admin` (this persists to `nea_config.json`, so it survives a restart
without the env var set on the platform).

The sheet must be shared as **"Anyone with the link can view"** and contain
exactly these 11 tabs. Tab names are matched **case- and
whitespace-insensitively** (`"System Loss "` and `"system loss"` both
match), but the wording must match one of the aliases below.

| Internal key | Required tab name | Shape |
|---|---|---|
| `system_loss` | **System Loss** | One row per fiscal year: `Fiscal Year \| Transmission Loss (%) \| Distribution Loss (%) \| System Loss (%)` |
| `financial_data` | **Financial Data** | One row per fiscal year: `Fiscal Year \| Overall Revenue \| Profit/(Loss) \| Import (MU) \| Import (Rs.) \| Export (MU) \| Export (Rs.)` — headers just need the right keywords (e.g. "Import" + "MU", "Import" + "Rs."/"Million") |
| `annual_energy_peak` | **Annual Energy and Peak Load** | One row per category, one column per fiscal year (`Particulars \| FY1 \| FY2 \| ...`). Row labels must contain: "NEA"+"Own", "NEA"+"Sub", "IPP", "India", "Total"+"Availab", "National"+"Peak", "System"+"Peak" |
| `consumers_growth` | **Consumers Growth** | Column-oriented FY, one row per consumer category, plus a "Total Consumers" row and a row containing "growth" |
| `sales_revenue` | **Sales Revenue** | Column-oriented FY, one row per consumer category, plus a "Total Gross Revenue" (or "Total") row and a row containing "growth" |
| `transmission_line` | **Transmission Line Length** | `Fiscal Year (B.S.) \| 66kV \| 132kV \| 220kV \| 400kV \| Total \| Increment` |
| `substation_capacity` | **Substation Capacity** | `Fiscal Year (B.S.) \| Capacity \| Increment` |
| `energy_export` | **Energy Export in GWh** | `Fiscal Year \| 12 month columns` |
| `energy_import` | **Energy Import in GWh from India** | `Fiscal Year \| 12 month columns` |
| `energy_balance` | **Energy Balance in GWh** | Wide grid: row 1 = FY spanning each 12-month block, row 2 = month names, then one row per generation-source category. Row labels must contain: "IPP", "NEA"+"Subsidiary", "ROR", "Import", "NEA"+"Storage", "NEA"+"Solar", "Thermal", "Interruption", "Monthly"+"System"+"Energy"+"Demand", "Export", "Monthly"+"National"+"Energy"+"Demand" |
| `capacity_balance` | **Capacity Balance in MW** | Same wide-grid shape as Energy Balance. Row labels must contain: "IPP", "NEA"+"Subsidiary", "ROR", "Import", "NEA"+"Storage", "Interruption", "Monthly"+"National"+"Peak", "Export", "Monthly"+"System"+"Peak" |

If any of these 11 tabs is missing, `NEA.parse_workbook()` raises a
`ValueError` naming exactly which one(s) are absent — check server logs (or
`/admin`'s sync status) if the NEA tabs come up empty.

**Forecast Lab parameter list:** the Forecast Lab's dropdowns (single-series
and stacked/composite) are built entirely from whatever the 11 sheets above
currently contain — no fiscal year or category is hardcoded. Adding a new
FY column, or a new consumer/revenue category row, shows up automatically
after the next sync; nothing needs to be redeployed.

## GIS Data

The bundled GIS data in `gis_bundled.py` / `nepal_*.geojson` contains
simplified boundaries for all 77 Nepal districts, provinces, local bodies,
and major protected areas — sufficient for choropleth shading and spatial
queries out of the box.

To use higher-resolution boundaries:
1. Obtain shapefiles from the Nepal Survey Department.
2. Simplify with mapshaper: `mapshaper -i input.shp -simplify 10% -o output.shp`
3. Zip and upload via the admin panel, or set `DEFAULT_GIS_DRIVE_URL` /
   `DEFAULT_PA_DRIVE_URL`.

## Visitor Counter (Google Sheets persistence)

The footer visitor counter is designed to **never reset to zero** on a
Render redeploy or restart — it persists to a Google Sheet via a service
account, independent of the license/NEA sheet syncs (which use public,
unauthenticated CSV export and don't need a service account).

Setup:
1. In Google Cloud Console, create a service account and download its JSON
   key.
2. Share the target Google Sheet (`VISITOR_SHEET_ID`, worksheet
   `VISITOR_SHEET_TAB`) with that service account's email as an **Editor**.
3. Set `GOOGLE_SERVICE_ACCOUNT_JSON` to the full JSON key content (as a
   single-line env var value).
4. On boot, `visitor_counter.bootstrap()` pulls the last-saved count in;
   `visitor_counter.start_background_flush()` persists new visits back out
   every `VISITOR_FLUSH_INTERVAL` seconds.

If `GOOGLE_SERVICE_ACCOUNT_JSON` is unset or unreachable, the counter falls
back to `COUNTAPI_BASE`/`COUNTAPI_KEY` and never blocks or crashes startup.

## Google Analytics

GA4 is wired into `app.index_string` via `GA_MEASUREMENT_ID` (defaults to
`G-DD12W6FLZ8` for www.neupanesandeep.com.np). GA runs **alongside** the
durable visitor counter purely for separate analytics reporting — it is not
the source of the displayed visitor count.

## SEO

- **Meta description tag** — set via `meta_tags` in the `dash.Dash(...)`
  constructor in `app.py`, summarizing the dashboard for search indexing.
- **Page title** — set via `title="Nepal Power Plants Dashboard"` in the
  same constructor (renders in the browser tab and search results).
- **Header** — visible on-page title/subtitle in `site-header`, citing
  `www.nea.org.np` as the operational-data source.
- **`/sitemap.xml`** and **`/robots.txt`** — served directly by Flask
  routes at the bottom of `app.py`.

## Admin Panel

`/admin/login` (password: `ADMIN_PASSWORD`) gives access to:

- **Sheet sync** — License Status sheet, NEA Operational Data sheet
- **Workbook upload** — License Status `.xlsx`, NEA Operational Data `.xlsx`
- **GIS sync** — high-res boundary zip, protected-areas zip (Drive links or
  upload)
- **Branding** — logo, flag, hero image, and per-category background images
  (by power-plant type, license status, and province)
- **Marquee toggle** — enable/disable the scrolling ticker bar
- **Sync status** (`/admin/api/status`) — last sync time/result for each
  data source

## API Endpoints

| Route | Method | Purpose |
|---|---|---|
| `/nea-operational-dashboard` | GET | Renders the NEA Operational Performance tab's HTML/Chart.js content |
| `/nea-forecast-lab` | GET | Renders the NEA Forecast Lab tab's HTML/Chart.js content |
| `/api/nea-forecast-params` | GET | Single-series forecastable parameter list |
| `/api/nea-forecast` | POST | Runs one forecast: `{param_key, model, n_ahead, monthly}` → `{past, pred, CI, fit stats}` |
| `/api/nea-forecast-composite-params` | GET | Stacked/composite parameter group list |
| `/api/nea-forecast-composite` | POST | Runs a composite forecast: per-component series plus the summed total |
| `/api/visitor-count` | GET | Current durable visitor count |
| `/nea-vendor/<file>` | GET | Serves the locally-bundled Chart.js (not loaded from a CDN) |
| `/assets-logo`, `/assets-flag`, `/assets-background`, `/assets-type-bg/<slug>`, `/assets-status-bg/<slug>`, `/assets-province-bg/<slug>` | GET | Serve admin-uploaded branding images |
| `/sitemap.xml`, `/robots.txt` | GET | SEO |

## Forecast Lab — Modeling Notes

All model fitting (Linear / Holt / Moving Average / ARIMA / SARIMA /
Linear+ARIMA Hybrid) happens server-side in `NEA.py` using `statsmodels`;
`nea_forecast_lab_template.html` only renders what the API returns.

- **Automatic fallback chain** — if the requested model fails to fit or
  produces an implausible forecast (`_is_reasonable_forecast`), the next
  model in `holt → moving → linear` is tried, ending at Linear Regression,
  which always succeeds.
- **Continuity correction** — every forecast's first predicted point is
  anchored to equal the last real observation exactly, so the
  history→forecast join has zero numeric jump by construction.
- **Straight-line rendering** — chart lines use `tension: 0` so Chart.js's
  default curve-fitting spline can't overshoot at the seam.
- **Independent stack groups** — every `type: "line"` dataset in the
  stacked/composite chart is given its own explicit `stack` id, so
  Chart.js's `scales.y.stacked: true` (needed for the stacked bars) never
  silently sums unrelated line datasets together.

## Deployment

### Render (Recommended)

1. Push to GitHub.
2. Create a new **Web Service** on Render, pointed at this repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:server`
5. Add environment variables as needed (see the table above — remember
   `NEA_SHEET_URL` is separate from `DEFAULT_SHEET_URL`, and set
   `ADMIN_PASSWORD` / `FLASK_SECRET_KEY` / `GOOGLE_SERVICE_ACCOUNT_JSON`
   explicitly for production).
6. Render sets `PORT` automatically; no change needed.

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "app:server", "--bind", "0.0.0.0:8050"]
```

```bash
docker build -t nepal-power-plants-dashboard .
docker run -p 8050:8050 \
  -e DEFAULT_SHEET_URL="..." \
  -e NEA_SHEET_URL="..." \
  -e ADMIN_PASSWORD="..." \
  -e GOOGLE_SERVICE_ACCOUNT_JSON='{"...": "..."}' \
  nepal-power-plants-dashboard
```

## Troubleshooting

- **"Chart is not defined" errors on NEA charts / Forecast Lab** — Chart.js
  is bundled locally at `nea_assets/vendor/chart.umd.min.js` and served via
  `/nea-vendor/<file>` specifically because a blocked/slow/ad-blocked CDN
  request was the historical cause of this. If it recurs, confirm that
  route is reachable and the vendor file is present.
- **NEA tabs show no data** — confirm `NEA_SHEET_URL` (or the admin panel's
  NEA Data Sync card) is set and the sheet is shared as "Anyone with the
  link can view." Check `/admin/api/status` or server logs for the specific
  missing-tab error from `NEA.parse_workbook()`.
- **Visitor counter resets or shows a fallback count** — confirm
  `GOOGLE_SERVICE_ACCOUNT_JSON` is set and the service account has Editor
  access to `VISITOR_SHEET_ID`.
- **Admin login fails after redeploy** — set a fixed `FLASK_SECRET_KEY`;
  without it a new random key is generated on every boot, invalidating
  existing sessions/cookies.

## Recent Changes

- Renamed to **Nepal Power Plants Dashboard**; header now cites
  `www.nea.org.np` as source, with an SEO meta description tag and updated
  page title for Google indexing.
- Fixed a rendering bug in the NEA Forecast Lab's stacked/composite chart
  where the history→forecast seam could show roughly double the base-year
  value: Chart.js was silently grouping same-type (`line`) datasets into
  one stack because `scales.y.stacked: true` applies chart-wide and none of
  those datasets had an explicit `stack` id. Each line dataset now has its
  own `stack` id, and the seam point is simply the base year value
  connected straight to the first forecasted year.

## License

© 2026 Er. Sandeep Neupane. All rights reserved.
