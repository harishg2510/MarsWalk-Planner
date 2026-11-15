"""Glue layer: mission JSON -> grids -> cost matrix (Friend 1) -> A* routes (Friend 2) -> JSON for the map.
Terrain is SIMULATED unless backend/data/dem/<mission_id>.npy (+ .json sidecar) exists."""
import json, math, os, zlib
import numpy as np
from cost_matrix_pipeline import generate_cost_matrix, make_mock_dem
from pathfinder import a_star_pathfinding, M_PER_DEG, SQRT2

HERE = os.path.dirname(os.path.abspath(__file__)); DATA = os.path.join(HERE, "data")
N, RES = 160, 15.0                                   # 160 x 160 cells of 15 m = 2.4 km square
WALK_MPS, EVA_MIN, RESERVE_PCT = 0.5, 480.0, 20.0    # model assumptions, not NASA values

def load_missions():
    with open(os.path.join(DATA, "marswalk_missions.json"), encoding="utf-8") as f:
        return json.load(f)

def _grid_for(m):
    ws = m["waypoints"]; clat = (min(w["lat"] for w in ws) + max(w["lat"] for w in ws)) / 2
    clon = (min(w["lon"] for w in ws) + max(w["lon"] for w in ws)) / 2; cs = math.cos(math.radians(clat))
    return {"rows": N, "cols": N, "res_m": RES, "cos": cs, "origin_lat": clat + N/2*RES/M_PER_DEG,
            "origin_lon": clon - N/2*RES/(M_PER_DEG*cs)}

def _rc(g, lat, lon):
    return (round((g["origin_lat"]-lat)*M_PER_DEG/g["res_m"]), round((lon-g["origin_lon"])*M_PER_DEG*g["cos"]/g["res_m"]))
def _ll(g, r, c):
    return (g["origin_lat"]-r*g["res_m"]/M_PER_DEG, g["origin_lon"]+c*g["res_m"]/(M_PER_DEG*g["cos"]))

def _dem(m, g):
    p = os.path.join(DATA, "dem", m["mission_id"] + ".npy")
    if os.path.exists(p):                                    # REAL elevation: sidecar json gives origin_lat, origin_lon, res_m
        dem = np.load(p); side = json.load(open(p[:-4] + ".json"))
        g.update(rows=dem.shape[0], cols=dem.shape[1], res_m=side["res_m"], origin_lat=side["origin_lat"], origin_lon=side["origin_lon"])
        return dem, False
    seed = zlib.crc32(m["mission_id"].encode()); rng = np.random.default_rng(seed)
    dem = make_mock_dem(N, seed % 10000, 35.0)
    cy, cx = N*(0.4+0.2*rng.random()), N*(0.4+0.2*rng.random()); y, x = np.mgrid[0:N, 0:N]
    a = np.arctan2(y-cy, x-cx); g1, g2 = rng.random()*6.28, rng.random()*6.28            # one scarp ring with two passes
    gap = np.clip(np.maximum((np.cos(a-g1)-.9)/.1, (np.cos(a-g2)-.9)/.1), 0, 1)
    return dem + (45-41*gap)/(1+np.exp(-(np.hypot(x-cx, y-cy)-N*0.3))), True

def _nudge(cm, rc):
    r0, c0 = rc; R, C = cm.shape; r0 = min(max(r0, 0), R-1); c0 = min(max(c0, 0), C-1)
    for rad in range(0, 40):
        for dr in range(-rad, rad+1):
            for dc in range(-rad, rad+1):
                r, c = r0+dr, c0+dc
                if max(abs(dr), abs(dc)) == rad and 0 <= r < R and 0 <= c < C and np.isfinite(cm[r, c]): return (r, c)
    raise ValueError("no passable cell near waypoint")

def _chain(cm, cells):
    path, idx = [], [0]
    for a, b in zip(cells, cells[1:]):
        seg = a_star_pathfinding(cm, a, b)
        if seg is None: return None
        path += seg if not path else seg[1:]; idx.append(len(path)-1)
    return path, idx

def _stats(path, idx, slope, radn, dem, g, msv, g_ll):
    d = tm = o2 = rs = 0.0; cum = [0.0]; ds = [0.0]
    for (r0, c0), (r1, c1) in zip(path, path[1:]):
        st = SQRT2 if r0 != r1 and c0 != c1 else 1.0; dt = st*g["res_m"]/WALK_MPS/60
        d += st*g["res_m"]; tm += dt; o2 += dt*(100/EVA_MIN)*(1+slope[r1, c1]/30); rs += radn[r1, c1]*dt; cum.append(o2); ds.append(d)
    return {"path_latlon": [[round(v, 6) for v in g_ll(r, c)] for r, c in path], "distance_m": round(d), "time_min": round(tm),
            "o2_used_pct": round(o2, 1), "dose_msv": round(msv/24*(tm/60)*(0.8+0.4*rs/max(tm, 1e-9)), 3),
            "max_slope_deg": round(float(max(slope[r, c] for r, c in path)), 1),
            "profile_m": [round(float(dem[r, c]), 1) for r, c in path],
            "wp_stats": [{"dist_m": round(ds[i]), "o2_left_pct": round(100-cum[i], 1), "walkback_margin_pct": round(100-2*cum[i]-RESERVE_PCT, 1)} for i in idx],
            "worst_walkback_margin_pct": round(min(100-2*cum[i]-RESERVE_PCT for i in idx), 1)}

def _clean(a, nd=1):
    return [[None if not math.isfinite(v) else round(float(v), nd) for v in row] for row in a]

def plan_site(m):
    g = _grid_for(m); dem, simulated = _dem(m, g); seed = zlib.crc32(m["mission_id"].encode())
    sm = np.random.default_rng(seed+1).standard_normal(dem.shape); f = np.fft.fft2(sm)
    ky, kx = np.meshgrid(np.fft.fftfreq(dem.shape[0]), np.fft.fftfreq(dem.shape[1]), indexing="ij"); f *= np.exp(-(kx**2+ky**2)/(2*0.05**2))
    sm = np.real(np.fft.ifft2(f)); sm = (sm-sm.min())/(sm.max()-sm.min())
    rad = 0.7*sm + 0.3*(dem-dem.min())/max(np.ptp(dem), 1e-9)                         # simulated radiation proxy
    pkg = generate_cost_matrix(dem, rad, g["res_m"], origin_lat=g["origin_lat"], origin_lon=g["origin_lon"])
    cm, slope, radn = pkg["total_cost_matrix"], pkg["slope_degrees"], pkg["radiation_cost"]
    ll = lambda r, c: _ll(g, r, c); msv = m["environmental_status"]["radiation_msv_day"]
    cells, wps = [], []
    for w in m["waypoints"]:
        want = _rc(g, w["lat"], w["lon"]); cell = _nudge(cm, want); cells.append(cell)
        wps.append({**w, "row": cell[0], "col": cell[1], "snapped_cells": int(max(abs(cell[0]-want[0]), abs(cell[1]-want[1]))),
                    "sim_slope_deg": round(float(slope[cell]), 1), "sim_radiation_msv_day": round(msv*(0.85+0.3*float(radn[cell])), 2)})
    nom = _chain(cm, cells)
    if nom is None: raise ValueError("No safe route between waypoints: cliffs block every path")
    out = {"mission_id": m["mission_id"], "simulated_terrain": simulated, "waypoints": wps,
           "grid": {"rows": dem.shape[0], "cols": dem.shape[1], "res_m": g["res_m"],
                    "bounds": [[ll(dem.shape[0], 0)[0], ll(0, 0)[1]], [ll(0, 0)[0], ll(0, dem.shape[1])[1]]]},
           "layers": {"elevation": _clean(dem), "slope": _clean(slope), "radiation": _clean(radn, 2), "cost": _clean(cm, 2)},
           "routes": {"nominal": _stats(*nom, slope, radn, dem, g, msv, ll), "reroute": None}, "hazard": None}
    hr = 7; hr_c = nom[0][int(len(nom[0])*.45)]; yy, xx = np.mgrid[0:dem.shape[0], 0:dem.shape[1]]
    block = np.hypot(yy-hr_c[0], xx-hr_c[1]) < hr
    for r, c in cells: block &= np.hypot(yy-r, xx-c) >= 4
    cm2 = np.where(block, np.inf, cm); rr = _chain(cm2, cells)
    out["hazard"] = {"lat": ll(*hr_c)[0], "lon": ll(*hr_c)[1], "radius_m": hr*g["res_m"], "label": "Simulated dust / radiation storm"}
    if rr: out["routes"]["reroute"] = _stats(*rr, slope, radn, dem, g, msv, ll)
    return out
