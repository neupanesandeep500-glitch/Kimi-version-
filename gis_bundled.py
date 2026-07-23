"""
gis_bundled.py

Real Nepal province / district / local-body / national-boundary / protected-
area / claimed-area geometry, derived from the official Survey Department
"hermes_NPL_new_wgs" shapefile (4 layers: national boundary, 7 provinces,
77 districts, 776 local bodies — one of which, in Darchula district, has no
local-government TYPE assigned: that is the Limpiyadhura-Kalapani-Lipulekh
tract on Nepal's 2020 official map, split out into its own layer below) plus
the separate Protected_Area.geojson (national parks / reserves / buffer
zones), simplified and shipped as repo assets under data/gis/*.geojson so the
map works immediately on first deploy with zero configuration.

CHANGED vs the previous version of this file:
  - NEPAL_PROTECTED_AREAS_GEOJSON now loads from data/gis/nepal_protected_areas.geojson
    (real 35-feature layer) instead of the 19-feature hardcoded rectangle
    placeholder. The old hardcoded dict is kept below, renamed with a
    _PLACEHOLDER suffix, as the last-resort fallback only.
  - Added NEPAL_CLAIMED_AREA_GEOJSON (new) for the disputed tract.
"""

import json
import os

_GIS_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "gis")
_EMPTY_FC = {"type": "FeatureCollection", "features": []}


def _load_geojson_file(filename, fallback):
    """Read a bundled GeoJSON asset; fall back gracefully (rather than
    crashing the whole app) if the file is missing from this deploy."""
    path = os.path.join(_GIS_DATA_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return fallback


# Real geometry, simplified from the Survey Department shapefile:
NEPAL_PROVINCES_GEOJSON = _load_geojson_file("nepal_provinces.geojson", _EMPTY_FC)
NEPAL_LOCALBODIES_GEOJSON = _load_geojson_file("nepal_localbodies.geojson", _EMPTY_FC)
NEPAL_BOUNDARY_GEOJSON = _load_geojson_file("nepal_boundary.geojson", _EMPTY_FC)

# NEW: the Limpiyadhura-Kalapani-Lipulekh tract, per Nepal's 2020 official
# map (disputed with India). Rendered as its own distinct, clearly-labeled
# layer in render_gis — see app.py.
NEPAL_CLAIMED_AREA_GEOJSON = _load_geojson_file("nepal_claimed_area.geojson", _EMPTY_FC)

# Rough rectangle placeholders — used ONLY if data/gis/nepal_districts.geojson
# is missing from this deploy (e.g. a fresh checkout that didn't pull the
# data/ folder). Kept as a last-resort fallback so the app never breaks.
_NEPAL_DISTRICTS_GEOJSON_PLACEHOLDER = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "properties": {"name": "Kathmandu", "province": "Bagmati"},
         "geometry": {"type": "Polygon", "coordinates": [[[85.2, 27.5], [85.4, 27.5], [85.4, 27.8], [85.2, 27.8], [85.2, 27.5]]]}},
    ]
}
NEPAL_DISTRICTS_GEOJSON = _load_geojson_file("nepal_districts.geojson",
                                              _NEPAL_DISTRICTS_GEOJSON_PLACEHOLDER)

# CHANGED: now loads the real 35-feature protected-area layer (National Park,
# Wildlife Reserve, Hunting Reserve, Buffer Zone, etc.) instead of 19
# hardcoded rectangles. The rectangles are kept below as _PLACEHOLDER, used
# only if the real file is missing from this deploy.
_NEPAL_PROTECTED_AREAS_GEOJSON_PLACEHOLDER = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "properties": {"name": "Chitwan National Park", "category": "National Park"},
         "geometry": {"type": "Polygon", "coordinates": [[[84.2, 27.3], [84.6, 27.3], [84.6, 27.6], [84.2, 27.6], [84.2, 27.3]]]}},
    ]
}
NEPAL_PROTECTED_AREAS_GEOJSON = _load_geojson_file("nepal_protected_areas.geojson",
                                                    _NEPAL_PROTECTED_AREAS_GEOJSON_PLACEHOLDER)

# Province bounding boxes for quick spatial queries
PROVINCE_BOUNDS = {
    "Koshi": {"min_lon": 86.5, "max_lon": 88.2, "min_lat": 26.4, "max_lat": 27.8},
    "Madhesh": {"min_lon": 84.6, "max_lon": 87.0, "min_lat": 26.4, "max_lat": 27.2},
    "Bagmati": {"min_lon": 84.2, "max_lon": 86.5, "min_lat": 26.8, "max_lat": 28.5},
    "Gandaki": {"min_lon": 82.5, "max_lon": 85.0, "min_lat": 27.0, "max_lat": 29.5},
    "Lumbini": {"min_lon": 81.0, "max_lon": 84.0, "min_lat": 27.0, "max_lat": 28.8},
    "Karnali": {"min_lon": 81.0, "max_lon": 83.5, "min_lat": 28.0, "max_lat": 30.5},
    "Sudurpaschim": {"min_lon": 80.0, "max_lon": 82.0, "min_lat": 28.0, "max_lat": 30.5},
}
