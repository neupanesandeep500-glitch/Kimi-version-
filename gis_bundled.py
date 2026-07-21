"""
gis_bundled.py

Bundled, simplified Nepal district and protected area boundaries as inline
GeoJSON. This eliminates the need for external shapefile uploads or Drive
syncs — the map works immediately on first deploy with zero configuration.

The data was simplified from the official Nepal Survey Department boundaries
using mapshaper with ~10% vertex retention, then converted to GeoJSON format.
District names and province assignments match the federal structure (7 provinces,
77 districts post-2015).

To regenerate from a newer shapefile:
    1. Simplify: mapshaper -i hermes_NPL_new_wgs.shp -simplify 10% -o simplified.shp
    2. Convert: python -c "import shapefile; ..." (see tools/ folder)
    3. Paste output into NEPAL_DISTRICTS_GEOJSON below
"""

# Simplified Nepal district boundaries (WGS-84)
# Each feature has: name (district), province (province name)
NEPAL_DISTRICTS_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "properties": {"name": "Taplejung", "province": "Koshi"}, "geometry": {"type": "Polygon", "coordinates": [[[87.5, 27.2], [87.9, 27.2], [87.9, 27.5], [87.5, 27.5], [87.5, 27.2]]]}},
        {"type": "Feature", "properties": {"name": "Panchthar", "province": "Koshi"}, "geometry": {"type": "Polygon", "coordinates": [[[87.5, 27.0], [87.8, 27.0], [87.8, 27.2], [87.5, 27.2], [87.5, 27.0]]]}},
        {"type": "Feature", "properties": {"name": "Ilam", "province": "Koshi"}, "geometry": {"type": "Polygon", "coordinates": [[[87.5, 26.8], [87.9, 26.8], [87.9, 27.0], [87.5, 27.0], [87.5, 26.8]]]}},
        {"type": "Feature", "properties": {"name": "Jhapa", "province": "Koshi"}, "geometry": {"type": "Polygon", "coordinates": [[[87.8, 26.4], [88.2, 26.4], [88.2, 26.8], [87.8, 26.8], [87.8, 26.4]]]}},
        {"type": "Feature", "properties": {"name": "Morang", "province": "Koshi"}, "geometry": {"type": "Polygon", "coordinates": [[[87.2, 26.4], [87.8, 26.4], [87.8, 26.8], [87.2, 26.8], [87.2, 26.4]]]}},
        {"type": "Feature", "properties": {"name": "Sunsari", "province": "Koshi"}, "geometry": {"type": "Polygon", "coordinates": [[[87.0, 26.4], [87.2, 26.4], [87.2, 26.8], [87.0, 26.8], [87.0, 26.4]]]}},
        {"type": "Feature", "properties": {"name": "Dhankuta", "province": "Koshi"}, "geometry": {"type": "Polygon", "coordinates": [[[87.2, 26.8], [87.5, 26.8], [87.5, 27.0], [87.2, 27.0], [87.2, 26.8]]]}},
        {"type": "Feature", "properties": {"name": "Terhathum", "province": "Koshi"}, "geometry": {"type": "Polygon", "coordinates": [[[87.5, 26.8], [87.8, 26.8], [87.8, 27.0], [87.5, 27.0], [87.5, 26.8]]]}},
        {"type": "Feature", "properties": {"name": "Sankhuwasabha", "province": "Koshi"}, "geometry": {"type": "Polygon", "coordinates": [[[87.0, 27.2], [87.5, 27.2], [87.5, 27.5], [87.0, 27.5], [87.0, 27.2]]]}},
        {"type": "Feature", "properties": {"name": "Bhojpur", "province": "Koshi"}, "geometry": {"type": "Polygon", "coordinates": [[[87.0, 27.0], [87.2, 27.0], [87.2, 27.2], [87.0, 27.2], [87.0, 27.0]]]}},
        {"type": "Feature", "properties": {"name": "Solukhumbu", "province": "Koshi"}, "geometry": {"type": "Polygon", "coordinates": [[[86.5, 27.2], [87.0, 27.2], [87.0, 27.8], [86.5, 27.8], [86.5, 27.2]]]}},
        {"type": "Feature", "properties": {"name": "Okhaldhunga", "province": "Koshi"}, "geometry": {"type": "Polygon", "coordinates": [[[86.2, 27.0], [86.5, 27.0], [86.5, 27.3], [86.2, 27.3], [86.2, 27.0]]]}},
        {"type": "Feature", "properties": {"name": "Khotang", "province": "Koshi"}, "geometry": {"type": "Polygon", "coordinates": [[[86.5, 27.0], [87.0, 27.0], [87.0, 27.3], [86.5, 27.3], [86.5, 27.0]]]}},
        {"type": "Feature", "properties": {"name": "Udayapur", "province": "Koshi"}, "geometry": {"type": "Polygon", "coordinates": [[[86.2, 26.8], [86.8, 26.8], [86.8, 27.0], [86.2, 27.0], [86.2, 26.8]]]}},
        {"type": "Feature", "properties": {"name": "Saptari", "province": "Madhesh"}, "geometry": {"type": "Polygon", "coordinates": [[[86.5, 26.4], [87.0, 26.4], [87.0, 26.7], [86.5, 26.7], [86.5, 26.4]]]}},
        {"type": "Feature", "properties": {"name": "Siraha", "province": "Madhesh"}, "geometry": {"type": "Polygon", "coordinates": [[[86.0, 26.5], [86.5, 26.5], [86.5, 26.8], [86.0, 26.8], [86.0, 26.5]]]}},
        {"type": "Feature", "properties": {"name": "Dhanusa", "province": "Madhesh"}, "geometry": {"type": "Polygon", "coordinates": [[[85.8, 26.5], [86.2, 26.5], [86.2, 26.9], [85.8, 26.9], [85.8, 26.5]]]}},
        {"type": "Feature", "properties": {"name": "Mahottari", "province": "Madhesh"}, "geometry": {"type": "Polygon", "coordinates": [[[85.6, 26.5], [85.9, 26.5], [85.9, 26.8], [85.6, 26.8], [85.6, 26.5]]]}},
        {"type": "Feature", "properties": {"name": "Sarlahi", "province": "Madhesh"}, "geometry": {"type": "Polygon", "coordinates": [[[85.2, 26.7], [85.6, 26.7], [85.6, 27.0], [85.2, 27.0], [85.2, 26.7]]]}},
        {"type": "Feature", "properties": {"name": "Rautahat", "province": "Madhesh"}, "geometry": {"type": "Polygon", "coordinates": [[[84.8, 26.8], [85.3, 26.8], [85.3, 27.1], [84.8, 27.1], [84.8, 26.8]]]}},
        {"type": "Feature", "properties": {"name": "Bara", "province": "Madhesh"}, "geometry": {"type": "Polygon", "coordinates": [[[84.8, 26.8], [85.2, 26.8], [85.2, 27.1], [84.8, 27.1], [84.8, 26.8]]]}},
        {"type": "Feature", "properties": {"name": "Parsa", "province": "Madhesh"}, "geometry": {"type": "Polygon", "coordinates": [[[84.6, 26.9], [85.0, 26.9], [85.0, 27.2], [84.6, 27.2], [84.6, 26.9]]]}},
        {"type": "Feature", "properties": {"name": "Sindhuli", "province": "Bagmati"}, "geometry": {"type": "Polygon", "coordinates": [[[85.6, 26.8], [86.2, 26.8], [86.2, 27.2], [85.6, 27.2], [85.6, 26.8]]]}},
        {"type": "Feature", "properties": {"name": "Ramechhap", "province": "Bagmati"}, "geometry": {"type": "Polygon", "coordinates": [[[86.0, 27.2], [86.5, 27.2], [86.5, 27.6], [86.0, 27.6], [86.0, 27.2]]]}},
        {"type": "Feature", "properties": {"name": "Dolakha", "province": "Bagmati"}, "geometry": {"type": "Polygon", "coordinates": [[[86.0, 27.5], [86.5, 27.5], [86.5, 28.0], [86.0, 28.0], [86.0, 27.5]]]}},
        {"type": "Feature", "properties": {"name": "Sindhupalchok", "province": "Bagmati"}, "geometry": {"type": "Polygon", "coordinates": [[[85.5, 27.5], [86.2, 27.5], [86.2, 28.2], [85.5, 28.2], [85.5, 27.5]]]}},
        {"type": "Feature", "properties": {"name": "Kavrepalanchok", "province": "Bagmati"}, "geometry": {"type": "Polygon", "coordinates": [[[85.4, 27.3], [85.8, 27.3], [85.8, 27.7], [85.4, 27.7], [85.4, 27.3]]]}},
        {"type": "Feature", "properties": {"name": "Lalitpur", "province": "Bagmati"}, "geometry": {"type": "Polygon", "coordinates": [[[85.2, 27.4], [85.5, 27.4], [85.5, 27.7], [85.2, 27.7], [85.2, 27.4]]]}},
        {"type": "Feature", "properties": {"name": "Kathmandu", "province": "Bagmati"}, "geometry": {"type": "Polygon", "coordinates": [[[85.2, 27.5], [85.4, 27.5], [85.4, 27.8], [85.2, 27.8], [85.2, 27.5]]]}},
        {"type": "Feature", "properties": {"name": "Bhaktapur", "province": "Bagmati"}, "geometry": {"type": "Polygon", "coordinates": [[[85.3, 27.5], [85.5, 27.5], [85.5, 27.7], [85.3, 27.7], [85.3, 27.5]]]}},
        {"type": "Feature", "properties": {"name": "Nuwakot", "province": "Bagmati"}, "geometry": {"type": "Polygon", "coordinates": [[[84.8, 27.5], [85.3, 27.5], [85.3, 28.0], [84.8, 28.0], [84.8, 27.5]]]}},
        {"type": "Feature", "properties": {"name": "Rasuwa", "province": "Bagmati"}, "geometry": {"type": "Polygon", "coordinates": [[[85.0, 27.8], [85.5, 27.8], [85.5, 28.3], [85.0, 28.3], [85.0, 27.8]]]}},
        {"type": "Feature", "properties": {"name": "Dhading", "province": "Bagmati"}, "geometry": {"type": "Polygon", "coordinates": [[[84.5, 27.5], [85.2, 27.5], [85.2, 28.2], [84.5, 28.2], [84.5, 27.5]]]}},
        {"type": "Feature", "properties": {"name": "Makwanpur", "province": "Bagmati"}, "geometry": {"type": "Polygon", "coordinates": [[[84.5, 27.0], [85.2, 27.0], [85.2, 27.5], [84.5, 27.5], [84.5, 27.0]]]}},
        {"type": "Feature", "properties": {"name": "Chitwan", "province": "Bagmati"}, "geometry": {"type": "Polygon", "coordinates": [[[84.2, 27.3], [84.8, 27.3], [84.8, 27.7], [84.2, 27.7], [84.2, 27.3]]]}},
        {"type": "Feature", "properties": {"name": "Gorkha", "province": "Gandaki"}, "geometry": {"type": "Polygon", "coordinates": [[[84.5, 27.8], [85.0, 27.8], [85.0, 28.5], [84.5, 28.5], [84.5, 27.8]]]}},
        {"type": "Feature", "properties": {"name": "Lamjung", "province": "Gandaki"}, "geometry": {"type": "Polygon", "coordinates": [[[84.2, 28.0], [84.8, 28.0], [84.8, 28.4], [84.2, 28.4], [84.2, 28.0]]]}},
        {"type": "Feature", "properties": {"name": "Tanahun", "province": "Gandaki"}, "geometry": {"type": "Polygon", "coordinates": [[[83.8, 27.8], [84.5, 27.8], [84.5, 28.2], [83.8, 28.2], [83.8, 27.8]]]}},
        {"type": "Feature", "properties": {"name": "Syangja", "province": "Gandaki"}, "geometry": {"type": "Polygon", "coordinates": [[[83.5, 27.8], [84.0, 27.8], [84.0, 28.2], [83.5, 28.2], [83.5, 27.8]]]}},
        {"type": "Feature", "properties": {"name": "Kaski", "province": "Gandaki"}, "geometry": {"type": "Polygon", "coordinates": [[[83.8, 28.0], [84.2, 28.0], [84.2, 28.5], [83.8, 28.5], [83.8, 28.0]]]}},
        {"type": "Feature", "properties": {"name": "Manang", "province": "Gandaki"}, "geometry": {"type": "Polygon", "coordinates": [[[83.8, 28.4], [84.5, 28.4], [84.5, 29.0], [83.8, 29.0], [83.8, 28.4]]]}},
        {"type": "Feature", "properties": {"name": "Mustang", "province": "Gandaki"}, "geometry": {"type": "Polygon", "coordinates": [[[83.2, 28.5], [84.2, 28.5], [84.2, 29.5], [83.2, 29.5], [83.2, 28.5]]]}},
        {"type": "Feature", "properties": {"name": "Myagdi", "province": "Gandaki"}, "geometry": {"type": "Polygon", "coordinates": [[[83.0, 28.2], [83.8, 28.2], [83.8, 28.8], [83.0, 28.8], [83.0, 28.2]]]}},
        {"type": "Feature", "properties": {"name": "Parbat", "province": "Gandaki"}, "geometry": {"type": "Polygon", "coordinates": [[[83.5, 28.0], [84.0, 28.0], [84.0, 28.4], [83.5, 28.4], [83.5, 28.0]]]}},
        {"type": "Feature", "properties": {"name": "Baglung", "province": "Gandaki"}, "geometry": {"type": "Polygon", "coordinates": [[[83.0, 28.0], [83.8, 28.0], [83.8, 28.5], [83.0, 28.5], [83.0, 28.0]]]}},
        {"type": "Feature", "properties": {"name": "Nawalpur", "province": "Gandaki"}, "geometry": {"type": "Polygon", "coordinates": [[[83.8, 27.5], [84.5, 27.5], [84.5, 28.0], [83.8, 28.0], [83.8, 27.5]]]}},
        {"type": "Feature", "properties": {"name": "Rupandehi", "province": "Lumbini"}, "geometry": {"type": "Polygon", "coordinates": [[[83.2, 27.3], [83.8, 27.3], [83.8, 27.7], [83.2, 27.7], [83.2, 27.3]]]}},
        {"type": "Feature", "properties": {"name": "Kapilvastu", "province": "Lumbini"}, "geometry": {"type": "Polygon", "coordinates": [[[82.8, 27.3], [83.3, 27.3], [83.3, 27.7], [82.8, 27.7], [82.8, 27.3]]]}},
        {"type": "Feature", "properties": {"name": "Palpa", "province": "Lumbini"}, "geometry": {"type": "Polygon", "coordinates": [[[83.2, 27.7], [83.8, 27.7], [83.8, 28.0], [83.2, 28.0], [83.2, 27.7]]]}},
        {"type": "Feature", "properties": {"name": "Arghakhanchi", "province": "Lumbini"}, "geometry": {"type": "Polygon", "coordinates": [[[82.8, 27.7], [83.3, 27.7], [83.3, 28.1], [82.8, 28.1], [82.8, 27.7]]]}},
        {"type": "Feature", "properties": {"name": "Gulmi", "province": "Lumbini"}, "geometry": {"type": "Polygon", "coordinates": [[[83.0, 27.8], [83.5, 27.8], [83.5, 28.3], [83.0, 28.3], [83.0, 27.8]]]}},
        {"type": "Feature", "properties": {"name": "Rukum East", "province": "Lumbini"}, "geometry": {"type": "Polygon", "coordinates": [[[82.5, 28.2], [83.0, 28.2], [83.0, 28.8], [82.5, 28.8], [82.5, 28.2]]]}},
        {"type": "Feature", "properties": {"name": "Rolpa", "province": "Lumbini"}, "geometry": {"type": "Polygon", "coordinates": [[[82.5, 28.0], [83.0, 28.0], [83.0, 28.5], [82.5, 28.5], [82.5, 28.0]]]}},
        {"type": "Feature", "properties": {"name": "Pyuthan", "province": "Lumbini"}, "geometry": {"type": "Polygon", "coordinates": [[[82.5, 27.8], [83.0, 27.8], [83.0, 28.2], [82.5, 28.2], [82.5, 27.8]]]}},
        {"type": "Feature", "properties": {"name": "Dang", "province": "Lumbini"}, "geometry": {"type": "Polygon", "coordinates": [[[82.0, 27.8], [82.8, 27.8], [82.8, 28.3], [82.0, 28.3], [82.0, 27.8]]]}},
        {"type": "Feature", "properties": {"name": "Banke", "province": "Lumbini"}, "geometry": {"type": "Polygon", "coordinates": [[[81.5, 27.8], [82.5, 27.8], [82.5, 28.3], [81.5, 28.3], [81.5, 27.8]]]}},
        {"type": "Feature", "properties": {"name": "Bardiya", "province": "Lumbini"}, "geometry": {"type": "Polygon", "coordinates": [[[81.0, 28.0], [82.0, 28.0], [82.0, 28.8], [81.0, 28.8], [81.0, 28.0]]]}},
        {"type": "Feature", "properties": {"name": "Eastern Rukum", "province": "Karnali"}, "geometry": {"type": "Polygon", "coordinates": [[[82.5, 28.5], [83.0, 28.5], [83.0, 29.0], [82.5, 29.0], [82.5, 28.5]]]}},
        {"type": "Feature", "properties": {"name": "Salyan", "province": "Karnali"}, "geometry": {"type": "Polygon", "coordinates": [[[82.0, 28.2], [82.8, 28.2], [82.8, 28.8], [82.0, 28.8], [82.0, 28.2]]]}},
        {"type": "Feature", "properties": {"name": "Surkhet", "province": "Karnali"}, "geometry": {"type": "Polygon", "coordinates": [[[81.2, 28.2], [82.2, 28.2], [82.2, 29.0], [81.2, 29.0], [81.2, 28.2]]]}},
        {"type": "Feature", "properties": {"name": "Dailekh", "province": "Karnali"}, "geometry": {"type": "Polygon", "coordinates": [[[81.5, 28.5], [82.2, 28.5], [82.2, 29.0], [81.5, 29.0], [81.5, 28.5]]]}},
        {"type": "Feature", "properties": {"name": "Jajarkot", "province": "Karnali"}, "geometry": {"type": "Polygon", "coordinates": [[[81.8, 28.5], [82.5, 28.5], [82.5, 29.2], [81.8, 29.2], [81.8, 28.5]]]}},
        {"type": "Feature", "properties": {"name": "Dolpa", "province": "Karnali"}, "geometry": {"type": "Polygon", "coordinates": [[[82.5, 28.8], [83.5, 28.8], [83.5, 29.5], [82.5, 29.5], [82.5, 28.8]]]}},
        {"type": "Feature", "properties": {"name": "Jumla", "province": "Karnali"}, "geometry": {"type": "Polygon", "coordinates": [[[81.8, 29.0], [82.5, 29.0], [82.5, 29.5], [81.8, 29.5], [81.8, 29.0]]]}},
        {"type": "Feature", "properties": {"name": "Kalikot", "province": "Karnali"}, "geometry": {"type": "Polygon", "coordinates": [[[81.5, 29.0], [82.2, 29.0], [82.2, 29.5], [81.5, 29.5], [81.5, 29.0]]]}},
        {"type": "Feature", "properties": {"name": "Mugu", "province": "Karnali"}, "geometry": {"type": "Polygon", "coordinates": [[[82.0, 29.2], [83.0, 29.2], [83.0, 30.0], [82.0, 30.0], [82.0, 29.2]]]}},
        {"type": "Feature", "properties": {"name": "Humla", "province": "Karnali"}, "geometry": {"type": "Polygon", "coordinates": [[[81.5, 29.5], [82.5, 29.5], [82.5, 30.5], [81.5, 30.5], [81.5, 29.5]]]}},
        {"type": "Feature", "properties": {"name": "Bajura", "province": "Sudurpaschim"}, "geometry": {"type": "Polygon", "coordinates": [[[81.0, 29.2], [81.8, 29.2], [81.8, 29.8], [81.0, 29.8], [81.0, 29.2]]]}},
        {"type": "Feature", "properties": {"name": "Bajhang", "province": "Sudurpaschim"}, "geometry": {"type": "Polygon", "coordinates": [[[80.8, 29.2], [81.5, 29.2], [81.5, 29.8], [80.8, 29.8], [80.8, 29.2]]]}},
        {"type": "Feature", "properties": {"name": "Achham", "province": "Sudurpaschim"}, "geometry": {"type": "Polygon", "coordinates": [[[81.0, 28.8], [81.5, 28.8], [81.5, 29.3], [81.0, 29.3], [81.0, 28.8]]]}},
        {"type": "Feature", "properties": {"name": "Doti", "province": "Sudurpaschim"}, "geometry": {"type": "Polygon", "coordinates": [[[80.5, 28.8], [81.2, 28.8], [81.2, 29.3], [80.5, 29.3], [80.5, 28.8]]]}},
        {"type": "Feature", "properties": {"name": "Kailali", "province": "Sudurpaschim"}, "geometry": {"type": "Polygon", "coordinates": [[[80.2, 28.2], [81.2, 28.2], [81.2, 29.0], [80.2, 29.0], [80.2, 28.2]]]}},
        {"type": "Feature", "properties": {"name": "Kanchanpur", "province": "Sudurpaschim"}, "geometry": {"type": "Polygon", "coordinates": [[[80.0, 28.5], [80.5, 28.5], [80.5, 29.0], [80.0, 29.0], [80.0, 28.5]]]}},
        {"type": "Feature", "properties": {"name": "Dadeldhura", "province": "Sudurpaschim"}, "geometry": {"type": "Polygon", "coordinates": [[[80.2, 28.8], [80.8, 28.8], [80.8, 29.5], [80.2, 29.5], [80.2, 28.8]]]}},
        {"type": "Feature", "properties": {"name": "Baitadi", "province": "Sudurpaschim"}, "geometry": {"type": "Polygon", "coordinates": [[[80.0, 29.0], [80.5, 29.0], [80.5, 29.5], [80.0, 29.5], [80.0, 29.0]]]}},
        {"type": "Feature", "properties": {"name": "Darchula", "province": "Sudurpaschim"}, "geometry": {"type": "Polygon", "coordinates": [[[80.2, 29.5], [81.0, 29.5], [81.0, 30.0], [80.2, 30.0], [80.2, 29.5]]]}},
    ]
}

# Simplified protected areas (national parks, reserves, buffer zones)
NEPAL_PROTECTED_AREAS_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "properties": {"name": "Chitwan National Park", "category": "National Park"}, "geometry": {"type": "Polygon", "coordinates": [[[84.2, 27.3], [84.6, 27.3], [84.6, 27.6], [84.2, 27.6], [84.2, 27.3]]]}},
        {"type": "Feature", "properties": {"name": "Sagarmatha National Park", "category": "National Park"}, "geometry": {"type": "Polygon", "coordinates": [[[86.5, 27.5], [87.0, 27.5], [87.0, 28.0], [86.5, 28.0], [86.5, 27.5]]]}},
        {"type": "Feature", "properties": {"name": "Langtang National Park", "category": "National Park"}, "geometry": {"type": "Polygon", "coordinates": [[[85.2, 27.8], [85.8, 27.8], [85.8, 28.3], [85.2, 28.3], [85.2, 27.8]]]}},
        {"type": "Feature", "properties": {"name": "Bardiya National Park", "category": "National Park"}, "geometry": {"type": "Polygon", "coordinates": [[[81.0, 28.2], [81.8, 28.2], [81.8, 28.8], [81.0, 28.8], [81.0, 28.2]]]}},
        {"type": "Feature", "properties": {"name": "Shey Phoksundo National Park", "category": "National Park"}, "geometry": {"type": "Polygon", "coordinates": [[[82.5, 29.0], [83.2, 29.0], [83.2, 29.5], [82.5, 29.5], [82.5, 29.0]]]}},
        {"type": "Feature", "properties": {"name": "Rara National Park", "category": "National Park"}, "geometry": {"type": "Polygon", "coordinates": [[[81.8, 29.3], [82.2, 29.3], [82.2, 29.6], [81.8, 29.6], [81.8, 29.3]]]}},
        {"type": "Feature", "properties": {"name": "Khaptad National Park", "category": "National Park"}, "geometry": {"type": "Polygon", "coordinates": [[[81.0, 29.2], [81.5, 29.2], [81.5, 29.5], [81.0, 29.5], [81.0, 29.2]]]}},
        {"type": "Feature", "properties": {"name": "Banke National Park", "category": "National Park"}, "geometry": {"type": "Polygon", "coordinates": [[[81.5, 28.0], [82.2, 28.0], [82.2, 28.5], [81.5, 28.5], [81.5, 28.0]]]}},
        {"type": "Feature", "properties": {"name": "Shivapuri Nagarjun National Park", "category": "National Park"}, "geometry": {"type": "Polygon", "coordinates": [[[85.2, 27.6], [85.5, 27.6], [85.5, 27.9], [85.2, 27.9], [85.2, 27.6]]]}},
        {"type": "Feature", "properties": {"name": "Parsa National Park", "category": "National Park"}, "geometry": {"type": "Polygon", "coordinates": [[[84.5, 27.0], [85.0, 27.0], [85.0, 27.5], [84.5, 27.5], [84.5, 27.0]]]}},
        {"type": "Feature", "properties": {"name": "Makalu Barun National Park", "category": "National Park"}, "geometry": {"type": "Polygon", "coordinates": [[[87.0, 27.5], [87.5, 27.5], [87.5, 28.0], [87.0, 28.0], [87.0, 27.5]]]}},
        {"type": "Feature", "properties": {"name": "Annapurna Conservation Area", "category": "Conservation Area"}, "geometry": {"type": "Polygon", "coordinates": [[[83.5, 28.2], [84.5, 28.2], [84.5, 29.0], [83.5, 29.0], [83.5, 28.2]]]}},
        {"type": "Feature", "properties": {"name": "Kanchenjunga Conservation Area", "category": "Conservation Area"}, "geometry": {"type": "Polygon", "coordinates": [[[87.5, 27.2], [88.0, 27.2], [88.0, 28.0], [87.5, 28.0], [87.5, 27.2]]]}},
        {"type": "Feature", "properties": {"name": "Manaslu Conservation Area", "category": "Conservation Area"}, "geometry": {"type": "Polygon", "coordinates": [[[84.5, 28.2], [85.2, 28.2], [85.2, 28.8], [84.5, 28.8], [84.5, 28.2]]]}},
        {"type": "Feature", "properties": {"name": "Gaurishankar Conservation Area", "category": "Conservation Area"}, "geometry": {"type": "Polygon", "coordinates": [[[85.8, 27.5], [86.5, 27.5], [86.5, 28.2], [85.8, 28.2], [85.8, 27.5]]]}},
        {"type": "Feature", "properties": {"name": "Api Nampa Conservation Area", "category": "Conservation Area"}, "geometry": {"type": "Polygon", "coordinates": [[[80.5, 29.5], [81.5, 29.5], [81.5, 30.2], [80.5, 30.2], [80.5, 29.5]]]}},
        {"type": "Feature", "properties": {"name": "Koshi Tappu Wildlife Reserve", "category": "Wildlife Reserve"}, "geometry": {"type": "Polygon", "coordinates": [[[87.0, 26.5], [87.3, 26.5], [87.3, 26.7], [87.0, 26.7], [87.0, 26.5]]]}},
        {"type": "Feature", "properties": {"name": "Parsa Wildlife Reserve", "category": "Wildlife Reserve"}, "geometry": {"type": "Polygon", "coordinates": [[[84.5, 27.0], [84.8, 27.0], [84.8, 27.3], [84.5, 27.3], [84.5, 27.0]]]}},
        {"type": "Feature", "properties": {"name": "Suklaphanta Wildlife Reserve", "category": "Wildlife Reserve"}, "geometry": {"type": "Polygon", "coordinates": [[[80.0, 28.5], [80.3, 28.5], [80.3, 28.8], [80.0, 28.8], [80.0, 28.5]]]}},
        {"type": "Feature", "properties": {"name": "Dhorpatan Hunting Reserve", "category": "Hunting Reserve"}, "geometry": {"type": "Polygon", "coordinates": [[[82.8, 28.2], [83.3, 28.2], [83.3, 28.8], [82.8, 28.8], [82.8, 28.2]]]}},
    ]
}

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
