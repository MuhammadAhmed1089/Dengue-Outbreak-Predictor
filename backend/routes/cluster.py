"""
GET /api/cluster
Returns all Punjab district risk-tier data from kmeans_clusters.pkl and
cluster_risk_map.pkl for the Leaflet.js map.
"""

from pathlib import Path
from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter()

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import MODELS_DIR

# ── All 36 Punjab districts with lat/lng ─────────────────────────────────────
DISTRICT_COORDS = {
    "Attock":          (33.7667, 72.3600),
    "Bahawalnagar":    (29.9980, 73.2529),
    "Bahawalpur":      (29.3544, 71.6911),
    "Bhakkar":         (31.6280, 71.0616),
    "Chakwal":         (32.9320, 72.8560),
    "Chiniot":         (31.7200, 72.9780),
    "Dera Ghazi Khan": (30.0321, 70.6403),
    "Faisalabad":      (31.4180, 73.0790),
    "Gujranwala":      (32.1877, 74.1945),
    "Gujrat":          (32.5740, 74.0790),
    "Hafizabad":       (32.0714, 73.6878),
    "Jhang":           (31.2681, 72.3181),
    "Jhelum":          (32.9361, 73.7292),
    "Kasur":           (31.1200, 74.4500),
    "Khanewal":        (30.3018, 71.9320),
    "Khushab":         (32.2978, 72.3551),
    "Lahore":          (31.5204, 74.3587),
    "Layyah":          (30.9693, 70.9392),
    "Lodhran":         (29.5363, 71.6314),
    "Mandi Bahauddin": (32.5870, 73.4937),
    "Mianwali":        (32.5838, 71.5437),
    "Multan":          (30.1575, 71.5249),
    "Muzaffargarh":    (30.0758, 71.1926),
    "Nankana Sahib":   (31.4500, 73.7100),
    "Narowal":         (32.1018, 74.8740),
    "Okara":           (30.8138, 73.4535),
    "Pakpattan":       (30.3437, 73.3876),
    "Rahim Yar Khan":  (28.4200, 70.2957),
    "Rajanpur":        (29.1039, 70.3275),
    "Rawalpindi":      (33.5651, 73.0169),
    "Sahiwal":         (30.6774, 73.1065),
    "Sargodha":        (32.0836, 72.6711),
    "Sheikhupura":     (31.7131, 73.9783),
    "Sialkot":         (32.4945, 74.5229),
    "Toba Tek Singh":  (30.9709, 72.4827),
    "Vehari":          (30.0449, 72.3522),
}

TIER_COLORS = {
    "critical": "#dc2626",
    "high":     "#ea580c",
    "moderate": "#f59e0b",
    "low":      "#10b981",
}


RISK_ZONE_TO_TIER = {
    "Low Risk":      "low",
    "Moderate Risk": "moderate",
    "High Risk":     "high",
    "Hotspot":       "critical",
}

import pandas as pd

@lru_cache(maxsize=1)
def _load_cluster_assignments():
    csv_path = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "cluster_assignments.csv"
    if not csv_path.exists():
        return {}

    df = pd.read_csv(csv_path)

    # district_encoded is assigned alphabetically by OrdinalEncoder
    # DISTRICT_COORDS keys sorted alphabetically matches that encoding
    sorted_districts = sorted(DISTRICT_COORDS.keys())
    enc_to_name = {float(i): name for i, name in enumerate(sorted_districts)}

    df["district_name"] = df["district_encoded"].map(enc_to_name)
    df = df.dropna(subset=["district_name", "risk_zone"])

    result = {}
    for district, grp in df.groupby("district_name"):
        majority_zone = grp["risk_zone"].mode()[0]
        peak          = grp[grp["epi_week"].between(30, 45)]
        avg_cases     = float(peak["mean_predicted"].mean()) if len(peak) else float(grp["mean_predicted"].mean())
        result[district] = {
            "tier":      RISK_ZONE_TO_TIER.get(majority_zone, "low"),
            "avg_cases": round(avg_cases, 1),
        }
    return result


@router.get("/cluster/debug")
def debug_cluster():
    import sys as _sys
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from config import DATA_DIR

    csv_path1 = DATA_DIR / "processed" / "cluster_assignments.csv"
    csv_path2 = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "cluster_assignments.csv"

    result = {
        "DATA_DIR":    str(DATA_DIR),
        "csv_path1":   str(csv_path1),
        "csv_path1_exists": csv_path1.exists(),
        "csv_path2":   str(csv_path2),
        "csv_path2_exists": csv_path2.exists(),
        "cluster_py_location": str(Path(__file__).resolve()),
    }

    # If CSV found, show columns and first 3 rows
    for p in [csv_path1, csv_path2]:
        if p.exists():
            df = pd.read_csv(p)
            result["csv_columns"] = df.columns.tolist()
            result["csv_rows"]    = len(df)
            result["csv_head"]    = df.head(3).to_dict(orient="records")
            break

    return result


@router.get("/cluster")
def get_cluster_data():
    """
    Returns all 36 Punjab districts with KMeans-assigned risk tier and
    average predicted cases, sourced from cluster_assignments.csv.
    """
    assignments = _load_cluster_assignments()

    districts_out = []
    for district, (lat, lng) in DISTRICT_COORDS.items():
        entry     = assignments.get(district, {})
        tier      = entry.get("tier",      "low")
        avg_cases = entry.get("avg_cases", 0)

        districts_out.append({
            "name":      district,
            "lat":       lat,
            "lng":       lng,
            "tier":      tier,
            "color":     TIER_COLORS.get(tier, "#10b981"),
            "avg_cases": avg_cases,
        })

    # ── Risk tier summary ─────────────────────────────────────────────────────
    summary = {}
    for tier_key, color in TIER_COLORS.items():
        matching = [d for d in districts_out if d["tier"] == tier_key]
        summary[tier_key] = {
            "color":     color,
            "districts": [d["name"] for d in matching],
            "count":     len(matching),
            "avg_cases": (
                int(np.mean([d["avg_cases"] for d in matching]))
                if matching else 0
            ),
        }

    return {"districts": districts_out, "summary": summary}