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

import data_engine as de
import server_state as ss
import coordinate_transform as ct
from admin import admin_bp

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

/* Requirement: License-Stage sub-category rows (per-province detail) use
   distinct font colors per province + a subtle hover/attractive effect. */
.stage-province-row { display: flex; justify-content: space-between; align-items: center;
  padding: 7px 10px; margin-bottom: 4px; border-radius: 6px;
  border-left: 4px solid transparent; background: rgba(0,0,0,0.015);
  transition: transform 0.12s ease, background 0.15s ease, border-color 0.15s ease; }
.stage-province-row:hover { transform: translateX(3px); background: rgba(0,0,0,0.045); }
.stage-province-name { font-weight: 700; letter-spacing: 0.01em; }
.stage-province-dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%;
  margin-right: 8px; box-shadow: 0 0 4px rgba(0,0,0,0.35); vertical-align: middle; }
.stage-province-detail { font-weight: 600; font-size: 12.5px; }
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


# ── CHART CUSTOMIZATION (public "Customize" tab) ────────────────────────────
CHART_TEMPLATES = [
    {"label": "Default", "value": "plotly"},
    {"label": "Dark", "value": "plotly_dark"},
    {"label": "Minimal / White", "value": "simple_white"},
    {"label": "Classic (ggplot)", "value": "ggplot2"},
    {"label": "Seaborn", "value": "seaborn"},
]
CHART_PALETTES = {
    "default": None,  # keep the existing type/province/stage semantic colors
    "ocean": ["#023047", "#219ebc", "#8ecae6", "#ffb703", "#fb8500", "#5390d9", "#48bfe3", "#8d99ae"],
    "sunset": ["#7400b8", "#6930c3", "#5e60ce", "#5390d9", "#4ea8de", "#48bfe3", "#64dfdf", "#80ffdb"],
    "earth": ["#606c38", "#283618", "#dda15e", "#bc6c25", "#a3b18a", "#3a5a40", "#588157", "#344e41"],
    "vibrant": ["#e63946", "#f4a261", "#e9c46a", "#2a9d8f", "#264653", "#a8dadc", "#457b9d", "#1d3557"],
    "grayscale": ["#212529", "#495057", "#868e96", "#adb5bd", "#ced4da", "#dee2e6", "#e9ecef", "#f1f3f5"],
}
CHART_PALETTE_OPTIONS = [
    {"label": "Default (by category)", "value": "default"},
    {"label": "Ocean", "value": "ocean"}, {"label": "Sunset", "value": "sunset"},
    {"label": "Earth", "value": "earth"}, {"label": "Vibrant", "value": "vibrant"},
    {"label": "Grayscale", "value": "grayscale"},
]
DEFAULT_CHART_PREFS = {"template": "plotly", "palette": "default", "donut": True}


def _palette_colors(prefs, keys, fallback_map):
    """Return a marker-color list for `keys`, honoring the chosen palette,
    falling back to the semantic color map (type/province/stage) otherwise."""
    prefs = prefs or DEFAULT_CHART_PREFS
    pal = CHART_PALETTES.get(prefs.get("palette", "default"))
    if not pal:
        return [fallback_map.get(k, "#607d8b") for k in keys]
    return [pal[i % len(pal)] for i in range(len(keys))]


def style_fig(fig, prefs=None):
    """Apply the public Customize-tab template + the DoED credit watermark
    to every chart before it is returned to the layout or downloaded."""
    prefs = prefs or DEFAULT_CHART_PREFS
    fig.update_layout(template=prefs.get("template", "plotly"))
    fig.add_annotation(
        text="Er. Sandeep Neupane", xref="paper", yref="paper",
        x=0.995, y=0.005, xanchor="right", yanchor="bottom",
        showarrow=False, font=dict(size=10, color="rgba(120,120,120,0.55)"),
    )
    return fig


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
                    html.Div("Department of Electricity Development · Live licensing pipeline overview",
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

    dcc.Store(id="chart-prefs", storage_type="local", data=DEFAULT_CHART_PREFS),

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
        dbc.Tab(label="🎨 Customize", tab_id="customize"),
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
        dbc.Row([
            dbc.Col(md="auto", children=[
                html.Label("Choropleth level", className="fw-semibold small me-2"),
                dcc.Dropdown(
                    id="gis-choropleth-level",
                    options=[
                        {"label": "Province", "value": "province"},
                        {"label": "District", "value": "district"},
                        {"label": "Local Body (Gaunpalika/Nagarpalika)", "value": "local"},
                    ],
                    value="district", clearable=False, searchable=False,
                    style={"width": "260px", "display": "inline-block"},
                ),
            ], className="d-flex align-items-center"),
            dbc.Col(md="auto", children=[
                dbc.Checklist(
                    id="gis-opt-layers",
                    options=[
                        {"label": " Country Outline", "value": "country"},
                        {"label": " License Boundary Polygons", "value": "boundary"},
                        {"label": " Protected Areas Overlay", "value": "pa"},
                    ],
                    value=["country", "boundary"],
                    inline=True, switch=True,
                ),
            ], className="d-flex align-items-center"),
        ], className="g-3 mb-2 align-items-center"),
    ]),

    html.Div(id="_init_trigger", style={"display": "none"}),
    dcc.Interval(id="init-once", n_intervals=0, max_intervals=1, interval=500),
    dcc.Interval(id="refresh-poll", n_intervals=0, interval=60_000),
    dcc.Interval(id="type-flip-interval", n_intervals=0, interval=4_000),
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
    provinces = [{"label": p, "value": p} for p in loader.get_provinces() if p != "Unspecified"]
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
    # Requirement: the Active Power Plants / Transmission Lines / GoN Studied
    # Projects / License Cancelled summary is an Overview-only KPI row — it
    # must not appear when any other tab is selected.
    if tab != "overview":
        return []

    loader = STATE["loader"]
    recs = list(loader.records) if loader and not loader.error else []
    active_recs = [r for r in recs if r["status"] not in de.EXTRA_STATUS_ORDER]
    plant_recs = [r for r in active_recs if r["type"] != "Transmission Line"]
    tx_recs = [r for r in active_recs if r["type"] == "Transmission Line"]

    n_plants = len(plant_recs)
    plant_mw = sum(r["capacity_mw"] or 0 for r in plant_recs)
    n_operating = sum(1 for r in plant_recs if r["status"] == "Operating")

    n_tx = len(tx_recs)
    tx_mw = sum(r["capacity_mw"] or 0 for r in tx_recs)
    tx_km = sum(r["line_length_km"] or 0 for r in tx_recs)

    n_gon = sum(1 for r in recs if r["status"] == "GoN Study Project")
    n_cancelled = sum(1 for r in recs if r["status"] == "Cancelled")

    cards = [
        kpi_card("Active Power Plants", f"{n_plants:,} Projects",
                  f"{plant_mw:,.1f} MW • {n_operating:,} operating", "#2e7d32"),
        kpi_card("Transmission Lines", f"{n_tx:,} Projects",
                  f"{tx_mw:,.1f} MW • {tx_km:,.1f} km circuit length", "#6a1b9a"),
        kpi_card("GoN Studied Projects", f"{n_gon:,}",
                  "studied, not counted in active capacity", "#0277bd"),
        kpi_card("License Cancelled", f"{n_cancelled:,}",
                  "cancelled, not counted in active capacity", "#c62828"),
    ]
    return [dbc.Col(c, md=3) for c in cards]


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
    Input("table-page-size-dd", "value"),
    Input("chart-prefs", "data"),
    Input("gis-choropleth-level", "value"),
)
def render_tab(tab, f_type, f_status, f_province, f_capacity, f_tx_length, f_year, f_search,
               f_date_from, f_date_to, f_cod_from, f_cod_to, f_crs, gis_layers,
               f_district, f_local, table_page_size, prefs, gis_level):
    loader = STATE["loader"]
    gis_controls_style = {"display": "block"} if tab == "gis" else {"display": "none"}
    prefs = prefs or DEFAULT_CHART_PREFS

    if tab == "customize":
        return render_customize_tab(prefs), gis_controls_style

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

    # Requirement: the Overview tab's summary KPIs/content only ever show on
    # the Overview tab (see update_kpis) and never react to filters.
    if tab == "overview":
        try:
            all_active_recs = [r for r in loader.records if r["status"] not in de.EXTRA_STATUS_ORDER]
            return render_overview(loader, all_active_recs, prefs=prefs), gis_controls_style
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
            return render_plants_tab(loader, active_recs, f_province=f_province, prefs=prefs), gis_controls_style
        if tab == "transmission":
            return render_transmission_tab(loader, active_recs, prefs=prefs), gis_controls_style
        if tab == "gon_study":
            return render_side_category_tab(loader, recs, "GoN Study Project", "GoN Studied Projects",
                                              prefs=prefs), gis_controls_style
        if tab == "cancelled":
            return render_side_category_tab(loader, recs, "Cancelled", "License Cancelled",
                                              prefs=prefs), gis_controls_style
        if tab == "growth":
            return render_growth(loader, active_recs, prefs=prefs), gis_controls_style
        if tab == "gis":
            gis_layers = gis_layers if gis_layers is not None else ["country", "boundary"]
            return render_gis_tab(loader, active_recs, f_crs or ct.CRS_WGS84,
                                   show_boundary="boundary" in gis_layers,
                                   show_pa="pa" in gis_layers,
                                   show_country="country" in gis_layers,
                                   level=gis_level or "district"), gis_controls_style
        if tab == "compare":
            return render_compare(loader, active_recs, prefs=prefs), gis_controls_style
        if tab == "table":
            return render_table(recs, f_crs or ct.CRS_WGS84, table_page_size), gis_controls_style
        return html.Div(), gis_controls_style
    except Exception:
        tb = traceback.format_exc()
        traceback.print_exc()
        return dbc.Alert([
            html.Div(f"This tab hit an error while rendering: {tab}", className="fw-semibold"),
            html.Pre(tb, className="small mt-2", style={"whiteSpace": "pre-wrap"}),
        ], color="danger", className="mt-3"), gis_controls_style


TYPE_COLOR_MAP = {
    "Hydro (>1MW)": "#1565c0", "Hydro (<=1MW)": "#42a5f5", "Solar": "#f9a825",
    "Wind": "#26a69a", "Co-generation": "#8d6e63", "Thermal": "#6d4c41",
    "Biomass": "#558b2f", "Transmission Line": "#6a1b9a", "Other": "#78909c",
}
PROVINCE_COLOR_MAP = {
    "Koshi": "#00695c", "Madhesh": "#ef6c00", "Bagmati": "#1565c0",
    "Gandaki": "#6a1b9a", "Lumbini": "#2e7d32", "Karnali": "#c62828",
    "Sudurpaschim": "#4527a0", "Unspecified": "#78909c",
}
STATUS_COLOR_MAP = {
    "Application for Survey License": "#90a4ae", "Survey License": "#42a5f5",
    "Application for Construction License": "#ffb300", "Construction License": "#fb8c00",
    "Operating": "#2e7d32",
}

STAGE_SHORT = {
    "Application for Survey License": "Application for Survey",
    "Survey License": "Survey License",
    "Application for Construction License": "Application for Construction",
    "Construction License": "Construction License",
    "Operating": "Operation",
}

FLIP_CARD_STAGE_ORDER = list(reversed(de.STATUS_ORDER))
# Requirement: every stage listing/chart across the dashboard must follow this
# exact display order: Operation -> Construction License -> Application for
# Construction License -> Survey License -> Application for Survey License.
STAGE_DISPLAY_ORDER = FLIP_CARD_STAGE_ORDER

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
    provs = [p.strip() for p in (r.get("provinces_all") or r.get("province") or "").split("/")
             if _looks_like_place(p)]
    dists = [d.strip() for d in (r.get("districts_all") or r.get("district") or "").split("/")
             if _looks_like_place(d)]
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
    for st in de.STATUS_ORDER:
        sel = [r for r in plants if r["status"] == st]
        if sel:
            segs.append((_cat_segment(STAGE_SHORT.get(st, st), len(sel),
                                       sum(r['capacity_mw'] or 0 for r in sel)),
                         de.STATUS_COLORS.get(st, "#c8d3e8")))
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
        spans.append(html.Span(text, style={"color": color, "marginRight": "48px"}))
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


def render_category_card(label, stage_map, total_n, total_mw, bg_url, base_color, total_km=0.0,
                          stage_order=None):
    stage_order = stage_order or de.STATUS_ORDER
    header_style = {
        "borderRadius": "8px 8px 0 0", "padding": "14px 16px", "color": "#fff",
        "position": "relative", "height": "180px", "display": "flex",
        "flexDirection": "column", "justifyContent": "flex-end",
    }
    if bg_url:
        header_style.update({
            "backgroundImage": f'linear-gradient(rgba(15,20,30,0.55), rgba(15,20,30,0.55)), url("{bg_url}")',
            "backgroundSize": "cover", "backgroundPosition": "center",
        })
    else:
        header_style["backgroundColor"] = base_color

    stage_rows = []
    for st in stage_order:
        if st not in stage_map:
            continue
        n, mw, km = stage_map[st]
        detail = f"{n:,} · {mw:,.1f} MW" + (f" · {km:,.1f} km" if km else "")
        stage_color = STATUS_COLOR_MAP.get(st, "#455a64")
        stage_rows.append(html.Div([
            html.Span([
                html.Span(className="stage-province-dot", style={"backgroundColor": stage_color}),
                html.Span(STAGE_SHORT.get(st, st), className="stage-province-name",
                          style={"color": stage_color}),
            ]),
            html.Span(detail, className="stage-province-detail text-muted"),
        ], className="stage-province-row", style={"borderLeftColor": stage_color}))

    totals_line = f"{total_n:,} projects · {total_mw:,.1f} MW" + (f" · {total_km:,.1f} km" if total_km else "")
    return dbc.Card([
        html.Div([
            html.Div(label, className="fw-bold", style={"fontSize": "15px"}),
            html.Div(totals_line, className="small", style={"opacity": 0.9}),
        ], style=header_style),
        dbc.CardBody(stage_rows or [html.Div("No records", className="small text-muted")],
                     style={"padding": "8px 16px", "overflowY": "auto"}),
    ], className="mb-3 shadow-sm", style={"height": "360px", "display": "flex",
                                            "flexDirection": "column"})


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


def status_pie(recs, title, prefs=None):
    prefs = prefs or DEFAULT_CHART_PREFS
    by_status = defaultdict(int)
    for r in recs:
        by_status[r["status"]] += 1
    labels = [s for s in STAGE_DISPLAY_ORDER if s in by_status] + \
             [s for s in by_status if s not in STAGE_DISPLAY_ORDER]
    fig = go.Figure(go.Pie(
        labels=labels, values=[by_status[s] for s in labels],
        hole=0.45 if prefs.get("donut", True) else 0,
        marker_colors=_palette_colors(prefs, labels, STATUS_COLOR_MAP),
    ))
    fig.update_layout(title=title, height=380, margin=dict(l=10, r=10, t=40, b=10))
    return style_fig(fig, prefs)


# FIX: Overview renders immediately with data
def render_overview(loader, recs, prefs=None):
    card, fig = _flip_card_and_chart(0, prefs=prefs)
    type_section = dbc.Row([
        dbc.Col(html.Div(id="type-flip-card", children=card, style={"height": "360px"}), md=5),
        dbc.Col(dcc.Graph(id="type-flip-chart", figure=fig, style={"height": "360px"}), md=7),
    ], className="mb-3")

    # Requirement: below the Power Plant Types, add a province-wise detail of
    # the same data — same background-image / standard-size treatment as the
    # Data Display (card) and Chart sections above.
    plant_recs = [r for r in recs if r["type"] != "Transmission Line"]
    prov_totals, prov_stages = compute_breakdown(plant_recs, "province")
    provinces_present = [p for p in de.PROVINCE_ORDER if p in prov_totals] + \
                        [p for p in prov_totals if p not in de.PROVINCE_ORDER]
    fig_prov = go.Figure(go.Bar(
        x=provinces_present, y=[prov_totals[p][1] for p in provinces_present],
        marker_color=_palette_colors(prefs, provinces_present, PROVINCE_COLOR_MAP),
        text=[f"{prov_totals[p][0]:,} projects" for p in provinces_present], textposition="outside",
    ))
    fig_prov.update_layout(title="Power Plants — Capacity (MW) by Province", height=360,
                            yaxis_title="MW", margin=dict(l=10, r=10, t=40, b=10))
    style_fig(fig_prov, prefs)

    prov_cards = [
        render_category_card(p, prov_stages[p], prov_totals[p][0], prov_totals[p][1],
                              ss.get_province_bg_url(p), PROVINCE_COLOR_MAP.get(p, "#455a64"),
                              stage_order=STAGE_DISPLAY_ORDER)
        for p in provinces_present
    ]
    province_section = html.Div([
        html.H5("Power Plants — By Province", className="mb-2"),
        dbc.Row([
            dbc.Col(html.Div(prov_cards, style={"maxHeight": "460px", "overflowY": "auto"}), md=5),
            dbc.Col(dcc.Graph(figure=fig_prov, style={"height": "460px"}), md=7),
        ]),
    ])

    return html.Div([type_section, html.Hr(), province_section])


def type_flip_chart_figure(t, stage_map, bg_url=None, prefs=None):
    stages_present = [s for s in FLIP_CARD_STAGE_ORDER if s in stage_map]
    use_km = (t == "Transmission Line")
    idx = 2 if use_km else 1
    unit = "km" if use_km else "MW"
    fig = go.Figure(go.Bar(
        x=stages_present, y=[stage_map[s][idx] for s in stages_present],
        marker_color=_palette_colors(prefs, stages_present, STATUS_COLOR_MAP),
        text=[f"{stage_map[s][idx]:,.1f} {unit}" for s in stages_present], textposition="outside",
    ))
    layout_kwargs = dict(
        title=f"{t} — {'Length (km)' if use_km else 'Capacity (MW)'} by License Stage",
        height=360, yaxis_title=unit, margin=dict(l=10, r=10, t=40, b=10),
    )
    # Standard-size background image treatment — identical to the card header
    # background so the Data Display (card) and Chart sections always match.
    if bg_url:
        layout_kwargs["images"] = [dict(
            source=bg_url, xref="paper", yref="paper",
            x=0, y=1, sizex=1, sizey=1, xanchor="left", yanchor="top",
            sizing="stretch", opacity=0.30, layer="below",
        )]
        layout_kwargs["plot_bgcolor"] = "rgba(255,255,255,0.72)"
        layout_kwargs["paper_bgcolor"] = "rgba(0,0,0,0)"
    fig.update_layout(**layout_kwargs)
    return style_fig(fig, prefs)


def _flip_card_and_chart(n, prefs=None):
    loader = STATE["loader"]
    empty_fig = go.Figure()
    if loader is None or loader.error or not loader.records:
        return None, empty_fig
    try:
        recs = [r for r in loader.records if r["status"] not in de.EXTRA_STATUS_ORDER]
        if not recs:
            return None, empty_fig
        totals, stages = compute_breakdown(recs, "type")
        types = [t for t in de.TYPE_ORDER if t in totals] + \
                [t for t in totals if t not in de.TYPE_ORDER]
        if not types:
            return None, empty_fig
        t = types[n % len(types)]
        bg_url = ss.get_type_bg_url(t)
        card = render_category_card(t, stages[t], totals[t][0], totals[t][1],
                                     bg_url, TYPE_COLOR_MAP.get(t, "#607d8b"),
                                     total_km=totals[t][2], stage_order=FLIP_CARD_STAGE_ORDER)
        return card, type_flip_chart_figure(t, stages[t], bg_url=bg_url, prefs=prefs)
    except Exception:
        tb = traceback.format_exc()
        traceback.print_exc()
        err_card = dbc.Alert([
            html.Div("The Overview activity card hit an error while rendering.",
                      className="fw-semibold small"),
            html.Pre(tb, className="small mt-1",
                      style={"whiteSpace": "pre-wrap", "maxHeight": "280px", "overflowY": "auto"}),
        ], color="danger")
        return err_card, empty_fig


@app.callback(
    Output("type-flip-card", "children"),
    Output("type-flip-chart", "figure"),
    Input("type-flip-interval", "n_intervals"),
    State("chart-prefs", "data"),
)
def flip_type_card(n, prefs):
    return _flip_card_and_chart(n, prefs)


def render_single_stage_card(stage, sel_recs, bg_url, base_color, is_transmission=False):
    n = len(sel_recs)
    mw = sum(r["capacity_mw"] or 0 for r in sel_recs)
    km = sum(r["line_length_km"] or 0 for r in sel_recs) if is_transmission else 0.0
    prov_totals = defaultdict(lambda: [0, 0.0, 0.0])
    for r in sel_recs:
        p = r["province"] or "Unspecified"
        prov_totals[p][0] += 1
        prov_totals[p][1] += r["capacity_mw"] or 0.0
        prov_totals[p][2] += r["line_length_km"] or 0.0
    # Requirement: give the details of ALL provinces here, in the canonical
    # Koshi -> Madhesh -> Bagmati -> Gandaki -> Lumbini -> Karnali ->
    # Sudurpaschim order — not just a top-N subset.
    all_provs = [p for p in de.PROVINCE_ORDER if p in prov_totals] + \
                [p for p in prov_totals if p not in de.PROVINCE_ORDER]

    header_style = {
        "borderRadius": "8px 8px 0 0", "padding": "14px 16px", "color": "#fff",
        "position": "relative", "height": "180px", "display": "flex",
        "flexDirection": "column", "justifyContent": "flex-end",
    }
    if bg_url:
        header_style.update({
            "backgroundImage": f'linear-gradient(rgba(15,20,30,0.55), rgba(15,20,30,0.55)), url("{bg_url}")',
            "backgroundSize": "cover", "backgroundPosition": "center",
        })
    else:
        header_style["backgroundColor"] = base_color

    # Requirement: each province gets its own distinct font color + a small
    # color dot, plus a hover "lift" effect (see .stage-province-row CSS).
    rows = []
    for p in all_provs:
        v = prov_totals[p]
        prov_color = PROVINCE_COLOR_MAP.get(p, "#455a64")
        detail = f"{v[0]:,} · {v[1]:,.1f} MW" + (f" · {v[2]:,.1f} km" if is_transmission and v[2] else "")
        rows.append(html.Div([
            html.Span([
                html.Span(className="stage-province-dot", style={"backgroundColor": prov_color}),
                html.Span(p, className="stage-province-name", style={"color": prov_color}),
            ]),
            html.Span(detail, className="stage-province-detail text-muted"),
        ], className="stage-province-row", style={"borderLeftColor": prov_color}))

    # Order: Projects, then Capacity (MW), then length (km) — kept consistent
    # across every summary line in the dashboard.
    totals_line = f"{n:,} projects · {mw:,.1f} MW" + (f" · {km:,.1f} km" if km else "")
    return dbc.Card([
        html.Div([
            html.Div(stage, className="fw-bold", style={"fontSize": "15px"}),
            html.Div(totals_line, className="small", style={"opacity": 0.9}),
        ], style=header_style),
        dbc.CardBody(rows or [html.Div("No records for this stage yet", className="small text-muted")],
                     style={"padding": "8px 16px", "overflowY": "auto"}),
    ], className="mb-3 shadow-sm", style={"height": "360px", "display": "flex",
                                            "flexDirection": "column"})


def stage_province_chart_figure(stage, sel_recs, is_transmission=False, bg_url=None, prefs=None):
    prov_totals = defaultdict(lambda: [0, 0.0, 0.0])
    for r in sel_recs:
        p = r["province"] or "Unspecified"
        prov_totals[p][0] += 1
        prov_totals[p][1] += r["capacity_mw"] or 0.0
        prov_totals[p][2] += r.get("line_length_km") or 0.0
    provinces_present = [p for p in de.PROVINCE_ORDER if p in prov_totals] + \
                        [p for p in prov_totals if p not in de.PROVINCE_ORDER]
    idx = 2 if is_transmission else 1
    unit = "km" if is_transmission else "MW"
    yvals = [prov_totals[p][idx] for p in provinces_present]
    fig = go.Figure(go.Bar(
        x=provinces_present, y=yvals,
        marker_color=_palette_colors(prefs, provinces_present, PROVINCE_COLOR_MAP),
        text=[f"{v:,.1f} {unit}" for v in yvals], textposition="outside",
    ))
    layout_kwargs = dict(
        title=f"{stage} — {'Length (km)' if is_transmission else 'Capacity (MW)'} by Province",
        height=360, yaxis_title=unit, margin=dict(l=10, r=10, t=40, b=10),
    )
    if bg_url:
        layout_kwargs["images"] = [dict(
            source=bg_url, xref="paper", yref="paper",
            x=0, y=1, sizex=1, sizey=1, xanchor="left", yanchor="top",
            sizing="stretch", opacity=0.30, layer="below",
        )]
        layout_kwargs["plot_bgcolor"] = "rgba(255,255,255,0.72)"
        layout_kwargs["paper_bgcolor"] = "rgba(0,0,0,0)"
    fig.update_layout(**layout_kwargs)
    return style_fig(fig, prefs)


def _stage_flip_card_and_chart(n, recs, is_transmission=False, prefs=None):
    empty_fig = go.Figure()
    try:
        # Display order: Operation -> Construction License -> Application for
        # Construction License -> Survey License -> Application for Survey License.
        stages_present = [s for s in STAGE_DISPLAY_ORDER if any(r["status"] == s for r in recs)]
        if not stages_present:
            return None, empty_fig
        st = stages_present[n % len(stages_present)]
        sel = [r for r in recs if r["status"] == st]
        bg_url = ss.get_status_bg_url(st)
        card = render_single_stage_card(st, sel, bg_url, STATUS_COLOR_MAP.get(st, "#90a4ae"),
                                         is_transmission=is_transmission)
        return card, stage_province_chart_figure(st, sel, is_transmission=is_transmission,
                                                  bg_url=bg_url, prefs=prefs)
    except Exception:
        tb = traceback.format_exc()
        traceback.print_exc()
        err_card = dbc.Alert([
            html.Div("This stage card hit an error while rendering.", className="fw-semibold small"),
            html.Pre(tb, className="small mt-1",
                      style={"whiteSpace": "pre-wrap", "maxHeight": "280px", "overflowY": "auto"}),
        ], color="danger")
        return err_card, empty_fig


@app.callback(
    Output("plants-stage-flip-card", "children"),
    Output("plants-stage-flip-chart", "figure"),
    Input("type-flip-interval", "n_intervals"),
    State("f-type", "value"), State("f-status", "value"), State("f-province", "value"),
    State("f-capacity", "value"), State("f-tx-length", "value"), State("f-year", "data"),
    State("f-search", "value"),
    State("f-date-from", "value"), State("f-date-to", "value"),
    State("f-cod-from", "value"), State("f-cod-to", "value"),
    State("f-district", "value"), State("f-local", "value"),
    State("chart-prefs", "data"),
)
def flip_plants_stage_card(n, f_type, f_status, f_province, f_capacity, f_tx_length, f_year,
                            f_search, f_date_from, f_date_to, f_cod_from, f_cod_to,
                            f_district, f_local, prefs):
    loader = STATE["loader"]
    if loader is None or loader.error or not loader.records:
        return None, go.Figure()
    recs = get_filtered_records(f_type, f_status, f_province, f_capacity, f_year, f_search,
                                 f_date_from, f_date_to, f_cod_from, f_cod_to, f_tx_length,
                                 f_district, f_local)
    plant_recs = [r for r in recs if r["type"] != "Transmission Line"
                  and r["status"] not in de.EXTRA_STATUS_ORDER]
    return _stage_flip_card_and_chart(n, plant_recs, prefs=prefs)


@app.callback(
    Output("tx-stage-flip-card", "children"),
    Output("tx-stage-flip-chart", "figure"),
    Input("type-flip-interval", "n_intervals"),
    State("f-type", "value"), State("f-status", "value"), State("f-province", "value"),
    State("f-capacity", "value"), State("f-tx-length", "value"), State("f-year", "data"),
    State("f-search", "value"),
    State("f-date-from", "value"), State("f-date-to", "value"),
    State("f-cod-from", "value"), State("f-cod-to", "value"),
    State("f-district", "value"), State("f-local", "value"),
    State("chart-prefs", "data"),
)
def flip_tx_stage_card(n, f_type, f_status, f_province, f_capacity, f_tx_length, f_year,
                        f_search, f_date_from, f_date_to, f_cod_from, f_cod_to,
                        f_district, f_local, prefs):
    loader = STATE["loader"]
    if loader is None or loader.error or not loader.records:
        return None, go.Figure()
    recs = get_filtered_records(f_type, f_status, f_province, f_capacity, f_year, f_search,
                                 f_date_from, f_date_to, f_cod_from, f_cod_to, f_tx_length,
                                 f_district, f_local)
    tx_recs = [r for r in recs if r["type"] == "Transmission Line"
               and r["status"] not in de.EXTRA_STATUS_ORDER]
    return _stage_flip_card_and_chart(n, tx_recs, is_transmission=True, prefs=prefs)


def _plants_province_flip_card_and_chart(n, plant_recs, f_province_filter, prefs=None):
    """Power Plants tab, 'By Province' section.

    With NO province filter applied: auto-cycles through every province in
    the canonical order Koshi -> Madhesh -> Bagmati -> Gandaki -> Lumbini ->
    Karnali -> Sudurpaschim, background image and chart changing with time.

    With a province filter applied: cycles only through the selected
    province(s) — showing that specific province's detail.
    """
    empty_fig = go.Figure()
    try:
        prov_totals, prov_stages = compute_breakdown(plant_recs, "province")
        if f_province_filter:
            sel = set(f_province_filter)
            provinces_present = [p for p in de.PROVINCE_ORDER if p in sel and p in prov_totals]
        else:
            provinces_present = [p for p in de.PROVINCE_ORDER if p in prov_totals]
        if not provinces_present:
            return None, empty_fig
        p = provinces_present[n % len(provinces_present)]
        bg_url = ss.get_province_bg_url(p)
        card = render_category_card(p, prov_stages[p], prov_totals[p][0], prov_totals[p][1],
                                     bg_url, PROVINCE_COLOR_MAP.get(p, "#455a64"),
                                     total_km=prov_totals[p][2], stage_order=STAGE_DISPLAY_ORDER)
        return card, type_flip_chart_figure(p, prov_stages[p], bg_url=bg_url, prefs=prefs)
    except Exception:
        tb = traceback.format_exc()
        traceback.print_exc()
        err_card = dbc.Alert([
            html.Div("This province card hit an error while rendering.", className="fw-semibold small"),
            html.Pre(tb, className="small mt-1",
                      style={"whiteSpace": "pre-wrap", "maxHeight": "280px", "overflowY": "auto"}),
        ], color="danger")
        return err_card, empty_fig


@app.callback(
    Output("plants-province-flip-card", "children"),
    Output("plants-province-flip-chart", "figure"),
    Input("type-flip-interval", "n_intervals"),
    State("f-type", "value"), State("f-status", "value"), State("f-province", "value"),
    State("f-capacity", "value"), State("f-tx-length", "value"), State("f-year", "data"),
    State("f-search", "value"),
    State("f-date-from", "value"), State("f-date-to", "value"),
    State("f-cod-from", "value"), State("f-cod-to", "value"),
    State("f-district", "value"), State("f-local", "value"),
    State("chart-prefs", "data"),
)
def flip_plants_province_card(n, f_type, f_status, f_province, f_capacity, f_tx_length, f_year,
                               f_search, f_date_from, f_date_to, f_cod_from, f_cod_to,
                               f_district, f_local, prefs):
    loader = STATE["loader"]
    if loader is None or loader.error or not loader.records:
        return None, go.Figure()
    recs = get_filtered_records(f_type, f_status, f_province, f_capacity, f_year, f_search,
                                 f_date_from, f_date_to, f_cod_from, f_cod_to, f_tx_length,
                                 f_district, f_local)
    plant_recs = [r for r in recs if r["type"] != "Transmission Line"
                  and r["status"] not in de.EXTRA_STATUS_ORDER]
    return _plants_province_flip_card_and_chart(n, plant_recs, f_province, prefs=prefs)


def render_plants_tab(loader, recs, f_province=None, prefs=None):
    plant_recs = [r for r in recs if r["type"] != "Transmission Line"]
    if not plant_recs:
        return dbc.Alert("No power-plant records match the current filters.", color="info")

    stage_totals, _ = compute_breakdown(plant_recs, "status")
    # Display order: Operation -> Construction License -> Application for
    # Construction License -> Survey License -> Application for Survey License.
    stages_present = [s for s in STAGE_DISPLAY_ORDER if s in stage_totals]

    stage_rows = [html.Div([
        html.Span([
            html.Span(className="stage-province-dot", style={"backgroundColor": STATUS_COLOR_MAP.get(st, "#455a64")}),
            html.Span(st, className="stage-province-name", style={"color": STATUS_COLOR_MAP.get(st, "#455a64")}),
        ]),
        html.Span([
            html.Span(f"{stage_totals[st][0]:,} projects", className="text-muted mx-2 small"),
            html.Span(f"{stage_totals[st][1]:,.1f} MW", className="stage-province-detail"),
        ]),
    ], className="stage-province-row", style={"borderLeftColor": STATUS_COLOR_MAP.get(st, "#455a64")})
        for st in stages_present]

    fig_stage = go.Figure(go.Bar(
        x=stages_present, y=[stage_totals[s][1] for s in stages_present],
        marker_color=_palette_colors(prefs, stages_present, STATUS_COLOR_MAP),
        text=[f"{stage_totals[s][1]:,.0f} MW" for s in stages_present], textposition="outside",
    ))
    fig_stage.update_layout(title="Power Plants — Capacity (MW) by License Stage", height=420,
                             yaxis_title="MW", margin=dict(l=10, r=10, t=40, b=10))
    style_fig(fig_stage, prefs)

    stage_flip_row = dbc.Row([
        dbc.Col(html.Div(id="plants-stage-flip-card", style={"height": "360px"}), md=5),
        dbc.Col(dcc.Graph(id="plants-stage-flip-chart", style={"height": "360px"}), md=7),
    ], className="mb-3")

    stage_section = dbc.Row([
        dbc.Col(html.Div([html.H5("All License Stages")] + stage_rows), md=5),
        dbc.Col(dcc.Graph(figure=fig_stage), md=7),
    ], className="mb-4")
    stage_section = html.Div([stage_flip_row, html.Hr(), stage_section])

    # By Province: with no province filter applied, this rotates automatically
    # through every province in the order Koshi, Madhesh, Bagmati, Gandaki,
    # Lumbini, Karnali, Sudurpaschim (background image + chart change on a
    # timer). With a province filter applied, it shows that specific
    # province's detail instead.
    note = (
        "Showing the selected province(s). Clear the Province filter to "
        "auto-cycle through all seven provinces." if f_province else
        "No province filter applied — auto-cycling Koshi → Madhesh → Bagmati → "
        "Gandaki → Lumbini → Karnali → Sudurpaschim."
    )
    prov_section = html.Div([
        html.Div(note, className="text-muted small mb-2"),
        dbc.Row([
            dbc.Col(html.Div(id="plants-province-flip-card", style={"height": "360px"}), md=5),
            dbc.Col(dcc.Graph(id="plants-province-flip-chart", style={"height": "360px"}), md=7),
        ]),
    ])

    return dbc.Tabs([
        dbc.Tab(stage_section, label="License Stage", tab_style={"marginTop": "10px"}),
        dbc.Tab(prov_section, label="By Province", tab_style={"marginTop": "10px"}),
    ])


def render_transmission_tab(loader, recs, prefs=None):
    tx_recs = [r for r in recs if r["type"] == "Transmission Line"]
    if not tx_recs:
        return dbc.Alert("No transmission-line records match the current filters.", color="info")

    total_n = len(tx_recs)
    total_km = sum(r["line_length_km"] or 0 for r in tx_recs)
    total_mw = sum(r["capacity_mw"] or 0 for r in tx_recs)
    n_volt_classes = len({r["voltage_kv"] for r in tx_recs if r["voltage_kv"]})

    # Requirement: only the Transmission Line summary at the top — no Power
    # Plants KPIs here — ordered Projects -> Capacity -> length (km).
    kpis = dbc.Row([
        dbc.Col(kpi_card("Total Lines", f"{total_n:,} Projects", "matching current filters", "#6a1b9a"), md=3),
        dbc.Col(kpi_card("Total Capacity", f"{total_mw:,.1f} MW", "transfer capacity", "#2e7d32"), md=3),
        dbc.Col(kpi_card("Total Length", f"{total_km:,.0f} km", "circuit length", "#1565c0"), md=3),
        dbc.Col(kpi_card("Voltage Classes", f"{n_volt_classes}", "distinct kV levels", "#e65100"), md=3),
    ], className="g-3 mb-4")

    stage_totals = defaultdict(lambda: [0, 0.0, 0.0])
    for r in tx_recs:
        s = stage_totals[r["status"]]
        s[0] += 1
        s[1] += r["line_length_km"] or 0
        s[2] += r["capacity_mw"] or 0
    # Display order: Operation -> Construction License -> Application for
    # Construction License -> Survey License -> Application for Survey License.
    stages_present = [s for s in STAGE_DISPLAY_ORDER if s in stage_totals]

    stage_rows = [html.Div([
        html.Span([
            html.Span(className="stage-province-dot", style={"backgroundColor": STATUS_COLOR_MAP.get(st, "#455a64")}),
            html.Span(st, className="stage-province-name", style={"color": STATUS_COLOR_MAP.get(st, "#455a64")}),
        ]),
        html.Span([
            html.Span(f"{stage_totals[st][0]:,} lines", className="text-muted mx-2 small"),
            html.Span(f"{stage_totals[st][2]:,.1f} MW", className="text-muted mx-2 small"),
            html.Span(f"{stage_totals[st][1]:,.0f} km", className="stage-province-detail"),
        ]),
    ], className="stage-province-row", style={"borderLeftColor": STATUS_COLOR_MAP.get(st, "#455a64")})
        for st in stages_present]

    fig_stage = go.Figure(go.Bar(
        x=stages_present, y=[stage_totals[s][1] for s in stages_present],
        marker_color=_palette_colors(prefs, stages_present, STATUS_COLOR_MAP),
        text=[f"{stage_totals[s][1]:,.0f} km" for s in stages_present], textposition="outside",
    ))
    fig_stage.update_layout(title="Transmission Lines — Length (km) by License Stage", height=420,
                             yaxis_title="km", margin=dict(l=10, r=10, t=40, b=10))
    style_fig(fig_stage, prefs)

    stage_flip_row = dbc.Row([
        dbc.Col(html.Div(id="tx-stage-flip-card", style={"height": "360px"}), md=5),
        dbc.Col(dcc.Graph(id="tx-stage-flip-chart", style={"height": "360px"}), md=7),
    ], className="mb-3")

    stage_section = dbc.Row([
        dbc.Col(html.Div([html.H5("All License Stages")] + stage_rows), md=5),
        dbc.Col(dcc.Graph(figure=fig_stage), md=7),
    ], className="mb-4")
    stage_section = html.Div([stage_flip_row, html.Hr(), stage_section])

    # Requirement: don't focus on transmission-line province/district here —
    # show other information (voltage class breakdown) instead.
    by_volt = defaultdict(lambda: [0, 0.0, 0.0])
    for r in tx_recs:
        if r["voltage_kv"]:
            v = by_volt[r["voltage_kv"]]
            v[0] += 1
            v[1] += r["line_length_km"] or 0
            v[2] += r["capacity_mw"] or 0
    volts = sorted(by_volt.keys())

    volt_rows = [html.Div([
        html.Span(f"{v:.0f} kV", className="fw-semibold"),
        html.Span(f"{by_volt[v][0]:,} lines", className="text-muted mx-2"),
        html.Span(f"{by_volt[v][2]:,.1f} MW", className="text-muted mx-2"),
        html.Span(f"{by_volt[v][1]:,.0f} km", className="fw-semibold float-end"),
    ], className="d-flex justify-content-between border-bottom py-2") for v in volts]

    fig_volt = go.Figure(go.Bar(
        x=[f"{v:.0f} kV" for v in volts], y=[by_volt[v][1] for v in volts],
        marker_color=(_palette_colors(prefs, volts, {}) if prefs and prefs.get("palette") != "default"
                      else "#6a1b9a"),
        text=[by_volt[v][0] for v in volts], textposition="outside",
    ))
    fig_volt.update_layout(title="Length (km) by Voltage Class", height=420,
                            yaxis_title="km", margin=dict(l=10, r=10, t=40, b=10))
    style_fig(fig_volt, prefs)

    volt_section = dbc.Row([
        dbc.Col(html.Div([html.H5("By Voltage Class")] + volt_rows), md=5),
        dbc.Col(dcc.Graph(figure=fig_volt), md=7),
    ])

    return html.Div([
        kpis,
        dbc.Tabs([
            dbc.Tab(stage_section, label="License Stage", tab_style={"marginTop": "10px"}),
            dbc.Tab(volt_section, label="By Voltage Class", tab_style={"marginTop": "10px"}),
        ]),
    ])


def render_side_category_tab(loader, recs, status_value, page_title, prefs=None):
    side_recs = [r for r in recs if r["status"] == status_value]
    color = de.EXTRA_STATUS_COLORS.get(status_value, "#455a64")
    if not side_recs:
        return dbc.Alert(f"No {page_title.lower()} records match the current filters.",
                          color="info")

    plant_recs = [r for r in side_recs if r["type"] != "Transmission Line"]
    tx_recs = [r for r in side_recs if r["type"] == "Transmission Line"]
    total_mw = sum(r["capacity_mw"] or 0 for r in plant_recs)
    total_km = sum(r["line_length_km"] or 0 for r in tx_recs)

    kpis = dbc.Row([
        dbc.Col(kpi_card("Total Records", f"{len(side_recs):,}", page_title, color), md=3),
        dbc.Col(kpi_card("Power Plants", f"{len(plant_recs):,}", f"{total_mw:,.1f} MW", color), md=3),
        dbc.Col(kpi_card("Transmission Lines", f"{len(tx_recs):,}", f"{total_km:,.0f} km", color), md=3),
    ], className="g-3 mb-4")

    by_type, _ = compute_breakdown(side_recs, "type")
    types = [t for t in de.TYPE_ORDER if t in by_type] + [t for t in by_type if t not in de.TYPE_ORDER]
    fig_type = go.Figure(go.Bar(
        x=types, y=[by_type[t][0] for t in types], marker_color=color,
        text=[by_type[t][0] for t in types], textposition="outside",
    ))
    fig_type.update_layout(title=f"{page_title} — Count by Project Type", height=380,
                            yaxis_title="Number of records", margin=dict(l=10, r=10, t=40, b=10))
    style_fig(fig_type, prefs)

    by_prov, _ = compute_breakdown(side_recs, "province")
    provs = [p for p in de.PROVINCE_ORDER if p in by_prov] + [p for p in by_prov if p not in de.PROVINCE_ORDER]
    fig_prov = go.Figure(go.Bar(
        x=provs, y=[by_prov[p][0] for p in provs], marker_color=color,
        text=[by_prov[p][0] for p in provs], textposition="outside",
    ))
    fig_prov.update_layout(title=f"{page_title} — Count by Province", height=380,
                            yaxis_title="Number of records", margin=dict(l=10, r=10, t=40, b=10))
    style_fig(fig_prov, prefs)

    return html.Div([
        kpis,
        dbc.Row([dbc.Col(dcc.Graph(figure=fig_type), md=6),
                 dbc.Col(dcc.Graph(figure=fig_prov), md=6)]),
        html.Hr(),
        render_table(side_recs, ct.CRS_WGS84),
    ])


def render_growth(loader, recs, prefs=None):
    # Requirement: power-plant types and the transmission line must never be
    # mixed into the same series/chart — build each independently.
    plant_recs = [r for r in recs if r["type"] != "Transmission Line"]
    tx_recs = [r for r in recs if r["type"] == "Transmission Line"]

    def _capacity_and_count_figs(records, key_field, color_map, section_label, y_label="Capacity (MW)"):
        series = loader.yearly_series(records, key_field=key_field)
        years = sorted(series.keys())
        keys = sorted({k for y in years for k in series[y].keys()})

        fig_cap = go.Figure()
        for k in keys:
            fig_cap.add_trace(go.Scatter(
                x=[str(y) for y in years],
                y=[series[y].get(k, [0, 0])[1] for y in years],
                mode="lines+markers", name=k,
                line=dict(color=color_map.get(k, "#607d8b")),
            ))
        fig_cap.update_layout(title=f"{section_label} — {y_label} by Year (License Issued Year, B.S.)",
                               xaxis_title="B.S. Year", yaxis_title=y_label,
                               height=440, legend=dict(orientation="h", y=-0.25))
        style_fig(fig_cap, prefs)

        fig_count = go.Figure()
        for k in keys:
            fig_count.add_trace(go.Bar(
                x=[str(y) for y in years], y=[series[y].get(k, [0, 0])[0] for y in years],
                name=k, marker_color=color_map.get(k, "#607d8b"),
            ))
        fig_count.update_layout(barmode="stack", title=f"{section_label} — Project Count by Year",
                                 height=380, xaxis_title="B.S. Year", yaxis_title="Number of projects")
        style_fig(fig_count, prefs)
        return fig_cap, fig_count

    plant_cap_fig, plant_count_fig = _capacity_and_count_figs(
        plant_recs, "type", TYPE_COLOR_MAP, "Power Plants")
    # Transmission growth is grouped by province (not mixed with plant types),
    # using capacity (MW) — the underlying series helper only tracks MW/count.
    tx_cap_fig, tx_count_fig = (
        _capacity_and_count_figs(tx_recs, "province", PROVINCE_COLOR_MAP, "Transmission Lines")
        if tx_recs else (go.Figure(), go.Figure())
    )

    return html.Div([
        html.H5("Power Plants — Growth Trends", className="mb-3"),
        dcc.Graph(figure=plant_cap_fig),
        dcc.Graph(figure=plant_count_fig),
        html.Hr(className="my-4"),
        html.H5("Transmission Lines — Growth Trends", className="mb-3"),
        dcc.Graph(figure=tx_cap_fig),
        dcc.Graph(figure=tx_count_fig),
    ])


def render_gis(loader, recs, f_crs=None, show_boundary=True, show_pa=False,
                show_country=True, level="district"):
    plant_recs = [r for r in recs if r["lat"] and r["lon"]]
    boundary_recs = [r for r in recs if r.get("bbox")] if show_boundary else []

    gis_loaded = getattr(de.GIS, 'loaded', False)
    pa_loaded = getattr(de.GIS, 'pa_loaded', False)

    if not gis_loaded and not plant_recs and not boundary_recs:
        return dbc.Alert(
            "No map data available yet — neither the province/district/"
            "local-body boundary package nor any licensed-project "
            "coordinates have been loaded. An administrator can add these "
            "at /admin (sync the workbook and the GIS package, or set "
            "DEFAULT_SHEET_URL / DEFAULT_GIS_DRIVE_URL on the server).",
            color="info",
        )

    fig = go.Figure()

    # Real national outline (from the Survey Department shapefile) as a
    # thin base-map reference layer, underneath the choropleth.
    if show_country and getattr(de.GIS, "boundary_polygons", None):
        for poly in de.GIS.boundary_polygons:
            for ring in poly:
                lons = [pt[0] for pt in ring]
                lats = [pt[1] for pt in ring]
                fig.add_trace(go.Scattermapbox(
                    lon=lons, lat=lats, mode="lines", fill="none",
                    line=dict(width=2, color="#0d47a1"),
                    hoverinfo="skip", showlegend=False, name="Nepal",
                ))

    # Choropleth polygons — province, district, or local body — shaded by
    # capacity (MW) of the currently-filtered records at that granularity.
    if gis_loaded:
        key_field = {"province": "province", "district": "district", "local": "local_body"}.get(level, "district")
        metric = loader.metric_by_field(recs, key_field) if key_field != "district" else loader.district_metric(recs)
        values = [v[1] for v in metric.values()]
        vmax = max(values) if values else 1
        for name, prov, rings in de.GIS.display_rings(level=level):
            cnt, mw = metric.get(name, [0, 0.0])
            intensity = min(mw / vmax, 1.0) if vmax else 0
            color = f"rgba(21,101,192,{0.15 + 0.65 * intensity:.2f})"
            label = {"province": "Province", "district": "District", "local": "Local Body"}.get(level, "District")
            for ring in rings:
                lons = [pt[0] for pt in ring]
                lats = [pt[1] for pt in ring]
                fig.add_trace(go.Scattermapbox(
                    lon=lons, lat=lats, mode="lines", fill="toself",
                    fillcolor=color, line=dict(width=1, color="#37474f"),
                    hoverinfo="text",
                    text=f"{label}: {name} ({prov})<br>{cnt:,} projects · {mw:,.1f} MW",
                    showlegend=False,
                ))

    if show_pa and pa_loaded:
        for name, category, rings in de.GIS.pa_display_rings():
            for ring in rings:
                lons = [pt[0] for pt in ring]
                lats = [pt[1] for pt in ring]
                fig.add_trace(go.Scattermapbox(
                    lon=lons, lat=lats, mode="lines", fill="toself",
                    fillcolor="rgba(46,125,50,0.28)", line=dict(width=1.5, color="#1b5e20"),
                    hoverinfo="text",
                    text=f"Protected area: {name}" + (f" ({category})" if category else ""),
                    showlegend=False,
                ))

    for r in boundary_recs:
        la1, la2, lo1, lo2 = r["bbox"]
        lons = [lo1, lo2, lo2, lo1, lo1]
        lats = [la1, la1, la2, la2, la1]
        detail = de.full_rec_tip(r).replace(chr(10), "<br>")
        fig.add_trace(go.Scattermapbox(
            lon=lons, lat=lats, mode="lines", fill="toself",
            fillcolor="rgba(230,81,0,0.18)", line=dict(width=1.5, color="#e65100"),
            hoverinfo="text", text=detail,
            customdata=[detail] * len(lons),
            name="License boundary", showlegend=False,
        ))

    if plant_recs:
        def _hover(r):
            lat, lon = r["lat"], r["lon"]
            if f_crs == ct.CRS_EVEREST:
                lat, lon = ct.wgs84_to_everest(lat, lon)
            base = (f"{r['project']}<br>{r['type']} · {r['status']} · {r['capacity_mw'] or 0:.1f} MW"
                    f"<br>{lat:.5f}, {lon:.5f} ({ct.CRS_LABELS.get(f_crs or ct.CRS_WGS84)})")
            return base

        def _detail(r):
            return de.full_rec_tip(r).replace(chr(10), "<br>")

        # Requirement: color every project marker by its current License
        # Stage (Operation / Construction License / ... / Application for
        # Survey License) rather than by project type, so the map shows
        # "the Projects with each stage of active license" at a glance.
        fig.add_trace(go.Scattermapbox(
            lon=[r["lon"] for r in plant_recs], lat=[r["lat"] for r in plant_recs],
            mode="markers",
            marker=dict(size=9, color=[STATUS_COLOR_MAP.get(r["status"], "#607d8b") for r in plant_recs]),
            text=[_hover(r) for r in plant_recs],
            customdata=[_detail(r) for r in plant_recs],
            hoverinfo="text", name="Projects",
        ))

        # A visible legend for the license-stage marker colors (Scattermapbox
        # doesn't auto-legend marker-array colors), in canonical stage order.
        stages_present = [s for s in STAGE_DISPLAY_ORDER if any(r["status"] == s for r in plant_recs)]
        for st in stages_present:
            fig.add_trace(go.Scattermapbox(
                lon=[None], lat=[None], mode="markers",
                marker=dict(size=9, color=STATUS_COLOR_MAP.get(st, "#607d8b")),
                name=st, showlegend=True, hoverinfo="skip",
            ))

    fig.update_layout(
        mapbox=dict(style="carto-positron", center=dict(lat=28.3, lon=84.1), zoom=5.6),
        height=650, margin=dict(l=0, r=0, t=0, b=0),
        legend=dict(bgcolor="rgba(255,255,255,0.85)", x=0.01, y=0.99),
    )
    graph = dcc.Graph(id="gis-map", figure=fig, config={"scrollZoom": True})

    if not gis_loaded:
        return html.Div([
            dbc.Alert(
                "Province/district/local-body boundary shading isn't loaded "
                "yet — showing project locations only. An administrator can "
                "add the GIS package at /admin.",
                color="warning", className="mb-2", dismissable=True,
            ),
            graph,
        ])
    return graph


def render_gis_tab(loader, recs, f_crs, show_boundary=True, show_pa=False,
                     show_country=True, level="district"):
    map_view = dbc.Row([
        dbc.Col(md=8, children=[
            html.Div(id="gis-controls-wrapper"),
            render_gis(loader, recs, f_crs, show_boundary=show_boundary, show_pa=show_pa,
                       show_country=show_country, level=level),
            html.Div("Scroll the mouse wheel over the map to zoom in/out.",
                      className="text-muted small mt-1"),
        ]),
        dbc.Col(md=4, children=[
            dbc.Card(dbc.CardBody([
                html.H6([html.I(className="bi bi-geo-alt me-2"), "Project Details"],
                         className="mb-2"),
                html.Div(
                    id="gis-detail-panel",
                    children=dbc.Alert(
                        "Hover over a project marker or license boundary on the "
                        "map to see its full details here.", color="light",
                    ),
                ),
            ]), className="shadow-sm", style={"maxHeight": "690px", "overflowY": "auto"}),
        ]),
    ])

    pa_names = de.GIS.pa_names() if getattr(de.GIS, 'pa_loaded', False) else []
    pa_view = (dbc.ListGroup([dbc.ListGroupItem(n) for n in pa_names])
               if pa_names else
               dbc.Alert("No protected-area layer is loaded.", color="info"))

    return dbc.Tabs([
        dbc.Tab(map_view, label="Map"),
        dbc.Tab(pa_view, label="Protected Areas List"),
    ])


@app.callback(
    Output("gis-detail-panel", "children"),
    Input("gis-map", "hoverData"),
    prevent_initial_call=True,
)
def show_gis_hover_detail(hover_data):
    if not hover_data or not hover_data.get("points"):
        return dash.no_update
    pt = hover_data["points"][0]
    detail = pt.get("customdata")
    if not detail:
        return dbc.Alert("No additional details for this map feature.", color="light")
    return html.Div(dcc.Markdown(str(detail), dangerously_allow_html=True), className="small")


def render_compare(loader, recs, prefs=None):
    plants = [r for r in recs if r["type"] != "Transmission Line"]
    lines = [r for r in recs if r["type"] == "Transmission Line"]

    by_status_mw = defaultdict(float)
    for r in plants:
        by_status_mw[r["status"]] += r["capacity_mw"] or 0
    order = [s for s in STAGE_DISPLAY_ORDER if s in by_status_mw]
    fig_plants = go.Figure(go.Bar(
        x=order, y=[by_status_mw[s] for s in order],
        marker_color=_palette_colors(prefs, order, STATUS_COLOR_MAP),
    ))
    fig_plants.update_layout(title="Power Plants — Capacity (MW) by License Stage",
                              height=380, yaxis_title="MW")
    style_fig(fig_plants, prefs)

    by_status_km = defaultdict(float)
    for r in lines:
        by_status_km[r["status"]] += r["line_length_km"] or 0
    order_km = [s for s in STAGE_DISPLAY_ORDER if s in by_status_km]
    fig_lines = go.Figure(go.Bar(
        x=order_km, y=[by_status_km[s] for s in order_km],
        marker_color=_palette_colors(prefs, order_km, STATUS_COLOR_MAP),
    ))
    fig_lines.update_layout(title="Transmission Lines — Length (km) by License Stage",
                             height=380, yaxis_title="km")
    style_fig(fig_lines, prefs)

    by_volt = defaultdict(int)
    for r in lines:
        if r["voltage_kv"]:
            by_volt[r["voltage_kv"]] += 1
    fig_volt = go.Figure(go.Bar(
        x=[f"{v:.0f} kV" for v in sorted(by_volt)], y=[by_volt[v] for v in sorted(by_volt)],
        marker_color=(_palette_colors(prefs, sorted(by_volt), {}) if prefs and prefs.get("palette") != "default"
                      else "#6a1b9a"),
    ))
    fig_volt.update_layout(title="Transmission Lines by Voltage Class", height=380)
    style_fig(fig_volt, prefs)

    return dbc.Tabs([
        dbc.Tab(dcc.Graph(figure=fig_plants), label="Power Plants",
                tab_style={"marginTop": "10px"}),
        dbc.Tab(dcc.Graph(figure=fig_lines), label="Transmission Lines",
                tab_style={"marginTop": "10px"}),
        dbc.Tab(dcc.Graph(figure=fig_volt), label="By Voltage Class",
                tab_style={"marginTop": "10px"}),
    ])


def render_customize_tab(prefs):
    prefs = prefs or DEFAULT_CHART_PREFS
    return html.Div([
        html.H5("Customize Charts", className="mb-1"),
        html.Div(
            "These preferences apply to every chart across the dashboard (Overview, "
            "Power Plants, Transmission Line, Growth Trends, Comparative Charts) for "
            "your own view, and are saved in your browser.",
            className="text-muted small mb-3",
        ),
        dbc.Row([
            dbc.Col(md=4, children=[
                html.Label("Chart style / template", className="fw-semibold small"),
                dcc.Dropdown(id="prefs-template", options=CHART_TEMPLATES,
                              value=prefs.get("template", "plotly"), clearable=False),
            ]),
            dbc.Col(md=4, children=[
                html.Label("Color palette", className="fw-semibold small"),
                dcc.Dropdown(id="prefs-palette", options=CHART_PALETTE_OPTIONS,
                              value=prefs.get("palette", "default"), clearable=False),
            ]),
            dbc.Col(md=4, children=[
                html.Label("Pie chart style", className="fw-semibold small"),
                dbc.RadioItems(
                    id="prefs-donut",
                    options=[{"label": " Donut", "value": True}, {"label": " Full pie", "value": False}],
                    value=prefs.get("donut", True), inline=True, className="mt-2",
                ),
            ]),
        ], className="g-3 mb-3"),
        dbc.Button("Reset to defaults", id="prefs-reset", color="secondary", size="sm", outline=True),
        html.Div(id="prefs-saved-note", className="text-success small mt-2"),
    ])


@app.callback(
    Output("chart-prefs", "data"),
    Output("prefs-saved-note", "children"),
    Input("prefs-template", "value"), Input("prefs-palette", "value"),
    Input("prefs-donut", "value"), Input("prefs-reset", "n_clicks"),
    prevent_initial_call=True,
)
def update_chart_prefs(template, palette, donut, _reset):
    if ctx.triggered_id == "prefs-reset":
        return DEFAULT_CHART_PREFS, "Reset to defaults."
    prefs = {
        "template": template or "plotly",
        "palette": palette or "default",
        "donut": True if donut is None else donut,
    }
    return prefs, "Preferences saved — applied across every chart."


TABLE_PAGE_SIZE_OPTIONS = [
    {"label": "10", "value": "10"}, {"label": "25", "value": "25"},
    {"label": "50", "value": "50"}, {"label": "100", "value": "100"},
    {"label": "All", "value": "all"},
]


def render_table(recs, f_crs=None, page_size_value=None):
    f_crs = f_crs or ct.CRS_WGS84
    page_size_value = page_size_value or "25"
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

    show_all = (page_size_value == "all")
    controls = dbc.Row([
        dbc.Col(width="auto", children=html.Div([
            html.Label("Rows to display:", className="fw-semibold small me-2"),
            dcc.Dropdown(
                id="table-page-size-dd", options=TABLE_PAGE_SIZE_OPTIONS,
                value=page_size_value, clearable=False, searchable=False,
                style={"width": "110px", "display": "inline-block", "verticalAlign": "middle"},
            ),
        ], className="d-flex align-items-center")),
        dbc.Col(width="auto", className="text-muted small d-flex align-items-center",
                children=f"{len(data):,} records total"),
    ], className="g-3 mb-2 align-items-center")

    table = dash_table.DataTable(
        id="data-table",
        data=data,
        columns=[{"name": label_map.get(c, c.replace("_", " ").title()), "id": c} for c in cols],
        page_action="none" if show_all else "native",
        page_size=max(len(data), 1) if show_all else int(page_size_value),
        sort_action="native", filter_action="native",
        virtualization=show_all,
        fixed_rows={"headers": True} if show_all else {},
        style_table={"overflowX": "auto", "overflowY": "auto",
                     "maxHeight": "650px" if show_all else "none"},
        style_cell={"fontFamily": "Helvetica", "fontSize": "13px", "padding": "6px"},
        style_header={"fontWeight": "bold", "backgroundColor": "#f1f3f5"},
    )
    return html.Div([controls, table])


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

    def _watermark(fig):
        # Requirement: every saved/downloaded figure carries this credit watermark.
        fig.text(0.5, 0.5, "Er. Sandeep Neupane", ha="center", va="center",
                  fontsize=42, color="gray", alpha=0.15, rotation=30)
        fig.text(0.99, 0.01, "Er. Sandeep Neupane", ha="right", va="bottom",
                  fontsize=8, color="gray", alpha=0.6)

    path = os.path.join(tempfile.gettempdir(), "license_status_report.pdf")
    with PdfPages(path) as pdf:
        fig = plt.figure(figsize=(11.69, 8.27))
        ax = fig.add_subplot(111)
        by_type = defaultdict(float)
        for r in recs:
            by_type[r["type"]] += r["capacity_mw"] or 0
        ax.barh(list(by_type.keys()), list(by_type.values()),
                color=[TYPE_COLOR_MAP.get(t, "#607d8b") for t in by_type])
        ax.set_title("Nepal Power Plant & Transmission Line License Status — Capacity by Type",
                      fontsize=13, fontweight="bold")
        ax.set_xlabel("Capacity (MW)")
        fig.tight_layout()
        _watermark(fig)
        pdf.savefig(fig)
        plt.close(fig)

        fig2 = plt.figure(figsize=(11.69, 8.27))
        ax2 = fig2.add_subplot(111)
        by_status = defaultdict(int)
        for r in recs:
            by_status[r["status"]] += 1
        # Display order: Operation -> Construction License -> Application for
        # Construction License -> Survey License -> Application for Survey License.
        labels = [s for s in STAGE_DISPLAY_ORDER if s in by_status] + \
                 [s for s in by_status if s not in STAGE_DISPLAY_ORDER]
        ax2.pie([by_status[s] for s in labels], labels=labels, autopct="%1.0f%%",
                colors=[STATUS_COLOR_MAP.get(s, "#90a4ae") for s in labels])
        ax2.set_title("License Stage Breakdown", fontsize=13, fontweight="bold")
        fig2.tight_layout()
        _watermark(fig2)
        pdf.savefig(fig2)
        plt.close(fig2)

    return dcc.send_file(path)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8050)))
