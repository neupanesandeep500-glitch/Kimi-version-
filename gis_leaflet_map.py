"""
gis_leaflet_map.py

Builds the self-contained interactive Leaflet map (sidebar filters +
province/district/local-body layers + protected-area/buffer/claimed-area
overlays + per-project popups) shown in the "GIS Map" tab.

This mirrors the design of the reference file the user supplied
(Nepal_Power_Project_GIS_Map.html), but instead of a frozen data snapshot
it is regenerated from the *live* workbook every time the tab is rendered,
using the real province/district/local-body/protected-area boundary
layers and the real per-project polygon-overlap percentages computed by
GISEngine.bbox_overlap_pct (see gis_area_methods logic folded into
data_engine.GISEngine).
"""

import json
import math

import coordinate_transform as ct
from gis_bundled import (
    NEPAL_PROVINCES_GEOJSON, NEPAL_DISTRICTS_GEOJSON, NEPAL_LOCALBODIES_GEOJSON,
    NEPAL_CLAIMED_AREA_GEOJSON, NEPAL_PROTECTED_AREAS_GEOJSON,
)

_BBOX_EPS = 0.0005  # matches GISEngine.bbox_overlap_pct's point fallback


def _bbox_wgs(rec):
    """Return (s, n, w, e) in WGS-84 for a record, falling back to a tiny
    box around lat/lon when no surveyed bbox is on file."""
    bbox = rec.get("bbox")
    if bbox and None not in bbox:
        lat1, lat2, lon1, lon2 = bbox
        s, n = sorted([lat1, lat2])
        w, e = sorted([lon1, lon2])
        if n - s < _BBOX_EPS:
            n = s + _BBOX_EPS
        if e - w < _BBOX_EPS:
            e = w + _BBOX_EPS
        return s, n, w, e
    lat, lon = rec.get("lat"), rec.get("lon")
    if lat is None or lon is None:
        return None
    return lat - _BBOX_EPS, lat + _BBOX_EPS, lon - _BBOX_EPS, lon + _BBOX_EPS


def _project_json(rec):
    bb = _bbox_wgs(rec)
    if bb is None:
        return None
    s, n, w, e = bb
    lat, lon = rec.get("lat"), rec.get("lon")
    if lat is None or lon is None:
        lat, lon = (s + n) / 2, (w + e) / 2

    ev_s, ev_w = ct.wgs84_to_everest(s, w)
    ev_n, ev_e = ct.wgs84_to_everest(n, e)

    return {
        "n": rec.get("project") or "Unnamed project",
        "pr": rec.get("promoter") or None,
        "ty": rec.get("type"),
        "st": rec.get("status"),
        "cap": rec.get("capacity_mw"),
        "cod": rec.get("cod_bs"),
        "iss": rec.get("license_year"),
        "prov": rec.get("province"),
        "provpct": rec.get("province_pct") or {},
        "distpct": rec.get("district_pct") or {},
        "lbpct": rec.get("local_pct") or [],
        "papct": rec.get("protected_pct") or {},
        "claimedpct": rec.get("claimed_pct") or {},
        "c": {"lat": round(lat, 6), "lon": round(lon, 6)},
        "bbox_wgs": {"s": round(s, 6), "n": round(n, 6), "w": round(w, 6), "e": round(e, 6)},
        "bbox_ev_dd": {"s": round(ev_s, 6), "n": round(ev_n, 6), "w": round(ev_w, 6), "e": round(ev_e, 6)},
        "bbox_ev_dms": {
            "s": ct.decimal_to_dms(ev_s), "n": ct.decimal_to_dms(ev_n),
            "w": ct.decimal_to_dms(ev_w), "e": ct.decimal_to_dms(ev_e),
        },
    }


def build_gis_map_html(records, status_colors, type_colors, province_colors, height_px=650):
    """Build the full standalone HTML for the interactive GIS map,
    populated with the current (already-filtered) set of records."""
    projects = [p for p in (_project_json(r) for r in records) if p is not None]

    stages = sorted({p["st"] for p in projects if p["st"]})
    types = sorted({p["ty"] for p in projects if p["ty"]})
    provs = sorted({p["prov"] for p in projects if p["prov"]})

    data_json = json.dumps({
        "PROVINCES_GEOJSON": NEPAL_PROVINCES_GEOJSON,
        "DISTRICTS_GEOJSON": NEPAL_DISTRICTS_GEOJSON,
        "LOCALS_GEOJSON": NEPAL_LOCALBODIES_GEOJSON,
        "CLAIMED_AREA_GEOJSON": NEPAL_CLAIMED_AREA_GEOJSON,
        "PA_GEOJSON": NEPAL_PROTECTED_AREAS_GEOJSON,
        "PROJECTS": projects,
        "STAGE_COLORS": status_colors,
        "TYPE_COLORS": type_colors,
        "PROV_COLORS": province_colors,
        "STAGES": stages,
        "TYPES": types,
        "PROVS": provs,
    })

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>DoED Nepal — Power Project GIS Map</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"/>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<style>
  :root{{
    --bg:#0f1720; --panel:#16212c; --panel2:#1c2a37; --border:#2a3a48;
    --text:#e7edf3; --muted:#93a4b3; --accent:#3aa6ff; --accent2:#ffb545;
  }}
  *{{box-sizing:border-box;}}
  html,body{{margin:0;height:100%;font-family:'Segoe UI',Arial,sans-serif;background:var(--bg);color:var(--text);}}
  #app{{display:flex;height:{height_px}px;}}
  #sidebar{{width:300px;min-width:300px;background:var(--panel);border-right:1px solid var(--border);
    overflow-y:auto;padding:12px;}}
  #sidebar h1{{font-size:14px;margin:0 0 2px;color:var(--text);}}
  #sidebar .sub{{font-size:10.5px;color:var(--muted);margin-bottom:12px;}}
  .section{{background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:9px 11px;margin-bottom:9px;}}
  .section h3{{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--accent);margin:0 0 7px;}}
  label.chk{{display:flex;align-items:center;gap:7px;font-size:12px;padding:3px 0;cursor:pointer;color:var(--text);}}
  label.chk input{{accent-color:var(--accent);}}
  .count{{margin-left:auto;color:var(--muted);font-size:10.5px;}}
  .swatch{{width:11px;height:11px;border-radius:3px;display:inline-block;flex:none;}}
  #stats{{font-size:11.5px;color:var(--muted);line-height:1.6;}}
  #stats b{{color:var(--text);}}
  button.small{{background:var(--panel);border:1px solid var(--border);color:var(--text);
    border-radius:5px;padding:4px 8px;font-size:11px;cursor:pointer;margin-right:6px;}}
  button.small:hover{{border-color:var(--accent);}}
  #map{{flex:1;background:#0a121a;}}
  .leaflet-popup-content-wrapper{{background:#182430;color:var(--text);border-radius:8px;}}
  .leaflet-popup-tip{{background:#182430;}}
  .pop{{font-size:12.5px;line-height:1.5;max-width:340px;}}
  .pop h4{{margin:0 0 6px;font-size:14px;color:var(--accent2);border-bottom:1px solid var(--border);padding-bottom:5px;}}
  .pop table{{border-collapse:collapse;width:100%;}}
  .pop td{{vertical-align:top;padding:1.5px 4px 1.5px 0;font-size:12px;}}
  .pop td.k{{color:var(--muted);white-space:nowrap;width:86px;}}
  .pop .tag{{display:inline-block;background:#233241;border:1px solid var(--border);border-radius:10px;
    padding:1px 7px;font-size:10.5px;margin:1px 3px 1px 0;color:var(--text);}}
  .pop .warn{{color:var(--accent2);font-size:10.5px;margin-top:5px;font-style:italic;}}
  .legend-row{{display:flex;align-items:center;gap:6px;font-size:11px;padding:2px 0;color:var(--muted);}}
  #search{{width:100%;padding:6px 8px;background:var(--panel);border:1px solid var(--border);
    border-radius:6px;color:var(--text);font-size:12px;margin-bottom:8px;}}
  ::-webkit-scrollbar{{width:8px;}} ::-webkit-scrollbar-thumb{{background:#2a3a48;border-radius:4px;}}
</style>
</head>
<body>
<div id="app">
  <div id="sidebar">
    <h1>⚡ Nepal Power Project GIS Map</h1>
    <div class="sub">DoED licensing pipeline · province &amp; protected-area overlay</div>

    <div class="section">
      <h3>Search</h3>
      <input id="search" placeholder="Project / promoter / district…"/>
    </div>

    <div class="section">
      <h3>License Stage</h3>
      <div id="stage-filters"></div>
    </div>

    <div class="section">
      <h3>Project Type</h3>
      <div id="type-filters"></div>
    </div>

    <div class="section">
      <h3>Province</h3>
      <div id="prov-filters"></div>
    </div>

    <div class="section">
      <h3>Coordinate System</h3>
      <label class="chk"><input type="radio" name="crs" value="wgs" checked> WGS-84 (map display)</label>
      <label class="chk"><input type="radio" name="crs" value="everest"> Everest 1830 (as surveyed)</label>
      <div class="warn" style="color:var(--muted);font-size:10.5px;margin-top:4px;">Both shown in popups regardless — this only affects which is emphasized.</div>
    </div>

    <div class="section">
      <h3>Layers</h3>
      <label class="chk"><input type="checkbox" id="toggle-choropleth" checked> Province choropleth</label>
      <label class="chk"><input type="checkbox" id="toggle-district" checked> District boundaries</label>
      <label class="chk"><input type="checkbox" id="toggle-local"> Local body boundaries (753)</label>
      <label class="chk"><input type="checkbox" id="toggle-pa" checked> Protected areas (core)</label>
      <label class="chk"><input type="checkbox" id="toggle-buffer" checked> Buffer zones (1st-stage protection)</label>
      <button class="small" id="btn-reset">Reset filters</button>
    </div>

    <div class="section">
      <h3>Summary</h3>
      <div id="stats"></div>
    </div>

    <div class="section" id="legend-section">
      <h3>Legend — project extent, by stage</h3>
      <div id="stage-legend"></div>
      <div class="legend-row" style="margin-top:6px;border-top:1px solid var(--border);padding-top:6px;"><span class="swatch" style="background:#e11d48;opacity:.55"></span> Protected area (core)</div>
      <div class="legend-row"><span class="swatch" style="background:#f59e0b;opacity:.35"></span> Buffer zone (1st-stage)</div>
    </div>
  </div>
  <div id="map"></div>
</div>

<script>
const DATA = {data_json};
</script>
<script>
const PROVINCES_GEOJSON = DATA.PROVINCES_GEOJSON;
const DISTRICTS_GEOJSON = DATA.DISTRICTS_GEOJSON;
const LOCALS_GEOJSON = DATA.LOCALS_GEOJSON;
const CLAIMED_AREA_GEOJSON = DATA.CLAIMED_AREA_GEOJSON;
const PA_GEOJSON = DATA.PA_GEOJSON;
const PROJECTS = DATA.PROJECTS;
const STAGE_COLORS = DATA.STAGE_COLORS;
const PROV_COLORS = DATA.PROV_COLORS;
const STAGES = DATA.STAGES;
const TYPES = DATA.TYPES;
const PROVS = DATA.PROVS;

const state = {{ stage:new Set(STAGES), type:new Set(TYPES), prov:new Set(PROVS), q:"" }};

// ---------- map ----------
const map = L.map('map', {{preferCanvas:true}}).setView([28.3,84.0], 7);
L.tileLayer('https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
  attribution:'&copy; OpenStreetMap &copy; CARTO', maxZoom:18, subdomains:'abcd'
}}).addTo(map);

// province choropleth
const provinceLayer = L.geoJSON(PROVINCES_GEOJSON, {{
  style: f => ({{ color: PROV_COLORS[f.properties.name]||'#888', weight:1.6,
                 fillColor: PROV_COLORS[f.properties.name]||'#888', fillOpacity:0.09 }}),
  onEachFeature: (f, layer) => layer.bindTooltip(f.properties.name, {{sticky:true}})
}}).addTo(map);

// district boundaries (outline only)
const districtLayer = L.geoJSON(DISTRICTS_GEOJSON, {{
  style: () => ({{ color:'#9fb3c8', weight:0.8, fillOpacity:0, opacity:0.55 }}),
  onEachFeature: (f, layer) => layer.bindTooltip(`${{f.properties.name}} district (${{f.properties.province}})`, {{sticky:true}})
}}).addTo(map);

// local body boundaries (outline only, off by default)
const localLayer = L.geoJSON(LOCALS_GEOJSON, {{
  style: f => ({{ color: f.properties.type && f.properties.type.includes('Rural') ? '#7dd3fc' : '#fbbf24',
                 weight:0.6, fillOpacity:0, opacity:0.6 }}),
  onEachFeature: (f, layer) => layer.bindTooltip(`${{f.properties.name}} — ${{f.properties.type}}<br>${{f.properties.district}} (${{f.properties.province}})`, {{sticky:true}})
}});

// disputed/claimed area (Limpiyadhura-Kalapani-Lipulekh, per Nepal's 2020 official map)
// Rendered on the map exactly as the other boundary layers are — no hover text.
const claimedLayer = L.geoJSON(CLAIMED_AREA_GEOJSON, {{
  style: () => ({{ color:'#22d3ee', weight:2, dashArray:'6,4', fillColor:'#22d3ee', fillOpacity:0.22 }})
}}).addTo(map);
const coreFeatures = PA_GEOJSON.features.filter(f => f.properties.category !== "Buffer Zone");
const bufferFeatures = PA_GEOJSON.features.filter(f => f.properties.category === "Buffer Zone");

const paCoreLayer = L.geoJSON({{type:"FeatureCollection", features: coreFeatures}}, {{
  style: () => ({{ color:'#e11d48', weight:1, fillColor:'#e11d48', fillOpacity:0.32 }}),
  onEachFeature: (f, layer) => layer.bindTooltip(`${{f.properties.name}} (${{f.properties.category}})`, {{sticky:true}})
}}).addTo(map);

const paBufferLayer = L.geoJSON({{type:"FeatureCollection", features: bufferFeatures}}, {{
  style: () => ({{ color:'#f59e0b', weight:1, dashArray:'4,3', fillColor:'#f59e0b', fillOpacity:0.16 }}),
  onEachFeature: (f, layer) => layer.bindTooltip(`${{f.properties.name}} — 1st-stage buffer`, {{sticky:true}})
}}).addTo(map);

// ---------- project polygons (project's surveyed extent, colored by stage) ----------
const markerLayer = L.layerGroup().addTo(map);
const markers = [];

function fmtPct(obj){{
  const keys = Object.keys(obj||{{}});
  if(!keys.length) return '<span style="color:var(--muted)">none</span>';
  return keys.map(k=>`<span class="tag">${{k}}: ${{obj[k]}}%</span>`).join(' ');
}}
function fmtLB(list){{
  if(!list || !list.length) return '<span style="color:var(--muted)">—</span>';
  return list.map(l=>`<span class="tag">${{l.name}} (${{l.type}}, ${{l.district}}): ${{l.pct}}%</span>`).join(' ');
}}
function popupHtml(p){{
  return `<div class="pop">
    <h4>${{p.n}}</h4>
    <table>
      <tr><td class="k">Promoter</td><td>${{p.pr||'—'}}</td></tr>
      <tr><td class="k">Type</td><td>${{p.ty||'—'}}</td></tr>
      <tr><td class="k">Stage</td><td>${{p.st||'—'}}</td></tr>
      <tr><td class="k">Capacity</td><td>${{p.cap!=null?p.cap+' MW':'—'}}</td></tr>
      <tr><td class="k">License Year / COD (BS)</td><td>${{p.iss||'—'}}${{p.cod?(' · COD '+p.cod):''}}</td></tr>
      <tr><td class="k">Province(s)</td><td>${{fmtPct(p.provpct)}}</td></tr>
      <tr><td class="k">District(s)</td><td>${{fmtPct(p.distpct)}}</td></tr>
      <tr><td class="k">Local Body(s)</td><td>${{fmtLB(p.lbpct)}}</td></tr>
      <tr><td class="k">Protected Zone</td><td>${{fmtPct(p.papct)}}</td></tr>
      <tr><td class="k">Centroid WGS-84</td><td>${{p.c.lat}}, ${{p.c.lon}}</td></tr>
      <tr><td class="k">Extent WGS-84</td><td>${{p.bbox_wgs.s}}–${{p.bbox_wgs.n}} N, ${{p.bbox_wgs.w}}–${{p.bbox_wgs.e}} E</td></tr>
      <tr><td class="k">Extent Everest</td><td>${{p.bbox_ev_dms.s}}–${{p.bbox_ev_dms.n}} N, ${{p.bbox_ev_dms.w}}–${{p.bbox_ev_dms.e}} E<br>(${{p.bbox_ev_dd.s}}–${{p.bbox_ev_dd.n}}, ${{p.bbox_ev_dd.w}}–${{p.bbox_ev_dd.e}} dd)</td></tr>
    </table>
    <div class="warn">Province / District / Local Body % are real polygon-overlay results (project's surveyed license extent vs the official province → district → local-body boundary hierarchy).</div>
  </div>`;
}}

PROJECTS.forEach(p=>{{
  const b = p.bbox_wgs;
  const bounds = [[b.s, b.w],[b.n, b.e]];
  const color = STAGE_COLORS[p.st] || '#ccc';
  const rect = L.rectangle(bounds, {{ color:'#0b131a', weight:1, fillColor: color, fillOpacity:0.55 }});
  rect.bindPopup(()=>popupHtml(p));
  rect.bindTooltip(p.n, {{sticky:true}});
  rect._proj = p;
  markers.push(rect);
}});

function applyFilters(){{
  markerLayer.clearLayers();
  let shown=0, cap=0;
  const q = state.q.trim().toLowerCase();
  markers.forEach(m=>{{
    const p = m._proj;
    let ok = state.stage.has(p.st) && state.type.has(p.ty) && (p.prov ? state.prov.has(p.prov) : true);
    if(ok && q){{
      const lbNames = (p.lbpct||[]).map(l=>l.name).join(' ');
      const distNames = Object.keys(p.distpct||{{}}).join(' ');
      const hay = (p.n+' '+(p.pr||'')+' '+distNames+' '+lbNames).toLowerCase();
      ok = hay.includes(q);
    }}
    if(ok){{ markerLayer.addLayer(m); shown++; cap += (p.cap||0); }}
  }});
  document.getElementById('stats').innerHTML =
    `Showing <b>${{shown}}</b> / ${{PROJECTS.length}} projects<br>`+
    `Total capacity shown: <b>${{cap.toFixed(1)}} MW</b><br>`+
    `Protected-zone overlap: <b>${{markers.filter(m=>markerLayer.hasLayer(m)&&Object.keys(m._proj.papct||{{}}).length).length}}</b> project(s)`;
}}

// ---------- filter UI ----------
function buildChecklist(containerId, items, stateSet, colorMap){{
  const el = document.getElementById(containerId);
  el.innerHTML = items.map(it=>{{
    const count = PROJECTS.filter(p=>{{
      if(containerId==='stage-filters') return p.st===it;
      if(containerId==='type-filters') return p.ty===it;
      return p.prov===it;
    }}).length;
    const sw = colorMap && colorMap[it] ? `<span class="swatch" style="background:${{colorMap[it]}}"></span>` : '';
    return `<label class="chk"><input type="checkbox" data-v="${{it}}" checked>${{sw}}${{it}}<span class="count">${{count}}</span></label>`;
  }}).join('');
  el.querySelectorAll('input').forEach(inp=>{{
    inp.addEventListener('change', ()=>{{
      const v = inp.getAttribute('data-v');
      if(inp.checked) stateSet.add(v); else stateSet.delete(v);
      applyFilters();
    }});
  }});
}}
buildChecklist('stage-filters', STAGES, state.stage, STAGE_COLORS);
buildChecklist('type-filters', TYPES, state.type);
buildChecklist('prov-filters', PROVS, state.prov, PROV_COLORS);

document.getElementById('stage-legend').innerHTML = STAGES.map(s=>
  `<div class="legend-row"><span class="swatch" style="background:${{STAGE_COLORS[s]||'#ccc'}}"></span> ${{s}}</div>`
).join('');

document.getElementById('search').addEventListener('input', e=>{{ state.q = e.target.value; applyFilters(); }});
document.getElementById('btn-reset').addEventListener('click', ()=>{{
  state.stage = new Set(STAGES); state.type = new Set(TYPES); state.prov = new Set(PROVS); state.q="";
  document.getElementById('search').value="";
  document.querySelectorAll('#sidebar input[type=checkbox][data-v]').forEach(c=>c.checked=true);
  applyFilters();
}});
document.getElementById('toggle-choropleth').addEventListener('change', e=>{{
  if(e.target.checked) provinceLayer.addTo(map); else map.removeLayer(provinceLayer);
}});
document.getElementById('toggle-district').addEventListener('change', e=>{{
  if(e.target.checked) districtLayer.addTo(map); else map.removeLayer(districtLayer);
}});
document.getElementById('toggle-local').addEventListener('change', e=>{{
  if(e.target.checked) localLayer.addTo(map); else map.removeLayer(localLayer);
}});
document.getElementById('toggle-pa').addEventListener('change', e=>{{
  if(e.target.checked) paCoreLayer.addTo(map); else map.removeLayer(paCoreLayer);
}});
document.getElementById('toggle-buffer').addEventListener('change', e=>{{
  if(e.target.checked) paBufferLayer.addTo(map); else map.removeLayer(paBufferLayer);
}});

applyFilters();
</script>
</body>
</html>
"""
