"""Build a standalone static copy in ../docs for GitHub Pages.
Run from backend/:  python export_static.py"""
import json
import os
import re
from planner import load_missions, plan_site

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
FRONTEND_HTML = os.path.join(ROOT, "frontend", "index.html")
DOCS_DIR = os.path.join(ROOT, "docs")


def build_static():
    os.makedirs(DOCS_DIR, exist_ok=True)
    missions_data = load_missions()
    plans = {}
    for m in missions_data.get("eva_missions", []):
        mid = m["mission_id"]
        print(f"Precomputing plan for {mid}...")
        plans[mid] = plan_site(m)

    # Write static JSON files for reference/inspection
    with open(os.path.join(DOCS_DIR, "missions.json"), "w", encoding="utf-8") as f:
        json.dump(missions_data, f, ensure_ascii=False, separators=(",", ":"))
    for mid, plan_data in plans.items():
        with open(os.path.join(DOCS_DIR, f"plan_{mid}.json"), "w", encoding="utf-8") as f:
            json.dump(plan_data, f, ensure_ascii=False, separators=(",", ":"))

    with open(FRONTEND_HTML, encoding="utf-8") as f:
        html = f.read()

    # Inject static snapshot fallback so GitHub Pages works without a live FastAPI backend
    snapshot_blob = json.dumps({"missions": missions_data, "plans": plans}, ensure_ascii=False, separators=(",", ":"))
    snapshot_script = f"<script>window.__STATIC_SNAPSHOT__={snapshot_blob};</script>\n"

    # Replace fetch calls with static-snapshot fallback when API is unreachable
    old_load = 'r=await fetch(`${API}/api/plan/${id}`);if(!r.ok)throw new Error((await r.json()).detail)}catch(e){showErr("Planner error: "+e.message);return}\nP=await r.json();'
    new_load = (
        'if(window.__STATIC_SNAPSHOT__&&window.__STATIC_SNAPSHOT__.plans[id]){'
        'P=window.__STATIC_SNAPSHOT__.plans[id];'
        '}else{'
        'r=await fetch(`${API}/api/plan/${id}`);if(!r.ok)throw new Error((await r.json()).detail);P=await r.json();'
        '}}catch(e){showErr("Planner error: "+e.message);return}\n'
    )

    old_init = 'try{M=await(await fetch(API+"/api/missions")).json();$("api").textContent="API connected";$("api").className="bd v"}\ncatch(e){$("api").textContent="API offline";$("api").className="bd";showErr("The planner API is not reachable. In a terminal run <code>cd backend</code> then <code>uvicorn server:app --port 8000</code> and open <code>http://localhost:8000</code>.");return}'
    new_init = (
        'try{M=await(await fetch(API+"/api/missions")).json();$("api").textContent="API connected";$("api").className="bd v"}\n'
        'catch(e){'
        'if(window.__STATIC_SNAPSHOT__){M=window.__STATIC_SNAPSHOT__.missions;$("api").textContent="Static snapshot";$("api").className="bd s"}'
        'else{$("api").textContent="API offline";$("api").className="bd";showErr("The planner API is not reachable. In a terminal run <code>cd backend</code> then <code>uvicorn server:app --port 8000</code> and open <code>http://localhost:8000</code>.");return}'
        '}'
    )

    assert old_load in html, "Could not find load() fetch block in frontend/index.html"
    assert old_init in html, "Could not find init() fetch block in frontend/index.html"

    static_html = html.replace(old_load, new_load).replace(old_init, new_init)
    static_html = static_html.replace("<script>", snapshot_script + "<script>", 1)

    out_html = os.path.join(DOCS_DIR, "index.html")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(static_html)
    print(f"Exported static site to {out_html}")


if __name__ == "__main__":
    build_static()
