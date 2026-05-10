"""
Configuration constants for the Dengue Predictor backend.
Override any of these via environment variables when deploying.
"""

import os
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT       = Path(__file__).resolve().parent          # project root
MODELS_DIR = ROOT / "models"
DATA_DIR   = ROOT / "data" / "processed"

# ── Server ────────────────────────────────────────────────────────────────────
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "5000"))

# ── CORS ──────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# ── Model settings ────────────────────────────────────────────────────────────
CI_FRACTION = float(os.getenv("CI_FRACTION", "0.20"))