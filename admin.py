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
import time
from functools import wraps

from flask import Blueprint, render_template_string, request, redirect, url_for, flash, session, jsonify

import server_state as ss
import data_engine as de

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

# Simple admin auth — in production, use proper authentication
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

# ── Image upload helpers ─────────────────────────────────────────────────────
ALLOWED_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
MAX_IMAGE_MB = int(os.environ.get("MAX_IMAGE_MB", "10"))


def _save_image(file_storage, base_name):
    """Validate and save an uploaded image into ASSETS_DIR.

    Returns (True, saved_filename) on success, or (False, error_message).
    """
    filename = file_storage.filename or ""
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXT:
        return False, (f"Unsupported file type '{ext or '?'}'. "
                        f"Use PNG, JPG, GIF, WEBP, or SVG.")

    # Guard against oversized uploads (Werkzeug FileStorage supports seek/tell).
    file_storage.stream.seek(0, os.SEEK_END)
    size_mb = file_storage.stream.tell() / (1024 * 1024)
    file_storage.stream.seek(0)
    if size_mb > MAX_IMAGE_MB:
        return False, f"Image is {size_mb:.1f} MB, over the {MAX_IMAGE_MB} MB limit."

    saved_name = f"{base_name}{ext}"
    path = os.path.join(ss.ASSETS_DIR, saved_name)
    file_storage.save(path)
    return True, saved_name


def _bg_category_rows(names, get_path_fn):
    """Build (name, configured) rows for a category-background management table."""
    return [(name, bool(get_path_fn(name))) for name in names]


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
select { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
.img-upload-row { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.img-preview { width: 64px; height: 64px; object-fit: contain; background: #eef1f4;
  border: 1px solid #ddd; border-radius: 4px; padding: 4px; }
.img-preview-wide { width: 160px; height: 60px; object-fit: cover; background: #eef1f4;
  border: 1px solid #ddd; border-radius: 4px; }
.img-upload-form { flex: 1 1 220px; }
.btn-mini { padding: 6px 12px; font-size: 13px; background: #78909c; }
.btn-mini:hover { background: #546e7a; }
.btn-remove { padding: 5px 10px; font-size: 12px; background: #c62828; }
.btn-remove:hover { background: #8e0000; }
.subsection-title { font-weight: 600; color: #1565c0; margin: 16px 0 4px; }
.cat-bg-table td, .cat-bg-table th { padding: 6px 10px; font-size: 13px; }
.cat-bg-form { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-top: 6px; }
.cat-bg-form select { width: auto; flex: 1 1 200px; margin: 0; }
.cat-bg-form input[type="file"] { width: auto; flex: 1 1 220px; margin: 0; }
.badge-yes { color: #2e7d32; font-weight: 600; }
.badge-no { color: #999; }
</style>
</head>
<body>
<div class="container">
<h1>⚙️ Admin Panel <a href="{{ url_for('admin.logout') }}" class="logout">Logout</a></h1>

{% with messages = get_flashed_messages(with_categories=true) %}
{% if messages %}
{% for category, message in messages %}
<div class="status-box {% if category == 'error' %}error{% elif category == 'warning' or category == 'info' %}warning{% endif %}">{{ message }}</div>
{% endfor %}
{% endif %}
{% endwith %}

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
<h3>🖼️ Branding Images</h3>

<div class="img-upload-row">
<img class="img-preview" src="/assets-flag?v={{ cache_bust }}" alt="Nepal flag preview">
<div class="img-upload-form">
<label>🏳️ Flag of Nepal (shown as the header logo image)</label>
<form method="post" action="{{ url_for('admin.upload_flag') }}" enctype="multipart/form-data" style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
<input type="file" name="flag" accept=".png,.jpg,.jpeg,.gif,.webp,.svg" style="flex:1 1 200px; margin:0;">
<button type="submit">Upload Flag</button>
</form>
{% if has_custom_flag %}
<form method="post" action="{{ url_for('admin.reset_flag') }}" style="margin-top:6px;">
<button type="submit" class="btn-mini">Reset to default</button>
</form>
{% endif %}
</div>
</div>

<hr style="margin:18px 0; border-color:#eee;">

<div class="img-upload-row">
{% if has_logo %}<img class="img-preview" src="/assets-logo?v={{ cache_bust }}" alt="Logo preview">{% endif %}
<div class="img-upload-form">
<label>🏢 Organisation Logo (shown next to the flag in the header)</label>
<form method="post" action="{{ url_for('admin.upload_logo') }}" enctype="multipart/form-data" style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
<input type="file" name="logo" accept=".png,.jpg,.jpeg,.gif,.webp,.svg" style="flex:1 1 200px; margin:0;">
<button type="submit">Upload Logo</button>
</form>
{% if has_logo %}
<form method="post" action="{{ url_for('admin.reset_logo') }}" style="margin-top:6px;">
<button type="submit" class="btn-mini">Remove</button>
</form>
{% endif %}
</div>
</div>

<hr style="margin:18px 0; border-color:#eee;">

<div class="img-upload-row">
{% if has_hero %}<img class="img-preview-wide" src="/assets-background?v={{ cache_bust }}" alt="Hero background preview">{% endif %}
<div class="img-upload-form">
<label>🌄 Hero Image (site header background banner)</label>
<form method="post" action="{{ url_for('admin.upload_hero') }}" enctype="multipart/form-data" style="display:flex; gap:8px; flex-wrap:wrap; align-items:center;">
<input type="file" name="hero" accept=".png,.jpg,.jpeg,.gif,.webp,.svg" style="flex:1 1 200px; margin:0;">
<button type="submit">Upload Hero Image</button>
</form>
{% if has_hero %}
<form method="post" action="{{ url_for('admin.reset_hero') }}" style="margin-top:6px;">
<button type="submit" class="btn-mini">Remove</button>
</form>
{% endif %}
</div>
</div>
</div>

<div class="card">
<h3>🎨 Category Background Images</h3>
<p style="color:#666; font-size:13px; margin-top:-6px;">
Watermark backgrounds shown behind the Overview flip-cards and charts for each
power type, license stage, and province.
</p>

<div class="subsection-title">⚡ Power Types</div>
<form method="post" action="{{ url_for('admin.upload_type_bg') }}" enctype="multipart/form-data" class="cat-bg-form">
<select name="type_name" required>
{% for t in type_options %}<option value="{{ t }}">{{ t }}</option>{% endfor %}
</select>
<input type="file" name="type_bg_file" accept=".png,.jpg,.jpeg,.gif,.webp,.svg" required>
<button type="submit">Upload</button>
</form>
<table class="cat-bg-table">
<tr><th>Power Type</th><th>Background Set?</th><th></th></tr>
{% for name, configured in type_rows %}
<tr>
<td>{{ name }}</td>
<td>{% if configured %}<span class="badge-yes">✔ Yes</span>{% else %}<span class="badge-no">— No</span>{% endif %}</td>
<td>{% if configured %}
<form method="post" action="{{ url_for('admin.remove_category_bg') }}">
<input type="hidden" name="kind" value="type"><input type="hidden" name="name" value="{{ name }}">
<button type="submit" class="btn-remove">Remove</button>
</form>
{% endif %}</td>
</tr>
{% endfor %}
</table>

<div class="subsection-title">📶 License Stages</div>
<form method="post" action="{{ url_for('admin.upload_status_bg') }}" enctype="multipart/form-data" class="cat-bg-form">
<select name="status_name" required>
{% for s in status_options %}<option value="{{ s }}">{{ s }}</option>{% endfor %}
</select>
<input type="file" name="status_bg_file" accept=".png,.jpg,.jpeg,.gif,.webp,.svg" required>
<button type="submit">Upload</button>
</form>
<table class="cat-bg-table">
<tr><th>License Stage</th><th>Background Set?</th><th></th></tr>
{% for name, configured in status_rows %}
<tr>
<td>{{ name }}</td>
<td>{% if configured %}<span class="badge-yes">✔ Yes</span>{% else %}<span class="badge-no">— No</span>{% endif %}</td>
<td>{% if configured %}
<form method="post" action="{{ url_for('admin.remove_category_bg') }}">
<input type="hidden" name="kind" value="status"><input type="hidden" name="name" value="{{ name }}">
<button type="submit" class="btn-remove">Remove</button>
</form>
{% endif %}</td>
</tr>
{% endfor %}
</table>

<div class="subsection-title">🗺️ Provinces</div>
<form method="post" action="{{ url_for('admin.upload_province_bg') }}" enctype="multipart/form-data" class="cat-bg-form">
<select name="province_name" required>
{% for p in province_options %}<option value="{{ p }}">{{ p }}</option>{% endfor %}
</select>
<input type="file" name="province_bg_file" accept=".png,.jpg,.jpeg,.gif,.webp,.svg" required>
<button type="submit">Upload</button>
</form>
<table class="cat-bg-table">
<tr><th>Province</th><th>Background Set?</th><th></th></tr>
{% for name, configured in province_rows %}
<tr>
<td>{{ name }}</td>
<td>{% if configured %}<span class="badge-yes">✔ Yes</span>{% else %}<span class="badge-no">— No</span>{% endif %}</td>
<td>{% if configured %}
<form method="post" action="{{ url_for('admin.remove_category_bg') }}">
<input type="hidden" name="kind" value="province"><input type="hidden" name="name" value="{{ name }}">
<button type="submit" class="btn-remove">Remove</button>
</form>
{% endif %}</td>
</tr>
{% endfor %}
</table>
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
    status_names = de.STATUS_ORDER + de.EXTRA_STATUS_ORDER
    return render_template_string(
        ADMIN_TEMPLATE,
        state=ss.STATE,
        default_sheet_url=default_sheet,
        default_gis_url=default_gis,
        default_pa_url=default_pa,
        marquee_enabled=ss.get_marquee_enabled(),
        cache_bust=int(time.time()),
        has_logo=bool(ss.get_logo_path()),
        has_custom_flag=bool(ss.STATE.get("flag_filename")),
        has_hero=bool(ss.get_background_path()),
        type_rows=_bg_category_rows(de.TYPE_ORDER, ss.get_type_bg_path),
        status_rows=_bg_category_rows(status_names, ss.get_status_bg_path),
        province_rows=_bg_category_rows(de.PROVINCE_ORDER, ss.get_province_bg_path),
        type_options=de.TYPE_ORDER,
        status_options=status_names,
        province_options=de.PROVINCE_ORDER,
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


# ── Logo / flag / hero image uploads ────────────────────────────────────────

@admin_bp.route("/upload-logo", methods=["POST"])
@admin_required
def upload_logo():
    file = request.files.get("logo")
    if not file or file.filename == "":
        flash("No logo file selected", "error")
        return redirect(url_for("admin.index"))
    ok, result = _save_image(file, "logo")
    if ok:
        ss.set_logo(result)
        flash("Organisation logo updated!", "success")
    else:
        flash(result, "error")
    return redirect(url_for("admin.index"))


@admin_bp.route("/reset-logo", methods=["POST"])
@admin_required
def reset_logo():
    ss.set_logo(None)
    flash("Organisation logo removed", "success")
    return redirect(url_for("admin.index"))


@admin_bp.route("/upload-flag", methods=["POST"])
@admin_required
def upload_flag():
    file = request.files.get("flag")
    if not file or file.filename == "":
        flash("No flag image selected", "error")
        return redirect(url_for("admin.index"))
    ok, result = _save_image(file, "flag")
    if ok:
        ss.set_flag_image(result)
        flash("Flag of Nepal (header logo image) updated!", "success")
    else:
        flash(result, "error")
    return redirect(url_for("admin.index"))


@admin_bp.route("/reset-flag", methods=["POST"])
@admin_required
def reset_flag():
    ss.set_flag_image(None)
    flash("Flag image reset to the bundled default Nepal flag", "success")
    return redirect(url_for("admin.index"))


@admin_bp.route("/upload-hero", methods=["POST"])
@admin_required
def upload_hero():
    file = request.files.get("hero")
    if not file or file.filename == "":
        flash("No hero image selected", "error")
        return redirect(url_for("admin.index"))
    ok, result = _save_image(file, "hero_background")
    if ok:
        ss.set_background(result)
        flash("Hero / header background image updated!", "success")
    else:
        flash(result, "error")
    return redirect(url_for("admin.index"))


@admin_bp.route("/reset-hero", methods=["POST"])
@admin_required
def reset_hero():
    ss.set_background(None)
    flash("Hero background removed — header reverts to the default gradient", "success")
    return redirect(url_for("admin.index"))


# ── Per-category (power type / license stage / province) backgrounds ───────

@admin_bp.route("/upload-type-bg", methods=["POST"])
@admin_required
def upload_type_bg():
    type_name = request.form.get("type_name", "").strip()
    file = request.files.get("type_bg_file")
    if not type_name:
        flash("Please select a power type", "error")
        return redirect(url_for("admin.index"))
    if not file or file.filename == "":
        flash("No image selected", "error")
        return redirect(url_for("admin.index"))
    slug = ss.slugify_type(type_name)
    ok, result = _save_image(file, f"typebg_{slug}")
    if ok:
        ss.set_type_bg(type_name, result)
        flash(f"Background image set for power type '{type_name}'", "success")
    else:
        flash(result, "error")
    return redirect(url_for("admin.index"))


@admin_bp.route("/upload-status-bg", methods=["POST"])
@admin_required
def upload_status_bg():
    status_name = request.form.get("status_name", "").strip()
    file = request.files.get("status_bg_file")
    if not status_name:
        flash("Please select a license stage", "error")
        return redirect(url_for("admin.index"))
    if not file or file.filename == "":
        flash("No image selected", "error")
        return redirect(url_for("admin.index"))
    slug = ss.slugify_type(status_name)
    ok, result = _save_image(file, f"statusbg_{slug}")
    if ok:
        ss.set_status_bg(status_name, result)
        flash(f"Background image set for license stage '{status_name}'", "success")
    else:
        flash(result, "error")
    return redirect(url_for("admin.index"))


@admin_bp.route("/upload-province-bg", methods=["POST"])
@admin_required
def upload_province_bg():
    province_name = request.form.get("province_name", "").strip()
    file = request.files.get("province_bg_file")
    if not province_name:
        flash("Please select a province", "error")
        return redirect(url_for("admin.index"))
    if not file or file.filename == "":
        flash("No image selected", "error")
        return redirect(url_for("admin.index"))
    slug = ss.slugify_type(province_name)
    ok, result = _save_image(file, f"provincebg_{slug}")
    if ok:
        ss.set_province_bg(province_name, result)
        flash(f"Background image set for province '{province_name}'", "success")
    else:
        flash(result, "error")
    return redirect(url_for("admin.index"))


@admin_bp.route("/remove-category-bg", methods=["POST"])
@admin_required
def remove_category_bg():
    kind = request.form.get("kind", "")
    name = request.form.get("name", "").strip()
    setters = {"type": ss.set_type_bg, "status": ss.set_status_bg, "province": ss.set_province_bg}
    setter = setters.get(kind)
    if not setter or not name:
        flash("Nothing to remove", "error")
        return redirect(url_for("admin.index"))
    setter(name, None)
    flash(f"Background removed for {name}", "success")
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
