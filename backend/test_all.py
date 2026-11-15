"""python test_all.py  -> each block tests one behaviour on its own."""
import heapq, math, numpy as np
from cost_matrix_pipeline import generate_cost_matrix, make_mock_dem
from pathfinder import a_star_pathfinding, export_path_to_json, M_PER_DEG

def ok(name, cond): print(("PASS " if cond else "FAIL ") + name); assert cond

# 1 pipeline: a 30 deg ramp is impassable, a 5 deg ramp is not
x = np.arange(50)[None, :].repeat(50, 0) * 10.0
steep = generate_cost_matrix(x*math.tan(math.radians(30)), np.zeros((50,50)))["total_cost_matrix"]
gentle = generate_cost_matrix(x*math.tan(math.radians(5)), np.zeros((50,50)))["total_cost_matrix"]
ok("pipeline: 30 deg -> inf", np.isinf(steep).all()); ok("pipeline: 5 deg -> finite", np.isfinite(gentle).all())
# 2 pipeline: missing elevation is never safe
e = np.zeros((20,20)); e[5,5] = np.nan
ok("pipeline: NaN elevation -> inf", np.isinf(generate_cost_matrix(e, np.zeros((20,20)))["total_cost_matrix"][5,5]))
# 3 pipeline: shape mismatch rejected
try: generate_cost_matrix(np.zeros((5,5)), np.zeros((4,4))); ok("pipeline: shape check", False)
except ValueError: ok("pipeline: shape check", True)
# 4 A*: optimal vs Dijkstra (costs below 1 would have broken the old heuristic)
rng = np.random.default_rng(1); c = rng.random((40,40))*3 + 0.2
def dijk(c, s, g):
    d = {s: 0}; h = [(0, s)]
    while h:
        k, u = heapq.heappop(h)
        if u == g: return k
        if k > d[u]: continue
        for dr in (-1,0,1):
            for dc in (-1,0,1):
                v = (u[0]+dr, u[1]+dc)
                if (dr or dc) and 0 <= v[0] < 40 and 0 <= v[1] < 40:
                    n = k + (math.sqrt(2) if dr and dc else 1) * c[v]
                    if n < d.get(v, 1e18): d[v] = n; heapq.heappush(h, (n, v))
p = a_star_pathfinding(c, (0,0), (39,39))
cost = sum((math.sqrt(2) if a[0]!=b[0] and a[1]!=b[1] else 1)*c[b] for a,b in zip(p,p[1:]))
ok("A*: optimal (%.3f vs %.3f)" % (cost, dijk(c,(0,0),(39,39))), abs(cost - dijk(c,(0,0),(39,39))) < 1e-6)
# 5 A*: detours through the single gap in a cliff wall
m = np.ones((60,60)); m[:, 30] = np.inf; m[40, 30] = 1.0
p = a_star_pathfinding(m, (10,5), (10,55)); ok("A*: crosses wall only at gap", p is not None and {r for r,cc in p if cc==30} == {40})
# 6 A*: sealed wall -> None; impassable start -> ValueError
m2 = np.ones((20,20)); m2[:,10] = np.inf
ok("A*: sealed wall -> None", a_star_pathfinding(m2, (5,2), (5,17)) is None)
try: a_star_pathfinding(m2, (5,10), (5,17)); ok("A*: bad start rejected", False)
except ValueError: ok("A*: bad start rejected", True)
# 7 export: rows go south, columns east, lon scaled by cos(lat), distance reported
import json, tempfile, os
f = os.path.join(tempfile.mkdtemp(), "r.json"); w = export_path_to_json([(0,c) for c in range(101)] + [(r,100) for r in range(1,101)], np.ones((101,101)), 18.4625, 77.4220, 10.0, f)
ok("export: south lowers lat", w[200]["lat"] < w[100]["lat"]); ok("export: east raises lon", w[100]["lon"] > w[0]["lon"])
ok("export: 1 km east = %.4f deg lon" % (w[100]["lon"]-w[0]["lon"]), abs((w[100]["lon"]-w[0]["lon"]) - 1000/(M_PER_DEG*math.cos(math.radians(18.4625)))) < 1e-5)
ok("export: distance 2000 m", json.load(open(f))["route_distance_m"] == 2000.0)
# 8 mock DEM now looks like terrain, not static
r = generate_cost_matrix(make_mock_dem(), np.random.default_rng(1).random((200,200)))
ok("mock DEM: impassable %.1f%% (was 19%% noise)" % (100*np.isinf(r['total_cost_matrix']).mean()), np.isinf(r['total_cost_matrix']).mean() < 0.10)
print("ALL TESTS PASSED")
