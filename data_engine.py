"""
data_engine.py

Core data loading, GIS engine, and coordinate transformation for the
Nepal Power Plant & Transmission Line License Status Dashboard.

This module is self-contained — it bundles simplified Nepal district and
protected area boundaries so the GIS map works immediately without any
external shapefile uploads or Google Drive syncs.
"""

import re
import os
import io
import json
import math
import traceback
from collections import defaultdict
from datetime import datetime

# Try to import pandas/openpyxl for workbook parsing
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import openpyxl
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False

# ── Constants ────────────────────────────────────────────────────────────────

STATUS_ORDER = [
    "Application for Survey License",
    "Survey License",
    "Application for Construction License",
    "Construction License",
    "Operating",
]

EXTRA_STATUS_ORDER = ["GoN Study Project", "Cancelled", "Technical Clearance"]

TYPE_ORDER = [
    "Hydro (>1MW)", "Hydro (<=1MW)", "Solar", "Wind",
    "Co-generation", "Thermal", "Biomass", "Transmission Line", "Other"
]

PROVINCE_ORDER = [
    "Koshi", "Madhesh", "Bagmati", "Gandaki",
    "Lumbini", "Karnali", "Sudurpaschim"
]

STATUS_COLORS = {
    "Application for Survey License": "#90a4ae",
    "Survey License": "#42a5f5",
    "Application for Construction License": "#ffb300",
    "Construction License": "#fb8c00",
    "Operating": "#2e7d32",
    "GoN Study Project": "#0277bd",
    "Cancelled": "#c62828",
    "Technical Clearance": "#9fb3c8",
}

EXTRA_STATUS_COLORS = {
    "GoN Study Project": "#0277bd",
    "Cancelled": "#c62828",
    "Technical Clearance": "#9fb3c8",
}

# ── B.S. Calendar Helpers ───────────────────────────────────────────────────

# Approximate: B.S. year = Gregorian year + 56 (rough, good enough for filtering)
# For precise conversion you'd need a full B.S. calendar library
def today_bs():
    """Return approximate current B.S. year, month, day."""
    now = datetime.utcnow()
    # Rough approximation: add 56 years, 8 months, 17 days
    year = now.year + 56
    month = now.month + 8
    day = now.day + 17
    if month > 12:
        month -= 12
        year += 1
    # Very rough — for production, use a proper B.S. library like bsdate
    return year, month, day


def parse_bs_input(s, end=False):
    """Parse a B.S. date string like '2078', '2078-01', or '2078-01-15'.
    Returns int year, or tuple (year, month, day) if more precision given."""
    if not s or not str(s).strip():
        return None
    s = str(s).strip()
    parts = s.split("-")
    try:
        year = int(parts[0])
        if len(parts) == 1:
            return year
        month = int(parts[1]) if parts[1] else (12 if end else 1)
        day = int(parts[2]) if len(parts) > 2 and parts[2] else (32 if end else 1)
        return (year, month, day)
    except (ValueError, IndexError):
        return None


def bs_str(bs_tuple):
    """Format a B.S. tuple as string."""
    if not bs_tuple:
        return "—"
    if isinstance(bs_tuple, int):
        return str(bs_tuple)
    return "-".join(str(x) for x in bs_tuple if x)


def fmt_mw(mw):
    """Format MW value, handling None."""
    if mw is None:
        return "—"
    return f"{mw:.1f}"


# ── GISEngine ─────────────────────────────────────────────────────────────────

class GISEngine:
    """Lightweight GIS engine for Nepal district/province boundaries and
    protected areas. Supports loading from inline GeoJSON (bundled), external
    shapefile zip, or a raw shapefile path."""

    def __init__(self):
        self.districts = {}           # name -> {province, polygons}
        self.province_districts = defaultdict(list)
        self.protected_areas = []     # [{name, category, polygons}]
        self.locals = []              # [{label, district, province}]
        self.district_province = {}   # district -> province
        self.loaded = False
        self.pa_loaded = False
        self.error = None

    # ── Loading methods ────────────────────────────────────────────────────

    def load_from_geojson(self, geojson_dict):
        """Load district/province boundaries from an inline GeoJSON dict."""
        try:
            self.districts = {}
            self.province_districts = defaultdict(list)
            self.district_province = {}
            self.locals = []

            for feat in geojson_dict.get("features", []):
                props = feat.get("properties", {})
                name = (props.get("name") or props.get("DIST_EN") or
                        props.get("DISTRICT") or f"District_{len(self.districts)}")
                province = (props.get("province") or props.get("Prov_EN") or
                           props.get("PROVINCE") or "Unspecified")
                geom = feat.get("geometry", {})

                polygons = self._geojson_to_polygons(geom)
                if not polygons:
                    continue

                self.districts[name] = {"province": province, "polygons": polygons}
                self.province_districts[province].append(name)
                self.district_province[name] = province

                # Generate synthetic local bodies (placeholder)
                self.locals.append({
                    "label": f"{name} Rural Municipality",
                    "district": name,
                    "province": province
                })
                self.locals.append({
                    "label": f"{name} Municipality",
                    "district": name,
                    "province": province
                })

            self.loaded = bool(self.districts)
            self.error = None
            return self.loaded
        except Exception as e:
            self.error = str(e)
            self.loaded = False
            return False

    def load_protected_from_geojson(self, geojson_dict):
        """Load protected areas from inline GeoJSON."""
        try:
            self.protected_areas = []
            for feat in geojson_dict.get("features", []):
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                polygons = self._geojson_to_polygons(geom)
                if polygons:
                    self.protected_areas.append({
                        "name": props.get("name", "Unknown"),
                        "category": props.get("category", "Protected Area"),
                        "polygons": polygons
                    })
            self.pa_loaded = bool(self.protected_areas)
            return self.pa_loaded
        except Exception as e:
            self.error = str(e)
            return False

    def load_from_path(self, path):
        """Load from a shapefile zip or directory path. Stub — implement
        with pyshp if needed. Falls back to bundled data if path invalid."""
        try:
            # Try pyshp if available
            try:
                import shapefile
                sf = shapefile.Reader(path)
                # ... parse shapefile records ...
                # (Full implementation would go here)
                self.loaded = True
                return True
            except ImportError:
                pass
            # Fall back to bundled data
            from gis_bundled import NEPAL_DISTRICTS_GEOJSON
            return self.load_from_geojson(NEPAL_DISTRICTS_GEOJSON)
        except Exception as e:
            self.error = str(e)
            return False

    def load(self):
        """Default load — uses bundled inline data."""
        from gis_bundled import NEPAL_DISTRICTS_GEOJSON
        return self.load_from_geojson(NEPAL_DISTRICTS_GEOJSON)

    def load_protected(self):
        """Default protected areas load — uses bundled inline data."""
        from gis_bundled import NEPAL_PROTECTED_AREAS_GEOJSON
        return self.load_protected_from_geojson(NEPAL_PROTECTED_AREAS_GEOJSON)

    def load_protected_from_path(self, path):
        """Load protected areas from external path. Falls back to bundled."""
        try:
            try:
                import shapefile
                sf = shapefile.Reader(path)
                # ... parse ...
                self.pa_loaded = True
                return True
            except ImportError:
                pass
            return self.load_protected()
        except Exception as e:
            self.error = str(e)
            return False

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _geojson_to_polygons(self, geom):
        """Convert GeoJSON geometry to list of polygon ring lists."""
        polygons = []
        gtype = geom.get("type", "")
        coords = geom.get("coordinates", [])

        if gtype == "Polygon":
            rings = []
            for ring in coords:
                rings.append([(pt[0], pt[1]) for pt in ring])
            polygons.append(rings)
        elif gtype == "MultiPolygon":
            for poly in coords:
                rings = []
                for ring in poly:
                    rings.append([(pt[0], pt[1]) for pt in ring])
                polygons.append(rings)

        return polygons

    def display_rings(self, level="district"):
        """Yield (name, province, rings) tuples for map rendering."""
        if level == "district":
            for name, info in self.districts.items():
                for poly in info.get("polygons", []):
                    yield (name, info.get("province", "Unspecified"), poly)
        elif level == "province":
            # Merge districts per province (simplified)
            for prov, dists in self.province_districts.items():
                for d in dists:
                    info = self.districts.get(d, {})
                    for poly in info.get("polygons", []):
                        yield (prov, prov, poly)

    def pa_display_rings(self):
        """Yield protected area rings for map overlay."""
        for pa in self.protected_areas:
            for poly in pa.get("polygons", []):
                yield (pa["name"], pa["category"], poly)

    def pa_names(self):
        """Return list of protected area names."""
        return [pa["name"] for pa in self.protected_areas]

    def locals_for_districts(self, district_names):
        """Return local body labels for given districts."""
        result = set()
        for loc in self.locals:
            if loc.get("district") in district_names:
                result.add(loc.get("label", ""))
        return sorted(result)

    def point_in_district(self, lon, lat):
        """Simple bounding-box check for district containment.
        For production, use proper point-in-polygon (ray casting)."""
        for name, info in self.districts.items():
            for poly in info.get("polygons", []):
                for ring in poly:
                    lons = [p[0] for p in ring]
                    lats = [p[1] for p in ring]
                    if min(lons) <= lon <= max(lons) and min(lats) <= lat <= max(lats):
                        return name, info.get("province", "Unspecified")
        return None, "Unspecified"


# Singleton instance
GIS = GISEngine()


# ── DataLoader ──────────────────────────────────────────────────────────────

class DataLoader:
    """Loads and filters power plant/transmission line license records
    from an Excel workbook."""

    def __init__(self, path=None):
        self.path = path
        self.records = []
        self.error = None
        self._types = set()
        self._statuses = set()
        self._provinces = set()
        self._year_bounds = (None, None)

    def load(self):
        """Parse the workbook at self.path."""
        if not self.path or not os.path.exists(self.path):
            self.error = f"Workbook not found: {self.path}"
            return

        if not HAS_PANDAS:
            self.error = "pandas not installed — cannot parse workbook"
            return

        try:
            # Try to read all sheets
            xls = pd.ExcelFile(self.path)
            all_records = []

            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                if df.empty:
                    continue

                # Normalize column names
                df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

                for _, row in df.iterrows():
                    rec = self._parse_row(row, sheet_name)
                    if rec:
                        all_records.append(rec)

            self.records = all_records
            self._build_indexes()
            self.error = None

        except Exception as e:
            self.error = f"Failed to load workbook: {str(e)}"
            traceback.print_exc()

    def _parse_row(self, row, sheet_name):
        """Parse a single DataFrame row into a standardized record dict."""
        # Flexible column name matching
        def get_col(*candidates):
            for c in candidates:
                if c in row.index:
                    v = row[c]
                    if pd.notna(v):
                        return v
            return None

        project = get_col("project_name", "project", "name", "project_name_")
        if not project or str(project).strip() in ("", "nan", "None"):
            return None

        # Determine type
        type_val = str(get_col("type", "project_type", "category", "plant_type") or "").strip()
        ptype = self._classify_type(type_val, sheet_name)

        # Determine status
        status_val = str(get_col("status", "license_status", "stage", "current_status") or "").strip()
        status = self._classify_status(status_val)

        # Capacity
        cap = get_col("capacity_mw", "capacity", "mw", "installed_capacity")
        try:
            capacity_mw = float(cap) if cap is not None else None
        except (ValueError, TypeError):
            capacity_mw = None

        # Voltage and line length (for transmission)
        volt = get_col("voltage_kv", "voltage", "kv")
        try:
            voltage_kv = float(volt) if volt is not None else None
        except (ValueError, TypeError):
            voltage_kv = None

        line_len = get_col("line_length_km", "length_km", "circuit_length", "transmission_length")
        try:
            line_length_km = float(line_len) if line_len is not None else None
        except (ValueError, TypeError):
            line_length_km = None

        # Location
        district = str(get_col("district", "dist", "district_name") or "").strip()
        province = str(get_col("province", "prov", "province_name") or "").strip()
        local_body = str(get_col("local_body", "gaunpalika", "nagarpalika", "municipality") or "").strip()

        # Coordinates
        lat = get_col("latitude", "lat", "y")
        lon = get_col("longitude", "lon", "long", "x")
        try:
            lat = float(lat) if lat is not None else None
            lon = float(lon) if lon is not None else None
        except (ValueError, TypeError):
            lat = lon = None

        # If coordinates exist but no district, try GIS lookup
        if lat and lon and (not district or district == "Unspecified"):
            district, province = GIS.point_in_district(lon, lat)

        # License date
        lic_date = get_col("license_date", "issue_date", "license_issued", "date")
        lic_year = self._extract_year(lic_date)

        # COD date
        cod_date = get_col("cod", "commercial_operation_date", "operation_date", "commissioning_date")
        cod_bs = self._parse_date_to_bs(cod_date)

        # Promoter
        promoter = str(get_col("promoter", "developer", "company", "promoter_name") or "").strip()

        # Bbox for license area (if available)
        bbox = None
        for col in ["bbox", "boundary", "license_area"]:
            if col in row.index and pd.notna(row[col]):
                try:
                    bbox = json.loads(str(row[col]))
                    if isinstance(bbox, list) and len(bbox) == 4:
                        break
                except:
                    pass

        return {
            "project": str(project).strip(),
            "type": ptype,
            "status": status,
            "capacity_mw": capacity_mw,
            "voltage_kv": voltage_kv,
            "line_length_km": line_length_km,
            "district": district or "Unspecified",
            "province": province or "Unspecified",
            "local_body": local_body or "",
            "lat": lat,
            "lon": lon,
            "promoter": promoter or "—",
            "license_year": lic_year,
            "cod_bs": cod_bs,
            "bbox": bbox,
            "sheet": sheet_name,
        }

    def _classify_type(self, val, sheet_hint=""):
        """Classify raw type string into standardized type."""
        v = val.lower()
        sh = sheet_hint.lower()

        if "transmission" in v or "transmission" in sh:
            return "Transmission Line"
        if "hydro" in v:
            if "<=1" in v or "micro" in v or "mini" in v or "pico" in v:
                return "Hydro (<=1MW)"
            return "Hydro (>1MW)"
        if "solar" in v or "pv" in v:
            return "Solar"
        if "wind" in v:
            return "Wind"
        if "thermal" in v or "coal" in v or "gas" in v or "diesel" in v:
            return "Thermal"
        if "biomass" in v:
            return "Biomass"
        if "co-gen" in v or "cogeneration" in v:
            return "Co-generation"
        if "gon" in v or "study" in v:
            return "GoN Study"
        return "Other"

    def _classify_status(self, val):
        """Classify raw status string into standardized status."""
        v = val.lower()
        if "cancel" in v or "terminated" in v or "revoke" in v:
            return "Cancelled"
        if "gon" in v and "study" in v:
            return "GoN Study Project"
        if "technical" in v and "clearance" in v:
            return "Technical Clearance"
        if "operat" in v or "commission" in v or "cod" in v:
            return "Operating"
        if "construction" in v and "application" in v:
            return "Application for Construction License"
        if "construction" in v and "license" in v:
            return "Construction License"
        if "survey" in v and "application" in v:
            return "Application for Survey License"
        if "survey" in v and "license" in v:
            return "Survey License"
        return "Application for Survey License"  # Default fallback

    def _extract_year(self, val):
        """Extract B.S. year from various date formats."""
        if val is None:
            return None
        s = str(val).strip()
        # Try to find 4-digit year
        m = re.search(r"(20[5-9]\d|21[0-5]\d)", s)
        if m:
            return int(m.group(1))
        return None

    def _parse_date_to_bs(self, val):
        """Parse a date value to B.S. tuple (year, month, day)."""
        if val is None:
            return None
        s = str(val).strip()
        # Try YYYY-MM-DD pattern
        m = re.match(r"(20[5-9]\d|21[0-5]\d)-(\d{1,2})-(\d{1,2})", s)
        if m:
            return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        # Try YYYY-MM
        m = re.match(r"(20[5-9]\d|21[0-5]\d)-(\d{1,2})", s)
        if m:
            return (int(m.group(1)), int(m.group(2)), None)
        # Try bare year
        m = re.match(r"(20[5-9]\d|21[0-5]\d)", s)
        if m:
            return (int(m.group(1)), None, None)
        return None

    def _build_indexes(self):
        """Build lookup indexes after loading."""
        self._types = set()
        self._statuses = set()
        self._provinces = set()
        years = []

        for r in self.records:
            self._types.add(r["type"])
            self._statuses.add(r["status"])
            self._provinces.add(r["province"])
            if r.get("license_year"):
                years.append(r["license_year"])

        if years:
            self._year_bounds = (min(years), max(years))
        else:
            self._year_bounds = (None, None)

    def get_types(self):
        return sorted(self._types)

    def get_statuses(self):
        return sorted(self._statuses, key=lambda s: (STATUS_ORDER + EXTRA_STATUS_ORDER).index(s) if s in (STATUS_ORDER + EXTRA_STATUS_ORDER) else 999)

    def get_provinces(self):
        return sorted(self._provinces)

    def get_license_year_bounds(self):
        return self._year_bounds

    def filter(self, types=None, statuses=None, provinces=None, districts=None,
               locals_sel=None, cap_min=None, cap_max=None, km_min=None, km_max=None,
               year_from=None, year_to=None, cod_from=None, cod_to=None, search=None):
        """Filter records by multiple criteria."""
        result = []
        for r in self.records:
            # Type filter
            if types and r["type"] not in types:
                continue
            # Status filter
            if statuses and r["status"] not in statuses:
                continue
            # Province filter
            if provinces and r["province"] not in provinces:
                continue
            # District filter
            if districts and r["district"] not in districts:
                continue
            # Local body filter
            if locals_sel and r.get("local_body") not in locals_sel:
                continue
            # Capacity filter
            if cap_min is not None and (r["capacity_mw"] is None or r["capacity_mw"] < cap_min):
                continue
            if cap_max is not None and (r["capacity_mw"] is None or r["capacity_mw"] >= cap_max):
                continue
            # Transmission length filter
            if km_min is not None and (r["line_length_km"] is None or r["line_length_km"] < km_min):
                continue
            if km_max is not None and (r["line_length_km"] is None or r["line_length_km"] >= km_max):
                continue
            # License year filter
            if year_from is not None and r.get("license_year") is not None:
                if isinstance(year_from, tuple):
                    if r["license_year"] < year_from[0]:
                        continue
                else:
                    if r["license_year"] < year_from:
                        continue
            if year_to is not None and r.get("license_year") is not None:
                if isinstance(year_to, tuple):
                    if r["license_year"] > year_to[0]:
                        continue
                else:
                    if r["license_year"] > year_to:
                        continue
            # COD filter
            if cod_from is not None and r.get("cod_bs"):
                if not self._bs_gte(r["cod_bs"], cod_from):
                    continue
            if cod_to is not None and r.get("cod_bs"):
                if not self._bs_lte(r["cod_bs"], cod_to):
                    continue
            # Search filter
            if search:
                search_lower = search.lower()
                found = False
                for field in ["project", "district", "province", "promoter", "local_body"]:
                    if r.get(field) and search_lower in str(r[field]).lower():
                        found = True
                        break
                if not found:
                    continue

            result.append(r)
        return result

    def _bs_gte(self, bs_a, bs_b):
        """Check if B.S. date A >= B.S. date B."""
        for i in range(3):
            a = bs_a[i] if i < len(bs_a) and bs_a[i] else 0
            b = bs_b[i] if i < len(bs_b) and bs_b[i] else 0
            if a > b:
                return True
            if a < b:
                return False
        return True

    def _bs_lte(self, bs_a, bs_b):
        """Check if B.S. date A <= B.S. date B."""
        for i in range(3):
            a = bs_a[i] if i < len(bs_a) and bs_a[i] else 9999
            b = bs_b[i] if i < len(bs_b) and bs_b[i] else 9999
            if a < b:
                return True
            if a > b:
                return False
        return True

    def yearly_series(self, recs, key_field="type"):
        """Aggregate records by license year and key field."""
        series = defaultdict(lambda: defaultdict(lambda: [0, 0.0]))  # [count, mw]
        for r in recs:
            year = r.get("license_year")
            if not year:
                continue
            key = r.get(key_field, "Other")
            series[year][key][0] += 1
            series[year][key][1] += r["capacity_mw"] or 0
        return series

    def district_metric(self, recs):
        """Aggregate capacity by district for choropleth shading."""
        metric = defaultdict(lambda: [0, 0.0])  # [count, mw]
        for r in recs:
            d = r.get("district", "Unspecified")
            if d and d != "Unspecified":
                metric[d][0] += 1
                metric[d][1] += r["capacity_mw"] or 0
        return metric


# ── Google Sheet / Drive Helpers ────────────────────────────────────────────

def download_google_sheet_xlsx(url_or_id, out_path):
    """Download a Google Sheet as .xlsx. Supports full URL or just the ID."""
    import urllib.request
    import urllib.parse

    # Extract ID from various URL formats
    sheet_id = url_or_id
    if "/" in url_or_id:
        # Try to extract from URL
        patterns = [
            r"/spreadsheets/d/([a-zA-Z0-9-_]+)",
            r"id=([a-zA-Z0-9-_]+)",
            r"([a-zA-Z0-9-_]{40,})"
        ]
        for pat in patterns:
            m = re.search(pat, url_or_id)
            if m:
                sheet_id = m.group(1)
                break

    export_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=xlsx"

    req = urllib.request.Request(export_url)
    req.add_header("User-Agent", "Mozilla/5.0")

    with urllib.request.urlopen(req, timeout=120) as resp:
        with open(out_path, "wb") as f:
            f.write(resp.read())

    return out_path


def download_google_drive_file(url_or_id, out_path):
    """Download a file from Google Drive share link. Returns (path, changed)."""
    import urllib.request
    import urllib.parse

    file_id = url_or_id
    if "/" in url_or_id:
        m = re.search(r"[/?]id=([a-zA-Z0-9-_]+)", url_or_id)
        if m:
            file_id = m.group(1)
        else:
            m = re.search(r"/d/([a-zA-Z0-9-_]+)", url_or_id)
            if m:
                file_id = m.group(1)

    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"

    req = urllib.request.Request(download_url)
    req.add_header("User-Agent", "Mozilla/5.0")

    # Check if file already exists and compare size
    old_size = os.path.getsize(out_path) if os.path.exists(out_path) else 0

    with urllib.request.urlopen(req, timeout=180) as resp:
        data = resp.read()
        with open(out_path, "wb") as f:
            f.write(data)

    new_size = os.path.getsize(out_path)
    return out_path, (new_size != old_size or old_size == 0)


# ── Record Helpers ──────────────────────────────────────────────────────────

def record_local(r):
    """Extract local body name from record."""
    return r.get("local_body") or r.get("gaunpalika") or r.get("nagarpalika") or ""


def full_rec_tip(r):
    """Build a detailed tooltip string for a record."""
    lines = [
        f"Project: {r.get('project', '—')}",
        f"Type: {r.get('type', '—')}",
        f"Status: {r.get('status', '—')}",
        f"Capacity: {fmt_mw(r.get('capacity_mw'))} MW",
    ]
    if r.get("voltage_kv"):
        lines.append(f"Voltage: {r['voltage_kv']:.0f} kV")
    if r.get("line_length_km"):
        lines.append(f"Line Length: {r['line_length_km']:.1f} km")
    lines.extend([
        f"District: {r.get('district', '—')}",
        f"Province: {r.get('province', '—')}",
        f"Promoter: {r.get('promoter', '—')}",
    ])
    if r.get("lat") and r.get("lon"):
        lines.append(f"Coordinates: {r['lat']:.5f}, {r['lon']:.5f}")
    return "\n".join(lines)
