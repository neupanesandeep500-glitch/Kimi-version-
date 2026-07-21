"""
admin.py

Simplified admin panel for data source management.
Provides routes for:
- /admin/login — admin authentication
- /admin — dashboard for uploading workbooks, syncing Google Sheets
- /admin/sync-gis — trigger GIS reload
- /admin/sync-pa — trigger protected area reload
"""

import os
import io
import json
from functools import wraps

from flask import Blueprint, render_template_string, request, redirect, url_for, flash, session, jsonify

import server_state as ss

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Simple admin auth — in production, use proper authentication
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return decorated


LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Admin Login</title>
<style>
body { font-family: Arial, sans-serif; background: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
.login-box { background: white; padding: 40px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); width: 320px; }
h2 { margin-top: 0; color: #1565c0; }
input[type="password"] { width: 100%; padding: 12px; margin: 10px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
button { width: 100%; padding: 12px; background: #1565c0; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; }
button:hover { background: #0d47a1; }
.error { color: #c62828; margin-top: 10px; }
</style>
</head>
<body>
<div class="login-box">
<h2>🔐 Admin Login</h2>
<form method="post">
<input type="password" name="password" placeholder="Enter admin password" required autofocus>
<button type="submit">Login</button>
</form>
{% if error %}<div class="error">{{ error }}</div>{% endif %}
</div>
</body>
</html>
"""

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head><title>Admin Panel — Nepal Power Dashboard</title>
<style>
body { font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }
.container { max-width: 900px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
h1 { color: #1565c0; margin-top: 0; }
.card { background: #f8f9fa; border-left: 4px solid #1565c0; padding: 20px; margin: 20px 0; border-radius: 4px; }
.card h3 { margin-top: 0; color: #333; }
input[type="text"], input[type="file"] { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
button { padding: 10px 20px; background: #1565c0; color: white; border: none; border-radius: 4px; cursor: pointer; margin-right: 10px; }
button:hover { background: #0d47a1; }
.status-box { background: #e8f5e9; padding: 15px; border-radius: 4px; margin: 15px 0; }
.status-box.error { background: #ffebee; }
.status-box.warning { background: #fff3e0; }
table { width: 100%; border-collapse: collapse; margin: 15px 0; }
th, td { text-align: left; padding: 10px; border-bottom: 1px solid #ddd; }
th { background: #1565c0; color: white; }
.logout { float: right; color: #c62828; text-decoration: none; }
.logout:hover { text-decoration: underline; }
</style>
</head>
<body>
<div class="container">
<h1>⚙️ Admin Panel <a href="{{ url_for('admin.logout') }}" class="logout">Logout</a></h1>

<div class="status-box {% if state.error %}error{% elif not state.loader %}warning{% endif %}">
<strong>Data Status:</strong> {{ state.source_label }}<br>
{% if state.last_sync %}<strong>Last Sync:</strong> {{ state.last_sync }}<br>{% endif %}
{% if state.error %}<strong>Error:</strong> {{ state.error }}{% endif %}<br>
<strong>Records:</strong> {{ state.loader.records|length if state.loader else 0 }}<br>
<strong>GIS Loaded:</strong> {{ "Yes" if state.gis_loaded else "No" }}<br>
<strong>Protected Areas:</strong> {{ "Yes" if state.pa_loaded else "No" }}
</div>

<div class="card">
<h3>📊 Google Sheet Sync</h3>
<form method="post" action="{{ url_for('admin.sync_sheet') }}">
<input type="text" name="sheet_url" placeholder="Google Sheet URL or ID" value="{{ default_sheet_url }}">
<button type="submit">Sync from Google Sheet</button>
</form>
</div>

<div class="card">
<h3>📁 Upload Workbook</h3>
<form method="post" action="{{ url_for('admin.upload_workbook') }}" enctype="multipart/form-data">
<input type="file" name="workbook" accept=".xlsx,.xls,.csv">
<button type="submit">Upload & Load</button>
</form>
</div>

<div class="card">
<h3>🗺️ GIS Data Sources</h3>
<form method="post" action="{{ url_for('admin.sync_gis_drive') }}">
<input type="text" name="gis_url" placeholder="Google Drive URL for GIS zip" value="{{ default_gis_url }}">
<button type="submit">Sync GIS from Drive</button>
</form>
<form method="post" action="{{ url_for('admin.sync_pa_drive') }}" style="margin-top:10px;">
<input type="text" name="pa_url" placeholder="Google Drive URL for Protected Areas zip" value="{{ default_pa_url }}">
<button type="submit">Sync Protected Areas from Drive</button>
</form>
<p style="color:#666; font-size:13px; margin-top:10px;">
ℹ️ Built-in Nepal district and protected area boundaries are always available.
Drive syncs provide higher-resolution data if needed.
</p>
</div>

<div class="card">
<h3>⚙️ Settings</h3>
<form method="post" action="{{ url_for('admin.toggle_marquee') }}">
<button type="submit">{{ "Disable" if marquee_enabled else "Enable" }} Ticker Marquee</button>
</form>
</div>

<div class="card">
<h3>📈 Statistics</h3>
<table>
<tr><th>Metric</th><th>Value</th></tr>
<tr><td>Total Records</td><td>{{ state.loader.records|length if state.loader else 0 }}</td></tr>
<tr><td>Project Types</td><td>{{ state.loader.get_types()|join(", ") if state.loader else "—" }}</td></tr>
<tr><td>License Stages</td><td>{{ state.loader.get_statuses()|join(", ") if state.loader else "—" }}</td></tr>
<tr><td>Visitor Count</td><td>{{ state.get("visitor_count", 0) }}</td></tr>
</table>
</div>

<p><a href="/">← Back to Dashboard</a></p>
</div>
</body>
</html>
"""


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin.index"))
        error = "Invalid password"
    return render_template_string(LOGIN_TEMPLATE, error=error)


@admin_bp.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@admin_required
def index():
    default_sheet = os.environ.get("DEFAULT_SHEET_URL", "")
    default_gis = os.environ.get("DEFAULT_GIS_DRIVE_URL", "")
    default_pa = os.environ.get("DEFAULT_PA_DRIVE_URL", "")
    return render_template_string(
        ADMIN_TEMPLATE,
        state=ss.STATE,
        default_sheet_url=default_sheet,
        default_gis_url=default_gis,
        default_pa_url=default_pa,
        marquee_enabled=ss.get_marquee_enabled(),
    )


@admin_bp.route("/sync-sheet", methods=["POST"])
@admin_required
def sync_sheet():
    url = request.form.get("sheet_url", "").strip()
    if not url:
        flash("Please provide a Google Sheet URL or ID", "error")
        return redirect(url_for("admin.index"))
    try:
        ss.load_from_google_sheet(url)
        flash("Sheet synced successfully!", "success")
    except Exception as e:
        flash(f"Sync failed: {str(e)}", "error")
    return redirect(url_for("admin.index"))


@admin_bp.route("/upload-workbook", methods=["POST"])
@admin_required
def upload_workbook():
    if "workbook" not in request.files:
        flash("No file selected", "error")
        return redirect(url_for("admin.index"))
    file = request.files["workbook"]
    if file.filename == "":
        flash("No file selected", "error")
        return redirect(url_for("admin.index"))

    filename = file.filename
    saved_path = os.path.join(ss.DATA_DIR, filename)
    file.save(saved_path)

    try:
        ss.load_from_uploaded_workbook(saved_path, filename)
        flash(f"Workbook '{filename}' loaded successfully!", "success")
    except Exception as e:
        flash(f"Failed to load workbook: {str(e)}", "error")

    return redirect(url_for("admin.index"))


@admin_bp.route("/sync-gis-drive", methods=["POST"])
@admin_required
def sync_gis_drive():
    url = request.form.get("gis_url", "").strip()
    if not url:
        flash("Please provide a Google Drive URL", "error")
        return redirect(url_for("admin.index"))
    try:
        ss.start_gis_drive_sync_async(url)
        flash("GIS sync started in background. Refresh to check status.", "info")
    except Exception as e:
        flash(f"GIS sync failed: {str(e)}", "error")
    return redirect(url_for("admin.index"))


@admin_bp.route("/sync-pa-drive", methods=["POST"])
@admin_required
def sync_pa_drive():
    url = request.form.get("pa_url", "").strip()
    if not url:
        flash("Please provide a Google Drive URL", "error")
        return redirect(url_for("admin.index"))
    try:
        ss.start_pa_drive_sync_async(url)
        flash("Protected areas sync started in background. Refresh to check status.", "info")
    except Exception as e:
        flash(f"PA sync failed: {str(e)}", "error")
    return redirect(url_for("admin.index"))


@admin_bp.route("/toggle-marquee", methods=["POST"])
@admin_required
def toggle_marquee():
    ss.set_marquee_enabled(not ss.get_marquee_enabled())
    flash("Marquee setting updated", "success")
    return redirect(url_for("admin.index"))


@admin_bp.route("/api/status")
def api_status():
    """Public API endpoint for checking sync status."""
    return jsonify({
        "records": len(ss.STATE["loader"].records) if ss.STATE.get("loader") else 0,
        "gis_loaded": ss.STATE.get("gis_loaded", False),
        "pa_loaded": ss.STATE.get("pa_loaded", False),
        "last_sync": ss.STATE.get("last_sync"),
        "error": ss.STATE.get("error"),
    })
