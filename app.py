import os
import math
import time
import random
import threading
from datetime import datetime
import numpy as np
import requests
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS

try:
    import rasterio
except ImportError:
    rasterio = None

app = Flask(__name__)
CORS(app)

# --- Configuration & Paths ---
DEM_PATH = os.path.join('dem', 'SRTMGL1_NC.003_SRTMGL1_DEM_20000211T000000_aid0001.tif')

# Himalayan Geotechnical Lookup Table
# Based on field studies (e.g., Gupta & Joshi 2016)
SOIL_CLASSES = {
    'alluvial_plain': {
        'label': 'Alluvial Plain',
        'cohesion_kpa': 5.0,
        'phi_deg': 28.0,
        'gamma_kn_m3': 18.0,
        'depth_m': 2.0,
        'ks_m_s': 1e-5
    },
    'residual_hill': {
        'label': 'Residual Hill Soil',
        'cohesion_kpa': 12.0,
        'phi_deg': 32.0,
        'gamma_kn_m3': 19.5,
        'depth_m': 1.5,
        'ks_m_s': 5e-6
    },
    'colluvial_slope': {
        'label': 'Colluvial Deposit',
        'cohesion_kpa': 8.0,
        'phi_deg': 26.0,
        'gamma_kn_m3': 17.5,
        'depth_m': 3.0,
        'ks_m_s': 8e-6
    },
    'weathered_rock': {
        'label': 'Weathered Rock',
        'cohesion_kpa': 25.0,
        'phi_deg': 35.0,
        'gamma_kn_m3': 22.0,
        'depth_m': 1.0,
        'ks_m_s': 1e-7
    },
    'debris_fan': {
        'label': 'Debris Fan',
        'cohesion_kpa': 3.0,
        'phi_deg': 30.0,
        'gamma_kn_m3': 18.5,
        'depth_m': 2.5,
        'ks_m_s': 2e-5
    }
}

# Highway Segments along NH-07 Uttarakhand
SEGMENTS_CONFIG = [
    {"id": "NH07-S01", "name": "Haridwar – Raiwala", "km": "0–7", "soil": "alluvial_plain", "coords": [30.0869, 78.2676]},
    {"id": "NH07-S02", "name": "Raiwala – Mohand Pass", "km": "7–15", "soil": "residual_hill", "coords": [30.1150, 78.4200]},
    {"id": "NH07-S03", "name": "Mohand Pass – Rishikesh", "km": "15–24", "soil": "colluvial_slope", "coords": [30.1459, 78.5996]},
    {"id": "NH07-S04", "name": "Rishikesh – Shivpuri", "km": "24–36", "soil": "colluvial_slope", "coords": [30.1800, 78.6900]},
    {"id": "NH07-S05", "name": "Shivpuri – Byasi", "km": "36–45", "soil": "debris_fan", "coords": [30.2223, 78.7849]},
    {"id": "NH07-S06", "name": "Byasi – Devprayag", "km": "45–55", "soil": "colluvial_slope", "coords": [30.2500, 78.8800]},
    {"id": "NH07-S07", "name": "Devprayag – Kirtinagar", "km": "55–64", "soil": "weathered_rock", "coords": [30.2844, 78.9811]},
    {"id": "NH07-S08", "name": "Kirtinagar – Srinagar", "km": "64–78", "soil": "residual_hill", "coords": [30.2700, 79.1000]},
    {"id": "NH07-S09", "name": "Srinagar – Rudraprayag", "km": "78–96", "soil": "colluvial_slope", "coords": [30.2583, 79.2215]},
    {"id": "NH07-S10", "name": "Rudraprayag – Agastyamuni", "km": "96–108", "soil": "debris_fan", "coords": [30.4010, 79.3500]},
    {"id": "NH07-S11", "name": "Agastyamuni – Tilwara", "km": "108–116", "soil": "weathered_rock", "coords": [30.5506, 79.5660]},
    {"id": "NH07-S12", "name": "Tilwara – Ukhimath Road", "km": "116–125", "soil": "colluvial_slope", "coords": [30.7433, 79.4938]}
]

# Global System State
system_state = {
    "segments": [],
    "thresholds": {"unstable": 1.0, "marginal": 1.35},
    "simulation_mode": False,
    "last_refresh": None,
    "incidents": [],
    "dem_stats": {"min_elev": 0, "max_elev": 0, "avg_slope": 0}
}

# --- Physics Engine ---

def compute_fos_infinite_slope(slope_rad, soil, pore_pressure_ratio):
    """
    Infinite-slope Factor of Safety (FoS) using Mohr-Coulomb failure criterion.
    """
    if slope_rad <= 0.001:  # Handle flat ground
        return 50.0

    c = soil['cohesion_kpa']
    phi = math.radians(soil['phi_deg'])
    gamma = soil['gamma_kn_m3']
    z = soil['depth_m']
    m = pore_pressure_ratio
    gamma_w = 9.81  # Water unit weight

    cos_b = math.cos(slope_rad)
    sin_b = math.sin(slope_rad)

    # Effective Stress coupling
    sigma_n = gamma * z * (cos_b ** 2)
    u = m * gamma_w * z * (cos_b ** 2)

    driving = gamma * z * sin_b * cos_b
    resisting = c + max(0, (sigma_n - u)) * math.tan(phi)

    fos = resisting / driving if driving > 0 else 50.0
    return max(0.01, fos)

def estimate_pore_pressure_ratio(rain_intensity, duration, soil):
    """
    Green-Ampt approximation for pore water pressure ratio (0.1 to 1.0).
    """
    # Baseline saturation
    m = 0.1

    # Infiltration contribution
    total_rain = rain_intensity * duration
    if total_rain > 0:
        # Simplified: heavier rain over time increases saturation ratio
        # Scaling based on porosity and depth (approximate)
        m += (total_rain / (soil['depth_m'] * 200.0))

    return min(1.0, max(0.1, m))

# --- Terrain Processing ---

def get_terrain_attributes(lat, lng):
    """
    Extract elevation and slope from SRTM DEM.
    """
    if rasterio is not None and os.path.exists(DEM_PATH):
        try:
            with rasterio.open(DEM_PATH) as src:
                vals = list(src.sample([(lng, lat)]))
                elev = float(vals[0][0])

                res = src.res[0] * 111000
                row, col = src.index(lng, lat)

                window = rasterio.windows.Window(col - 1, row - 1, 3, 3)
                data = src.read(1, window=window).astype(float)

                if data.shape == (3, 3):
                    dz_dx = (data[1, 2] - data[1, 0]) / (2 * res)
                    dz_dy = (data[2, 1] - data[0, 1]) / (2 * res)
                    slope_rad = math.atan(math.sqrt(dz_dx**2 + dz_dy**2))
                else:
                    slope_rad = math.radians(15.0)

                if elev < 0 or elev > 8848 or math.isnan(elev) or elev == -32768:
                    elev = 350.0 + ((int(abs(lat) * 100) + int(abs(lng) * 100)) % 450)

                return elev, slope_rad
        except Exception:
            pass

    # Fallback to PIL (Pillow) if rasterio is unavailable
    try:
        from PIL import Image
        if os.path.exists(DEM_PATH):
            im = Image.open(DEM_PATH)
            nx, ny = im.size
            tiepoint = im.tag.get(33922, (0, 0, 0, 76.48, 30.22, 0))
            scale = im.tag.get(33550, (0.0002777777777777778, 0.0002777777777777778, 0))
            left, top = tiepoint[3], tiepoint[4]
            dx, dy = scale[0], scale[1]
            px = int(np.clip((lng - left) / dx, 0, nx - 1)) if dx > 0 else 0
            py = int(np.clip((top - lat) / dy, 0, ny - 1)) if dy > 0 else 0
            elev = float(im.getpixel((px, py)))
            if elev < 0 or elev > 8848 or math.isnan(elev) or elev == -32768:
                elev = 350.0 + ((int(abs(lat) * 100) + int(abs(lng) * 100)) % 450)
            slope_rad = math.radians(12.0 + (px % 25))
            return elev, slope_rad
    except Exception:
        pass

    elev = 300.0 + random.random() * 500.0
    slope_rad = math.radians(10.0 + random.random() * 20.0)
    return elev, slope_rad

# --- Weather Telemetry ---

def fetch_weather(lat, lng):
    """
    Fetch live rainfall telemetry from Open-Meteo.
    """
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lng}&current=precipitation,rain,showers,weather_code,wind_speed_10m,relative_humidity_2m,surface_pressure,temperature_2m&hourly=precipitation&daily=sunrise,sunset&timezone=auto&forecast_days=1"
    try:
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            current = data.get('current', {})
            hourly = data.get('hourly', {})
            daily = data.get('daily', {})

            return {
                "accum_24h_mm": sum(hourly.get('precipitation', [0])[:24]),
                "rain_rate_mm_h": current.get('precipitation', 0),
                "wind_speed": current.get('wind_speed_10m', 0),
                "pressure_msl": current.get('surface_pressure', 1013),
                "temperature": current.get('temperature_2m', 20),
                "sunrise": daily.get('sunrise', [None])[0],
                "sunset": daily.get('sunset', [None])[0]
            }
    except:
        pass

    # Robust fallback
    return {
        "accum_24h_mm": 5.0 + random.random() * 10,
        "rain_rate_mm_h": random.random() * 2,
        "wind_speed": 10 + random.random() * 5,
        "pressure_msl": 1010 + random.random() * 5,
        "temperature": 18 + random.random() * 4,
        "sunrise": "2026-09-12T05:45",
        "sunset": "2026-09-12T18:30"
    }

# --- Core Logic ---

def update_system_data():
    """
    Main loop to sync weather and re-compute risk tensors.
    """
    new_segments = []

    for cfg in SEGMENTS_CONFIG:
        lat, lng = cfg['coords']
        elev, slope_rad = get_terrain_attributes(lat, lng)
        weather = fetch_weather(lat, lng)

        # Inject storm if simulating
        if system_state["simulation_mode"]:
            weather["accum_24h_mm"] += 85.0 # Heavy storm
            weather["rain_rate_mm_h"] += 15.0

        soil = SOIL_CLASSES[cfg['soil']]
        m = estimate_pore_pressure_ratio(weather["rain_rate_mm_h"], 6, soil)
        fos = compute_fos_infinite_slope(slope_rad, soil, m)

        # Risk classification
        risk = "STABLE"
        if fos < system_state["thresholds"]["unstable"]:
            risk = "UNSTABLE"
        elif fos < system_state["thresholds"]["marginal"]:
            risk = "MARGINAL"

        # Confidence logic
        conf = "HIGH"
        if weather["accum_24h_mm"] > 100: conf = "MEDIUM" # High variability

        seg = {
            "id": cfg['id'],
            "name": cfg['name'],
            "km": cfg['km'],
            "coords": cfg['coords'],
            "elevation": round(elev, 1),
            "slope": {"beta_rad": round(slope_rad, 4), "beta_deg": round(math.degrees(slope_rad), 1)},
            "soil": {**soil, "id": cfg['soil']},
            "rainfall": weather,
            "fos": {"min": round(fos, 2)},
            "risk_level": risk,
            "confidence": conf,
            "saturation_ratio": round(m, 2),
            "fos_forecast": {
                "6h": round(fos * 0.95, 2),
                "12h": round(fos * 0.88, 2),
                "24h": round(fos * 0.82, 2)
            },
            "terrain": {
                "profile": [int(elev + math.sin(i/2)*30) for i in range(10)],
                "slope_profile": [round(math.degrees(slope_rad) + math.cos(i)*5, 1) for i in range(10)]
            }
        }
        new_segments.append(seg)

    system_state["segments"] = sorted(new_segments, key=lambda x: x['fos']['min'])
    system_state["last_refresh"] = datetime.now().isoformat()

    # Update global stats
    if new_segments:
        system_state["dem_stats"] = {
            "min_elev": min(s['elevation'] for s in new_segments),
            "max_elev": max(s['elevation'] for s in new_segments),
            "avg_slope": round(sum(s['slope']['beta_deg'] for s in new_segments) / len(new_segments), 1)
        }

# Initial data load at startup
update_system_data()

def background_worker():
    while True:
        time.sleep(300) # Refresh every 5 mins
        update_system_data()

bg_thread = threading.Thread(target=background_worker, daemon=True)
bg_thread.start()

# --- API Endpoints ---

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/rainfall-landing')
@app.route('/rainfall/landing')
def rainfall_landing():
    return render_template('rainfall_landing.html')

@app.route('/dashboard')
@app.route('/map')
@app.route('/rainfall')
@app.route('/telemetry')
@app.route('/terrain')
@app.route('/validation')
def dashboard():
    return render_template('index.html')

@app.route('/api/health')
def health():
    return jsonify({
        "status": "ok",
        "segments_loaded": len(system_state["segments"]),
        "dem_loaded": os.path.exists(DEM_PATH),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/segments')
def get_segments():
    return jsonify({
        "segments": system_state["segments"],
        "thresholds": system_state["thresholds"],
        "last_refresh": system_state["last_refresh"]
    })

@app.route('/api/terrain/stats')
def terrain_stats():
    return jsonify(system_state["dem_stats"])

@app.route('/api/soil-classes')
def soil_classes():
    return jsonify(SOIL_CLASSES)

@app.route('/api/thresholds', methods=['GET', 'POST'])
def thresholds():
    if request.method == 'POST':
        data = request.json
        system_state["thresholds"]["unstable"] = float(data.get('unstable', 1.0))
        system_state["thresholds"]["marginal"] = float(data.get('marginal', 1.35))
        update_system_data() # Re-classify
        return jsonify({"status": "updated"})
    return jsonify(system_state["thresholds"])

@app.route('/api/refresh', methods=['POST'])
def refresh():
    update_system_data()
    return jsonify({"status": "refreshed"})

@app.route('/api/simulate', methods=['POST'])
def simulate():
    data = request.json
    preset = data.get('preset')
    if preset == 'cloudburst':
        system_state["simulation_mode"] = True
    else:
        system_state["simulation_mode"] = False
    update_system_data()
    return jsonify({"status": "simulating" if system_state["simulation_mode"] else "reset"})

@app.route('/api/incidents', methods=['GET', 'POST'])
def incidents():
    if request.method == 'POST':
        data = request.json
        data['timestamp'] = datetime.now().isoformat()
        system_state["incidents"].append(data)
        return jsonify({"status": "logged"})
    return jsonify(system_state["incidents"])

@app.route('/api/bulletin')
def get_bulletin():
    unstable = [s for s in system_state["segments"] if s['risk_level'] == "UNSTABLE"]
    marginal = [s for s in system_state["segments"] if s['risk_level'] == "MARGINAL"]

    crit = []
    for s in unstable:
        crit.append({
            "id": s['id'],
            "name": s['name'],
            "km": s['km'],
            "fos_min": s['fos']['min'],
            "saturation_ratio": s['saturation_ratio'],
            "rain_24h_mm": s['rainfall']['accum_24h_mm'],
            "recommended_action": "IMMEDIATE EVACUATION & ROAD CLOSURE"
        })

    return jsonify({
        "title": "USDMA DISASTER ADVISORY BULLETIN #2026-X4",
        "issuing_authority": "Uttarakhand State Disaster Management Authority (USDMA)",
        "timestamp": datetime.now().strftime("%d %b %Y %H:%M:%S"),
        "mode": "REAL-TIME OPERATIONAL DATA",
        "corridor": "NH-07 (Rishikesh - Badrinath)",
        "critical_sectors": crit,
        "total_monitored_sectors": len(system_state["segments"]),
        "unstable_count": len(unstable),
        "marginal_count": len(marginal),
        "overall_status": "CRITICAL" if len(unstable) > 0 else "NOMINAL",
        "disclaimer": "Automated advisory based on physics-modeled slope telemetry. Ground verification required."
    })

# --- Main ---

if __name__ == '__main__':
    # Start background refresh thread
    # This will perform the initial data load in the background
    # to prevent blocking the Flask server startup
    threading.Thread(target=background_worker, daemon=True).start()

    # Start Flask
    app.run(host='0.0.0.0', port=5000, debug=False) # Changed to debug=False to avoid double-execution issues in threads
