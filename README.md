# MarsWalk Planner (FastAPI + A* Cost-Surface Engine + NASA Mars Trek)

An interactive extravehicular activity (EVA) mission planner and multi-layered surface navigation tool built for the **2026 NASA Space Apps Challenge** (*Interplanetary Survival Guide: Martian Map*). It fuses real NASA Mars Trek orbital tile layers with a latitude-scaled A* pathfinding engine and multi-hazard terrain cost model to plan, inspect, and dynamically re-route human surface traverses on Mars.

Built on Python, FastAPI, NumPy, and Leaflet.js, with a zero-server static export pipeline for GitHub Pages.

---

## Features

- **Latitude-scaled A* pathfinder**: computes optimal least-cost traverses across Martian surface grids using an 8-connected octile heuristic scaled accurately for Mars's planetary radius ($59,274\text{ m/deg}$ at the equator, scaled by $\cos(\text{lat})$ along longitude).
- **Multi-layered hazard & mobility cost surface**: models spacesuit mobility constraints by combining terrain slope (derived via gradient stencils over elevation grids), steep-slope cutoffs ($> 25^\circ$ impassable), boulder/rock-field drag, radiation exposure, and mission-specific hazardous zones into a unified traversal cost matrix.
- **Dynamic hazard avoidance**: allows astronauts or flight controllers to toggle active environmental alerts (such as dust fronts, solar particle radiation spikes, or unstable boxwork/scarp zones) and immediately recomputes an alternate safe detour around the blocked corridor.
- **NASA Mars Trek orbital imagery**: renders real WMTS tile layers from NASA JPL's Mars Trek (Viking MDIM21 colorized mosaic, MOLA elevation relief, CTX, and HiRISE) alongside ground-truth rover sites and candidate EVA waypoints.
- **Bilingual astronaut interface**: includes one-click switching between English and Tamil (`தமிழ்`) across mission controls, layer inspectors, and safety telemetry.
- **Dual-mode deployment (Live API + Static Snapshot)**: runs locally against a live FastAPI backend for real-time route synthesis, or exports a self-contained static snapshot (`docs/`) via `export_static.py` so the full interactive map works directly on GitHub Pages without a running server.
- **Transparent data provenance**: explicitly tags every map layer and telemetry readout as **Real** (NASA Mars Trek tiles, mission coordinates, ground-truth rover landmarks, environmental baselines), **Simulated** (synthetic DEM elevation, slope cost surfaces, $O_2$ burn, radiation dose, computed routes), or **Planned** (high-resolution DEM and USGS geologic unit tiles).

---

## Repository layout

| File / Folder | What it is |
|---|---|
| `backend/pathfinder.py` | Core 8-connected A* pathfinding engine with latitude-compensated octile distance and impassable-cell guards. |
| `backend/cost_matrix_pipeline.py` | Builds the terrain elevation grid, computes slope angles in degrees, applies hazard/radiation penalties, and outputs the traversal cost matrix. |
| `backend/planner.py` | Joins the mission dataset (`marswalk_missions.json`) with the cost pipeline and pathfinder to generate primary routes, hazard-avoidance detours, elevation profiles, and $O_2$/energy budgets. |
| `backend/server.py` | FastAPI application serving the frontend and exposing `/api/missions` and `/api/plan/{mission_id}` endpoints. |
| `backend/main.py` | CLI runner that executes the planner offline and writes `route.json` for inspection. |
| `backend/export_static.py` | Precomputes all mission plans and injects them into `docs/index.html` (plus standalone JSON files) for GitHub Pages hosting. |
| `backend/test_all.py` | Automated verification suite (16 checks) validating coordinate scaling, A* optimality, impassable obstacle handling, and API schema integrity. |
| `backend/data/marswalk_missions.json` | Primary mission database containing EVA waypoints, environmental alerts, 5 ground-truth landing sites, 7 candidate sites, and NASA Mars Trek tile layer definitions. |
| `frontend/index.html` | Single-file Leaflet map interface, layer toggles, route inspector, elevation/hazard telemetry, and bilingual UI. |
| `docs/` | Generated static build served by GitHub Pages when no Python backend is active. |
| `requirements.txt` | Python package dependencies (`fastapi`, `uvicorn`, `numpy`, etc.). |

---

## Requirements

- Python 3.10+
- Active internet connection (required in the browser to stream NASA Mars Trek WMTS tiles and Leaflet assets)
- Python packages listed in `requirements.txt` (`fastapi`, `uvicorn`, `numpy`, `pydantic`)

```bash
pip install -r requirements.txt
```

---

## Setup & Running Locally

1. Clone or extract the `marswalk` repository and open a terminal in the project root.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the verification suite, generate a standalone route output, and start the FastAPI server:
   ```bash
   cd backend
   python test_all.py              # all 16 checks should print PASS
   python main.py                  # writes route.json
   uvicorn server:app --port 8000
   ```
4. Open **`http://localhost:8000`** in your browser. Verify that the top status badge reads **`API connected`**, NASA Viking imagery loads, and the route waypoints appear.

### Building & Publishing the Static Snapshot (GitHub Pages)

Because GitHub Pages hosts static files without a Python runtime, generate the `/docs` snapshot before pushing:

```bash
cd backend
python export_static.py
```

This writes `docs/index.html`, `docs/missions.json`, and `docs/plan_<mission_id>.json`. When opened without the FastAPI server running, the interface automatically switches its badge to **`Static snapshot`** and serves the precomputed routes and hazard detours.

To host publicly on GitHub:
1. Push the `marswalk/` folder to a public GitHub repository on the `main` branch.
2. Open **Settings → Pages → Build and deployment**, select **Deploy from a branch**, choose **`main`** and **`/docs`**, and click **Save**.

---

## How it works

1. **Grid & Planetary Scaling**: Each EVA mission defines a bounding extent around a Martian target region (such as Jezero Crater Delta or Gale Crater / Mount Sharp). Degrees are converted to meters using Mars's equatorial arc factor ($59,274\text{ m/deg}$) and $\cos(\text{latitude})$ longitudinal scaling.
2. **Terrain & Hazard Cost Synthesis**: `cost_matrix_pipeline.py` constructs a 2D elevation grid and calculates local slope angles. Cells exceeding the spacesuit slope limit ($> 25^\circ$) or marked as missing/null elevation are flagged impassable ($\infty$ cost), while moderate slopes, rocky terrain, and radiation zones add proportional traversal penalties.
3. **Optimal Traverse Routing**: `pathfinder.py` executes A* across the cost grid between sequential mission waypoints, minimizing total physiological and energetic cost rather than raw Euclidean distance.
4. **Hazard Re-routing**: Activating **Simulate hazard avoidance** injects an active environmental alert (e.g., dust storm front or solar radiation spike) into the cost layer and re-runs A* to route the crew safely around the affected sector.
5. **Telemetry & Crew Resource Estimation**: `planner.py` aggregates path distance, cumulative elevation gain, peak slope, estimated traverse duration, $O_2$ consumption, and radiation dose for display in the mission inspector.

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | `GET` | Serves `frontend/index.html`. |
| `/api/missions` | `GET` | Returns the full mission catalog, tile layer URLs, ground-truth sites, and candidate sites from `marswalk_missions.json`. |
| `/api/plan/{mission_id}` | `GET` | Computes and returns the baseline route, hazard-avoidance detour, waypoint metrics, elevation profile, and safety telemetry for the given mission ID (e.g., `jezero-delta-eva-01`, `gale-mount-sharp-eva-02`). |

---

## Testing

The backend includes an automated test suite (`backend/test_all.py`) covering 16 unit and integration checks:

- **Planetary geometry**: verifies $59,274\text{ m/deg}$ scaling and $\cos(\text{lat})$ longitudinal compression.
- **Pathfinder optimality**: confirms A* selects lower-cost detours over steeper/higher-penalty direct lines and handles 8-neighbor diagonal costs properly.
- **Safety boundaries**: ensures missing/NaN elevation cells and $> 25^\circ$ cliffs are treated as impassable rather than zero-cost safe terrain.
- **End-to-end mission planning**: validates all missions in `marswalk_missions.json` produce connected routes and valid JSON payloads.

Run all checks from `backend/`:

```bash
python test_all.py
```

---

## Known limitations & planned upgrades

- **Simulated vs. real DEMs**: Terrain elevation, slope, $O_2$ burn, and radiation values are currently generated by a deterministic physical proxy model; integrating real HiRISE/CTX digital elevation models (DEMs) and USGS planetary geologic map tiles is planned for the next release.
- **Mars Trek auxiliary layers**: While Viking MDIM21 base tiles are verified, MOLA, CTX, and HiRISE WMTS overlay availability depends on regional coverage and zoom bounds on NASA's public tile servers.
- **Gale Crater waypoint alignment**: The `gale-mount-sharp-eva-02` waypoints sit approximately $18\text{ km}$ south of the nominal Gale bounding extent and are scheduled for coordinate refinement.
- **Concept demonstrator**: This tool is built for mission planning visualization and educational exploration—it is not a certified flight or EVA life-support navigation system.

---

## AI Disclosure (NASA Space Apps Challenge)

In accordance with NASA Space Apps Challenge submission guidelines:
- **AI-assisted development**: Generative AI tools were used to assist in auditing pathfinding edge cases, structuring the FastAPI/Leaflet codebase, generating Tamil UI translations, and drafting documentation.
- **Data provenance**: Planetary tile URLs, mission site coordinates, and landmark references originate from public NASA JPL Mars Trek and planetary science datasets, while localized elevation grids, traversal cost matrices, and simulated hazard scenarios are synthetically generated by the project's Python backend.