"""
Dengue Predictor Punjab — FastAPI application entry point
Run with:  uvicorn app:app --reload --port 5000
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # project root → config.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import predict, cluster, Insights, models_meta

app = FastAPI(
    title="Dengue Predictor Punjab API",
    description="ML-powered dengue outbreak prediction for Punjab, Pakistan",
    version="1.0.0",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Allow the frontend (served from any local origin or deployed domain) to call
# the API. Restrict origins in production to your actual frontend domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten to specific origin(s) in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ROUTERS ──────────────────────────────────────────────────────────────────
app.include_router(predict.router,     prefix="/api")
app.include_router(cluster.router,     prefix="/api")
app.include_router(Insights.router,    prefix="/api")
app.include_router(models_meta.router, prefix="/api")


# ── HEALTH CHECK ─────────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return {"status": "ok", "service": "Dengue Predictor Punjab API v1.0"}
