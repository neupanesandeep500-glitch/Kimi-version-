"""
coordinate_transform.py

Coordinate system conversions for Nepal.
- WGS-84 (EPSG:4326): standard GPS coordinates
- Everest 1830 / India Zone IIIa: used by Nepal Survey Department (DoED)

This module provides approximate conversions sufficient for dashboard display.
For survey-grade accuracy, use a proper geodetic library like pyproj.
"""

import math

# Coordinate system identifiers
CRS_WGS84 = "wgs84"
CRS_EVEREST = "everest1830"

CRS_LABELS = {
    CRS_WGS84: "WGS-84 (GPS)",
    CRS_EVEREST: "Everest 1830 (DoED Survey)",
}

# Approximate datum shift parameters for Nepal (Everest 1830 -> WGS-84)
# These are rough estimates; proper transformation requires 7-parameter Helmert
_DX = -0.282  # meters
_DY = 0.726   # meters
_DZ = 0.254   # meters

# Approximate conversion: WGS-84 to Everest 1830 (inverse of above)
def wgs84_to_everest(lat, lon):
    """Convert WGS-84 lat/lon to Everest 1830 approximate.
    Returns (lat, lon) in degrees."""
    if lat is None or lon is None:
        return None, None
    # Very rough approximation: shift by ~0.0001 degrees
    # For production, use pyproj with proper datum parameters
    lat_e = lat - 0.000025
    lon_e = lon - 0.000035
    return lat_e, lon_e


def everest_to_wgs84(lat, lon):
    """Convert Everest 1830 lat/lon to WGS-84 approximate.
    Returns (lat, lon) in degrees."""
    if lat is None or lon is None:
        return None, None
    lat_w = lat + 0.000025
    lon_w = lon + 0.000035
    return lat_w, lon_w


def decimal_to_dms(value):
    """Format a decimal-degree value as DDD°MM'SS.SS" (as used throughout
    the DoED workbook). Returns None for a missing value."""
    if value is None:
        return None
    sign = "-" if value < 0 else ""
    value = abs(value)
    deg = int(value)
    minutes_full = (value - deg) * 60
    minutes = int(minutes_full)
    seconds = (minutes_full - minutes) * 60
    return f"{sign}{deg}\u00b0{minutes:02d}'{seconds:05.2f}\""
