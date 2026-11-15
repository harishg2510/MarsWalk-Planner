"""A* EVA route planner + route.json export (Friend 2)."""
import heapq, json, math
import numpy as np

MARS_RADIUS_M = 3396190.0  # Mars 2000 sphere, same as the Mars Trek tiles
M_PER_DEG = math.pi * MARS_RADIUS_M / 180.0      # ~59,274 m per degree (matches Mars Trek)
SQRT2 = math.sqrt(2.0)
NEIGHBORS = [(-1,0),(1,0),(0,-1),(0,1),(-1,-1),(-1,1),(1,-1),(1,1)]

def a_star_pathfinding(cost_matrix, start, goal, forbid_corner_cutting=False):
    """Lowest-cost path (row, col) list from start to goal, or None if no safe path.
    np.inf cells are impassable. Raises ValueError for a start/goal that is off-grid or impassable."""
    cm = np.asarray(cost_matrix, dtype=float)
    rows, cols = cm.shape
    for name, (r, c) in (("start", start), ("goal", goal)):
        if not (0 <= r < rows and 0 <= c < cols):
            raise ValueError(f"{name} {(r, c)} is outside the {rows}x{cols} grid")
        if not np.isfinite(cm[r, c]):
            raise ValueError(f"{name} {(r, c)} is on an impassable cell")
    finite = cm[np.isfinite(cm)]
    h_scale = float(finite.min())          # heuristic scaled by cheapest cell => admissible, so path is optimal
    start, goal = tuple(start), tuple(goal)
    g_score = {start: 0.0}; came_from = {}; open_set = [(0.0, start)]
    while open_set:
        f, cur = heapq.heappop(open_set)
        if f - h_scale * math.hypot(goal[0]-cur[0], goal[1]-cur[1]) > g_score[cur] + 1e-9:
            continue                        # stale queue entry
        if cur == goal:
            path = [cur]
            while cur in came_from:
                cur = came_from[cur]; path.append(cur)
            return path[::-1]
        for dr, dc in NEIGHBORS:
            nr, nc = cur[0]+dr, cur[1]+dc
            if not (0 <= nr < rows and 0 <= nc < cols) or not np.isfinite(cm[nr, nc]):
                continue
            if forbid_corner_cutting and dr and dc and not (np.isfinite(cm[cur[0], nc]) and np.isfinite(cm[nr, cur[1]])):
                continue
            tg = g_score[cur] + (SQRT2 if dr and dc else 1.0) * cm[nr, nc]
            if tg < g_score.get((nr, nc), math.inf):
                g_score[(nr, nc)] = tg; came_from[(nr, nc)] = cur
                heapq.heappush(open_set, (tg + h_scale*math.hypot(goal[0]-nr, goal[1]-nc), (nr, nc)))
    return None

def export_path_to_json(path, cost_matrix, origin_lat=-5.413, origin_lon=137.442, res_m=10.0, filename="route.json"):
    """origin_lat/lon = coordinates of grid cell (0,0), the NORTH-WEST corner: rows run south, columns east.
    Longitude degrees shrink with cos(latitude)."""
    wps, dist = [], 0.0
    for i, (r, c) in enumerate(path):
        if i: dist += res_m * (SQRT2 if path[i-1][0] != r and path[i-1][1] != c else 1.0)
        lat = origin_lat - r * res_m / M_PER_DEG
        lon = origin_lon + c * res_m / (M_PER_DEG * math.cos(math.radians(lat)))
        wps.append({"step": i+1, "grid_rc": [int(r), int(c)], "lat": round(lat, 6), "lon": round(lon, 6),
                    "cell_cost": round(float(cost_matrix[r, c]), 3)})
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({"route_distance_m": round(dist, 1), "route_waypoints": wps}, f, indent=2)
    return wps
