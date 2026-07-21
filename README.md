# Kimi-version-
Nepal Power Plant & Transmission Line License Status Dashboard
A fully self-contained web dashboard for visualizing Nepal’s power plant and transmission line license data.
Key Features
•	Zero-config GIS: Nepal district/province boundaries and protected areas are bundled inline — no shapefile uploads or Drive syncs needed
•	Admin panel at /admin for uploading workbooks, syncing Google Sheets, and managing settings
•	9 dashboard tabs: Overview, Power Plants, Transmission Lines, GoN Studied, Cancelled, Growth, GIS Map, Compare, Data Table
•	Live ticker with KPIs and latest connections
•	PDF report generation
•	Visitor counter and live clock
Quick Start
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run locally
python app.py

# 3. Open browser to http://localhost:8050
Environment Variables (optional)
Variable	Description
DEFAULT_SHEET_URL	Google Sheet URL/ID to auto-sync on startup
DEFAULT_GIS_DRIVE_URL	Google Drive link for high-res GIS zip (optional)
DEFAULT_PA_DRIVE_URL	Google Drive link for protected areas zip (optional)
ADMIN_PASSWORD	Password for /admin panel (default: admin123)
FLASK_SECRET_KEY	Session encryption key
DATA_DIR	Path to persistent data storage
AUTO_REFRESH_HOURS	Background refresh interval (default: 6)
File Structure
.
├── app.py                  # Main Dash application
├── data_engine.py          # Data loading, GIS engine, B.S. calendar helpers
├── server_state.py         # Shared state, config persistence, background refresh
├── coordinate_transform.py # WGS-84 / Everest 1830 conversions
├── admin.py                # Admin panel blueprint
├── gis_bundled.py          # Inline Nepal GIS data (districts + protected areas)
├── nepal_flag.png          # Default flag image
├── requirements.txt        # Python dependencies
└── data/                   # Created at runtime (workbooks, uploads, config)
Adding Project Data
Option 1: Upload via Admin Panel
1.	Go to /admin/login (default password: admin123)
2.	Upload an .xlsx workbook with columns like:
–	project_name, type, status, capacity_mw, voltage_kv, line_length_km
–	district, province, promoter, latitude, longitude
–	license_date, cod (commercial operation date in B.S.)
Option 2: Google Sheet Sync
1.	Share your Google Sheet as “Anyone with the link”
2.	Paste the URL in the admin panel or set DEFAULT_SHEET_URL
Option 3: Local File
Place workbook.xlsx in the data/ folder before starting.
GIS Data
The bundled GIS data in gis_bundled.py contains simplified boundaries for all 77 Nepal districts and major protected areas. This is sufficient for choropleth shading and spatial queries.
To use higher-resolution boundaries: 1. Obtain shapefiles from Nepal Survey Department 2. Simplify with mapshaper: mapshaper -i input.shp -simplify 10% -o output.shp 3. Upload via admin panel or set DEFAULT_GIS_DRIVE_URL
Deployment
Render (Recommended)
1.	Push to GitHub
2.	Create new Web Service on Render
3.	Set build command: pip install -r requirements.txt
4.	Set start command: gunicorn app:server
5.	Add environment variables as needed
Docker
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "app:server", "--bind", "0.0.0.0:8050"]
License
© 2026 Er. Sandeep Neupane. All rights reserved.
