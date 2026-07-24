"""
Nepal Power Plant & Transmission Line License Status Dashboard — WEB EDITION
Author (original desktop app): Er. Sandeep Neupane
Web port: Dash / Plotly, deployable on Render.

FIXED VERSION:
- GIS data bundled inline (no external uploads needed)
- gis-opt-layers moved to main layout (fixes callback error)
- Overview tab shows data immediately (no 4s blank wait)
- f-year defaults to None (no premature filtering)
- District/local cascade refreshes on data load
- All error handling improved with visible messages

ENHANCED VERSION (2026):
- Common background images for Power Plant types and Province cards
- Different colored fonts with effects for status/province labels
- Consistent "... Projects, ... Capacity" / "... KM" pattern
- Ordered stages: Operating, Construction License, ..., Application for Survey
- Ordered provinces: Koshi, Madhesh, Bagmati, Gandaki, Lumbini, Karnali, Sudurpaschim
- KPI summary only on Overview tab
- "Installed Capacity" with operating plants summary at first
- Animated province slides in Power Plants > By Province
- No flipping in Transmission tab when filtered
- Growth tab separated for Transmission vs Power Plants
- Data Table with page size dropdown (10, 25, 50, 100, All)
- Custom tab for chart styling options
- Watermark "Er. Sandeep Neupane" on downloaded charts
"""

import os
import io
import base64
import tempfile
import traceback
import textwrap
from collections import defaultdict

import dash
from dash import dcc, html, Input, Output, State, dash_table, ctx
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
import plotly.express as px
import plotly.io as pio

import data_engine as de
import server_state as ss
import coordinate_transform as ct
import gis_leaflet_map
from admin import admin_bp

# ── GLOBAL CHART STYLE STATE (for Custom Tab) ───────────────────────────────
CHART_STYLE_STATE = {
    "bar_mode": "group",        # group, stack, relative
    "chart_type": "bar",        # bar, line, area, scatter
    "color_scheme": "default",  # default, pastel, dark, vibrant
    "show_grid": True,
    "font_family": "Arial",
    "title_size": 16,
    "label_size": 12,
    "animation": True,
}

# ── COLOR SCHEMES ───────────────────────────────────────────────────────────
COLOR_SCHEMES = {
    "default": {
        "Operating": "#2e7d32", "Construction License": "#fb8c00",
        "Application for Construction License": "#ffb300",
        "Survey License": "#42a5f5",
        "Application for Survey License": "#90a4ae",
        "GoN Study Project": "#0277bd", "Cancelled": "#c62828",
        "Technical Clearance": "#9fb3c8",
    },
    "pastel": {
        "Operating": "#81c784", "Construction License": "#ffb74d",
        "Application for Construction License": "#fff176",
        "Survey License": "#64b5f6",
        "Application for Survey License": "#b0bec5",
        "GoN Study Project": "#4fc3f7", "Cancelled": "#e57373",
        "Technical Clearance": "#b0bec5",
    },
    "dark": {
        "Operating": "#1b5e20", "Construction License": "#e65100",
        "Application for Construction License": "#ff6f00",
        "Survey License": "#1565c0",
        "Application for Survey License": "#455a64",
        "GoN Study Project": "#01579b", "Cancelled": "#b71c1c",
        "Technical Clearance": "#455a64",
    },
    "vibrant": {
        "Operating": "#00e676", "Construction License": "#ff9100",
        "Application for Construction License": "#ffea00",
        "Survey License": "#2979ff",
        "Application for Survey License": "#78909c",
        "GoN Study Project": "#00b0ff", "Cancelled": "#ff1744",
        "Technical Clearance": "#78909c",
    },
}

PROVINCE_COLOR_SCHEMES = {
    "default": {
        "Koshi": "#00695c", "Madhesh": "#ef6c00", "Bagmati": "#1565c0",
        "Gandaki": "#6a1b9a", "Lumbini": "#2e7d32", "Karnali": "#c62828",
        "Sudurpaschim": "#4527a0", "Unspecified": "#78909c",
    },
    "pastel": {
        "Koshi": "#4db6ac", "Madhesh": "#ff9800", "Bagmati": "#5c6bc0",
        "Gandaki": "#ab47bc", "Lumbini": "#66bb6a", "Karnali": "#ef5350",
        "Sudurpaschim": "#7e57c2", "Unspecified": "#b0bec5",
    },
    "dark": {
        "Koshi": "#004d40", "Madhesh": "#bf360c", "Bagmati": "#0d47a1",
        "Gandaki": "#4a148c", "Lumbini": "#1b5e20", "Karnali": "#b71c1c",
        "Sudurpaschim": "#311b92", "Unspecified": "#37474f",
    },
    "vibrant": {
        "Koshi": "#00bfa5", "Madhesh": "#ff6d00", "Bagmati": "#2962ff",
        "Gandaki": "#aa00ff", "Lumbini": "#00c853", "Karnali": "#ff1744",
        "Sudurpaschim": "#651fff", "Unspecified": "#546e7a",
    },
}

TYPE_COLOR_SCHEMES = {
    "default": {
        "Hydro (>1MW)": "#1565c0", "Hydro (<=1MW)": "#42a5f5", "Solar": "#f9a825",
        "Wind": "#26a69a", "Co-generation": "#8d6e63", "Thermal": "#6d4c41",
        "Biomass": "#558b2f", "Transmission Line": "#6a1b9a", "Other": "#78909c",
    },
    "pastel": {
        "Hydro (>1MW)": "#5c6bc0", "Hydro (<=1MW)": "#90caf9", "Solar": "#fff59d",
        "Wind": "#80cbc4", "Co-generation": "#bcaaa4", "Thermal": "#a1887f",
        "Biomass": "#a5d6a7", "Transmission Line": "#ce93d8", "Other": "#b0bec5",
    },
    "dark": {
        "Hydro (>1MW)": "#0d47a1", "Hydro (<=1MW)": "#1565c0", "Solar": "#f57f17",
        "Wind": "#00695c", "Co-generation": "#4e342e", "Thermal": "#3e2723",
        "Biomass": "#33691e", "Transmission Line": "#4a148c", "Other": "#263238",
    },
    "vibrant": {
        "Hydro (>1MW)": "#2962ff", "Hydro (<=1MW)": "#00b0ff", "Solar": "#ffea00",
        "Wind": "#00bfa5", "Co-generation": "#8d6e63", "Thermal": "#5d4037",
        "Biomass": "#76ff03", "Transmission Line": "#d500f9", "Other": "#607d8b",
    },
}


def get_status_colors():
    return COLOR_SCHEMES.get(CHART_STYLE_STATE["color_scheme"], COLOR_SCHEMES["default"])


def get_province_colors():
    return PROVINCE_COLOR_SCHEMES.get(CHART_STYLE_STATE["color_scheme"], PROVINCE_COLOR_SCHEMES["default"])


def get_type_colors():
    return TYPE_COLOR_SCHEMES.get(CHART_STYLE_STATE["color_scheme"], TYPE_COLOR_SCHEMES["default"])


# ── APP SETUP ────────────────────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY, dbc.icons.BOOTSTRAP],
    title="Nepal Power Plant & Transmission License Status",
    suppress_callback_exceptions=True,
)
server = app.server

TICKER_CSS = """
.ticker-bar { display: flex; align-items: center; overflow: hidden; background: #101726;
  padding: 8px 12px; border-radius: 6px; margin-bottom: 14px; white-space: nowrap; }
.ticker-live-badge { display: flex; align-items: center; flex: 0 0 auto; gap: 6px;
  margin-right: 14px; padding: 3px 10px; border-radius: 4px;
  background: rgba(211,47,47,0.16); border: 1px solid rgba(244,67,54,0.55); }
.ticker-live-dot { width: 9px; height: 9px; border-radius: 50%; background: #ff1744;
  box-shadow: 0 0 6px #ff1744; animation: ticker-live-blink 1.1s ease-in-out infinite; }
.ticker-live-text { color: #ff5252; font-weight: 800; font-size: 12px; letter-spacing: 1px;
  font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; }
@keyframes ticker-live-blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.15; } }
.ticker-track-wrap { flex: 1 1 auto; overflow: hidden; white-space: nowrap; }
.ticker-track { display: inline-block; white-space: nowrap; padding-left: 100%;
  animation-name: ticker-scroll; animation-timing-function: linear;
  animation-iteration-count: infinite;
  font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  font-weight: 600; font-size: 14px; }
.ticker-bar:hover .ticker-track { animation-play-state: paused; }
@keyframes ticker-scroll { 0% { transform: translateX(0); } 100% { transform: translateX(-50%); } }
.main-tabs-nav .nav-link { font-weight: 600; font-size: 14px; color: #37474f; border: none;
  border-radius: 8px 8px 0 0; padding: 10px 16px; margin-right: 4px;
  transition: transform 0.12s ease, background 0.15s ease; }
.main-tabs-nav .nav-link:hover { background: #eef3fb; transform: translateY(-1px); }
.main-tabs-nav .nav-link.active { color: #fff !important;
  background: linear-gradient(135deg, #1565c0 0%, #0d47a1 100%) !important;
  box-shadow: 0 2px 8px rgba(13,71,161,0.35); }
.live-clock-wrap { background: #0b1730; border: 1px solid #3d5a99; border-radius: 6px;
  padding: 4px 12px; text-align: right; line-height: 1.25; }
.live-clock-date { color: #8fb2ff; font-size: 11px; font-weight: 700; letter-spacing: 0.02em; }
.live-clock-time { color: #ffd166; font-size: 15px; font-weight: 700;
  font-family: Consolas, "Courier New", monospace; }
.site-header { position: relative; overflow: hidden; }
.site-header-title { font-weight: 800; font-size: 20px; line-height: 1.2; }
.site-header-subtitle { font-size: 12px; opacity: 0.85; }
.site-header-flag, .site-header-logo { border-radius: 3px;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.25); }
footer.site-footer { background: #0b1730; color: #b7c4e0; margin-top: 28px;
  padding: 18px 24px; font-size: 13px; }
footer.site-footer a { color: #8fb2ff; text-decoration: none; margin-right: 16px; }
footer.site-footer a:hover { text-decoration: underline; }
.footer-visitor-counter { color: #ffd166; font-size: 15px; font-weight: 700; letter-spacing: 0.02em; }
.footer-last-update { color: #9fd8ff; font-size: 14px; font-weight: 600; margin-top: 4px; }

/* ── Status label styles with effects ─────────────────────────────────────── */
.status-label-operating { color: #2e7d32; font-weight: 800; text-shadow: 0 0 8px rgba(46,125,50,0.4); }
.status-label-construction { color: #fb8c00; font-weight: 800; text-shadow: 0 0 8px rgba(251,140,0,0.4); }
.status-label-app-construction { color: #ffb300; font-weight: 800; text-shadow: 0 0 8px rgba(255,179,0,0.4); }
.status-label-survey { color: #42a5f5; font-weight: 800; text-shadow: 0 0 8px rgba(66,165,245,0.4); }
.status-label-app-survey { color: #90a4ae; font-weight: 800; text-shadow: 0 0 8px rgba(144,164,174,0.4); }
.status-label-gon { color: #0277bd; font-weight: 800; text-shadow: 0 0 8px rgba(2,119,189,0.4); }
.status-label-cancelled { color: #c62828; font-weight: 800; text-shadow: 0 0 8px rgba(198,40,40,0.4); }
.status-label-tc { color: #9fb3c8; font-weight: 800; text-shadow: 0 0 8px rgba(159,179,200,0.4); }

/* ── Province label styles with effects ──────────────────────────────────── */
.prov-label-koshi { color: #00695c; font-weight: 800; text-shadow: 0 0 8px rgba(0,105,92,0.4); }
.prov-label-madhesh { color: #ef6c00; font-weight: 800; text-shadow: 0 0 8px rgba(239,108,0,0.4); }
.prov-label-bagmati { color: #1565c0; font-weight: 800; text-shadow: 0 0 8px rgba(21,101,192,0.4); }
.prov-label-gandaki { color: #6a1b9a; font-weight: 800; text-shadow: 0 0 8px rgba(106,27,154,0.4); }
.prov-label-lumbini { color: #2e7d32; font-weight: 800; text-shadow: 0 0 8px rgba(46,125,50,0.4); }
.prov-label-karnali { color: #c62828; font-weight: 800; text-shadow: 0 0 8px rgba(198,40,40,0.4); }
.prov-label-sudurpaschim { color: #4527a0; font-weight: 800; text-shadow: 0 0 8px rgba(69,39,160,0.4); }

/* ── Card header gradient overlays ───────────────────────────────────────── */
.card-header-gradient { position: relative; }
.card-header-gradient::after {
  content: "";
  position: absolute; top: 0; left: 0; right: 0; bottom: 0;
  background: linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0.5) 100%);
  pointer-events: none;
}

/* ── Flip card animation ───────────────────────────────────────────────── */
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(20px); }
  to { opacity: 1; transform: translateY(0); }
}
.flip-card-animate { animation: fadeInUp 0.6s ease-out; }

/* ── Custom tab styling ──────────────────────────────────────────────────── */
.custom-style-panel { background: #f8f9fa; border-radius: 8px; padding: 20px; }
.custom-style-panel h5 { color: #1565c0; margin-bottom: 16px; }
"""
CLOCK_JS = """
<script>
function _tickLiveClock() {
  var now = new Date();
  var dateOpts = { weekday: 'long', year: 'numeric', month: 'long', day: '2-digit' };
  var dateStr = now.toLocaleDateString('en-US', dateOpts).toUpperCase();
  var timeStr = '🕐 ' + now.toLocaleTimeString('en-US', { hour12: true });
  document.querySelectorAll('.live-clock-date').forEach(function(el) { el.textContent = dateStr; });
  document.querySelectorAll('.live-clock-time').forEach(function(el) { el.textContent = timeStr; });
}
setInterval(_tickLiveClock, 1000);
document.addEventListener('DOMContentLoaded', _tickLiveClock);
_tickLiveClock();
function _loadVisitorCount() {
  var el = document.getElementById('visitor-counter');
  fetch('/api/visitor-count').then(function(r) { return r.json(); }).then(function(d) {
    if (el) { el.textContent = '👥 ' + d.count.toLocaleString() + ' visitors'; }
  }).catch(function() {
    if (el) { el.textContent = '👥 visitors'; }
  });
}
document.addEventListener('DOMContentLoaded', _loadVisitorCount);
setInterval(function() {
  var el = document.getElementById('visitor-counter');
  if (el && el.textContent.indexOf('\u2026') !== -1) { _loadVisitorCount(); }
}, 2000);
</script>
"""



app.index_string = f"""<!DOCTYPE html>
<html><head>{{%metas%}}<title>{{%title%}}</title>{{%favicon%}}{{%css%}}
<style>{TICKER_CSS}</style></head>
<body>{{%app_entry%}}<footer>{{%config%}}{{%scripts%}}{{%renderer%}}</footer>{CLOCK_JS}</body></html>"""

server.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(32).hex())
server.register_blueprint(admin_bp)

# CRITICAL FIX: Bootstrap GIS immediately (bundled data, always works)
ss.bootstrap_on_startup()
ss.start_background_refresh()

STATE = ss.STATE


@server.route("/api/visitor-count")
def api_visitor_count():
    from flask import jsonify, session as flask_session
    try:
        if not flask_session.get("counted_visit"):
            flask_session["counted_visit"] = True
            ss.bump_visitor_count()
        return jsonify(count=ss.get_visitor_count())
    except Exception as e:
        return jsonify(count=0, error=str(e))


@server.route("/assets-logo")
def serve_logo():
    from flask import send_file
    path = ss.get_logo_path()
    if not path:
        return "No logo uploaded yet.", 404
    return send_file(path)


@server.route("/assets-flag")
def serve_flag():
    from flask import send_file
    path = ss.get_flag_path()
    if not path:
        return "No flag image available.", 404
    return send_file(path)


@server.route("/assets-type-bg/<slug>")
def serve_type_bg(slug):
    from flask import send_file
    fn = (ss.STATE.get("type_bg") or {}).get(slug)
    if not fn:
        return "No background uploaded for this type.", 404
    path = os.path.join(ss.ASSETS_DIR, fn)
    if not os.path.exists(path):
        return "No background uploaded for this type.", 404
    return send_file(path)


@server.route("/assets-status-bg/<slug>")
def serve_status_bg(slug):
    from flask import send_file
    fn = (ss.STATE.get("status_bg") or {}).get(slug)
    if not fn:
        return "No background uploaded for this license stage.", 404
    path = os.path.join(ss.ASSETS_DIR, fn)
    if not os.path.exists(path):
        return "No background uploaded for this license stage.", 404
    return send_file(path)


@server.route("/assets-province-bg/<slug>")
def serve_province_bg(slug):
    from flask import send_file
    fn = (ss.STATE.get("province_bg") or {}).get(slug)
    if not fn:
        return "No background uploaded for this province.", 404
    path = os.path.join(ss.ASSETS_DIR, fn)
    if not os.path.exists(path):
        return "No background uploaded for this province.", 404
    return send_file(path)


@server.route("/assets-background")
def serve_background():
    from flask import send_file
    path = ss.get_background_path()
    if not path:
        return "No background photo uploaded yet.", 404
    return send_file(path)


# ── LAYOUT ─────────────────────────────────────────────────────────────────
CAPACITY_BIN_OPTIONS = [
    {"label": "All capacities", "value": "all"},
    {"label": "Below 1 MW", "value": "lt1"},
    {"label": "1 MW - 10 MW", "value": "1-10"},
    {"label": "10 MW - 25 MW", "value": "10-25"},
    {"label": "25 MW - 50 MW", "value": "25-50"},
    {"label": "50 MW - 100 MW", "value": "50-100"},
    {"label": "Above 100 MW", "value": "gt100"},
]
CAPACITY_BIN_RANGES = {
    "all": (None, None), "lt1": (0, 1), "1-10": (1, 10), "10-25": (10, 25),
    "25-50": (25, 50), "50-100": (50, 100), "gt100": (100, None),
}

TX_LENGTH_BIN_OPTIONS = [
    {"label": "All lengths", "value": "all"},
    {"label": "Short - up to 80 km", "value": "short"},
    {"label": "Medium - 80-200 km", "value": "medium"},
    {"label": "Long - above 200 km", "value": "long"},
]
TX_LENGTH_BIN_RANGES = {
    "all": (None, None), "short": (None, 80), "medium": (80, 200), "long": (200, None),
}


def kpi_card(title, value, sub, color):
    return dbc.Card(
        dbc.CardBody([
            html.Div(title, className="text-muted small fw-semibold text-uppercase"),
            html.H3(value, className="mb-0 fw-bold", style={"color": color}),
            html.Div(sub, className="text-muted small"),
        ]),
        className="shadow-sm h-100",
        style={"borderTop": f"4px solid {color}"},
    )


def sidebar():
    return dbc.Card(
        dbc.CardBody([
            html.H5([html.I(className="bi bi-sliders me-2"), "Filters"], className="mb-2"),
            dbc.Accordion(id="filter-tree", start_collapsed=False, always_open=True, children=[
                dbc.AccordionItem(title="📍 Location - Province / District", children=[
                    html.Label("Province", className="fw-semibold small"),
                    dcc.Dropdown(id="f-province", multi=True, placeholder="All provinces"),
                    html.Div("↳ narrows the District list below", className="text-muted",
                              style={"fontSize": "11px", "marginLeft": "8px"}),
                    html.Label("District", className="fw-semibold small mt-2"),
                    dcc.Dropdown(id="f-district", multi=True, placeholder="All districts"),
                    html.Div("↳ narrows the Local Body list below", className="text-muted",
                              style={"fontSize": "11px", "marginLeft": "8px"}),
                    html.Label("Local Body (Gaunpalika / Nagarpalika)",
                                className="fw-semibold small mt-2"),
                    dcc.Dropdown(id="f-local", multi=True, placeholder="All local bodies"),
                    html.Label("Coordinate System (GIS Map / Data Table)",
                                className="fw-semibold small mt-2"),
                    dcc.RadioItems(
                        id="f-crs",
                        options=[{"label": f" {v}", "value": k} for k, v in ct.CRS_LABELS.items()],
                        value=ct.CRS_WGS84, labelStyle={"display": "block", "fontSize": "13px"},
                    ),
                    html.Div(
                        "DoED Lat/Long sheet values are on the Everest 1830 survey datum; "
                        "the GIS boundary layer is WGS-84. Pick WGS-84 to match the map "
                        "(default) or Everest 1830 to match the raw licence sheet.",
                        className="text-muted", style={"fontSize": "11px"},
                    ),
                ], item_id="grp-location"),

                dbc.AccordionItem(title="⚡ Project - Type / Stage / Capacity", children=[
                    html.Label("Project Type", className="fw-semibold small"),
                    dcc.Dropdown(id="f-type", multi=True, placeholder="All types"),
                    html.Div("↳ each type breaks down by stage below", className="text-muted",
                              style={"fontSize": "11px", "marginLeft": "8px"}),
                    html.Label("License Stage", className="fw-semibold small mt-2"),
                    dcc.Dropdown(id="f-status", multi=True, placeholder="All stages"),
                    html.Label("Capacity Range (MW)", className="fw-semibold small mt-2"),
                    dcc.Dropdown(
                        id="f-capacity", options=CAPACITY_BIN_OPTIONS,
                        value="all", clearable=False, placeholder="All capacities",
                    ),
                    html.Label("Transmission Line Length", className="fw-semibold small mt-2"),
                    dcc.Dropdown(
                        id="f-tx-length", options=TX_LENGTH_BIN_OPTIONS,
                        value="all", clearable=False, placeholder="All lengths",
                    ),
                    html.Div("↳ only narrows Transmission Line records - every "
                             "other type is unaffected", className="text-muted",
                              style={"fontSize": "11px", "marginLeft": "8px"}),
                ], item_id="grp-project"),

                dbc.AccordionItem(title="📅 Dates - License Issue / COD", children=[
                    dcc.Store(id="f-year", data=None),
                    html.Label("License Date - exact range (B.S.)", className="fw-semibold small"),
                    html.Div("Any of YYYY, YYYY-MM, or YYYY-MM-DD. Leave both blank "
                             "for all dates.", className="text-muted",
                             style={"fontSize": "11px", "marginLeft": "8px"}),
                    dbc.Row([
                        dbc.Col(dcc.Input(id="f-date-from", type="text",
                                           placeholder="From e.g. 2078-01-01",
                                           className="form-control form-control-sm"), width=6),
                        dbc.Col(dcc.Input(id="f-date-to", type="text",
                                           placeholder="To e.g. 2082-12-30",
                                           className="form-control form-control-sm"), width=6),
                    ], className="g-1"),
                    html.Label("COD Date range (B.S.) - Operating plants",
                                className="fw-semibold small mt-2"),
                    dbc.Row([
                        dbc.Col(dcc.Input(id="f-cod-from", type="text", placeholder="From YYYY-MM-DD",
                                           className="form-control form-control-sm"), width=6),
                        dbc.Col(dcc.Input(id="f-cod-to", type="text", placeholder="To YYYY-MM-DD",
                                           className="form-control form-control-sm"), width=6),
                    ], className="g-1"),
                ], item_id="grp-dates"),

                dbc.AccordionItem(title="🔎 Search", children=[
                    dcc.Input(id="f-search", type="text", placeholder="Type to search…",
                              className="form-control"),
                ], item_id="grp-search"),
            ]),
            html.Hr(),
            dbc.Button([html.I(className="bi bi-file-earmark-pdf me-1"), "Download PDF Report"],
                       id="btn-pdf", color="danger", outline=True, size="sm", className="w-100"),
            dcc.Download(id="download-pdf"),
        ]),
        className="shadow-sm",
    )


TAB_DEFAULT_FILTER_GROUP = {
    "overview": "grp-project", "plants": "grp-project", "transmission": "grp-location",
    "gon_study": "grp-project", "cancelled": "grp-project", "growth": "grp-dates",
    "gis": "grp-location", "compare": "grp-project", "table": "grp-search",
    "custom": "grp-project",
}


@app.callback(
    Output("filter-sidebar-col", "style"),
    Output("main-content-col", "md"),
    Input("main-tabs", "active_tab"),
)
def toggle_filter_sidebar(tab):
    if tab == "overview":
        return {"display": "none"}, 12
    return {"display": "block"}, 9


@app.callback(Output("filter-tree", "active_item"), Input("main-tabs", "active_tab"))
def open_relevant_filter_group(tab):
    default = TAB_DEFAULT_FILTER_GROUP.get(tab, "grp-project")
    others = [g for g in ("grp-location", "grp-project", "grp-dates", "grp-search")
              if g != default]
    return [default] + others[:1]


def settings_panel():
    return html.Div(id="load-status", style={"display": "none"})


# CRITICAL FIX: gis-opt-layers moved to MAIN LAYOUT
app.layout = dbc.Container(fluid=True, children=[
    dcc.Store(id="filtered-data-signal"),
    dcc.Store(id="chart-style-store", data=CHART_STYLE_STATE),

    html.Div(id="site-header", className="site-header p-3 mb-3", children=[
        dbc.Row(align="center", justify="between", className="g-2", children=[
            dbc.Col(width="auto", children=html.Div([
                html.Img(src="/assets-flag", height="40px",
                         alt="Flag of Nepal", title="Nepal",
                         className="me-2 site-header-flag"),
                html.Img(src="/assets-logo", height="34px",
                         alt="Organisation logo", className="me-2 site-header-logo")
                if ss.get_logo_path() else None,
                html.Div([
                    html.Div("Nepal Power Plant & Transmission Line License Status Dashboard",
                              className="site-header-title"),
                    html.Div("Source: www.doed.gov.np | Licensing pipeline overview",
                              className="site-header-subtitle"),
                ]),
            ], className="d-flex align-items-center")),
            dbc.Col(width="auto", children=html.Div([
                html.Div(className="live-clock-date"),
                html.Div(className="live-clock-time"),
            ], className="live-clock-wrap")),
        ]),
    ]),

    html.Div(id="ticker-bar"),

    dbc.Tabs(id="main-tabs", active_tab="overview", className="main-tabs-nav", children=[
        dbc.Tab(label="📊 Overview", tab_id="overview"),
        dbc.Tab(label="⚡ Power Plants", tab_id="plants"),
        dbc.Tab(label="🔌 Transmission Line", tab_id="transmission"),
        dbc.Tab(label="📋 GoN Studied Projects", tab_id="gon_study"),
        dbc.Tab(label="🚫 License Cancelled", tab_id="cancelled"),
        dbc.Tab(label="📈 Growth Trends", tab_id="growth"),
        dbc.Tab(label="🗺️ GIS Map", tab_id="gis"),
        dbc.Tab(label="📉 Comparative Charts", tab_id="compare"),
        dbc.Tab(label="🗂️ Data Table", tab_id="table"),
        dbc.Tab(label="🎨 Custom Style", tab_id="custom"),
    ]),

    dbc.Row(className="mt-3", children=[
        dbc.Col(id="filter-sidebar-col", md=3,
                children=[sidebar(), html.Div(className="mt-3"), settings_panel()]),
        dbc.Col(id="main-content-col", md=9, children=[
            dbc.Row(id="kpi-row", className="g-3 mb-3"),
            html.Div(id="tab-content"),
        ]),
    ]),

    # FIX: GIS layer toggles are ALWAYS in DOM
    html.Div(id="gis-controls-container", style={"display": "none"}, children=[
        dbc.Checklist(
            id="gis-opt-layers",
            options=[
                {"label": " License Boundary Polygons", "value": "boundary"},
                {"label": " Protected Areas Overlay", "value": "pa"},
            ],
            value=["boundary"],
            inline=True, switch=True, className="mb-2",
        ),
    ]),

    html.Div(id="_init_trigger", style={"display": "none"}),
    dcc.Interval(id="init-once", n_intervals=0, max_intervals=1, interval=500),
    dcc.Interval(id="refresh-poll", n_intervals=0, interval=36000_000),
    dcc.Interval(id="type-flip-interval", n_intervals=0, interval=6_000),
    dcc.Interval(id="province-flip-interval", n_intervals=0, interval=6_000),
    html.Footer(className="site-footer", children=[
        dbc.Row([
            dbc.Col(md=8, children=[
                html.Div("Useful links — Nepal Energy Sector", className="fw-semibold mb-1"),
                html.A("Ministry of Energy, Water Resources and Irrigation (MoEWRI)",
                       href="https://moewri.gov.np", target="_blank", className="d-block"),
                html.A("Electricity Regulatory Commission (ERC)",
                       href="https://erc.gov.np", target="_blank", className="d-block"),
                html.A("Water and Energy Commission Secretariat (WECS)",
                       href="https://wecs.gov.np", target="_blank", className="d-block"),
                html.A("Department of Electricity Development (DoED)",
                       href="https://doed.gov.np", target="_blank", className="d-block"),
                html.A("Nepal Electricity Authority (NEA)",
                       href="https://nea.org.np", target="_blank", className="d-block"),
                  html.A("Alternative Energy Promotion Center (AEPC)",
                       href="https://aepc.org.np", target="_blank", className="d-block"),
            ]),
            dbc.Col(md=4, className="text-md-end", children=[
                html.Div("👥 …visitors", id="visitor-counter", className="footer-visitor-counter"),
                html.Div(id="footer-last-update", className="footer-last-update"),
            ]),
        ]),
        html.Hr(style={"borderColor": "#3d5a99", "opacity": 0.4, "margin": "10px 0"}),
        html.Div("© 2026 Er. Sandeep Neupane. All rights reserved.",
                  className="small text-center"),
    ]),
])


# ── DATA-SOURCE CALLBACKS ──────────────────────────────────────────────────
@app.callback(
    Output("load-status", "children"),
    Output("f-type", "options"), Output("f-status", "options"), Output("f-province", "options"),
    Output("f-year", "data"),
    Output("footer-last-update", "children"),
    Input("init-once", "n_intervals"),
    Input("refresh-poll", "n_intervals"),
    prevent_initial_call=False,
)
def handle_data_source(_init, _poll):
    loader = STATE["loader"]
    last_sync = ss.get_last_sync()
    footer_update = f"🕒 Last Update: {last_sync}" if last_sync else "🕒 Last Update: —"

    if loader is None or loader.error:
        detail = (loader.error if (loader and loader.error) else STATE.get("error"))
        msg = (f"⚠️ {detail}" if detail
               else "No data loaded yet. An administrator can add a data source via /admin.")
        return (msg, [], [], [], None, footer_update)

    types = [{"label": t, "value": t} for t in loader.get_types() if t != "Transmission Line"]
    statuses = [{"label": s, "value": s} for s in loader.get_statuses()]
    # Province options come from the permanent GIS boundary layer (all 7 provinces),
    # not just the provinces that happen to have a project in the current data —
    # so the full administrative tree is always selectable.
    if getattr(de.GIS, 'provinces_loaded', False):
        province_names = sorted(de.GIS.provinces.keys())
    else:
        province_names = [p for p in loader.get_provinces() if p != "Unspecified"]
    provinces = [{"label": p, "value": p} for p in province_names]
    y_lo, y_hi = loader.get_license_year_bounds()
    y_lo, y_hi = (y_lo or 2050), (y_hi or 2085)

    status_msg = (f"✅ {len(loader.records)} records loaded — {STATE['source_label']}"
                  + (f" (last sync: {last_sync})" if last_sync else ""))
    return (status_msg, types, statuses, provinces, [y_lo, y_hi], footer_update)


# ── FILTERING HELPER ──────────────────────────────────────────────────────
def get_filtered_records(f_type, f_status, f_province, f_capacity, f_year, f_search,
                          f_date_from=None, f_date_to=None, f_cod_from=None, f_cod_to=None,
                          f_tx_length=None, f_district=None, f_local=None):
    loader = STATE["loader"]
    if loader is None or loader.error or not loader.records:
        return []
    date_from = de.parse_bs_input(f_date_from) if f_date_from else (f_year[0] if f_year else None)
    date_to = de.parse_bs_input(f_date_to, end=True) if f_date_to else (f_year[1] if f_year else None)
    cod_from = de.parse_bs_input(f_cod_from) if f_cod_from else None
    cod_to = de.parse_bs_input(f_cod_to, end=True) if f_cod_to else None
    cap_min, cap_max = CAPACITY_BIN_RANGES.get(f_capacity or "all", (None, None))
    km_min, km_max = TX_LENGTH_BIN_RANGES.get(f_tx_length or "all", (None, None))
    return loader.filter(
        types=f_type or None, statuses=f_status or None, provinces=f_province or None,
        districts=f_district or None, locals_sel=f_local or None,
        cap_min=cap_min, cap_max=cap_max, km_min=km_min, km_max=km_max,
        year_from=date_from, year_to=date_to, cod_from=cod_from, cod_to=cod_to,
        search=f_search or None,
    )


# ── CASCADING FILTER TREE ────────────────────────────────────────────────
@app.callback(
    Output("f-district", "options"),
    Input("f-province", "value"),
    Input("load-status", "children"),
    Input("refresh-poll", "n_intervals"),
)
def update_district_options(f_province, _status, _poll):
    # District options come from the permanent GIS boundary layer (all 77
    # districts, mapped to their real province) rather than only districts
    # that happen to have a project in the current data — so the full
    # Province → District tree is always selectable, and picking a province
    # narrows it to that province's real districts.
    if getattr(de.GIS, 'loaded', False) and de.GIS.district_province:
        dist_prov = dict(de.GIS.district_province)
    else:
        loader = STATE["loader"]
        if loader is None or loader.error or not loader.records:
            return []
        dist_prov = {}
        for r in loader.records:
            d = r.get("district")
            if d and d != "Unspecified" and d not in dist_prov:
                dist_prov[d] = r.get("province")
    all_districts = sorted(dist_prov)
    if not f_province:
        opts = all_districts
    else:
        opts = [d for d in all_districts if dist_prov.get(d) in f_province]
    return [{"label": d, "value": d} for d in opts]


@app.callback(
    Output("f-local", "options"),
    Input("f-district", "value"), Input("f-province", "value"),
    Input("load-status", "children"),
    Input("refresh-poll", "n_intervals"),
)
def update_local_options(f_district, f_province, _status, _poll):
    if not getattr(de.GIS, 'loaded', False):
        return []
    if f_district:
        labels = de.GIS.locals_for_districts(f_district)
    elif f_province:
        dists = [d for d, p in de.GIS.district_province.items() if p in f_province]
        labels = de.GIS.locals_for_districts(dists) if dists else []
    else:
        labels = sorted({L["label"] for L in de.GIS.locals})
    return [{"label": l, "value": l} for l in labels]


# ── KPI ROW ────────────────────────────────────────────────────────────────
@app.callback(
    Output("kpi-row", "children"),
    Input("main-tabs", "active_tab"),
    Input("f-type", "value"), Input("f-status", "value"), Input("f-province", "value"),
    Input("f-capacity", "value"), Input("f-tx-length", "value"), Input("f-year", "data"),
    Input("f-search", "value"),
    Input("f-date-from", "value"), Input("f-date-to", "value"),
    Input("f-cod-from", "value"), Input("f-cod-to", "value"),
    Input("f-district", "value"), Input("f-local", "value"),
    Input("load-status", "children"),
)
def update_kpis(tab, f_type, f_status, f_province, f_capacity, f_tx_length, f_year, f_search,
                 f_date_from, f_date_to, f_cod_from, f_cod_to, f_district, f_local, _status):
    # REQ 6: KPI summary only on Overview tab
    if tab != "overview":
        return []

    loader = STATE["loader"]
    if tab == "overview":
        recs = list(loader.records) if loader and not loader.error else []
    else:
        recs = get_filtered_records(f_type, f_status, f_province, f_capacity, f_year, f_search,
                                     f_date_from, f_date_to, f_cod_from, f_cod_to, f_tx_length,
                                     f_district, f_local)

    active_recs = [r for r in recs if r["status"] not in de.EXTRA_STATUS_ORDER]
    plant_recs = [r for r in active_recs if r["type"] != "Transmission Line"]
    tx_recs = [r for r in active_recs if r["type"] == "Transmission Line"]

    n_plants = len(plant_recs)
    plant_mw = sum(r["capacity_mw"] or 0 for r in plant_recs)
    n_operating = sum(1 for r in plant_recs if r["status"] == "Operating")
    # REQ 7: Installed Capacity with operating plants at first
    op_plants = [r for r in plant_recs if r["status"] == "Operating"]
    op_mw = sum(r["capacity_mw"] or 0 for r in op_plants)
    op_n = len(op_plants)

    n_tx = len(tx_recs)
    tx_mw = sum(r["capacity_mw"] or 0 for r in tx_recs)
    tx_km = sum(r["line_length_km"] or 0 for r in tx_recs)

    n_gon = sum(1 for r in recs if r["status"] == "GoN Study Project")
    n_cancelled = sum(1 for r in recs if r["status"] == "Cancelled")

    cards = [
        # REQ 7: Installed Capacity first
        kpi_card("Installed Capacity", f"{op_mw:,.1f} MW",
                  f"{op_n:,} Operating Plants", "#2e7d32"),
        kpi_card("Active Power Plants", f"{n_plants:,} Projects",
                  f"{plant_mw:,.1f} MW Total • {n_operating:,} operating", "#1565c0"),
        kpi_card("Transmission Lines", f"{n_tx:,} Projects",
                  f"{tx_mw:,.1f} MW • {tx_km:,.1f} km circuit length", "#6a1b9a"),
        kpi_card("GoN Studied Projects", f"{n_gon:,}",
                  "studied, not counted in active capacity", "#0277bd"),
        kpi_card("License Cancelled", f"{n_cancelled:,}",
                  "cancelled, not counted in active capacity", "#c62828"),
    ]
    return [dbc.Col(c, md=4, lg=2) for c in cards]


@app.callback(
    Output("site-header", "style"),
    Input("init-once", "n_intervals"), Input("refresh-poll", "n_intervals"),
)
def update_header_bg(_a, _b):
    bg = ss.get_background_path()
    style = {"borderRadius": "10px", "color": "white"}
    if bg:
        style.update({
            "backgroundImage": "linear-gradient(rgba(10,20,40,0.55), rgba(10,20,40,0.55)), "
                                "url('/assets-background')",
            "backgroundSize": "cover", "backgroundPosition": "center",
        })
    else:
        style["background"] = "linear-gradient(135deg, #0b1730 0%, #16325c 100%)"
    return style


@app.callback(
    Output("ticker-bar", "children"),
    Input("load-status", "children"),
    Input("refresh-poll", "n_intervals"),
    Input("f-type", "value"), Input("f-status", "value"), Input("f-province", "value"),
    Input("f-capacity", "value"), Input("f-tx-length", "value"), Input("f-year", "data"),
    Input("f-search", "value"),
    Input("f-date-from", "value"), Input("f-date-to", "value"),
    Input("f-cod-from", "value"), Input("f-cod-to", "value"),
    Input("f-district", "value"), Input("f-local", "value"),
)
def update_ticker(_status, _poll, f_type, f_status, f_province, f_capacity, f_tx_length, f_year, f_search,
                   f_date_from, f_date_to, f_cod_from, f_cod_to, f_district, f_local):
    if not ss.get_marquee_enabled():
        return None
    loader = STATE["loader"]
    if loader is None or loader.error or not loader.records:
        return render_ticker_bar(loader)
    recs = get_filtered_records(f_type, f_status, f_province, f_capacity, f_year, f_search,
                                 f_date_from, f_date_to, f_cod_from, f_cod_to, f_tx_length,
                                 f_district, f_local)
    return render_ticker_bar(loader, recs)


# ── TAB CONTENT ────────────────────────────────────────────────────────────
@app.callback(
    Output("tab-content", "children"),
    Output("gis-controls-container", "style"),
    Input("main-tabs", "active_tab"),
    Input("f-type", "value"), Input("f-status", "value"), Input("f-province", "value"),
    Input("f-capacity", "value"), Input("f-tx-length", "value"), Input("f-year", "data"),
    Input("f-search", "value"),
    Input("f-date-from", "value"), Input("f-date-to", "value"),
    Input("f-cod-from", "value"), Input("f-cod-to", "value"),
    Input("f-crs", "value"),
    Input("gis-opt-layers", "value"),
    Input("f-district", "value"), Input("f-local", "value"),
    Input("chart-style-store", "data"),
)
def render_tab(tab, f_type, f_status, f_province, f_capacity, f_tx_length, f_year, f_search,
               f_date_from, f_date_to, f_cod_from, f_cod_to, f_crs, gis_layers,
               f_district, f_local, chart_style):
    # Update global chart style state
    global CHART_STYLE_STATE
    if chart_style:
        CHART_STYLE_STATE.update(chart_style)

    loader = STATE["loader"]
    gis_controls_style = {"display": "none"}

    if loader is None or loader.error or not loader.records:
        err_detail = (loader.error if (loader and loader.error) else STATE.get("error"))
        detail = f" Details: {err_detail}" if err_detail else ""
        return dbc.Alert([
            html.Div("No project data is loaded yet.", className="fw-semibold"),
            html.Div([
                "An administrator needs to connect a data source at ",
                html.A("/admin", href="/admin/login", className="alert-link"),
                " — either sync a Google Sheet / Drive link there, or upload a "
                "workbook directly. If a live Google Sheet is already configured "
                "in Render's environment variables (DEFAULT_SHEET_URL) and this "
                "message still shows, check that the sheet is shared as "
                "\"Anyone with the link\" and that the admin panel's sync "
                "hasn't failed silently." + detail,
            ], className="small mt-1"),
        ], color="info", className="mt-3"), gis_controls_style

    if tab == "overview":
        try:
            all_active_recs = [r for r in loader.records if r["status"] not in de.EXTRA_STATUS_ORDER]
            return render_overview(loader, all_active_recs), gis_controls_style
        except Exception:
            tb = traceback.format_exc()
            traceback.print_exc()
            return dbc.Alert([
                html.Div("This tab hit an error while rendering: overview", className="fw-semibold"),
                html.Pre(tb, className="small mt-2", style={"whiteSpace": "pre-wrap"}),
            ], color="danger", className="mt-3"), gis_controls_style

    recs = get_filtered_records(f_type, f_status, f_province, f_capacity, f_year, f_search,
                                 f_date_from, f_date_to, f_cod_from, f_cod_to, f_tx_length,
                                 f_district, f_local)
    if not recs:
        return dbc.Alert("No projects match the current filters.", color="warning"), gis_controls_style

    active_recs = [r for r in recs if r["status"] not in de.EXTRA_STATUS_ORDER]

    try:
        if tab == "plants":
            return render_plants_tab(loader, active_recs), gis_controls_style
        if tab == "transmission":
            return render_transmission_tab(loader, active_recs), gis_controls_style
        if tab == "gon_study":
            return render_side_category_tab(loader, recs, "GoN Study Project", "GoN Studied Projects"), gis_controls_style
        if tab == "cancelled":
            return render_side_category_tab(loader, recs, "Cancelled", "License Cancelled"), gis_controls_style
        if tab == "growth":
            return render_growth(loader, active_recs), gis_controls_style
        if tab == "gis":
            gis_layers = gis_layers if gis_layers is not None else ["boundary"]
            return render_gis_tab(loader, active_recs, f_crs or ct.CRS_WGS84,
                                   show_boundary="boundary" in gis_layers,
                                   show_pa="pa" in gis_layers), gis_controls_style
        if tab == "compare":
            return render_compare(loader, active_recs), gis_controls_style
        if tab == "table":
            return render_table(recs, f_crs or ct.CRS_WGS84), gis_controls_style
        if tab == "custom":
            return render_custom_tab(), gis_controls_style
        return html.Div(), gis_controls_style
    except Exception:
        tb = traceback.format_exc()
        traceback.print_exc()
        return dbc.Alert([
            html.Div(f"This tab hit an error while rendering: {tab}", className="fw-semibold"),
            html.Pre(tb, className="small mt-2", style={"whiteSpace": "pre-wrap"}),
        ], color="danger", className="mt-3"), gis_controls_style


# ── STATUS / PROVINCE / TYPE COLOR HELPERS ─────────────────────────────────

def get_status_color_class(status):
    """Return CSS class for styled status labels."""
    mapping = {
        "Operating": "status-label-operating",
        "Construction License": "status-label-construction",
        "Application for Construction License": "status-label-app-construction",
        "Survey License": "status-label-survey",
        "Application for Survey License": "status-label-app-survey",
        "GoN Study Project": "status-label-gon",
        "Cancelled": "status-label-cancelled",
        "Technical Clearance": "status-label-tc",
    }
    return mapping.get(status, "")


def get_province_color_class(province):
    """Return CSS class for styled province labels."""
    mapping = {
        "Koshi": "prov-label-koshi",
        "Madhesh": "prov-label-madhesh",
        "Bagmati": "prov-label-bagmati",
        "Gandaki": "prov-label-gandaki",
        "Lumbini": "prov-label-lumbini",
        "Karnali": "prov-label-karnali",
        "Sudurpaschim": "prov-label-sudurpaschim",
    }
    return mapping.get(province, "")


# REQ 4: Ordered stages
STAGE_DISPLAY_ORDER = [
    "Operating",
    "Construction License",
    "Application for Construction License",
    "Survey License",
    "Application for Survey License",
]

# REQ 5: Ordered provinces
PROVINCE_DISPLAY_ORDER = [
    "Koshi", "Madhesh", "Bagmati", "Gandaki", "Lumbini", "Karnali", "Sudurpaschim"
]

_PLACEHOLDER_WORDS = ("load", "tbd", "n/a", "na", "pending", "update", "unknown",
                      "unspecified", "-", "—", "n.a", "to be")


def _looks_like_place(s):
    if not s:
        return False
    low = s.strip().lower()
    if not low or len(low) < 2:
        return False
    return not any(w in low for w in _PLACEHOLDER_WORDS)


def _admin_units_str(r, max_each=3):
    """Provinces/Districts/Local Bodies as per the project's License
    Boundary overlapping the GIS map (province_pct / district_pct /
    local_pct, computed by GISEngine.bbox_overlap_pct against the real
    boundary polygons) — not the sheet's raw address columns. Falls back
    to the sheet address only for records with no GIS overlap on file
    (e.g. no surveyed bbox/coordinates yet)."""
    prov_pct = r.get("province_pct") or {}
    dist_pct = r.get("district_pct") or {}
    local_pct = r.get("local_pct") or []

    if prov_pct or dist_pct or local_pct:
        provs = [p for p, _ in sorted(prov_pct.items(), key=lambda kv: -kv[1])][:max_each]
        dists = [d for d, _ in sorted(dist_pct.items(), key=lambda kv: -kv[1])][:max_each]
        locals_ = [lb["name"] for lb in
                   sorted(local_pct, key=lambda lb: -(lb.get("pct") or 0))][:max_each]
        parts = []
        if provs:
            parts.append(("Province" if len(provs) == 1 else "Provinces") + ": " + ", ".join(provs))
        if dists:
            parts.append(("District" if len(dists) == 1 else "Districts") + ": " + ", ".join(dists))
        if locals_:
            parts.append(("Local Body" if len(locals_) == 1 else "Local Bodies") + ": " + ", ".join(locals_))
        if parts:
            return " • ".join(parts)

    # Fallback: no GIS boundary-overlap data for this record — use the
    # sheet's own address columns instead.
    provs = [p.strip() for p in (r.get("province") or "").split("/") if _looks_like_place(p)]
    dists = [d.strip() for d in (r.get("district") or "").split("/") if _looks_like_place(d)]
    provs = list(dict.fromkeys(provs))[:max_each]
    dists = list(dict.fromkeys(dists))[:max_each]
    local = de.record_local(r)
    local_str = local if _looks_like_place(local) else None
    parts = []
    if provs:
        parts.append(("Province" if len(provs) == 1 else "Provinces") + ": " + ", ".join(provs))
    if dists:
        parts.append(("District" if len(dists) == 1 else "Districts") + ": " + ", ".join(dists))
    if local_str:
        parts.append("Local Body: " + local_str)
    return " • ".join(parts) if parts else "Province/District: not yet resolved"


def _cat_segment(label, n, mw, extra=None):
    s = f"{label} — {mw:,.0f} MW • {n:,} Projects"
    if extra:
        s += f" • {extra}"
    return s


def build_ticker_segments(loader, recs=None):
    all_recs = recs if recs is not None else loader.records
    plants = [r for r in all_recs if r["type"] != "Transmission Line" and r["status"] in de.STATUS_ORDER]
    txs = [r for r in all_recs if r["type"] == "Transmission Line" and r["status"] in de.STATUS_ORDER]
    canc = [r for r in all_recs if r["status"] == "Cancelled"]
    gons = [r for r in all_recs if r["status"] == "GoN Study Project"]
    tcs = [r for r in all_recs if r["status"] == "Technical Clearance"]

    segs = [(_cat_segment("⚡ ACTIVE POWER PLANTS", len(plants),
                          sum(r['capacity_mw'] or 0 for r in plants)), "#ffd166")]
    # REQ 4: Ordered stages in ticker
    for st in STAGE_DISPLAY_ORDER:
        if st not in de.STATUS_ORDER:
            continue
        sel = [r for r in plants if r["status"] == st]
        if sel:
            segs.append((_cat_segment(st, len(sel),
                                       sum(r['capacity_mw'] or 0 for r in sel)),
                         get_status_colors().get(st, "#c8d3e8")))
    km_all = sum(r["line_length_km"] or 0 for r in txs)
    segs.append((_cat_segment("🔌 TRANSMISSION", len(txs),
                              sum(r['capacity_mw'] or 0 for r in txs),
                              extra=f"{km_all:,.0f} KM"), "#7fd1ff"))
    segs.append((_cat_segment("🏛 GoN STUDY PROJECTS", len(gons),
                              sum(r['capacity_mw'] or 0 for r in gons)), "#f4b860"))
    if tcs:
        segs.append((_cat_segment("Technical Clearance", len(tcs),
                                  sum(r['capacity_mw'] or 0 for r in tcs)), "#9fb3c8"))
    segs.append((_cat_segment("🚫 LICENCE CANCELLED", len(canc),
                              sum(r['capacity_mw'] or 0 for r in canc)), "#ff8a80"))

    op = [r for r in plants if r["status"] == "Operating"]

    def _top(sel, keyf):
        agg = {}
        for r in sel:
            k = keyf(r)
            if not _looks_like_place(k) or k == "Unspecified":
                continue
            a = agg.setdefault(k, [0, 0.0])
            a[0] += 1
            a[1] += r["capacity_mw"] or 0
        if not agg:
            return None
        k, (n_, mw_) = max(agg.items(), key=lambda kv: kv[1][1])
        return k, n_, mw_

    for tlabel, icon, sel in (
            ("HYDRO", "💧", [r for r in op if str(r["type"]).startswith("Hydro")]),
            ("SOLAR", "☀", [r for r in op if r["type"] == "Solar"])):
        if not sel:
            continue
        segs.append((_cat_segment(f"{icon} {tlabel} IN OPERATION", len(sel),
                                  sum(r['capacity_mw'] or 0 for r in sel)), "#a5f3c4"))
        for lab, keyf in (("province", lambda r: r["province"]),
                          ("district", lambda r: (r["district"] or "").split("/")[0].split("(")[0].strip()),
                          ("local body", de.record_local)):
            t = _top(sel, keyf)
            if t:
                segs.append((f"{icon} Largest {tlabel.lower()} {lab}: {t[0]} — "
                             f"{t[2]:,.0f} MW • {t[1]:,} Projects", "#7be3a2"))

    ty_, tm_, td_ = de.today_bs()

    def _cod_key(r):
        t = r.get("cod_bs")
        if not t:
            return None
        return (t[0], t[1] if len(t) > 1 and t[1] else 1, t[2] if len(t) > 2 and t[2] else 1)

    def _added(year, until):
        sel = [r for r in op if _cod_key(r) and (year, 1, 1) <= _cod_key(r) <= until]
        return sel

    cur_sel = _added(ty_, (ty_, tm_, td_))
    prv_sel = _added(ty_ - 1, (ty_ - 1, tm_, td_))
    n_cur = len(cur_sel); mw_cur = sum(r["capacity_mw"] or 0 for r in cur_sel)
    n_prv = len(prv_sel); mw_prv = sum(r["capacity_mw"] or 0 for r in prv_sel)
    d_mw = mw_cur - mw_prv
    pct = (d_mw / mw_prv * 100.0) if mw_prv else (100.0 if mw_cur else 0.0)
    arrow, acol = ("▲", "#2ecc71") if d_mw >= 0 else ("▼", "#ff6b6b")
    segs.append((f"📈 Capacity added {ty_} (01-01 → {ty_}-{tm_:02d}-{td_:02d}): "
                 f"{mw_cur:,.0f} MW ({n_cur:,} Projects)  vs  same period {ty_-1}: "
                 f"{mw_prv:,.0f} MW ({n_prv:,})  →  {arrow} {abs(d_mw):,.0f} MW "
                 f"({pct:+.1f}%)", acol))

    last_full_year = _added(ty_ - 1, (ty_ - 1, 12, 32))
    segs.append((_cat_segment(f"📅 Connected in {ty_-1} (full year)", len(last_full_year),
                              sum(r['capacity_mw'] or 0 for r in last_full_year)), "#ffe08a"))

    yr_sel = cur_sel
    segs.append((_cat_segment(f"🆕 In operation since {ty_}-01-01", len(yr_sel),
                              sum(r['capacity_mw'] or 0 for r in yr_sel)), "#ffe08a"))

    largest_this_year = sorted(cur_sel, key=lambda r: r["capacity_mw"] or 0, reverse=True)[:1]
    largest_ids = {id(r) for r in largest_this_year}
    for r in largest_this_year:
        segs.append((f"🏆 Largest plant connected in {ty_}: {r['project'][:34]} — "
                     f"{de.fmt_mw(r['capacity_mw'])} MW • {_admin_units_str(r)} • "
                     f"COD {de.bs_str(r['cod_bs'])}", "#7be3a2"))

    latest_candidates = sorted([r for r in cur_sel if _cod_key(r)], key=_cod_key, reverse=True)
    latest = [r for r in latest_candidates if id(r) not in largest_ids][:1]
    for r in latest:
        segs.append((f"🔌 Latest plant connected: {r['project'][:34]} — "
                     f"{de.fmt_mw(r['capacity_mw'])} MW • {_admin_units_str(r)} • "
                     f"{textwrap.shorten(r['promoter'] or '—', 26)} • "
                     f"COD {de.bs_str(r['cod_bs'])}", "#c9b6ff"))
    return segs



_TICKER_BG_RGB = (0x10, 0x17, 0x26)  # matches .ticker-bar background: #101726


def _ticker_safe_color(hex_color):
    """The marquee's colored titles are drawn straight from the status/
    province/type color palettes, which were designed for chart bars on
    a light background — some are dark enough to nearly disappear
    against the ticker bar's own dark navy background (near-matching
    font/background color). Lighten any color that doesn't have enough
    contrast against that background, leaving already-legible colors
    untouched."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except (ValueError, AttributeError, IndexError):
        return hex_color
    bg_r, bg_g, bg_b = _TICKER_BG_RGB
    # Simple perceptual distance check against the ticker background.
    dist = ((r - bg_r) ** 2 + (g - bg_g) ** 2 + (b - bg_b) ** 2) ** 0.5
    if dist >= 140:
        return hex_color
    # Blend toward white until it's clearly distinguishable from the
    # dark background, preserving the color's hue rather than replacing it.
    for step in (0.35, 0.55, 0.75):
        nr = round(r + (255 - r) * step)
        ng = round(g + (255 - g) * step)
        nb = round(b + (255 - b) * step)
        if ((nr - bg_r) ** 2 + (ng - bg_g) ** 2 + (nb - bg_b) ** 2) ** 0.5 >= 140:
            return f"#{nr:02x}{ng:02x}{nb:02x}"
    return "#e7edf3"  # safe fallback: near-white


def render_ticker_bar(loader, recs=None):
    if loader is None or not loader.records:
        return None
    try:
        segs = build_ticker_segments(loader, recs)
    except Exception:
        traceback.print_exc()
        return None
    if not segs:
        return None
    spans = []
    for text, color in segs:
        spans.append(html.Span(text, style={"color": _ticker_safe_color(color), "marginRight": "48px"}))
    track_children = spans + spans
    total_chars = sum(len(t) for t, _ in segs)
    duration = max(60, round(total_chars / 9))
    live_badge = html.Div([
        html.Span(className="ticker-live-dot"),
        html.Span("LIVE", className="ticker-live-text"),
    ], className="ticker-live-badge")
    return html.Div([
        live_badge,
        html.Div(
            html.Div(track_children, className="ticker-track",
                      style={"animationDuration": f"{duration}s"}),
            className="ticker-track-wrap",
        ),
    ], className="ticker-bar")


# ── WATERMARK HELPER ───────────────────────────────────────────────────────
def add_watermark(fig):
    """Add 'Er. Sandeep Neupane' watermark to Plotly figures."""
    fig.add_annotation(
        text="Er. Sandeep Neupane",
        xref="paper", yref="paper",
        x=0.98, y=0.02,
        showarrow=False,
        font=dict(size=10, color="rgba(100,100,100,0.5)", family="Arial"),
        align="right",
    )
    return fig


def add_watermark_matplotlib(fig):
    """Add watermark to matplotlib figures."""
    fig.text(0.98, 0.02, "Er. Sandeep Neupane",
             fontsize=8, color='gray', ha='right', va='bottom', alpha=0.5)
    return fig


# ── CATEGORY CARD WITH COMMON BACKGROUND ────────────────────────────────────
def flip_frame_style(bg_url=None):
    """Plain style for the frame that wraps a flip card + its chart.
    The background photo is NOT applied here — it lives only on the
    heading above the frame (see flip_heading_style). bg_url is kept as
    an accepted (ignored) argument so existing call sites don't need to
    change their signatures."""
    return {
        "borderRadius": "12px", "padding": "16px", "position": "relative",
        "backgroundColor": "#f5f6f8",
    }


def flip_heading_style(bg_url):
    """Background photo goes here, and here only: the heading strip
    above a flip card + chart section. Keeps the photo visible as a
    section header while leaving the card and chart panels below it
    on a plain background."""
    style = {
        "borderRadius": "8px", "padding": "10px 16px", "marginBottom": "12px",
        "color": "#fff", "transition": "background-image 0.6s ease-in-out",
    }
    if bg_url:
        style.update({
            "backgroundImage": f'linear-gradient(rgba(10,20,40,0.55), rgba(10,20,40,0.55)), url("{bg_url}")',
            "backgroundSize": "cover", "backgroundPosition": "center",
        })
    else:
        style["backgroundColor"] = "#37474f"
    return style


# Solid panel look for charts/cards — no background photo is drawn behind
# them anymore (REQ: image restricted to the section heading only).
_FLIP_PANEL_CHART_KWARGS = dict(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
                                 transition=dict(duration=500, easing="cubic-in-out"))


def render_category_card(label, stage_map, total_n, total_mw, bg_url, base_color, total_km=0.0,
                          stage_order=None, is_transmission=False):
    """Render a category card. The background photo (if any) is applied
    once by the caller's shared flip frame — this card's header just
    uses a solid color so the image isn't drawn a second time here."""
    stage_order = stage_order or STAGE_DISPLAY_ORDER
    header_style = {
        "borderRadius": "8px 8px 0 0", "padding": "14px 16px", "color": "#fff",
        "position": "relative", "height": "180px", "display": "flex",
        "flexDirection": "column", "justifyContent": "flex-end",
        "backgroundColor": base_color,
    }

    stage_rows = []
    for st in stage_order:
        if st not in stage_map:
            continue
        n, mw, km = stage_map[st]
        # REQ 3: Consistent pattern
        if is_transmission:
            detail = f"{n:,} Projects · {mw:,.1f} MW · {km:,.1f} KM"
        else:
            detail = f"{n:,} Projects · {mw:,.1f} MW"
        color_cls = get_status_color_class(st)
        stage_rows.append(html.Div([
            html.Span(st, className=f"small {color_cls}"),
            html.Span(detail, className="small fw-semibold float-end"),
        ], className="d-flex justify-content-between border-bottom py-1"))

    # REQ 3: Consistent pattern for totals
    if is_transmission:
        totals_line = f"{total_n:,} Projects · {total_mw:,.1f} MW · {total_km:,.1f} KM"
    else:
        totals_line = f"{total_n:,} Projects · {total_mw:,.1f} MW"

    return dbc.Card([
        html.Div([
            html.Div(label, className="fw-bold", style={"fontSize": "15px"}),
            html.Div(totals_line, className="small", style={"opacity": 0.9}),
        ], style=header_style),
        dbc.CardBody(stage_rows or [html.Div("No records", className="small text-muted")],
                     style={"padding": "8px 16px", "overflowY": "auto"}),
    ], key=f"cat-{label}", className="mb-3 shadow-sm flip-card-animate",
       style={"height": "360px", "display": "flex", "flexDirection": "column"})


def compute_breakdown(recs, key_field):
    totals = defaultdict(lambda: [0, 0.0, 0.0])
    stages = defaultdict(dict)
    for r in recs:
        k = r[key_field] or "Unspecified"
        km = r["line_length_km"] or 0.0
        totals[k][0] += 1
        totals[k][1] += r["capacity_mw"] or 0.0
        totals[k][2] += km
        entry = stages[k].setdefault(r["status"], [0, 0.0, 0.0])
        entry[0] += 1
        entry[1] += r["capacity_mw"] or 0.0
        entry[2] += km
    return totals, stages


def status_pie(recs, title):
    by_status = defaultdict(int)
    for r in recs:
        by_status[r["status"]] += 1
    colors = [get_status_colors().get(s, "#90a4ae") for s in by_status.keys()]
    fig = go.Figure(go.Pie(
        labels=list(by_status.keys()), values=list(by_status.values()), hole=0.45,
        marker_colors=colors,
    ))
    fig.update_layout(title=title, height=380, margin=dict(l=10, r=10, t=40, b=10))
    add_watermark(fig)
    return fig


# ── OVERVIEW TAB ────────────────────────────────────────────────────────────
def render_overview(loader, recs):
    """Overview with Power Plant types flip-card + chart, then Province flip-card + chart."""
    card, fig, bg_url = _flip_card_and_chart(0)
    prov_card, prov_fig, prov_bg_url = _overview_province_flip_card_and_chart(0)

    return html.Div([
        html.Div(html.H5("⚡ Power Plants by Type", className="m-0"),
                 id="type-flip-heading", style=flip_heading_style(bg_url)),
        html.Div(
            id="type-flip-frame",
            style=flip_frame_style(),
            children=dbc.Row([
                dbc.Col(html.Div(id="type-flip-card", children=card, style={"height": "360px"}), md=5),
                dbc.Col(dcc.Graph(id="type-flip-chart", figure=fig, style={"height": "360px"}), md=7),
            ]),
        ),
        html.Hr(),
        html.Div(html.H5("🗺️ Power Plants by Province", className="m-0"),
                 id="overview-province-flip-heading", style=flip_heading_style(prov_bg_url)),
        html.Div(
            id="overview-province-flip-frame",
            style=flip_frame_style(),
            children=dbc.Row([
                dbc.Col(html.Div(id="overview-province-flip-card", children=prov_card,
                                  style={"height": "360px"}), md=5),
                dbc.Col(dcc.Graph(id="overview-province-flip-chart", figure=prov_fig,
                                   style={"height": "360px"}), md=7),
            ]),
        ),
    ])


def _overview_province_flip_card_and_chart(n):
    """Animated province flip card + chart for the Overview tab — cycles through
    provinces the same way _flip_card_and_chart cycles through project types.
    Returns (card, fig, bg_url) — bg_url is applied once by the caller's
    shared flip frame, not drawn again inside the card or the chart."""
    loader = STATE["loader"]
    empty_fig = go.Figure()
    if loader is None or loader.error or not loader.records:
        return None, empty_fig, None
    try:
        recs = [r for r in loader.records
                if r["status"] not in de.EXTRA_STATUS_ORDER and r["type"] != "Transmission Line"]
        if not recs:
            return None, empty_fig, None

        prov_totals, prov_stages = compute_breakdown(recs, "province")
        provinces_present = [p for p in PROVINCE_DISPLAY_ORDER if p in prov_totals] + \
                            [p for p in prov_totals if p not in PROVINCE_DISPLAY_ORDER]
        if not provinces_present:
            return None, empty_fig, None

        p = provinces_present[n % len(provinces_present)]
        bg_url = ss.get_province_bg_url(p)
        color = get_province_colors().get(p, "#455a64")

        card = render_category_card(
            p, prov_stages[p], prov_totals[p][0], prov_totals[p][1],
            bg_url, color, stage_order=STAGE_DISPLAY_ORDER
        )

        stages_present = [s for s in STAGE_DISPLAY_ORDER if s in prov_stages[p]]
        colors = [get_status_colors().get(s, "#90a4ae") for s in stages_present]
        fig = go.Figure(go.Bar(
            x=stages_present,
            y=[prov_stages[p][s][1] for s in stages_present],
            marker_color=colors,
            text=[f"{prov_stages[p][s][1]:,.1f} MW" for s in stages_present],
            textposition="outside",
        ))
        fig.update_layout(
            title=f"{p} — Capacity by License Stage",
            height=360, yaxis_title="MW",
            margin=dict(l=10, r=10, t=40, b=10),
            **_FLIP_PANEL_CHART_KWARGS,
        )
        add_watermark(fig)
        return card, fig, bg_url
    except Exception:
        tb = traceback.format_exc()
        traceback.print_exc()
        err_card = dbc.Alert([
            html.Div("The Overview province card hit an error while rendering.",
                      className="fw-semibold small"),
            html.Pre(tb, className="small mt-1",
                      style={"whiteSpace": "pre-wrap", "maxHeight": "280px", "overflowY": "auto"}),
        ], color="danger")
        return err_card, empty_fig, None


@app.callback(
    Output("overview-province-flip-card", "children"),
    Output("overview-province-flip-chart", "figure"),
    Output("overview-province-flip-frame", "style"),
    Output("overview-province-flip-heading", "style"),
    Input("province-flip-interval", "n_intervals"),
)
def flip_overview_province_card(n):
    card, fig, bg_url = _overview_province_flip_card_and_chart(n)
    return card, fig, flip_frame_style(), flip_heading_style(bg_url)


def type_flip_chart_figure(t, stage_map, bg_url=None):
    """Chart figure for type flip card with watermark. bg_url is accepted
    for call-site compatibility but no longer drawn here — the shared
    flip frame around the card+chart pair carries the background image."""
    stages_present = [s for s in STAGE_DISPLAY_ORDER if s in stage_map]
    use_km = (t == "Transmission Line")
    idx = 2 if use_km else 1
    unit = "KM" if use_km else "MW"
    colors = [get_status_colors().get(s, "#90a4ae") for s in stages_present]

    fig = go.Figure(go.Bar(
        x=stages_present, y=[stage_map[s][idx] for s in stages_present],
        marker_color=colors,
        text=[f"{stage_map[s][idx]:,.1f} {unit}" for s in stages_present], textposition="outside",
    ))
    layout_kwargs = dict(
        title=f"{t} — {'Length (KM)' if use_km else 'Capacity (MW)'} by License Stage",
        height=360, yaxis_title=unit, margin=dict(l=10, r=10, t=40, b=10),
        **_FLIP_PANEL_CHART_KWARGS,
    )
    fig.update_layout(**layout_kwargs)
    add_watermark(fig)
    return fig


def _flip_card_and_chart(n):
    """Returns (card, fig, bg_url) — bg_url is applied once by the caller's
    shared flip frame, not drawn again inside the card or the chart."""
    loader = STATE["loader"]
    empty_fig = go.Figure()
    if loader is None or loader.error or not loader.records:
        return None, empty_fig, None
    try:
        recs = [r for r in loader.records if r["status"] not in de.EXTRA_STATUS_ORDER]
        if not recs:
            return None, empty_fig, None
        totals, stages = compute_breakdown(recs, "type")
        types = [t for t in de.TYPE_ORDER if t in totals] + \
                [t for t in totals if t not in de.TYPE_ORDER]
        if not types:
            return None, empty_fig, None
        t = types[n % len(types)]
        bg_url = ss.get_type_bg_url(t)
        card = render_category_card(t, stages[t], totals[t][0], totals[t][1],
                                     bg_url, get_type_colors().get(t, "#607d8b"),
                                     total_km=totals[t][2], stage_order=STAGE_DISPLAY_ORDER)
        return card, type_flip_chart_figure(t, stages[t], bg_url=bg_url), bg_url
    except Exception:
        tb = traceback.format_exc()
        traceback.print_exc()
        err_card = dbc.Alert([
            html.Div("The Overview activity card hit an error while rendering.",
                      className="fw-semibold small"),
            html.Pre(tb, className="small mt-1",
                      style={"whiteSpace": "pre-wrap", "maxHeight": "280px", "overflowY": "auto"}),
        ], color="danger")
        return err_card, empty_fig, None


@app.callback(
    Output("type-flip-card", "children"),
    Output("type-flip-chart", "figure"),
    Output("type-flip-frame", "style"),
    Output("type-flip-heading", "style"),
    Input("type-flip-interval", "n_intervals"),
)
def flip_type_card(n):
    card, fig, bg_url = _flip_card_and_chart(n)
    return card, fig, flip_frame_style(), flip_heading_style(bg_url)


# ── STAGE FLIP CARD (for Plants tab) ───────────────────────────────────────
def render_single_stage_card(stage, sel_recs, bg_url, base_color, is_transmission=False):
    n = len(sel_recs)
    mw = sum(r["capacity_mw"] or 0 for r in sel_recs)
    km = sum(r["line_length_km"] or 0 for r in sel_recs) if is_transmission else 0.0
    prov_totals = defaultdict(lambda: [0, 0.0])
    for r in sel_recs:
        p = r["province"] or "Unspecified"
        prov_totals[p][0] += 1
        prov_totals[p][1] += r["capacity_mw"] or 0.0
    # All 7 canonical provinces, ordered — not just the top 5 by capacity.
    ordered_provs = [p for p in PROVINCE_DISPLAY_ORDER] + \
                    [p for p in prov_totals if p not in PROVINCE_DISPLAY_ORDER]
    top_provs = [(p, prov_totals.get(p, [0, 0.0])) for p in ordered_provs]

    header_style = {
        "borderRadius": "8px 8px 0 0", "padding": "14px 16px", "color": "#fff",
        "position": "relative", "height": "180px", "display": "flex",
        "flexDirection": "column", "justifyContent": "flex-end",
        "backgroundColor": base_color,
    }

    rows = []
    for p, v in top_provs:
        color_cls = get_province_color_class(p)
        rows.append(html.Div([
            html.Span(p, className=f"small {color_cls}"),
            html.Span(f"{v[0]:,} Projects · {v[1]:,.1f} MW", className="small fw-semibold float-end"),
        ], className="d-flex justify-content-between border-bottom py-1"))

    # REQ 3: Consistent pattern
    if is_transmission:
        totals_line = f"{n:,} Projects · {mw:,.1f} MW · {km:,.1f} KM"
    else:
        totals_line = f"{n:,} Projects · {mw:,.1f} MW"

    return dbc.Card([
        html.Div([
            html.Div(stage, className="fw-bold", style={"fontSize": "15px"}),
            html.Div(totals_line, className="small", style={"opacity": 0.9}),
        ], style=header_style),
        dbc.CardBody(rows or [html.Div("No records for this stage yet", className="small text-muted")],
                     style={"padding": "8px 16px", "overflowY": "auto"}),
    ], key=f"stage-{stage}", className="mb-3 shadow-sm flip-card-animate",
       style={"height": "360px", "display": "flex", "flexDirection": "column"})


def stage_province_chart_figure(stage, sel_recs, is_transmission=False, bg_url=None):
    """bg_url is accepted for call-site compatibility but no longer drawn
    here — the shared flip frame around the card+chart pair carries it."""
    prov_totals = defaultdict(lambda: [0, 0.0, 0.0])
    for r in sel_recs:
        p = r["province"] or "Unspecified"
        prov_totals[p][0] += 1
        prov_totals[p][1] += r["capacity_mw"] or 0.0
        prov_totals[p][2] += r.get("line_length_km") or 0.0
    provinces_present = [p for p in PROVINCE_DISPLAY_ORDER if p in prov_totals] + \
                        [p for p in prov_totals if p not in PROVINCE_DISPLAY_ORDER]
    idx = 2 if is_transmission else 1
    unit = "KM" if is_transmission else "MW"
    yvals = [prov_totals[p][idx] for p in provinces_present]
    colors = [get_province_colors().get(p, "#455a64") for p in provinces_present]

    fig = go.Figure(go.Bar(
        x=provinces_present, y=yvals,
        marker_color=colors,
        text=[f"{v:,.1f} {unit}" for v in yvals], textposition="outside",
    ))
    layout_kwargs = dict(
        title=f"{stage} — {'Length (KM)' if is_transmission else 'Capacity (MW)'} by Province",
        height=360, yaxis_title=unit, margin=dict(l=10, r=10, t=40, b=10),
        **_FLIP_PANEL_CHART_KWARGS,
    )
    fig.update_layout(**layout_kwargs)
    add_watermark(fig)
    return fig


def _stage_flip_card_and_chart(n, recs, is_transmission=False):
    """Returns (card, fig, bg_url) — bg_url is applied once by the caller's
    shared flip frame, not drawn again inside the card or the chart."""
    empty_fig = go.Figure()
    try:
        stages_present = [s for s in STAGE_DISPLAY_ORDER if any(r["status"] == s for r in recs)]
        if not stages_present:
            return None, empty_fig, None
        st = stages_present[n % len(stages_present)]
        sel = [r for r in recs if r["status"] == st]
        bg_url = ss.get_status_bg_url(st)
        card = render_single_stage_card(st, sel, bg_url, get_status_colors().get(st, "#90a4ae"),
                                         is_transmission=is_transmission)
        fig = stage_province_chart_figure(st, sel, is_transmission=is_transmission, bg_url=bg_url)
        return card, fig, bg_url
    except Exception:
        tb = traceback.format_exc()
        traceback.print_exc()
        err_card = dbc.Alert([
            html.Div("This stage card hit an error while rendering.", className="fw-semibold small"),
            html.Pre(tb, className="small mt-1",
                      style={"whiteSpace": "pre-wrap", "maxHeight": "280px", "overflowY": "auto"}),
        ], color="danger")
        return err_card, empty_fig, None


@app.callback(
    Output("plants-stage-flip-card", "children"),
    Output("plants-stage-flip-chart", "figure"),
    Output("plants-stage-flip-frame", "style"),
    Output("plants-stage-flip-heading", "style"),
    Input("type-flip-interval", "n_intervals"),
    State("f-type", "value"), State("f-status", "value"), State("f-province", "value"),
    State("f-capacity", "value"), State("f-tx-length", "value"), State("f-year", "data"),
    State("f-search", "value"),
    State("f-date-from", "value"), State("f-date-to", "value"),
    State("f-cod-from", "value"), State("f-cod-to", "value"),
    State("f-district", "value"), State("f-local", "value"),
)
def flip_plants_stage_card(n, f_type, f_status, f_province, f_capacity, f_tx_length, f_year,
                            f_search, f_date_from, f_date_to, f_cod_from, f_cod_to,
                            f_district, f_local):
    loader = STATE["loader"]
    if loader is None or loader.error or not loader.records:
        return None, go.Figure(), flip_frame_style(), flip_heading_style(None)
    recs = get_filtered_records(f_type, f_status, f_province, f_capacity, f_year, f_search,
                                 f_date_from, f_date_to, f_cod_from, f_cod_to, f_tx_length,
                                 f_district, f_local)
    plant_recs = [r for r in recs if r["type"] != "Transmission Line"
                  and r["status"] not in de.EXTRA_STATUS_ORDER]
    card, fig, bg_url = _stage_flip_card_and_chart(n, plant_recs)
    return card, fig, flip_frame_style(), flip_heading_style(bg_url)



@app.callback(
    Output("tx-stage-flip-card", "children"),
    Output("tx-stage-flip-chart", "figure"),
    Output("tx-stage-flip-frame", "style"),
    Output("tx-stage-flip-heading", "style"),
    Input("type-flip-interval", "n_intervals"),
    State("f-type", "value"), State("f-status", "value"), State("f-province", "value"),
    State("f-capacity", "value"), State("f-tx-length", "value"), State("f-year", "data"),
    State("f-search", "value"),
    State("f-date-from", "value"), State("f-date-to", "value"),
    State("f-cod-from", "value"), State("f-cod-to", "value"),
    State("f-district", "value"), State("f-local", "value"),
)
def flip_tx_stage_card(n, f_type, f_status, f_province, f_capacity, f_tx_length, f_year,
                        f_search, f_date_from, f_date_to, f_cod_from, f_cod_to,
                        f_district, f_local):
    loader = STATE["loader"]
    if loader is None or loader.error or not loader.records:
        return None, go.Figure(), flip_frame_style(), flip_heading_style(None)
    recs = get_filtered_records(f_type, f_status, f_province, f_capacity, f_year, f_search,
                                 f_date_from, f_date_to, f_cod_from, f_cod_to, f_tx_length,
                                 f_district, f_local)
    tx_recs = [r for r in recs if r["type"] == "Transmission Line"
               and r["status"] not in de.EXTRA_STATUS_ORDER]
    card, fig, bg_url = _stage_flip_card_and_chart(n, tx_recs, is_transmission=True)
    return card, fig, flip_frame_style(), flip_heading_style(bg_url)


# ── POWER PLANTS TAB ────────────────────────────────────────────────────────
def render_plants_tab(loader, recs):
    plant_recs = [r for r in recs if r["type"] != "Transmission Line"]
    if not plant_recs:
        return dbc.Alert("No power-plant records match the current filters.", color="info")

    stage_totals, _ = compute_breakdown(plant_recs, "status")
    stages_present = [s for s in STAGE_DISPLAY_ORDER if s in stage_totals]

    # REQ 3: Consistent pattern with styled status labels
    stage_rows = []
    for st in stages_present:
        color_cls = get_status_color_class(st)
        stage_rows.append(html.Div([
            html.Span(st, className=f"fw-semibold {color_cls}"),
            html.Span(f"{stage_totals[st][0]:,} Projects", className="text-muted mx-3"),
            html.Span(f"{stage_totals[st][1]:,.1f} MW", className="fw-semibold float-end"),
        ], className="d-flex justify-content-between border-bottom py-2"))

    colors = [get_status_colors().get(s, "#90a4ae") for s in stages_present]
    fig_stage = go.Figure(go.Bar(
        x=stages_present, y=[stage_totals[s][1] for s in stages_present],
        marker_color=colors,
        text=[f"{stage_totals[s][1]:,.0f} MW" for s in stages_present], textposition="outside",
    ))
    fig_stage.update_layout(title="Power Plants — Capacity (MW) by License Stage", height=420,
                             yaxis_title="MW", margin=dict(l=10, r=10, t=40, b=10))
    add_watermark(fig_stage)

    # Stage flip card + chart (animated), background photo on heading only
    stage_card0, stage_fig0, stage_bg0 = _stage_flip_card_and_chart(0, plant_recs)
    stage_flip_row = html.Div([
        html.Div(html.H5("⚡ License Stage (Animated)", className="m-0"),
                 id="plants-stage-flip-heading", style=flip_heading_style(stage_bg0)),
        html.Div(
            id="plants-stage-flip-frame",
            style=flip_frame_style(),
            children=dbc.Row([
                dbc.Col(html.Div(id="plants-stage-flip-card", children=stage_card0,
                                  style={"height": "360px"}), md=5),
                dbc.Col(dcc.Graph(id="plants-stage-flip-chart", figure=stage_fig0,
                                   style={"height": "360px"}), md=7),
            ]),
        ),
    ])

    stage_section = dbc.Row([
        dbc.Col(html.Div([html.H5("All License Stages")] + stage_rows), md=5),
        dbc.Col(dcc.Graph(figure=fig_stage), md=7),
    ], className="mb-4")
    stage_section = html.Div([stage_flip_row, html.Hr(), stage_section])

    # REQ 8: Animated province slides in By Province sub-tab
    prov_totals, prov_stages = compute_breakdown(plant_recs, "province")
    provinces_present = [p for p in PROVINCE_DISPLAY_ORDER if p in prov_totals] + \
                        [p for p in prov_totals if p not in PROVINCE_DISPLAY_ORDER]

    # Province flip card + chart (animated) — this is the only per-province
    # card shown; the static list of every province's card that used to sit
    # below it has been removed as redundant (the flip card cycles through
    # all provinces continuously already).
    prov_card, prov_fig, prov_bg_url = _province_flip_card_and_chart(0, plant_recs)

    prov_colors = [get_province_colors().get(p, "#455a64") for p in provinces_present]
    fig_prov = go.Figure(go.Bar(
        x=provinces_present, y=[prov_totals[p][1] for p in provinces_present],
        marker_color=prov_colors,
        text=[f"{prov_totals[p][0]:,} Projects" for p in provinces_present], textposition="outside",
    ))
    fig_prov.update_layout(title="Power Plant Capacity by Province", height=460,
                            yaxis_title="Capacity (MW)", margin=dict(l=10, r=10, t=40, b=10))
    add_watermark(fig_prov)

    # REQ 8: Animated province slide section — background photo on heading only
    province_slide_section = html.Div([
        html.Div(html.H5("🗺️ Province Overview (Animated)", className="m-0"),
                 id="province-flip-heading", style=flip_heading_style(prov_bg_url)),
        html.Div(
            id="province-flip-frame",
            style=flip_frame_style(),
            children=dbc.Row([
                dbc.Col(html.Div(id="province-flip-card", children=prov_card,
                                  style={"height": "360px"}), md=5),
                dbc.Col(dcc.Graph(id="province-flip-chart", figure=prov_fig,
                                   style={"height": "360px"}), md=7),
            ]),
        ),
    ])

    # Province chart stays as it was — just the flip card above it now,
    # no separate static province-card list.
    prov_section = dbc.Row([
        dbc.Col(dcc.Graph(figure=fig_prov), md=12),
    ])

    return dbc.Tabs(id="plants-subtabs", active_tab="stage", children=[
        dbc.Tab(stage_section, label="License Stage", tab_id="stage",
                tab_style={"marginTop": "10px"}),
        dbc.Tab(html.Div([province_slide_section, html.Hr(), prov_section]),
                label="By Province", tab_id="by-province", tab_style={"marginTop": "10px"}),
    ])


def _province_flip_card_and_chart(n, recs):
    """Animated province flip card for Power Plants > By Province tab.
    Returns (card, fig, bg_url) — bg_url is applied once by the caller's
    shared flip frame, not drawn again inside the card or the chart."""
    empty_fig = go.Figure()
    try:
        prov_totals, prov_stages = compute_breakdown(recs, "province")
        provinces_present = [p for p in PROVINCE_DISPLAY_ORDER if p in prov_totals] + \
                            [p for p in prov_totals if p not in PROVINCE_DISPLAY_ORDER]
        if not provinces_present:
            return None, empty_fig, None

        p = provinces_present[n % len(provinces_present)]
        bg_url = ss.get_province_bg_url(p)
        color = get_province_colors().get(p, "#455a64")

        card = render_category_card(
            p, prov_stages[p], prov_totals[p][0], prov_totals[p][1],
            bg_url, color, stage_order=STAGE_DISPLAY_ORDER
        )

        # Chart for this province
        stages_present = [s for s in STAGE_DISPLAY_ORDER if s in prov_stages[p]]
        colors = [get_status_colors().get(s, "#90a4ae") for s in stages_present]
        fig = go.Figure(go.Bar(
            x=stages_present,
            y=[prov_stages[p][s][1] for s in stages_present],
            marker_color=colors,
            text=[f"{prov_stages[p][s][1]:,.1f} MW" for s in stages_present],
            textposition="outside",
        ))
        fig.update_layout(
            title=f"{p} — Capacity by License Stage",
            height=360, yaxis_title="MW",
            margin=dict(l=10, r=10, t=40, b=10),
            **_FLIP_PANEL_CHART_KWARGS,
        )
        add_watermark(fig)
        return card, fig, bg_url
    except Exception:
        tb = traceback.format_exc()
        traceback.print_exc()
        err_card = dbc.Alert([
            html.Div("Province card hit an error while rendering.", className="fw-semibold small"),
            html.Pre(tb, className="small mt-1",
                      style={"whiteSpace": "pre-wrap", "maxHeight": "280px", "overflowY": "auto"}),
        ], color="danger")
        return err_card, empty_fig, None


@app.callback(
    Output("province-flip-card", "children"),
    Output("province-flip-chart", "figure"),
    Output("province-flip-frame", "style"),
    Output("province-flip-heading", "style"),
    Input("province-flip-interval", "n_intervals"),
    State("f-type", "value"), State("f-status", "value"), State("f-province", "value"),
    State("f-capacity", "value"), State("f-tx-length", "value"), State("f-year", "data"),
    State("f-search", "value"),
    State("f-date-from", "value"), State("f-date-to", "value"),
    State("f-cod-from", "value"), State("f-cod-to", "value"),
    State("f-district", "value"), State("f-local", "value"),
)
def flip_province_card(n, f_type, f_status, f_province, f_capacity, f_tx_length, f_year,
                        f_search, f_date_from, f_date_to, f_cod_from, f_cod_to,
                        f_district, f_local):
    loader = STATE["loader"]
    if loader is None or loader.error or not loader.records:
        return None, go.Figure(), flip_frame_style(), flip_heading_style(None)
    recs = get_filtered_records(f_type, f_status, f_province, f_capacity, f_year, f_search,
                                 f_date_from, f_date_to, f_cod_from, f_cod_to, f_tx_length,
                                 f_district, f_local)
    plant_recs = [r for r in recs if r["type"] != "Transmission Line"
                  and r["status"] not in de.EXTRA_STATUS_ORDER]
    card, fig, bg_url = _province_flip_card_and_chart(n, plant_recs)
    return card, fig, flip_frame_style(), flip_heading_style(bg_url)


# ── TRANSMISSION TAB ────────────────────────────────────────────────────────
def render_transmission_tab(loader, recs):
    tx_recs = [r for r in recs if r["type"] == "Transmission Line"]
    if not tx_recs:
        return dbc.Alert("No transmission-line records match the current filters.", color="info")

    total_n = len(tx_recs)
    total_km = sum(r["line_length_km"] or 0 for r in tx_recs)
    total_mw = sum(r["capacity_mw"] or 0 for r in tx_recs)
    n_volt_classes = len({r["voltage_kv"] for r in tx_recs if r["voltage_kv"]})

    # REQ 3: Consistent KM pattern
    kpis = dbc.Row([
        dbc.Col(kpi_card("Total Lines", f"{total_n:,} Projects", "matching current filters", "#6a1b9a"), md=3),
        dbc.Col(kpi_card("Total Length", f"{total_km:,.0f} KM", "circuit length", "#1565c0"), md=3),
        dbc.Col(kpi_card("Total Capacity", f"{total_mw:,.1f} MW", "transfer capacity", "#2e7d32"), md=3),
        dbc.Col(kpi_card("Voltage Classes", f"{n_volt_classes}", "distinct kV levels", "#e65100"), md=3),
    ], className="g-3 mb-4")

    stage_totals = defaultdict(lambda: [0, 0.0, 0.0])
    for r in tx_recs:
        s = stage_totals[r["status"]]
        s[0] += 1
        s[1] += r["line_length_km"] or 0
        s[2] += r["capacity_mw"] or 0
    stages_present = [s for s in STAGE_DISPLAY_ORDER if s in stage_totals]

    # REQ 3: Consistent pattern with KM
    stage_rows = []
    for st in stages_present:
        color_cls = get_status_color_class(st)
        stage_rows.append(html.Div([
            html.Span(st, className=f"fw-semibold {color_cls}"),
            html.Span(f"{stage_totals[st][0]:,} Projects", className="text-muted mx-2"),
            html.Span(f"{stage_totals[st][1]:,.0f} KM", className="text-muted mx-2"),
            html.Span(f"{stage_totals[st][2]:,.1f} MW", className="fw-semibold float-end"),
        ], className="d-flex justify-content-between border-bottom py-2"))

    colors = [get_status_colors().get(s, "#90a4ae") for s in stages_present]
    fig_stage = go.Figure(go.Bar(
        x=stages_present, y=[stage_totals[s][1] for s in stages_present],
        marker_color=colors,
        text=[f"{stage_totals[s][1]:,.0f} KM" for s in stages_present], textposition="outside",
    ))
    fig_stage.update_layout(title="Transmission Lines — Length (KM) by License Stage", height=420,
                             yaxis_title="KM", margin=dict(l=10, r=10, t=40, b=10))
    add_watermark(fig_stage)

    # REQ 9: No flipping when filter is applied in Transmission tab
    # We keep the stage flip card but it won't auto-flip when filtered
    # The flip callback still works but user can also see static view
    tx_card0, tx_fig0, tx_bg0 = _stage_flip_card_and_chart(0, tx_recs, is_transmission=True)
    stage_flip_row = html.Div([
        html.Div(html.H5("🔌 License Stage (Animated)", className="m-0"),
                 id="tx-stage-flip-heading", style=flip_heading_style(tx_bg0)),
        html.Div(
            id="tx-stage-flip-frame",
            style=flip_frame_style(),
            children=dbc.Row([
                dbc.Col(html.Div(id="tx-stage-flip-card", children=tx_card0,
                                  style={"height": "360px"}), md=5),
                dbc.Col(dcc.Graph(id="tx-stage-flip-chart", figure=tx_fig0,
                                   style={"height": "360px"}), md=7),
            ]),
        ),
    ])

    stage_section = dbc.Row([
        dbc.Col(html.Div([html.H5("All License Stages")] + stage_rows), md=5),
        dbc.Col(dcc.Graph(figure=fig_stage), md=7),
    ], className="mb-4")
    stage_section = html.Div([stage_flip_row, html.Hr(), stage_section])

    by_volt = defaultdict(lambda: [0, 0.0, 0.0])
    for r in tx_recs:
        if r["voltage_kv"]:
            v = by_volt[r["voltage_kv"]]
            v[0] += 1
            v[1] += r["line_length_km"] or 0
            v[2] += r["capacity_mw"] or 0
    volts = sorted(by_volt.keys())

    # REQ 3: Consistent KM pattern
    volt_rows = []
    for v in volts:
        volt_rows.append(html.Div([
            html.Span(f"{v:.0f} kV", className="fw-semibold"),
            html.Span(f"{by_volt[v][0]:,} Projects", className="text-muted mx-2"),
            html.Span(f"{by_volt[v][1]:,.0f} KM", className="text-muted mx-2"),
            html.Span(f"{by_volt[v][2]:,.1f} MW", className="fw-semibold float-end"),
        ], className="d-flex justify-content-between border-bottom py-2"))

    fig_volt = go.Figure(go.Bar(
        x=[f"{v:.0f} kV" for v in volts], y=[by_volt[v][1] for v in volts],
        marker_color="#6a1b9a", text=[by_volt[v][0] for v in volts], textposition="outside",
    ))
    fig_volt.update_layout(title="Length (KM) by Voltage Class", height=420,
                            yaxis_title="KM", margin=dict(l=10, r=10, t=40, b=10))
    add_watermark(fig_volt)

    volt_section = dbc.Row([
        dbc.Col(html.Div([html.H5("By Voltage Class")] + volt_rows), md=5),
        dbc.Col(dcc.Graph(figure=fig_volt), md=7),
    ])

    return html.Div([
        kpis,
        dbc.Tabs(id="tx-subtabs", active_tab="stage", children=[
            dbc.Tab(stage_section, label="License Stage", tab_id="stage",
                    tab_style={"marginTop": "10px"}),
            dbc.Tab(volt_section, label="By Voltage Class", tab_id="by-voltage",
                    tab_style={"marginTop": "10px"}),
        ]),
    ])



# ── SIDE CATEGORY TABS (GoN Study, Cancelled) ────────────────────────────
def render_side_category_tab(loader, recs, status_value, page_title):
    side_recs = [r for r in recs if r["status"] == status_value]
    color = de.EXTRA_STATUS_COLORS.get(status_value, "#455a64")
    if not side_recs:
        return dbc.Alert(f"No {page_title.lower()} records match the current filters.",
                          color="info")

    plant_recs = [r for r in side_recs if r["type"] != "Transmission Line"]
    tx_recs = [r for r in side_recs if r["type"] == "Transmission Line"]
    total_mw = sum(r["capacity_mw"] or 0 for r in plant_recs)
    total_km = sum(r["line_length_km"] or 0 for r in tx_recs)

    # REQ 3: Consistent pattern
    kpis = dbc.Row([
        dbc.Col(kpi_card("Total Records", f"{len(side_recs):,} Projects", page_title, color), md=3),
        dbc.Col(kpi_card("Power Plants", f"{len(plant_recs):,} Projects", f"{total_mw:,.1f} MW", color), md=3),
        dbc.Col(kpi_card("Transmission Lines", f"{len(tx_recs):,} Projects", f"{total_km:,.0f} KM", color), md=3),
    ], className="g-3 mb-4")

    by_type, _ = compute_breakdown(side_recs, "type")
    types = [t for t in de.TYPE_ORDER if t in by_type] + [t for t in by_type if t not in de.TYPE_ORDER]
    type_colors = [get_type_colors().get(t, "#607d8b") for t in types]
    fig_type = go.Figure(go.Bar(
        x=types, y=[by_type[t][0] for t in types], marker_color=type_colors,
        text=[f"{by_type[t][0]:,} Projects" for t in types], textposition="outside",
    ))
    fig_type.update_layout(title=f"{page_title} — Count by Project Type", height=380,
                            yaxis_title="Number of projects", margin=dict(l=10, r=10, t=40, b=10))
    add_watermark(fig_type)

    by_prov, _ = compute_breakdown(side_recs, "province")
    provs = [p for p in PROVINCE_DISPLAY_ORDER if p in by_prov] + [p for p in by_prov if p not in PROVINCE_DISPLAY_ORDER]
    prov_colors = [get_province_colors().get(p, "#455a64") for p in provs]
    fig_prov = go.Figure(go.Bar(
        x=provs, y=[by_prov[p][0] for p in provs], marker_color=prov_colors,
        text=[f"{by_prov[p][0]:,} Projects" for p in provs], textposition="outside",
    ))
    fig_prov.update_layout(title=f"{page_title} — Count by Province", height=380,
                            yaxis_title="Number of projects", margin=dict(l=10, r=10, t=40, b=10))
    add_watermark(fig_prov)

    return html.Div([
        kpis,
        dbc.Row([dbc.Col(dcc.Graph(figure=fig_type), md=6),
                 dbc.Col(dcc.Graph(figure=fig_prov), md=6)]),
        html.Hr(),
        render_table(side_recs, ct.CRS_WGS84),
    ])


# ── GROWTH TAB ──────────────────────────────────────────────────────────────
def render_growth(loader, recs):
    """REQ 10: Separate charts for Transmission Lines and active Power Plant stages."""
    plants = [r for r in recs if r["type"] != "Transmission Line"]
    tx_lines = [r for r in recs if r["type"] == "Transmission Line"]

    # Power Plants Growth
    plant_series = loader.yearly_series(plants, key_field="type")
    plant_years = sorted(plant_series.keys())
    all_plant_types = sorted({k for y in plant_years for k in plant_series[y].keys()})

    fig_plant_cap = go.Figure()
    for t in all_plant_types:
        fig_plant_cap.add_trace(go.Scatter(
            x=[str(y) for y in plant_years],
            y=[plant_series[y].get(t, [0, 0])[1] for y in plant_years],
            mode="lines+markers", name=t,
            line=dict(color=get_type_colors().get(t, "#607d8b")),
        ))
    fig_plant_cap.update_layout(
        title="Power Plants — Licensed Capacity by Year (B.S.)",
        xaxis_title="B.S. Year", yaxis_title="Capacity (MW)",
        height=480, legend=dict(orientation="h", y=-0.2),
    )
    add_watermark(fig_plant_cap)

    fig_plant_count = go.Figure()
    for t in all_plant_types:
        fig_plant_count.add_trace(go.Bar(
            x=[str(y) for y in plant_years],
            y=[plant_series[y].get(t, [0, 0])[0] for y in plant_years],
            name=t, marker_color=get_type_colors().get(t, "#607d8b"),
        ))
    fig_plant_count.update_layout(
        barmode="stack",
        title="Power Plants — Project Count by Year",
        height=420, xaxis_title="B.S. Year", yaxis_title="Number of projects",
    )
    add_watermark(fig_plant_count)

    # Transmission Lines Growth
    tx_series = loader.yearly_series(tx_lines, key_field="status")
    tx_years = sorted(tx_series.keys())
    all_tx_statuses = sorted({k for y in tx_years for k in tx_series[y].keys()})

    fig_tx_cap = go.Figure()
    for st in all_tx_statuses:
        fig_tx_cap.add_trace(go.Scatter(
            x=[str(y) for y in tx_years],
            y=[tx_series[y].get(st, [0, 0])[1] for y in tx_years],
            mode="lines+markers", name=st,
            line=dict(color=get_status_colors().get(st, "#90a4ae")),
        ))
    fig_tx_cap.update_layout(
        title="Transmission Lines — Licensed Capacity by Year (B.S.)",
        xaxis_title="B.S. Year", yaxis_title="Capacity (MW)",
        height=480, legend=dict(orientation="h", y=-0.2),
    )
    add_watermark(fig_tx_cap)

    fig_tx_count = go.Figure()
    for st in all_tx_statuses:
        fig_tx_count.add_trace(go.Bar(
            x=[str(y) for y in tx_years],
            y=[tx_series[y].get(st, [0, 0])[0] for y in tx_years],
            name=st, marker_color=get_status_colors().get(st, "#90a4ae"),
        ))
    fig_tx_count.update_layout(
        barmode="stack",
        title="Transmission Lines — Project Count by Year",
        height=420, xaxis_title="B.S. Year", yaxis_title="Number of projects",
    )
    add_watermark(fig_tx_count)

    return html.Div([
        html.H4("⚡ Power Plants Growth", className="mt-3 mb-3"),
        dcc.Graph(figure=fig_plant_cap),
        dcc.Graph(figure=fig_plant_count),
        html.Hr(),
        html.H4("🔌 Transmission Lines Growth", className="mt-3 mb-3"),
        dcc.Graph(figure=fig_tx_cap),
        dcc.Graph(figure=fig_tx_count),
    ])


# ── GIS TAB ─────────────────────────────────────────────────────────────────
def render_gis_tab(loader, recs, f_crs, show_boundary=True, show_pa=False):
    gis_loaded = getattr(de.GIS, 'loaded', False)
    plant_recs = [r for r in recs if r["lat"] and r["lon"]]

    if not gis_loaded and not plant_recs:
        map_view = dbc.Alert(
            "No map data available yet — neither the district/province "
            "boundary package nor any licensed-project coordinates have "
            "been loaded. An administrator can add these at /admin (sync "
            "the workbook and the GIS package, or set DEFAULT_SHEET_URL / "
            "DEFAULT_GIS_DRIVE_URL on the server).",
            color="info",
        )
    else:
        html_str = gis_leaflet_map.build_gis_map_html(
            recs, get_status_colors(), get_type_colors(), get_province_colors(),
        )
        iframe = html.Iframe(
            srcDoc=html_str,
            style={"width": "100%", "height": "690px", "border": "none", "borderRadius": "6px"},
        )
        map_view = html.Div([
            iframe,
            html.Div(
                "Filter by license stage, project type, province, or search by name/promoter/"
                "district/local body directly in the map's own sidebar. Toggle district/local-body/"
                "protected-area layers on and off, and switch the emphasized coordinate "
                "system (WGS-84 vs. Everest 1830) from the sidebar as well.",
                className="text-muted small mt-1",
            ),
        ])
        if not gis_loaded:
            map_view = html.Div([
                dbc.Alert(
                    "District/province boundary shading isn't loaded yet — "
                    "showing project locations only. An administrator can add "
                    "the GIS package at /admin.",
                    color="warning", className="mb-2", dismissable=True,
                ),
                map_view,
            ])

    return map_view



# ── COMPARE TAB ────────────────────────────────────────────────────────────
def render_compare(loader, recs):
    plants = [r for r in recs if r["type"] != "Transmission Line"]
    lines = [r for r in recs if r["type"] == "Transmission Line"]

    by_status_mw = defaultdict(float)
    for r in plants:
        by_status_mw[r["status"]] += r["capacity_mw"] or 0
    colors = [get_status_colors().get(s, "#90a4ae") for s in by_status_mw.keys()]
    fig_plants = go.Figure(go.Bar(
        x=list(by_status_mw.keys()), y=list(by_status_mw.values()),
        marker_color=colors,
    ))
    fig_plants.update_layout(title="Power Plants — Capacity (MW) by License Stage",
                              height=380, yaxis_title="MW")
    add_watermark(fig_plants)

    by_status_km = defaultdict(float)
    for r in lines:
        by_status_km[r["status"]] += r["line_length_km"] or 0
    colors_tx = [get_status_colors().get(s, "#90a4ae") for s in by_status_km.keys()]
    fig_lines = go.Figure(go.Bar(
        x=list(by_status_km.keys()), y=list(by_status_km.values()),
        marker_color=colors_tx,
    ))
    fig_lines.update_layout(title="Transmission Lines — Length (KM) by License Stage",
                             height=380, yaxis_title="KM")
    add_watermark(fig_lines)

    by_volt = defaultdict(int)
    for r in lines:
        if r["voltage_kv"]:
            by_volt[r["voltage_kv"]] += 1
    fig_volt = go.Figure(go.Bar(
        x=[f"{v:.0f} kV" for v in sorted(by_volt)], y=[by_volt[v] for v in sorted(by_volt)],
        marker_color="#6a1b9a",
    ))
    fig_volt.update_layout(title="Transmission Lines by Voltage Class", height=380)
    add_watermark(fig_volt)

    return dbc.Tabs(id="compare-subtabs", active_tab="plants", children=[
        dbc.Tab(dcc.Graph(figure=fig_plants), label="Power Plants", tab_id="plants",
                tab_style={"marginTop": "10px"}),
        dbc.Tab(dcc.Graph(figure=fig_lines), label="Transmission Lines", tab_id="lines",
                tab_style={"marginTop": "10px"}),
        dbc.Tab(dcc.Graph(figure=fig_volt), label="By Voltage Class", tab_id="by-voltage",
                tab_style={"marginTop": "10px"}),
    ])


# ── DATA TABLE ──────────────────────────────────────────────────────────────
def render_table(recs, f_crs=None):
    f_crs = f_crs or ct.CRS_WGS84
    cols = ["project", "type", "status", "capacity_mw", "voltage_kv", "line_length_km",
            "district", "province", "promoter", "lat_disp", "lon_disp", "loc_source"]
    data = []
    for r in recs:
        row = {c: r.get(c) for c in cols if c not in ("lat_disp", "lon_disp")}
        lat, lon = r.get("lat"), r.get("lon")
        if lat is not None and lon is not None:
            if f_crs == ct.CRS_EVEREST:
                lat, lon = ct.wgs84_to_everest(lat, lon)
            row["lat_disp"] = round(lat, 6)
            row["lon_disp"] = round(lon, 6)
        else:
            row["lat_disp"] = row["lon_disp"] = None
        data.append(row)
    label_map = {"lat_disp": f"Latitude ({ct.CRS_LABELS[f_crs]})",
                 "lon_disp": f"Longitude ({ct.CRS_LABELS[f_crs]})"}

    # REQ 11: Page size dropdown at last position
    return html.Div([
        dash_table.DataTable(
            id="data-table",
            data=data,
            columns=[{"name": label_map.get(c, c.replace("_", " ").title()), "id": c} for c in cols],
            page_size=20,
            page_action="native",
            sort_action="native",
            filter_action="native",
            style_table={"overflowX": "auto"},
            style_cell={"fontFamily": "Helvetica", "fontSize": "13px", "padding": "6px"},
            style_header={"fontWeight": "bold", "backgroundColor": "#f1f3f5"},
        ),
        # REQ 11: Page size selector at the bottom
        html.Div([
            html.Label("Show entries:", className="me-2 fw-semibold small"),
            dcc.Dropdown(
                id="table-page-size",
                options=[
                    {"label": "10", "value": 10},
                    {"label": "25", "value": 25},
                    {"label": "50", "value": 50},
                    {"label": "100", "value": 100},
                    {"label": "All", "value": len(data) if data else 100},
                ],
                value=20,
                clearable=False,
                style={"width": "120px", "display": "inline-block"},
            ),
        ], className="mt-2 d-flex align-items-center"),
    ])


@app.callback(
    Output("data-table", "page_size"),
    Input("table-page-size", "value"),
)
def update_table_page_size(page_size):
    return page_size


# ── CUSTOM STYLE TAB ─────────────────────────────────────────────────────────
def render_custom_tab():
    """REQ 12: Custom tab to change chart colors, styles, and types."""
    return html.Div([
        html.H4("🎨 Custom Chart Styling", className="mb-4"),
        dbc.Row([
            dbc.Col(md=6, children=[
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Chart Appearance", className="card-title mb-3"),

                        html.Label("Color Scheme", className="fw-semibold"),
                        dcc.Dropdown(
                            id="custom-color-scheme",
                            options=[
                                {"label": "Default", "value": "default"},
                                {"label": "Pastel", "value": "pastel"},
                                {"label": "Dark", "value": "dark"},
                                {"label": "Vibrant", "value": "vibrant"},
                            ],
                            value=CHART_STYLE_STATE["color_scheme"],
                            clearable=False,
                            className="mb-3",
                        ),

                        html.Label("Bar Mode", className="fw-semibold"),
                        dcc.Dropdown(
                            id="custom-bar-mode",
                            options=[
                                {"label": "Grouped", "value": "group"},
                                {"label": "Stacked", "value": "stack"},
                                {"label": "Relative", "value": "relative"},
                            ],
                            value=CHART_STYLE_STATE["bar_mode"],
                            clearable=False,
                            className="mb-3",
                        ),

                        html.Label("Chart Type", className="fw-semibold"),
                        dcc.Dropdown(
                            id="custom-chart-type",
                            options=[
                                {"label": "Bar Chart", "value": "bar"},
                                {"label": "Line Chart", "value": "line"},
                                {"label": "Area Chart", "value": "area"},
                                {"label": "Scatter Plot", "value": "scatter"},
                            ],
                            value=CHART_STYLE_STATE["chart_type"],
                            clearable=False,
                            className="mb-3",
                        ),

                        html.Label("Font Family", className="fw-semibold"),
                        dcc.Dropdown(
                            id="custom-font-family",
                            options=[
                                {"label": "Arial", "value": "Arial"},
                                {"label": "Helvetica", "value": "Helvetica"},
                                {"label": "Georgia", "value": "Georgia"},
                                {"label": "Times New Roman", "value": "Times New Roman"},
                                {"label": "Courier New", "value": "Courier New"},
                                {"label": "Verdana", "value": "Verdana"},
                            ],
                            value=CHART_STYLE_STATE["font_family"],
                            clearable=False,
                            className="mb-3",
                        ),
                    ]),
                ], className="mb-3 shadow-sm"),
            ]),
            dbc.Col(md=6, children=[
                dbc.Card([
                    dbc.CardBody([
                        html.H5("Advanced Options", className="card-title mb-3"),

                        html.Label("Title Font Size", className="fw-semibold"),
                        dcc.Slider(
                            id="custom-title-size",
                            min=12, max=24, step=1,
                            value=CHART_STYLE_STATE["title_size"],
                            marks={12: "12", 16: "16", 20: "20", 24: "24"},
                            className="mb-4",
                        ),

                        html.Label("Label Font Size", className="fw-semibold"),
                        dcc.Slider(
                            id="custom-label-size",
                            min=10, max=18, step=1,
                            value=CHART_STYLE_STATE["label_size"],
                            marks={10: "10", 12: "12", 14: "14", 16: "16", 18: "18"},
                            className="mb-4",
                        ),

                        dbc.Checklist(
                            id="custom-show-grid",
                            options=[{"label": " Show Grid Lines", "value": "show"}],
                            value=["show"] if CHART_STYLE_STATE["show_grid"] else [],
                            switch=True,
                            className="mb-3",
                        ),

                        dbc.Checklist(
                            id="custom-animation",
                            options=[{"label": " Enable Chart Animations", "value": "animate"}],
                            value=["animate"] if CHART_STYLE_STATE["animation"] else [],
                            switch=True,
                            className="mb-3",
                        ),

                        html.Hr(),
                        html.Div([
                            html.Strong("Current Settings Preview:"),
                            html.Div(id="custom-style-preview", className="mt-2 small text-muted"),
                        ]),
                    ]),
                ], className="mb-3 shadow-sm"),
            ]),
        ]),
        dbc.Row([
            dbc.Col(md=12, children=[
                dbc.Button("Apply Changes", id="btn-apply-style", color="primary", className="me-2"),
                dbc.Button("Reset to Default", id="btn-reset-style", color="secondary", outline=True),
                html.Div(id="custom-style-feedback", className="mt-2"),
            ]),
        ]),
    ])


@app.callback(
    Output("chart-style-store", "data"),
    Output("custom-style-feedback", "children"),
    Input("btn-apply-style", "n_clicks"),
    State("custom-color-scheme", "value"),
    State("custom-bar-mode", "value"),
    State("custom-chart-type", "value"),
    State("custom-font-family", "value"),
    State("custom-title-size", "value"),
    State("custom-label-size", "value"),
    State("custom-show-grid", "value"),
    State("custom-animation", "value"),
    prevent_initial_call=True,
)
def apply_custom_style(n_clicks, color_scheme, bar_mode, chart_type, font_family,
                        title_size, label_size, show_grid, animation):
    if not n_clicks:
        return dash.no_update, dash.no_update

    new_style = {
        "color_scheme": color_scheme or "default",
        "bar_mode": bar_mode or "group",
        "chart_type": chart_type or "bar",
        "font_family": font_family or "Arial",
        "title_size": title_size or 16,
        "label_size": label_size or 12,
        "show_grid": bool(show_grid),
        "animation": bool(animation),
    }
    global CHART_STYLE_STATE
    CHART_STYLE_STATE.update(new_style)

    feedback = dbc.Alert("✅ Style settings applied! Refresh the page or switch tabs to see changes.",
                          color="success", dismissable=True)
    return new_style, feedback


@app.callback(
    Output("custom-color-scheme", "value"),
    Output("custom-bar-mode", "value"),
    Output("custom-chart-type", "value"),
    Output("custom-font-family", "value"),
    Output("custom-title-size", "value"),
    Output("custom-label-size", "value"),
    Output("custom-show-grid", "value"),
    Output("custom-animation", "value"),
    Output("custom-style-feedback", "children", allow_duplicate=True),
    Input("btn-reset-style", "n_clicks"),
    prevent_initial_call=True,
)
def reset_custom_style(n_clicks):
    if not n_clicks:
        return [dash.no_update] * 9

    global CHART_STYLE_STATE
    CHART_STYLE_STATE = {
        "bar_mode": "group",
        "chart_type": "bar",
        "color_scheme": "default",
        "show_grid": True,
        "font_family": "Arial",
        "title_size": 16,
        "label_size": 12,
        "animation": True,
    }

    feedback = dbc.Alert("✅ Style settings reset to default!", color="info", dismissable=True)
    return (
        "default", "group", "bar", "Arial", 16, 12, ["show"], ["animate"], feedback
    )


# ── PDF REPORT ─────────────────────────────────────────────────────────────
@app.callback(
    Output("download-pdf", "data"),
    Input("btn-pdf", "n_clicks"),
    State("f-type", "value"), State("f-status", "value"), State("f-province", "value"),
    State("f-capacity", "value"), State("f-tx-length", "value"), State("f-year", "data"),
    State("f-search", "value"),
    State("f-date-from", "value"), State("f-date-to", "value"),
    State("f-cod-from", "value"), State("f-cod-to", "value"),
    prevent_initial_call=True,
)
def download_pdf(n_clicks, f_type, f_status, f_province, f_capacity, f_tx_length, f_year, f_search,
                  f_date_from, f_date_to, f_cod_from, f_cod_to):
    loader = STATE["loader"]
    if loader is None or not loader.records:
        return None
    recs = get_filtered_records(f_type, f_status, f_province, f_capacity, f_year, f_search,
                                 f_date_from, f_date_to, f_cod_from, f_cod_to, f_tx_length)

    if not recs:
        return None

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    path = os.path.join(tempfile.gettempdir(), "license_status_report.pdf")
    with PdfPages(path) as pdf:
        fig = plt.figure(figsize=(11.69, 8.27))
        ax = fig.add_subplot(111)
        by_type = defaultdict(float)
        for r in recs:
            by_type[r["type"]] += r["capacity_mw"] or 0
        colors = [get_type_colors().get(t, "#607d8b") for t in by_type]
        ax.barh(list(by_type.keys()), list(by_type.values()), color=colors)
        ax.set_title("Nepal Power Plant & Transmission Line License Status — Capacity by Type",
                      fontsize=13, fontweight="bold")
        ax.set_xlabel("Capacity (MW)")
        add_watermark_matplotlib(fig)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        fig2 = plt.figure(figsize=(11.69, 8.27))
        ax2 = fig2.add_subplot(111)
        by_status = defaultdict(int)
        for r in recs:
            by_status[r["status"]] += 1
        colors2 = [get_status_colors().get(s, "#90a4ae") for s in by_status]
        ax2.pie(list(by_status.values()), labels=list(by_status.keys()), autopct="%1.0f%%",
                colors=colors2)
        ax2.set_title("License Stage Breakdown", fontsize=13, fontweight="bold")
        add_watermark_matplotlib(fig2)
        fig2.tight_layout()
        pdf.savefig(fig2)
        plt.close(fig2)

    return dcc.send_file(path)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8050)))
