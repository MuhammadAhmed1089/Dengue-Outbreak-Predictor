"""
GET /api/cluster
Returns all Punjab district risk-tier data from kmeans_clusters.pkl and
cluster_risk_map.pkl for the Leaflet.js map.
"""

from pathlib import Path
from functools import lru_cache

import joblib
import numpy as np
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


@lru_cache(maxsize=1)
def _load_cluster_artifacts():
    def _try_load(name):
        p = MODELS_DIR / name
        return joblib.load(p) if p.exists() else None

    return {
        "kmeans_zone":     _try_load("kmeans_zone.pkl"),
        "cluster_risk_map":_try_load("cluster_risk_map.pkl"),
        "kmeans_clusters": _try_load("kmeans_clusters.pkl"),
    }


def _zone_to_tier(zone_id: int, n_clusters: int = 4) -> str:
    """Map an integer cluster id to a named risk tier."""
    # Assumes cluster_risk_map is a dict {zone_id: {"tier": ...}}
    # If not, fall back to ordinal mapping.
    tier_map = {0: "low", 1: "moderate", 2: "high", 3: "critical"}
    return tier_map.get(int(zone_id) % 4, "low")


@router.get("/cluster")
def get_cluster_data():
    """
    Returns list of districts with lat/lng, risk tier, color, and
    average predicted cases derived from the KMeans clustering model.
    """
    arts = _load_cluster_artifacts()
    kmeans_zone      = arts["kmeans_zone"]
    cluster_risk_map = arts["cluster_risk_map"]

    districts_out = []

    for district, (lat, lng) in DISTRICT_COORDS.items():
        tier  = "low"
        cases = 0

        # ── Try to read tier from pkl artifacts ──────────────────────────────
        if cluster_risk_map is not None:
            # cluster_risk_map: {district_name: {tier, avg_cases, ...}} OR
            #                   {cluster_id: {tier, avg_cases, ...}}
            if isinstance(cluster_risk_map, dict):
                entry = cluster_risk_map.get(district)
                if entry and isinstance(entry, dict):
                    tier  = entry.get("tier",      tier)
                    cases = entry.get("avg_cases",  cases)

        if kmeans_zone is not None and tier == "low":
            # kmeans_zone: {district_name: cluster_id}
            if isinstance(kmeans_zone, dict):
                zone_id = kmeans_zone.get(district)
                if zone_id is not None:
                    tier = _zone_to_tier(zone_id)

        districts_out.append({
            "name":       district,
            "lat":        lat,
            "lng":        lng,
            "tier":       tier,
            "color":      TIER_COLORS.get(tier, "#10b981"),
            "avg_cases":  cases,
        })

    # ── Risk tier summary ─────────────────────────────────────────────────────
    summary = {}
    for tier_key, color in TIER_COLORS.items():
        matching = [d for d in districts_out if d["tier"] == tier_key]
        summary[tier_key] = {
            "color":        color,
            "districts":    [d["name"] for d in matching],
            "count":        len(matching),
            "avg_cases":    (
                int(np.mean([d["avg_cases"] for d in matching]))
                if matching else 0
            ),
        }

    return {"districts": districts_out, "summary": summary}