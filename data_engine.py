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

# ── Sheet name -> (type, status) lookup ────────────────────────────────────
#
# The DoED workbook has no "Type" or "Status" column on any sheet — each
# sheet IS a type/status combination (e.g. "Survey_Solar" = Solar projects
# that hold a Survey License). "Hydro" here is a marker resolved per-row in
# _parse_row() using the row's capacity (<=1MW vs >1MW), for the sheets that
# don't already split hydro by size. Keys are matched against the *exact*
# sheet name (including any stray leading/trailing spaces in the workbook)
# because two sheets in this workbook are named identically except for a
# trailing space yet hold different data (see the Technical Clearance note
# below).
SHEET_META = {
    "Survey_Hydro_Less 1": ("Hydro (<=1MW)", "Survey License"),
    "Survey_Hydro_More 1 ": ("Hydro (>1MW)", "Survey License"),
    "Survey_Thermal": ("Thermal", "Survey License"),
    "Survey_Solar": ("Solar", "Survey License"),
    "Survey_Wind": ("Wind", "Survey License"),
    "Survey_Biomass": ("Biomass", "Survey License"),
    "Survey_Cogeneration": ("Co-generation", "Survey License"),
    "Survey_Transmission Line": ("Transmission Line", "Survey License"),

    "Construction Lice_Hydro_Less 1": ("Hydro (<=1MW)", "Construction License"),
    "Construction Lice_Hydro_More 1": ("Hydro (>1MW)", "Construction License"),
    "Construction Lice_Thermal": ("Thermal", "Construction License"),
    "Construction_Lice_Solar": ("Solar", "Construction License"),
    "Construction_Lice_Wind": ("Wind", "Construction License"),
    "Construction_Lice_Biomass": ("Biomass", "Construction License"),
    "Construction_Lice_Cogeneration": ("Co-generation", "Construction License"),
    "Construction_Lice_Transmission": ("Transmission Line", "Construction License"),

    "Appl_Survey_Hydro_Less 1": ("Hydro (<=1MW)", "Application for Survey License"),
    "Appl_Survey_Hydro_More 1": ("Hydro (>1MW)", "Application for Survey License"),
    "Appl_Survey_Thermal": ("Thermal", "Application for Survey License"),
    "Appl_Survey_Solar ": ("Solar", "Application for Survey License"),
    "Appl_Survey_Wind": ("Wind", "Application for Survey License"),
    "Appl_Survey_Biomass": ("Biomass", "Application for Survey License"),
    "Appl_Survey_Cogeneration": ("Co-generation", "Application for Survey License"),
    "Appl_Survey_Transmission Line ": ("Transmission Line", "Application for Survey License"),
    "Appl_Survey_Cancelled_Hydro": ("Hydro", "Cancelled"),

    "Appl_Construction Lic_Hydro": ("Hydro", "Application for Construction License"),
    "Appl_Construction Lic_Thermal": ("Thermal", "Application for Construction License"),
    "Appl_Construction Lic_Solar": ("Solar", "Application for Construction License"),
    "Appl_Construction Lic_Wind": ("Wind", "Application for Construction License"),
    "Appl_Construction Lic_Biomass": ("Biomass", "Application for Construction License"),
    "Appl_Construction_Cogeneration": ("Co-generation", "Application for Construction License"),
    "Appl_Construction_Transmission ": ("Transmission Line", "Application for Construction License"),

    "Power Plants_Hydro Less 1": ("Hydro (<=1MW)", "Operating"),
    "Power Plants_Hydro More 1": ("Hydro (>1MW)", "Operating"),
    "Power Plants_Thermal": ("Thermal", "Operating"),
    "Power Plants_Solar": ("Solar", "Operating"),
    "Power Plants_Wind ": ("Wind", "Operating"),
    "Power Plants_Biomass": ("Biomass", "Operating"),
    "Power Plants_Cogeneration": ("Co-generation", "Operating"),

    "Generation Lic_Cancelled ": ("Hydro", "Cancelled"),
    "Survey License_Cancelled": ("Hydro", "Cancelled"),
    "Generation Application_Cancelle": ("Hydro", "Cancelled"),
    "40 M Criteria License_Cancelled": ("Hydro", "Cancelled"),

    "GoN_Studied Projects": ("Hydro", "GoN Study Project"),
    "GoN_Under Study Projects": ("Hydro", "GoN Study Project"),

    "Technical Clearance Hydro": ("Hydro", "Technical Clearance"),
    "Technical Clearance Solar ": ("Solar", "Technical Clearance"),
    # NOTE: this sheet name is a duplicate of the one above (source data
    # entry mistake) — its IMPORTHTML formula actually pulls from doed.gov.np's
    # "tcwind" page, so its rows are Wind, not Solar. Kept as a distinct dict
    # key (no trailing space) precisely so it does not collide with the real
    # Solar sheet above.
    "Technical Clearance Solar": ("Wind", "Technical Clearance"),
}

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
    """Lightweight GIS engine for Nepal province/district/local-body
    boundaries and protected areas. Supports loading from inline GeoJSON
    (bundled), external shapefile zip, or a raw shapefile path."""

    def __init__(self):
        self.districts = {}           # name -> {province, polygons}
        self.provinces = {}           # name -> {polygons}  (real province geometry)
        self.localbodies = []         # [{name, district, province, type, polygons}]
        self.province_districts = defaultdict(list)
        self.protected_areas = []     # [{name, category, polygons}]
        self.locals = []              # [{label, district, province}]  (cascade filter labels)
        self.district_province = {}   # district -> province
        self.boundary_polygons = []   # national outline, for the base map layer
        self.claimed_area_name = None
        self.claimed_area_polygons = []  # Limpiyadhura-Kalapani-Lipulekh tract
        self.loaded = False
        self.provinces_loaded = False
        self.localbodies_loaded = False
        self.pa_loaded = False
        self.claimed_area_loaded = False
        self.error = None

    # ── Loading methods ────────────────────────────────────────────────────

    def load_from_geojson(self, geojson_dict):
        """Load district/province boundaries from an inline GeoJSON dict."""
        try:
            self.districts = {}
            self.province_districts = defaultdict(list)
            self.district_province = {}
            if not self.localbodies:
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

                self.districts[name] = {"province": province, "polygons": polygons,
                                         "bbox": self._polygons_bbox(polygons)}
                self.province_districts[province].append(name)
                self.district_province[name] = province

                # Only synthesize placeholder local bodies if a real
                # local-body layer hasn't been loaded separately.
                if not self.localbodies:
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

    def load_provinces_from_geojson(self, geojson_dict):
        """Load real province boundaries (not merged from districts)."""
        try:
            self.provinces = {}
            for feat in geojson_dict.get("features", []):
                props = feat.get("properties", {})
                name = props.get("name") or props.get("PR_NAME") or f"Province_{len(self.provinces)}"
                geom = feat.get("geometry", {})
                polygons = self._geojson_to_polygons(geom)
                if polygons:
                    self.provinces[name] = {"polygons": polygons,
                                             "bbox": self._polygons_bbox(polygons)}
            self.provinces_loaded = bool(self.provinces)
            return self.provinces_loaded
        except Exception as e:
            self.error = str(e)
            return False

    def load_localbodies_from_geojson(self, geojson_dict):
        """Load real local-body (Gaunpalika/Nagarpalika) boundaries — this
        replaces the synthetic "District Rural Municipality" placeholders
        with the actual ~753 local units and their real geometry."""
        try:
            self.localbodies = []
            self.locals = []
            for feat in geojson_dict.get("features", []):
                props = feat.get("properties", {})
                name = props.get("name") or "Unknown Local Body"
                district = props.get("district") or "Unspecified"
                province = props.get("province") or "Unspecified"
                lb_type = props.get("type") or ""
                geom = feat.get("geometry", {})
                polygons = self._geojson_to_polygons(geom)
                if not polygons:
                    continue
                self.localbodies.append({
                    "name": name, "district": district, "province": province,
                    "type": lb_type, "polygons": polygons,
                    "bbox": self._polygons_bbox(polygons),
                })
                self.locals.append({"label": name, "district": district, "province": province})
            self.localbodies_loaded = bool(self.localbodies)
            return self.localbodies_loaded
        except Exception as e:
            self.error = str(e)
            return False

    def load_boundary_from_geojson(self, geojson_dict):
        """Load the national outline (used as a base map layer)."""
        try:
            polys = []
            for feat in geojson_dict.get("features", []):
                polys.extend(self._geojson_to_polygons(feat.get("geometry", {})))
            self.boundary_polygons = polys
            return bool(polys)
        except Exception as e:
            self.error = str(e)
            return False

    def load_claimed_area_from_geojson(self, geojson_dict):
        """Load the Limpiyadhura-Kalapani-Lipulekh disputed tract (per
        Nepal's 2020 official map) as its own distinct layer — it isn't
        assigned to any province/district/local-government unit."""
        try:
            feats = geojson_dict.get("features", [])
            polys = []
            name = "Limpiyadhura-Kalapani-Lipulekh"
            for feat in feats:
                props = feat.get("properties", {})
                name = props.get("name", name)
                polys.extend(self._geojson_to_polygons(feat.get("geometry", {})))
            self.claimed_area_name = name
            self.claimed_area_polygons = polys
            self.claimed_area_loaded = bool(polys)
            return self.claimed_area_loaded
        except Exception as e:
            self.error = str(e)
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
        """Load from a shapefile zip or directory path. Falls back to
        bundled data if the path is invalid or pyshp isn't available."""
        try:
            try:
                import shapefile
                sf = shapefile.Reader(path)
                self.loaded = True
                return True
            except ImportError:
                pass
            from gis_bundled import NEPAL_DISTRICTS_GEOJSON
            return self.load_from_geojson(NEPAL_DISTRICTS_GEOJSON)
        except Exception as e:
            self.error = str(e)
            return False

    def load(self):
        """Default load — uses the bundled real Nepal Survey Dept-derived
        province/district/local-body/boundary layers (see gis_bundled.py)."""
        from gis_bundled import (NEPAL_DISTRICTS_GEOJSON, NEPAL_PROVINCES_GEOJSON,
                                  NEPAL_LOCALBODIES_GEOJSON, NEPAL_BOUNDARY_GEOJSON,
                                  NEPAL_CLAIMED_AREA_GEOJSON)
        ok_district = self.load_from_geojson(NEPAL_DISTRICTS_GEOJSON)
        self.load_provinces_from_geojson(NEPAL_PROVINCES_GEOJSON)
        self.load_localbodies_from_geojson(NEPAL_LOCALBODIES_GEOJSON)
        self.load_boundary_from_geojson(NEPAL_BOUNDARY_GEOJSON)
        self.load_claimed_area_from_geojson(NEPAL_CLAIMED_AREA_GEOJSON)
        return ok_district

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

    @staticmethod
    def _polygons_bbox(polygons):
        """Cheap bounding box over every ring of every polygon — used as a
        fast pre-filter before the exact ray-casting test."""
        lons, lats = [], []
        for poly in polygons:
            for ring in poly:
                for lon, lat in ring:
                    lons.append(lon)
                    lats.append(lat)
        if not lons:
            return None
        return (min(lons), max(lons), min(lats), max(lats))

    @staticmethod
    def _point_in_ring(lon, lat, ring):
        """Standard ray-casting point-in-polygon test for a single ring."""
        inside = False
        n = len(ring)
        j = n - 1
        for i in range(n):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if ((yi > lat) != (yj > lat)) and \
               (lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi):
                inside = not inside
            j = i
        return inside

    @classmethod
    def _point_in_polygons(cls, lon, lat, polygons, bbox=None):
        """True point-in-polygon test (with hole support) across every
        polygon in a feature's polygon list, gated by a cheap bbox check."""
        if bbox:
            lon_min, lon_max, lat_min, lat_max = bbox
            if not (lon_min <= lon <= lon_max and lat_min <= lat <= lat_max):
                return False
        for poly in polygons:
            if not poly:
                continue
            exterior, holes = poly[0], poly[1:]
            if cls._point_in_ring(lon, lat, exterior):
                if any(cls._point_in_ring(lon, lat, hole) for hole in holes):
                    continue
                return True
        return False

    def display_rings(self, level="district"):
        """Yield (name, province, rings) tuples for map rendering.
        level: "district" (default), "province" (real province geometry,
        not merged from districts), or "local" (real local-body geometry)."""
        if level == "district":
            for name, info in self.districts.items():
                for poly in info.get("polygons", []):
                    yield (name, info.get("province", "Unspecified"), poly)
        elif level == "province":
            if self.provinces_loaded:
                for name, info in self.provinces.items():
                    for poly in info.get("polygons", []):
                        yield (name, name, poly)
            else:
                # Fallback: merge districts per province (legacy behavior).
                for prov, dists in self.province_districts.items():
                    for d in dists:
                        info = self.districts.get(d, {})
                        for poly in info.get("polygons", []):
                            yield (prov, prov, poly)
        elif level == "local":
            for lb in self.localbodies:
                for poly in lb.get("polygons", []):
                    yield (lb["name"], lb.get("province", "Unspecified"), poly)

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

    # ── Area / % overlap (pure Python, no shapely — Sutherland-Hodgman clip
    #    of each candidate polygon against the project's rectangle, then
    #    shoelace-formula area). ────────────────────────────────────────────
    @staticmethod
    def _clip_poly_rect(ring, xmin, ymin, xmax, ymax):
        """Sutherland-Hodgman: clip a (lon,lat) ring to an axis-aligned
        rectangle. Returns the clipped ring (possibly empty)."""
        def clip(points, inside, intersect):
            if not points:
                return []
            out = []
            n = len(points)
            for i in range(n):
                cur, prev = points[i], points[i - 1]
                cur_in, prev_in = inside(cur), inside(prev)
                if cur_in:
                    if not prev_in:
                        out.append(intersect(prev, cur))
                    out.append(cur)
                elif prev_in:
                    out.append(intersect(prev, cur))
            return out

        def isect_x(p1, p2, xb):
            x1, y1 = p1; x2, y2 = p2
            t = (xb - x1) / (x2 - x1)
            return (xb, y1 + t * (y2 - y1))

        def isect_y(p1, p2, yb):
            x1, y1 = p1; x2, y2 = p2
            t = (yb - y1) / (y2 - y1)
            return (x1 + t * (x2 - x1), yb)

        pts = list(ring)
        pts = clip(pts, lambda p: p[0] >= xmin, lambda a, b: isect_x(a, b, xmin))
        pts = clip(pts, lambda p: p[0] <= xmax, lambda a, b: isect_x(a, b, xmax))
        pts = clip(pts, lambda p: p[1] >= ymin, lambda a, b: isect_y(a, b, ymin))
        pts = clip(pts, lambda p: p[1] <= ymax, lambda a, b: isect_y(a, b, ymax))
        return pts

    @staticmethod
    def _shoelace_area(ring):
        if len(ring) < 3:
            return 0.0
        area = 0.0
        n = len(ring)
        for i in range(n):
            x1, y1 = ring[i]
            x2, y2 = ring[(i + 1) % n]
            area += x1 * y2 - x2 * y1
        return abs(area) / 2.0

    @classmethod
    def _polygon_area_in_bbox(cls, polygons, xmin, ymin, xmax, ymax):
        """Net area (exterior minus holes) of a feature's polygons that
        falls inside the given rectangle."""
        total = 0.0
        for poly in polygons:
            if not poly:
                continue
            exterior, holes = poly[0], poly[1:]
            clipped_ext = cls._clip_poly_rect(exterior, xmin, ymin, xmax, ymax)
            ext_area = cls._shoelace_area(clipped_ext)
            hole_area = 0.0
            for hole in holes:
                clipped_hole = cls._clip_poly_rect(hole, xmin, ymin, xmax, ymax)
                hole_area += cls._shoelace_area(clipped_hole)
            total += max(0.0, ext_area - hole_area)
        return total

    def bbox_overlap_pct(self, bbox):
        """bbox: [lat1, lat2, lon1, lon2] (as stored on each record).
        Returns dict with province_pct / district_pct / local_pct /
        protected_pct / claimed_pct — each {name: percent_of_bbox_area}."""
        if not bbox or None in bbox:
            return {}
        lat1, lat2, lon1, lon2 = bbox
        ymin, ymax = sorted([lat1, lat2])
        xmin, xmax = sorted([lon1, lon2])
        eps = 0.0005  # guard against a degenerate (point) box
        if ymax - ymin < eps: ymax = ymin + eps
        if xmax - xmin < eps: xmax = xmin + eps
        total_area = (xmax - xmin) * (ymax - ymin)
        if total_area <= 0:
            return {}

        def _pct_for(items):
            out = {}
            for name, polygons, ibbox in items:
                if ibbox:
                    ilon_min, ilon_max, ilat_min, ilat_max = ibbox
                    if ilon_max < xmin or ilon_min > xmax or ilat_max < ymin or ilat_min > ymax:
                        continue  # cheap reject before the exact clip
                area = self._polygon_area_in_bbox(polygons, xmin, ymin, xmax, ymax)
                if area <= 0:
                    continue
                pct = round(100.0 * area / total_area, 1)
                if pct > 0.01:
                    out[name] = out.get(name, 0) + pct
            return out

        if self.provinces_loaded:
            province_items = [(n, info["polygons"], info.get("bbox")) for n, info in self.provinces.items()]
        else:
            province_items = [(info.get("province", n), info["polygons"], info.get("bbox"))
                               for n, info in self.districts.items()]
        district_items = [(n, info["polygons"], info.get("bbox")) for n, info in self.districts.items()]
        local_items = [(lb["name"], lb["polygons"], lb.get("bbox")) for lb in self.localbodies]
        pa_items = [(f'{pa["name"]} ({pa["category"]})', pa["polygons"], None) for pa in self.protected_areas]
        claimed_items = ([(self.claimed_area_name, self.claimed_area_polygons, None)]
                          if getattr(self, "claimed_area_polygons", None) else [])

        return {
            "province_pct": _pct_for(province_items),
            "district_pct": _pct_for(district_items),
            "local_pct": _pct_for(local_items),
            "protected_pct": _pct_for(pa_items),
            "claimed_pct": _pct_for(claimed_items),
        }

    def point_in_district(self, lon, lat):
        """Exact ray-casting point-in-polygon district lookup (falls back
        to the containing province's boundary if no district matches)."""
        if lon is None or lat is None:
            return None, "Unspecified"
        for name, info in self.districts.items():
            if self._point_in_polygons(lon, lat, info.get("polygons", []), info.get("bbox")):
                return name, info.get("province", "Unspecified")
        # No district polygon matched (e.g. point just outside a simplified
        # boundary) — fall back to the real province layer if we have one.
        if self.provinces_loaded:
            _, province = self.point_in_province(lon, lat)
            return None, province
        return None, "Unspecified"

    def point_in_province(self, lon, lat):
        """Exact ray-casting point-in-polygon lookup against the real
        province layer (independent of district data)."""
        if lon is None or lat is None or not self.provinces_loaded:
            return None, "Unspecified"
        for name, info in self.provinces.items():
            if self._point_in_polygons(lon, lat, info.get("polygons", []), info.get("bbox")):
                return name, name
        return None, "Unspecified"

    def point_in_local(self, lon, lat):
        """Exact ray-casting point-in-polygon lookup against the real
        local-body (Gaunpalika/Nagarpalika) layer."""
        if lon is None or lat is None or not self.localbodies_loaded:
            return None, "Unspecified", "Unspecified"
        for lb in self.localbodies:
            if self._point_in_polygons(lon, lat, lb.get("polygons", []), lb.get("bbox")):
                return lb["name"], lb.get("district", "Unspecified"), lb.get("province", "Unspecified")
        return None, "Unspecified", "Unspecified"


# Singleton instance
GIS = GISEngine()


# ── Column / coordinate parsing helpers ────────────────────────────────────

def _normalize_col_name(c):
    """Turn a raw workbook header into a stable lookup key.

    The workbook's headers are messy in ways a plain
    ``.lower().replace(" ", "_")`` doesn't handle:
      * Some sheets wrap headers in asterisks: "*Project*".
      * "Capacity (MW)" / "Voltage (kV)" / "Line Length (km)" carry
        parentheses that survive a space-only replace.
      * "VDC/District" has a slash.
      * The Transmission Line sheets have Google-Sheets filter-chip text
        appended after a newline, e.g. "Promoter\\nFilter: All ...", which
        would otherwise turn into one giant, unmatchable column name.
      * A stray sort-arrow character shows up on "Appn Date ▾".
    This keeps only the text before the first newline, strips asterisks,
    lowercases, and collapses every run of non-word characters to a single
    underscore, so "*Capacity (MW)*" and "Voltage (kV)\\nFilter: ..." both
    become clean, matchable keys ("capacity_mw", "voltage_kv").
    """
    s = str(c).split("\n", 1)[0]
    s = s.replace("*", "")
    s = s.strip().lower()
    s = re.sub(r"[^\w]+", "_", s)
    return s.strip("_")


_DMS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[o°]\s*(\d+(?:\.\d+)?)?\s*'?\s*(\d+(?:\.\d+)?)?\s*\"?")


def _dms_to_decimal(s):
    """Parse a 'DDDo MM' SS"' string (as used throughout this workbook,
    e.g. 28o 09' 18") into decimal degrees. Returns None for blank/missing
    values and for the "00o 00' 00\"" placeholder the source uses for
    "no data" (0,0 isn't a real coordinate anywhere in Nepal)."""
    if s is None:
        return None
    s = str(s).strip()
    if not s:
        return None
    m = _DMS_RE.match(s)
    if not m:
        try:
            v = float(s)
        except (ValueError, TypeError):
            return None
        return v if v != 0 else None
    deg = float(m.group(1))
    minutes = float(m.group(2)) if m.group(2) else 0.0
    seconds = float(m.group(3)) if m.group(3) else 0.0
    if deg == 0 and minutes == 0 and seconds == 0:
        return None
    return deg + minutes / 60.0 + seconds / 3600.0


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
                df.columns = [_normalize_col_name(c) for c in df.columns]

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

        # Value at `candidate` plus whatever sits in the very next column,
        # but ONLY if that next column has a blank/"Unnamed" header — i.e. a
        # true paired second value (this workbook stores each lat/lon as a
        # start/end pair spanning two adjacent, mostly-unlabeled columns),
        # not just the next labeled field.
        def get_paired(*candidates):
            cols = list(row.index)
            for c in candidates:
                if c in cols:
                    idx = cols.index(c)
                    primary = row.iloc[idx]
                    secondary = None
                    if idx + 1 < len(cols):
                        nxt = cols[idx + 1]
                        if nxt.startswith("unnamed") or nxt == "":
                            secondary = row.iloc[idx + 1]
                    return primary, secondary
            return None, None

        project = get_col("project_name", "project", "name", "project_name_")
        if not project or str(project).strip() in ("", "nan", "None"):
            return None

        # Capacity (needed before type classification, to resolve the
        # sheets that mix <=1MW and >1MW hydro projects together)
        cap = get_col("capacity_mw", "capacity", "mw", "installed_capacity")
        try:
            capacity_mw = float(cap) if cap is not None and pd.notna(cap) else None
        except (ValueError, TypeError):
            capacity_mw = None

        # Determine type — sheet identity is authoritative for this workbook
        # (no sheet has an actual "Type" column); fall back to any explicit
        # type/status columns for other workbooks that do have them.
        type_val = str(get_col("type", "project_type", "category", "plant_type") or "").strip()
        ptype = self._classify_type(type_val, sheet_name)
        if ptype == "Hydro":
            # Generic marker from SHEET_META for sheets that don't split by
            # size — resolve using this row's own capacity.
            ptype = "Hydro (<=1MW)" if (capacity_mw is not None and capacity_mw <= 1) else "Hydro (>1MW)"

        # Determine status
        status_val = str(get_col("status", "license_status", "stage", "current_status") or "").strip()
        status = self._classify_status(status_val, sheet_name)

        # Voltage and line length (for transmission)
        volt = get_col("voltage_kv", "voltage", "kv")
        try:
            voltage_kv = float(volt) if volt is not None and pd.notna(volt) else None
        except (ValueError, TypeError):
            voltage_kv = None

        line_len = get_col("line_length_km", "length_km", "circuit_length", "transmission_length")
        try:
            line_length_km = float(line_len) if line_len is not None and pd.notna(line_len) else None
        except (ValueError, TypeError):
            line_length_km = None

        # Location
        district = str(get_col("district", "vdc_district", "dist", "district_name") or "").strip()
        province = str(get_col("province", "prov", "province_name") or "").strip()
        local_body = str(get_col("local_body", "gaunpalika", "nagarpalika", "municipality") or "").strip()

        # Coordinates — stored as DMS strings ("28o 09' 18\"") across a
        # start/end column pair (a small license-area bounding box), under
        # a misspelled "Latitiude N" / "Longitude E" header.
        lat_start_raw, lat_end_raw = get_paired("latitiude_n", "latitude", "lat", "y")
        lon_start_raw, lon_end_raw = get_paired("longitude_e", "longitude", "lon", "long", "x")
        lat_start = _dms_to_decimal(lat_start_raw)
        lat_end = _dms_to_decimal(lat_end_raw)
        lon_start = _dms_to_decimal(lon_start_raw)
        lon_end = _dms_to_decimal(lon_end_raw)

        if lat_start is not None and lat_end is not None:
            lat = (lat_start + lat_end) / 2.0
        else:
            lat = lat_start if lat_start is not None else lat_end
        if lon_start is not None and lon_end is not None:
            lon = (lon_start + lon_end) / 2.0
        else:
            lon = lon_start if lon_start is not None else lon_end

        # Fill in whichever of district/province/local-body the source
        # didn't give us via exact GIS point-in-polygon boundary lookup
        # (real Survey Department geometry, not a bounding box). The
        # workbook has no Province column at all, so this is the only way
        # province gets populated; district/local-body from the source's
        # own text (when present) is kept as-is since it may be more
        # specific or differently-spelled than the GIS match.
        if lat and lon and (not district or district == "Unspecified" or
                             not province or province == "Unspecified"):
            gis_district, gis_province = GIS.point_in_district(lon, lat)
            if not district or district == "Unspecified":
                district = gis_district
            if not province or province == "Unspecified":
                province = gis_province
        if lat and lon and (not local_body or local_body == "Unspecified"):
            gis_local, _, _ = GIS.point_in_local(lon, lat)
            if gis_local:
                local_body = gis_local

        # License date (source header is itself misspelled "Isuue Date")
        lic_date = get_col("license_date", "isuue_date", "issue_date", "license_issued", "date")
        lic_year = self._extract_year(lic_date)

        # COD date
        cod_date = get_col("cod", "c_o_d", "commercial_operation_date", "operation_date", "commissioning_date")
        cod_bs = self._parse_date_to_bs(cod_date)

        # Promoter
        promoter = str(get_col("promoter", "developer", "company", "promoter_name") or "").strip()

        # Bbox for license area — build it from the DMS start/end corners
        # when we have a genuine (non-degenerate) box; otherwise fall back
        # to any explicit bbox/boundary/license_area column if present.
        bbox = None
        if None not in (lat_start, lat_end, lon_start, lon_end) and (lat_start != lat_end or lon_start != lon_end):
            bbox = [lat_start, lat_end, lon_start, lon_end]
        else:
            for col in ["bbox", "boundary", "license_area"]:
                if col in row.index and pd.notna(row[col]):
                    try:
                        candidate = json.loads(str(row[col]))
                        if isinstance(candidate, list) and len(candidate) == 4:
                            bbox = candidate
                            break
                    except (ValueError, TypeError):
                        pass

        # Real polygon-overlay % breakdown of the license area's bounding
        # box against province / district / local-body / protected-area /
        # claimed-area boundaries (falls back to {} if no bbox or GIS
        # boundary layers aren't loaded).
        overlap = GIS.bbox_overlap_pct(bbox) if bbox else {}
        local_pct_list = []
        for lb_name, pct in (overlap.get("local_pct") or {}).items():
            lb_info = next((l for l in GIS.localbodies if l["name"] == lb_name), None)
            local_pct_list.append({
                "name": lb_name,
                "type": lb_info.get("type", "") if lb_info else "",
                "district": lb_info.get("district", "") if lb_info else "",
                "pct": pct,
            })

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
            "province_pct": overlap.get("province_pct") or {},
            "district_pct": overlap.get("district_pct") or {},
            "local_pct": local_pct_list,
            "protected_pct": overlap.get("protected_pct") or {},
            "claimed_pct": overlap.get("claimed_pct") or {},
        }

    def _classify_type(self, val, sheet_hint=""):
        """Classify raw type string into standardized type.

        Checks the sheet-name lookup table first (authoritative for this
        workbook, which has no explicit type column on any sheet), then
        falls back to keyword matching on `val` / the sheet name — kept for
        workbooks that DO carry an explicit type column, or sheets added
        later that aren't yet in SHEET_META.
        """
        meta = SHEET_META.get(sheet_hint)
        if meta is None:
            meta = SHEET_META.get(sheet_hint.strip())
        if meta is not None:
            return meta[0]

        v = val.lower()
        sh = sheet_hint.lower()

        if "transmission" in v or "transmission" in sh:
            return "Transmission Line"
        if "hydro" in v or "hydro" in sh:
            if "<=1" in v or "micro" in v or "mini" in v or "pico" in v or "less" in sh:
                return "Hydro (<=1MW)"
            return "Hydro (>1MW)"
        if "solar" in v or "pv" in v or "solar" in sh:
            return "Solar"
        if "wind" in v or "wind" in sh:
            return "Wind"
        if "thermal" in v or "coal" in v or "gas" in v or "diesel" in v or "thermal" in sh:
            return "Thermal"
        if "biomass" in v or "biomass" in sh:
            return "Biomass"
        if "co-gen" in v or "cogeneration" in v or "cogeneration" in sh:
            return "Co-generation"
        if "gon" in v or "study" in v or ("gon" in sh and "study" in sh):
            return "GoN Study"
        return "Other"

    def _classify_status(self, val, sheet_hint=""):
        """Classify raw status string into standardized status.

        Checks SHEET_META first (see _classify_type); falls back to keyword
        matching on `val` for workbooks with an explicit status column.
        """
        meta = SHEET_META.get(sheet_hint)
        if meta is None:
            meta = SHEET_META.get(sheet_hint.strip())
        if meta is not None:
            return meta[1]

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

    def metric_by_field(self, recs, key_field):
        """Aggregate capacity by an arbitrary record field (e.g. "province"
        or "local_body") for choropleth shading at any GIS level."""
        metric = defaultdict(lambda: [0, 0.0])  # [count, mw]
        for r in recs:
            k = r.get(key_field, "Unspecified")
            if k and k != "Unspecified":
                metric[k][0] += 1
                metric[k][1] += r["capacity_mw"] or 0
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
