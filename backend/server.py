"""FastAPI server.  Run from the backend folder:  uvicorn server:app --reload --port 8000
Then open http://localhost:8000  (the frontend is served from ../frontend)."""
import os
from functools import lru_cache
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from planner import load_missions, plan_site

app = FastAPI(title="MarsWalk Planner API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])
FRONTEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

@app.get("/api/health")
def health(): return {"status": "ok"}

@app.get("/api/missions")
def missions(): return load_missions()

@lru_cache(maxsize=8)
def _plan(mission_id: str):
    m = next((x for x in load_missions()["eva_missions"] if x["mission_id"] == mission_id), None)
    if m is None: raise KeyError(mission_id)
    return plan_site(m)

@app.get("/api/plan/{mission_id}")
def plan(mission_id: str):
    """Cost matrix + A* nominal route + hazard reroute for one mission (all computed by pipeline + pathfinder)."""
    try: return _plan(mission_id)
    except KeyError: raise HTTPException(404, f"Unknown mission '{mission_id}'")
    except ValueError as e: raise HTTPException(422, str(e))

app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
