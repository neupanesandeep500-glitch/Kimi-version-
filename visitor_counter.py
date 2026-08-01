"""
visitor_counter.py — Google-Sheets-backed visitor counter
=============================================================
Problem this solves: a plain in-memory counter (or a JSON file on
ephemeral disk) resets to 0 every time the app redeploys, because most
hosts spin up a brand-new container/filesystem on each deploy. This
module fixes that by treating a small Google Sheet as the durable
store — the ONLY things ever written to it are:

    B1: current visitor count
    B2: last-update timestamp (when the app itself was last deployed/
        restarted — useful to see "the count survived this deploy")

Nothing else in your Google Sheet is touched. Reads/writes are scoped
to exactly these two cells.

DESIGN
------
- On boot: one read from the sheet seeds the in-memory counter. If the
  sheet is unreachable, we fall back to 0 and keep serving — a visitor
  counter glitch should never take the whole app down.
- On every visit: increment the FAST in-memory counter only. No
  network call per visit — that would hit Google Sheets API quotas
  under any real traffic and add latency to every page load.
- A background timer flushes the in-memory counter to the sheet every
  FLUSH_INTERVAL_SECONDS (default 60s), and also flushes immediately
  on flush_now()/shutdown, so you never lose more than ~1 minute of
  visits even in a hard crash.
- record_deploy() writes a "last update" timestamp to B2 — call this
  once at startup so you (or the sheet) can see when the app last
  redeployed, without that write happening on every visit either.

HOW TO WIRE THIS INTO app.py
-----------------------------
    import visitor_counter

    visitor_counter.bootstrap()             # call once at startup
    visitor_counter.start_background_flush()  # call once at startup

    @server.before_request
    def _count_visitor():
        # only count real page views, not static assets/API polling
        if request.path.startswith(("/static", "/api/")):
            return
        visitor_counter.increment()

    # anywhere you render a template / build a response:
    current_count = visitor_counter.get_count()

    # optional: call this once at the very end of your startup sequence
    # (after NEA.bootstrap() etc.) to stamp "last update" in the sheet
    visitor_counter.record_deploy()
"""

from __future__ import annotations

import json
import os
import threading
import traceback
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

# ── Configuration ────────────────────────────────────────────────────────

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Defaults point at the "Visitors Counter" sheet already created and
# shared (Editor) with the service account
# (https-github-com-neupanesandee@seismic-rarity-503315-i5.iam.gserviceaccount.com).
# Still overridable via env var if you ever point this at a different
# sheet without a code change.
_SHEET_ID = os.environ.get("VISITOR_SHEET_ID", "1KbNdAqGUrNVa44FJrTo4q0h8kHQ-4Dpsp_Uovg8PVvk")
_WORKSHEET_NAME = os.environ.get("VISITOR_SHEET_TAB", "Website Visitor Counter")
FLUSH_INTERVAL_SECONDS = float(os.environ.get("VISITOR_FLUSH_INTERVAL", "60"))

# Cell layout inside the worksheet — change here, not scattered below.
_COUNT_LABEL_CELL = "A1"
_COUNT_VALUE_CELL = "B1"
_UPDATE_LABEL_CELL = "A2"
_UPDATE_VALUE_CELL = "B2"

_lock = threading.Lock()
_count = 0                 # authoritative in-memory value, served on every request
_last_synced_count = None  # value we last successfully wrote to the sheet
_dirty = False              # True if _count has changed since the last successful write
_boot_error = None
_client_cache = None


# ── Google Sheets client ─────────────────────────────────────────────────

def _client():
    """Lazily build (and cache) the gspread client. Raises if the service
    account JSON / sheet ID env vars aren't set — callers should catch."""
    global _client_cache
    if _client_cache is not None:
        return _client_cache
    creds_raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds_raw:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not set — visitor counter "
                            "cannot reach Google Sheets.")
    if not _SHEET_ID:
        raise RuntimeError("VISITOR_SHEET_ID is not set — visitor counter has no "
                            "sheet to read/write.")
    creds = Credentials.from_service_account_info(json.loads(creds_raw), scopes=_SCOPES)
    _client_cache = gspread.authorize(creds)
    return _client_cache


def _worksheet():
    """Get (or create, with headers) the dedicated counter worksheet.
    Never touches any other tab in the spreadsheet."""
    gc = _client()
    sh = gc.open_by_key(_SHEET_ID)
    try:
        return sh.worksheet(_WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(_WORKSHEET_NAME, rows=4, cols=2)
        # NOTE: use update_acell(label, value), not update(label, value).
        # gspread 6.x flipped update()'s argument order to
        # update(values, range_name) — a plain update("B1", "5") call now
        # sends "B1" as the values matrix and "5" as the range name, which
        # is an invalid A1 range and raises, silently caught by the
        # try/except wrappers around every caller. update_acell() takes a
        # single (label, value) pair directly and its signature hasn't
        # changed, so it isn't affected by that break.
        ws.update_acell(_COUNT_LABEL_CELL, "visitor_count")
        ws.update_acell(_COUNT_VALUE_CELL, "0")
        ws.update_acell(_UPDATE_LABEL_CELL, "last_update")
        ws.update_acell(_UPDATE_VALUE_CELL, "")
        return ws


def _read_remote_count() -> int:
    ws = _worksheet()
    val = ws.acell(_COUNT_VALUE_CELL).value
    try:
        return int(str(val).strip())
    except (TypeError, ValueError):
        return 0


def _write_remote_count(count: int) -> None:
    ws = _worksheet()
    ws.update_acell(_COUNT_VALUE_CELL, str(count))


def _write_remote_update_stamp(stamp: str) -> None:
    ws = _worksheet()
    ws.update_acell(_UPDATE_VALUE_CELL, stamp)


# ── Public API ────────────────────────────────────────────────────────────

def bootstrap() -> None:
    """Call once at app startup. Pulls the last-saved count from the
    sheet into memory so a redeploy picks up exactly where the previous
    run left off. Never raises — if the sheet is unreachable, starts
    from 0 and records the error for admin/status display, so a broken
    sheet connection degrades the counter, not the whole app."""
    global _count, _last_synced_count, _boot_error
    with _lock:
        try:
            _count = _read_remote_count()
            _last_synced_count = _count
            _boot_error = None
            print(f"[VISITOR COUNTER] Loaded starting count from Google Sheet: {_count}")
        except Exception as exc:
            traceback.print_exc()
            _boot_error = str(exc)
            _count = 0
            _last_synced_count = None
            print(f"[VISITOR COUNTER] Could not load count from Google Sheet, "
                  f"starting at 0: {exc}")


def increment() -> int:
    """Bump the in-memory counter for one visit. Fast — no network call.
    The background flusher (or flush_now()) is what actually persists
    this to the sheet."""
    global _count, _dirty
    with _lock:
        _count += 1
        _dirty = True
        return _count


def get_count() -> int:
    with _lock:
        return _count


def flush_now() -> bool:
    """Force an immediate write of the current count to the sheet.
    Returns True on success. Safe to call from a shutdown handler or
    an admin 'sync now' button, in addition to the periodic timer."""
    global _last_synced_count, _dirty
    with _lock:
        if not _dirty:
            return True  # nothing changed since the last successful write
        current = _count
    try:
        _write_remote_count(current)
        with _lock:
            _last_synced_count = current
            # only clear _dirty if nothing incremented while we were writing
            _dirty = (_count != current)
        return True
    except Exception as exc:
        traceback.print_exc()
        print(f"[VISITOR COUNTER] Flush to Google Sheet failed (will retry on next "
              f"interval, counter keeps counting locally in the meantime): {exc}")
        return False


def record_deploy(note: str = "") -> bool:
    """Stamp 'last update' in the sheet — call this once at startup,
    NOT on every visit. Separate from the counter flush so a deploy
    stamp doesn't depend on a visitor having triggered a flush yet."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if note:
        stamp = f"{stamp} — {note}"
    try:
        _write_remote_update_stamp(stamp)
        print(f"[VISITOR COUNTER] Recorded deploy stamp in Google Sheet: {stamp}")
        return True
    except Exception as exc:
        traceback.print_exc()
        print(f"[VISITOR COUNTER] Could not record deploy stamp: {exc}")
        return False


def start_background_flush(interval_seconds: float = None) -> None:
    """Call once at startup. Periodically pushes the in-memory count to
    the sheet so a crash between deploys loses at most one interval's
    worth of visits, without hitting the Sheets API on every request."""
    interval = interval_seconds or FLUSH_INTERVAL_SECONDS

    def _tick():
        flush_now()
        t = threading.Timer(interval, _tick)
        t.daemon = True
        t.start()

    t = threading.Timer(interval, _tick)
    t.daemon = True
    t.start()


def status() -> dict:
    """JSON-friendly status for an admin panel."""
    with _lock:
        return {
            "count": _count,
            "last_synced_count": _last_synced_count,
            "dirty": _dirty,
            "boot_error": _boot_error,
            "sheet_id_configured": bool(_SHEET_ID),
        }


# ── Smoke test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    bootstrap()
    print("status after bootstrap:", status())
    for _ in range(3):
        print("count now:", increment())
    print("flush ok:", flush_now())
    print("status after flush:", status())
    record_deploy("manual smoke test")
