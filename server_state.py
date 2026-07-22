"""
server_state.py

Shared, single-source-of-truth server state for the Nepal Power Plant &
Transmission Line License Status web app.

KEY FIX: GIS data is now bundled inline via gis_bundled.py — the map works
immediately on first deploy with zero configuration, no uploads, no Drive syncs.
Admin uploads still work as overrides if provided.
"""

import os
import copy
import json
import threading
import traceback

import data_engine as de

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.getcwd(), "data"))
GIS_DIR = os.path.join(DATA_DIR, "gis")
ASSETS_DIR = os.path.join(DATA_DIR, "assets")

for d in (DATA_DIR, GIS_DIR, ASSETS_DIR):
    os.makedirs(d, exist_ok=True)

WORKBOOK_PATH = os.path.join(DATA_DIR, "workbook.xlsx")
GIS_ZIP_PATH = os.path.join(GIS_DIR, "hermes_NPL_new_wgs.zip")
PA_ZIP_PATH = os.path.join(GIS_DIR, "Protected_Area.zip")
LOGO_PATH_JSON = os.path.join(DATA_DIR, "config.json")

MAX_GIS_ZIP_MB = int(os.environ.get("MAX_GIS_ZIP_MB", "80"))

STATE = {
    "loader": None,
    "gis_loaded": False,
    "pa_loaded": False,
    "gis_loading": False,
    "pa_loading": False,
    "gis_load_error": None,
    "pa_load_error": None,
    "error": None,
    "source_label": "No data loaded yet",
    "last_sync": None,
    "logo_filename": None,
    "flag_filename": None,
}

_gis_lock = threading.Lock()


def _read_config_file():
    if os.path.exists(LOGO_PATH_JSON):
        try:
            with open(LOGO_PATH_JSON) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _sync_state_from_config():
    cfg = _read_config_file()
    STATE["logo_filename"] = cfg.get("logo_filename")
    STATE["flag_filename"] = cfg.get("flag_filename")
    STATE["background_filename"] = cfg.get("background_filename")
    STATE["marquee_enabled"] = cfg.get("marquee_enabled", True)
    STATE["last_sync"] = cfg.get("last_sync")
    STATE["type_bg"] = cfg.get("type_bg", {})
    STATE["province_bg"] = cfg.get("province_bg", {})
    STATE["status_bg"] = cfg.get("status_bg", {})
    STATE["visitor_count"] = cfg.get("visitor_count", 0)
    return cfg


def _save_config(**updates):
    cfg = _read_config_file()
    cfg.update(updates)
    with open(LOGO_PATH_JSON, "w") as f:
        json.dump(cfg, f)


def _check_zip_size(path, label):
    size_mb = os.path.getsize(path) / (1024 * 1024)
    if size_mb > MAX_GIS_ZIP_MB:
        raise ValueError(
            f"{label} is {size_mb:.0f} MB, over the {MAX_GIS_ZIP_MB} MB limit."
        )


def ensure_gis_loaded(force=False):
    """Load GIS data. Uses bundled inline GeoJSON as guaranteed fallback.
    Admin-uploaded zips and Drive links still work as overrides."""
    if not force and STATE["gis_loaded"] and STATE["pa_loaded"]:
        return

    try:
        # ── Load districts from bundled data (ALWAYS works) ──
        from gis_bundled import NEPAL_DISTRICTS_GEOJSON
        candidate = copy.copy(de.GIS)
        ok = candidate.load_from_geojson(NEPAL_DISTRICTS_GEOJSON)
        if ok:
            de.GIS = candidate
            STATE["gis_loaded"] = True
            STATE["gis_load_error"] = None

        # ── Try admin-uploaded zip as override (higher detail) ──
        if os.path.exists(GIS_ZIP_PATH):
            try:
                _check_zip_size(GIS_ZIP_PATH, "GIS package")
                override = copy.copy(de.GIS)
                if override.load_from_path(GIS_ZIP_PATH):
                    de.GIS = override
                    STATE["gis_loaded"] = True
            except Exception as e:
                # Keep bundled data, log the error
                STATE["gis_load_error"] = f"Admin GIS override failed: {e}. Using bundled data."

    except Exception as exc:
        traceback.print_exc()
        if not STATE["gis_loaded"]:
            STATE["gis_load_error"] = str(exc)

    # ── Load protected areas ──
    try:
        from gis_bundled import NEPAL_PROTECTED_AREAS_GEOJSON
        candidate = copy.copy(de.GIS)
        ok = candidate.load_protected_from_geojson(NEPAL_PROTECTED_AREAS_GEOJSON)
        if ok:
            de.GIS = candidate
            STATE["pa_loaded"] = True
            STATE["pa_load_error"] = None

        # Try admin-uploaded override
        if os.path.exists(PA_ZIP_PATH):
            try:
                _check_zip_size(PA_ZIP_PATH, "Protected-area package")
                override = copy.copy(de.GIS)
                if override.load_protected_from_path(PA_ZIP_PATH):
                    de.GIS = override
                    STATE["pa_loaded"] = True
            except Exception as e:
                STATE["pa_load_error"] = f"Admin PA override failed: {e}. Using bundled data."

    except Exception as exc:
        traceback.print_exc()
        if not STATE["pa_loaded"]:
            STATE["pa_load_error"] = str(exc)


def _run_async(loading_flag, error_flag, fn):
    def _worker():
        with _gis_lock:
            STATE[loading_flag] = True
            try:
                fn()
            except Exception as exc:
                traceback.print_exc()
                STATE[error_flag] = str(exc)
            finally:
                STATE[loading_flag] = False

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def start_gis_reload_async():
    def _do():
        ensure_gis_loaded(force=True)
        _reparse_current_workbook_if_any()
    _run_async("gis_loading", "gis_load_error", _do)


def start_pa_reload_async():
    def _do():
        ensure_gis_loaded(force=True)
        _reparse_current_workbook_if_any()
    _run_async("pa_loading", "pa_load_error", _do)


def load_from_path(path, label):
    """Parse a workbook and make it the active data source."""
    ensure_gis_loaded()
    loader = de.DataLoader(path)
    loader.load()
    got_data = bool(loader.records) and not loader.error
    had_data_before = STATE.get("loader") is not None and bool(STATE["loader"].records)

    if got_data or not had_data_before:
        STATE["loader"] = loader
        STATE["error"] = loader.error
        STATE["source_label"] = label
    else:
        STATE["error"] = ((loader.error or "This sync returned 0 records.") +
                           " Previously loaded data is still being served.")
    return loader


def load_from_google_sheet(url_or_id):
    de.download_google_sheet_xlsx(url_or_id, WORKBOOK_PATH)
    loader = load_from_path(WORKBOOK_PATH, "Google Sheet (live sync)")
    _save_config(last_sync=_now_str(), source="google_sheet", gs_url=url_or_id)
    STATE["last_sync"] = _now_str()
    return loader


def load_from_uploaded_workbook(saved_path, filename):
    loader = load_from_path(saved_path, f"Uploaded file: {filename}")
    _save_config(last_sync=_now_str(), source="upload")
    STATE["last_sync"] = _now_str()
    return loader


def _reparse_current_workbook_if_any():
    loader = STATE.get("loader")
    if loader is not None and getattr(loader, "path", None) and os.path.exists(loader.path):
        try:
            load_from_path(loader.path, STATE.get("source_label", "Reloaded after GIS update"))
        except Exception:
            traceback.print_exc()


def load_gis_from_drive(url_or_id):
    _, changed = de.download_google_drive_file(url_or_id, GIS_ZIP_PATH)
    ensure_gis_loaded(force=True)
    _save_config(gis_drive_url=url_or_id, last_gis_sync=_now_str())
    if changed:
        _reparse_current_workbook_if_any()
    return changed


def load_pa_from_drive(url_or_id):
    _, changed = de.download_google_drive_file(url_or_id, PA_ZIP_PATH)
    ensure_gis_loaded(force=True)
    _save_config(pa_drive_url=url_or_id, last_pa_sync=_now_str())
    if changed:
        _reparse_current_workbook_if_any()
    return changed


def start_gis_drive_sync_async(url_or_id):
    def _do():
        de.download_google_drive_file(url_or_id, GIS_ZIP_PATH)
        ensure_gis_loaded(force=True)
        _save_config(gis_drive_url=url_or_id, last_gis_sync=_now_str())
        STATE["gis_drive_url"] = url_or_id
        STATE["last_gis_sync"] = _now_str()
        _reparse_current_workbook_if_any()
    _run_async("gis_loading", "gis_load_error", _do)


def start_pa_drive_sync_async(url_or_id):
    def _do():
        de.download_google_drive_file(url_or_id, PA_ZIP_PATH)
        ensure_gis_loaded(force=True)
        _save_config(pa_drive_url=url_or_id, last_pa_sync=_now_str())
        STATE["pa_drive_url"] = url_or_id
        STATE["last_pa_sync"] = _now_str()
        _reparse_current_workbook_if_any()
    _run_async("pa_loading", "pa_load_error", _do)


def reload_cached_on_startup():
    bootstrap_on_startup()


def bootstrap_on_startup():
    """Zero-dependency startup. GIS loads from bundled data immediately.
    Workbook loads from env vars or cache if available."""
    # Restore anything previously configured via the admin panel (logo, flag,
    # hero background, per-type/status/province backgrounds, marquee toggle,
    # visitor count) so it survives a process/dyno restart.
    cfg = _sync_state_from_config()
    sheet_url = cfg.get("gs_url") or os.environ.get("DEFAULT_SHEET_URL")
    gis_url = cfg.get("gis_drive_url") or os.environ.get("DEFAULT_GIS_DRIVE_URL")
    pa_url = cfg.get("pa_drive_url") or os.environ.get("DEFAULT_PA_DRIVE_URL")

    # ── GIS FIRST (bundled data guarantees this always works) ──
    ensure_gis_loaded()

    # Try Drive overrides if configured
    if gis_url:
        try:
            load_gis_from_drive(gis_url)
        except Exception:
            traceback.print_exc()
    if pa_url:
        try:
            load_pa_from_drive(pa_url)
        except Exception:
            traceback.print_exc()

    # ── Workbook LAST (needs GIS for district/province resolution) ──
    if sheet_url:
        try:
            load_from_google_sheet(sheet_url)
        except Exception:
            traceback.print_exc()
            if os.path.exists(WORKBOOK_PATH):
                try:
                    load_from_path(WORKBOOK_PATH, "Cached workbook (Sheet fetch failed)")
                except Exception:
                    traceback.print_exc()
    elif os.path.exists(WORKBOOK_PATH):
        try:
            load_from_path(WORKBOOK_PATH, "Cached workbook (auto-restored)")
        except Exception:
            traceback.print_exc()
    else:
        STATE["error"] = (
            "No project data loaded.\n"
            "1. Set DEFAULT_SHEET_URL environment variable, OR\n"
            "2. Upload a workbook via /admin panel, OR\n"
            "3. Place workbook.xlsx in the data/ folder."
        )


_REFRESH_INTERVAL_SECONDS = int(os.environ.get("AUTO_REFRESH_HOURS", "6")) * 3600


def start_background_refresh():
    def _tick():
        try:
            cfg = _read_config_file()
            sheet_url = cfg.get("gs_url") or os.environ.get("DEFAULT_SHEET_URL")
            gis_url = cfg.get("gis_drive_url") or os.environ.get("DEFAULT_GIS_DRIVE_URL")
            pa_url = cfg.get("pa_drive_url") or os.environ.get("DEFAULT_PA_DRIVE_URL")
            if gis_url:
                load_gis_from_drive(gis_url)
            if pa_url:
                load_pa_from_drive(pa_url)
            if sheet_url:
                load_from_google_sheet(sheet_url)
        except Exception:
            traceback.print_exc()
        finally:
            t = threading.Timer(_REFRESH_INTERVAL_SECONDS, _tick)
            t.daemon = True
            t.start()

    t = threading.Timer(_REFRESH_INTERVAL_SECONDS, _tick)
    t.daemon = True
    t.start()


import datetime as _dt

# Nepal Standard Time is a fixed UTC+5:45 offset (no daylight-saving rules),
# so a plain fixed-offset timezone is correct and avoids depending on an
# IANA tzdata install being present in the deployment environment.
NEPAL_TZ = _dt.timezone(_dt.timedelta(hours=5, minutes=45), name="NPT")


def _now_str():
    return _dt.datetime.now(NEPAL_TZ).strftime("%Y-%m-%d %H:%M NPT")


def get_last_sync():
    return STATE.get("last_sync")


def get_logo_path():
    fn = STATE.get("logo_filename")
    if fn and os.path.exists(os.path.join(ASSETS_DIR, fn)):
        return os.path.join(ASSETS_DIR, fn)
    return None


def set_logo(filename):
    STATE["logo_filename"] = filename
    _save_config(logo_filename=filename)


_BUNDLED_FLAG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nepal_flag.png")


def get_flag_path():
    fn = STATE.get("flag_filename")
    if fn and os.path.exists(os.path.join(ASSETS_DIR, fn)):
        return os.path.join(ASSETS_DIR, fn)
    if os.path.exists(_BUNDLED_FLAG_PATH):
        return _BUNDLED_FLAG_PATH
    return None


def set_flag_image(filename):
    STATE["flag_filename"] = filename
    _save_config(flag_filename=filename)


def get_background_path():
    fn = STATE.get("background_filename")
    if fn and os.path.exists(os.path.join(ASSETS_DIR, fn)):
        return os.path.join(ASSETS_DIR, fn)
    return None


def set_background(filename):
    STATE["background_filename"] = filename
    _save_config(background_filename=filename)


def get_marquee_enabled():
    return STATE.get("marquee_enabled", True)


def set_marquee_enabled(enabled):
    STATE["marquee_enabled"] = bool(enabled)
    _save_config(marquee_enabled=bool(enabled))


def bump_visitor_count():
    n = int(STATE.get("visitor_count", 0)) + 1
    STATE["visitor_count"] = n
    _save_config(visitor_count=n)
    return n


def get_visitor_count():
    return int(STATE.get("visitor_count", 0))


def slugify_type(type_name):
    s = type_name.lower().strip()
    s = s.replace(">", "gt").replace("<=", "lte").replace("<", "lt")
    out = []
    for ch in s:
        out.append(ch if ch.isalnum() else "_")
    slug = "".join(out)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")


def get_type_bg_path(type_name):
    slug = slugify_type(type_name)
    fn = STATE.get("type_bg", {}).get(slug)
    if fn and os.path.exists(os.path.join(ASSETS_DIR, fn)):
        return os.path.join(ASSETS_DIR, fn)
    return None


def get_type_bg_url(type_name):
    slug = slugify_type(type_name)
    if STATE.get("type_bg", {}).get(slug):
        return f"/assets-type-bg/{slug}"
    return None


def set_type_bg(type_name, filename):
    slug = slugify_type(type_name)
    d = dict(STATE.get("type_bg") or {})
    d[slug] = filename
    STATE["type_bg"] = d
    _save_config(type_bg=d)


def get_province_bg_path(province_name):
    slug = slugify_type(province_name)
    fn = STATE.get("province_bg", {}).get(slug)
    if fn and os.path.exists(os.path.join(ASSETS_DIR, fn)):
        return os.path.join(ASSETS_DIR, fn)
    return None


def get_province_bg_url(province_name):
    slug = slugify_type(province_name)
    if STATE.get("province_bg", {}).get(slug):
        return f"/assets-province-bg/{slug}"
    return None


def set_province_bg(province_name, filename):
    slug = slugify_type(province_name)
    d = dict(STATE.get("province_bg") or {})
    d[slug] = filename
    STATE["province_bg"] = d
    _save_config(province_bg=d)


def get_status_bg_path(status_name):
    slug = slugify_type(status_name)
    fn = STATE.get("status_bg", {}).get(slug)
    if fn and os.path.exists(os.path.join(ASSETS_DIR, fn)):
        return os.path.join(ASSETS_DIR, fn)
    return None


def get_status_bg_url(status_name):
    slug = slugify_type(status_name)
    if STATE.get("status_bg", {}).get(slug):
        return f"/assets-status-bg/{slug}"
    return None


def set_status_bg(status_name, filename):
    slug = slugify_type(status_name)
    d = dict(STATE.get("status_bg") or {})
    d[slug] = filename
    STATE["status_bg"] = d
    _save_config(status_bg=d)
