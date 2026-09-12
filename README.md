# 🛡️ JANRAKSHAK — Highway Landslide Early Warning System

> **Physics-Based Slope Stability + Live Rainfall for NH-07 Uttarakhand**  
> Geospatial Predictive Intelligence | COGNITIA 2026
LIVE-https://janrakshak-cognitia.vercel.app/
[![CI/CD Pipeline](https://github.com/<your-username>/janrakshak/actions/workflows/deploy.yml/badge.svg)](https://github.com/<your-username>/janrakshak/actions)

---

## 🎯 Overview & Key Features

**JANRAKSHAK** identifies high-risk road segments on NH-07 (Haridwar–Rishikesh–Badrinath corridor) by combining:

1. **NASA SRTM 30m DEM Processing**: Calculates elevation, slope angle ($\beta$), aspect ($\alpha$), and terrain profile curvature using finite differences.
2. **Infinite-Slope Stability Physics Engine**: Computes the Factor of Safety ($\text{FoS}$) based on Mohr-Coulomb shear strength parameters.
3. **Hydrological Pore-Water Pressure Coupling**: Integrates live Open-Meteo precipitation intensity, duration, and 24h accumulated rainfall using a Green-Ampt infiltration model.
4. **24-Hour Predictive Forecasting**: Predicts future Factor of Safety trends ($+6\text{h}, +12\text{h}, +24\text{h}$) using Open-Meteo hourly forecast models.
5. **Interactive SatCom Dashboard & Tactical 3D Engine**: Features Leaflet satellite map tiles, draggable geospatial probe, interactive WebGL 3D terrain analysis, live alert marquee ticker, and threshold sliders.
6. **Extreme Event Cloudburst Simulation**: Interactive cloudburst simulation mode ($110\,\text{mm/hr}$ downpour) with audio synthesis to test real-time warning cascades.
7. **USDMA Emergency Warning Advisory Exporter**: Generates official geohazard advisories for District Control Room operators.

---

## 📐 Physics Models & Mathematical Formulas

JANRAKSHAK utilizes rigorous, physically grounded geotechnical and hydrological equations rather than heuristic scoring:

### 1. Mohr-Coulomb Failure Criterion & Infinite-Slope Model

The **Factor of Safety ($\text{FoS}$)** represents the ratio of shear resistance ($\tau_{\text{resist}}$) to driving shear stress ($\tau_{\text{drive}}$) along a potential planar failure surface at soil depth $z$:

$$\text{FoS} = \frac{\tau_{\text{resist}}}{\tau_{\text{drive}}} = \frac{c' + (\sigma_n - u) \tan\phi'}{\gamma \cdot z \cdot \sin\beta \cdot \cos\beta}$$

$$\sigma_n = \gamma \cdot z \cdot \cos^2\beta$$

Where:
- **$c'$** = Effective Cohesion ($\text{kPa}$) — retrieved from geotechnical soil lookup
- **$\phi'$** = Effective Internal Friction Angle ($\text{degrees}$)
- **$\gamma$** = Moist Unit Weight of Soil ($\text{kN/m}^3$)
- **$z$** = Soil Layer Thickness / Depth ($\text{m}$)
- **$\beta$** = Slope Angle ($\text{radians}$, derived from NASA SRTM 30m DEM)
- **$\sigma_n$** = Total Normal Stress on the failure plane ($\text{kPa}$)
- **$u$** = Pore-Water Pressure ($\text{kPa}$)

### 2. Pore-Water Pressure & Green-Ampt Infiltration Coupling

Rainfall infiltration increases subsurface moisture and generates pore-water pressure ($u$), reducing effective normal stress ($\sigma_n' = \sigma_n - u$) and lowering slope stability:

$$u = m \cdot \gamma_w \cdot z \cdot \cos^2\beta \quad (\gamma_w = 9.81\,\text{kN/m}^3)$$

The **Saturation Ratio ($m$)** ($0.1 \le m \le 1.0$) is calculated from current precipitation intensity ($I$), continuous rainfall duration ($t$), and 24-hour antecedent rainfall ($P_{24h}$):

$$m = \max \left( \frac{\min(I, K_s) \cdot t}{z \cdot n}, \, \frac{\min(P_{24h}, K_s \cdot 24)}{z \cdot n} \right)$$

Where:
- **$K_s$** = Saturated Hydraulic Conductivity ($\text{m/s}$)
- **$n$** = Soil Porosity ($n \approx 0.40$)

### 3. Infiltration & Stability Cascade Logic

$$\text{Rainfall } I \uparrow \; \longrightarrow \; \text{Infiltration } F \uparrow \; \longrightarrow \; \text{Saturation } m \uparrow \; \longrightarrow \; \text{Pore Pressure } u \uparrow \; \longrightarrow \; \text{Effective Stress } \sigma_n' \downarrow \; \longrightarrow \; \text{FoS } \downarrow \; \longrightarrow \; \text{Risk Alert } \text{🔴}$$

---

## 🪨 Soil Mechanics Lookup Matrix

Geotechnical parameters parameterized for Himalayan soils (Gupta & Joshi 2016, Geological Survey of India):

| Class | Soil Label | Cohesion $c'$ | Friction $\phi'$ | Unit Weight $\gamma$ | Depth $z$ | Conductivity $K_s$ |
|-------|------------|---------------|------------------|----------------------|-----------|-------------------|
| `alluvial_plain` | Alluvial Plain | $5\,\text{kPa}$ | $28^\circ$ | $18.0\,\text{kN/m}^3$ | $2.0\,\text{m}$ | $1 \times 10^{-5}\,\text{m/s}$ |
| `residual_hill` | Residual Hill Soil | $12\,\text{kPa}$ | $32^\circ$ | $19.5\,\text{kN/m}^3$ | $1.5\,\text{m}$ | $5 \times 10^{-6}\,\text{m/s}$ |
| `colluvial_slope` | Colluvial Deposit | $8\,\text{kPa}$ | $26^\circ$ | $17.5\,\text{kN/m}^3$ | $3.0\,\text{m}$ | $8 \times 10^{-6}\,\text{m/s}$ |
| `weathered_rock` | Weathered Rock | $25\,\text{kPa}$ | $35^\circ$ | $22.0\,\text{kN/m}^3$ | $1.0\,\text{m}$ | $1 \times 10^{-7}\,\text{m/s}$ |
| `debris_fan` | Debris Fan | $3\,\text{kPa}$ | $30^\circ$ | $18.5\,\text{kN/m}^3$ | $2.5\,\text{m}$ | $2 \times 10^{-5}\,\text{m/s}$ |

---

## 📝 Important System Notes

- **Screening Tool Intent**: JANRAKSHAK is an early warning screening framework. It provides indicative slope stability estimates for regional road networks and does not replace site-specific geotechnical borings or inclinometer monitoring.
- **Zero-GIS Dependency Architecture**: Built using pure Python (`PIL`, `NumPy`, `Flask`) to process 32-bit floating point SRTM GeoTIFF DEMs directly, ensuring seamless execution across Windows, Linux, and macOS without GDAL C-library installation issues.
- **Continuous Background Daemon**: Background thread automatically refreshes Open-Meteo precipitation telemetry every 5 minutes and recalculates segment risk rankings.

---

## 🙏 Credits & Acknowledgments

Special thanks and acknowledgment to the platforms, data providers, and AI tools that made **JANRAKSHAK** possible:

1. **NASA AppEEARS (appeears.earthdata.nasa.gov)**:
   - For providing high-resolution NASA Shuttle Radar Topography Mission (**SRTM 30m 1-arc-second DEM**) datasets used to calculate terrain elevation, slope angle ($\beta$), aspect ($\alpha$), and soil depth profiles.
2. **Open-Meteo (open-meteo.com)**:
   - For providing free, high-precision, real-time hourly meteorological forecast and precipitation APIs, soil moisture datasets, and cartographic map telemetry.
3. **Kiro AI**:
   - For assistance in architectural design, geospatial data pipeline optimization, and code refactoring.
4. **Google Gemini**:
   - For expert guidance on Jetpack/Android standards, geotechnical formula derivations, and mathematical verification.
5. **OpenStreetMap & CartoDB / Esri World Imagery**:
   - For satellite, topographic, and tactical dark map tiles used in the Leaflet GIS interface.

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the application
python app.py

# 3. Open in browser
http://localhost:5000
```

---

## 🛠️ REST API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Tactical 3D Three.js Boot Sequence Landing Page |
| `/dashboard` | GET | Main Glassmorphism Command Center Dashboard |
| `/rainfall-landing` | GET | Dedicated SatCom Rainfall Telemetry Landing Page |
| `/rainfall` | GET | Direct link to Infiltration & Rainfall Telemetry View |
| `/terrain` | GET | Direct link to 3D WebGL Structural Kinematics View |
| `/validation` | GET | Direct link to Historical Failures & ML Audit View |
| `/api/segments` | GET | Retrieves all 12 sectors with FoS, forecasts, and live weather |
| `/api/simulate` | POST | Trigger Cloudburst (110mm/h) or Monsoon simulation mode |
| `/api/bulletin` | GET | Export USDMA Official Emergency Advisory Bulletin |
| `/api/thresholds` | GET/POST | Query or calibrate FoS cutoffs (`unstable`, `marginal`) |
| `/api/refresh` | POST | Force immediate weather refresh |
| `/api/incidents` | GET/POST | Record confirmed incidents / false alarms feedback loop |
| `/api/health` | GET | System health & telemetry status |


<div align="center">
  <h1><img width="300" height="300" src="https://user-images.githubusercontent.com/173/77249168-99488080-6c15-11ea-98de-3d14a412265d.png" alt="Spiderman"></h1>

---

## 📜 License

MIT — Built for **COGNITIA 2026 Hackathon**

<div align="center">
  <h1><img width="300" height="300" src="https://user-images.githubusercontent.com/173/77249168-99488080-6c15-11ea-98de-3d14a412265d.png" alt="Spiderman"></h1>
