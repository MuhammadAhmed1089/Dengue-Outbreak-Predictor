"""
GET /api/insights/eda       — Real EDA statistics from processed CSV
GET /api/insights/pair_plot — Seaborn pair plot as base64 PNG
"""

import io
import base64
import traceback
from pathlib import Path
from functools import lru_cache

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

router = APIRouter()

import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import DATA_DIR

@lru_cache(maxsize=1)
def _load_df() -> pd.DataFrame:
    candidates = [
        DATA_DIR / "updated-Punjab.csv",
        DATA_DIR / "updated-punjab.csv",
        DATA_DIR / "train.csv",
    ]
    for p in candidates:
        if p.exists():
            df = pd.read_csv(p)
            df.columns = df.columns.str.strip()
            return df
    raise FileNotFoundError(
        "Processed data CSV not found. "
        f"Tried: {[str(c) for c in candidates]}"
    )


# ── EDA endpoint ──────────────────────────────────────────────────────────────
@router.get("/insights/eda")
def get_eda_data():
    """
    Returns real arrays computed from the processed CSV so the frontend
    Plotly charts display actual data instead of hardcoded dummy values.
    """
    try:
        df = _load_df()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # ── Temperature vs Cases scatter ─────────────────────────────────────────
    temp_cases = (
        df[["T2M_mean", "cases"]].dropna()
          .sample(min(500, len(df)), random_state=42)
    )
    temp_vs_cases = {
        "T2M_mean": temp_cases["T2M_mean"].tolist(),
        "cases":    temp_cases["cases"].tolist(),
    }

    # ── Humidity vs Cases scatter ─────────────────────────────────────────────
    hum_cases = (
        df[["RH2M_mean", "cases"]].dropna()
          .sample(min(500, len(df)), random_state=43)
    )
    hum_vs_cases = {
        "RH2M_mean": hum_cases["RH2M_mean"].tolist(),
        "cases":     hum_cases["cases"].tolist(),
    }

    # ── Precipitation distribution ────────────────────────────────────────────
    precip_dist = df["PRECTOTCORR_sum"].dropna().tolist()

    # ── Cases by epi-week (mean across all districts/years) ──────────────────
    epi_week_agg = (
        df.groupby("epi_week")["cases"]
          .mean()
          .reindex(range(1, 53), fill_value=0)
          .reset_index()
    )
    epi_week_chart = {
        "weeks":      epi_week_agg["epi_week"].tolist(),
        "avg_cases":  epi_week_agg["cases"].round(1).tolist(),
    }

    # ── Feature correlation with cases ────────────────────────────────────────
    target_col = "cases"
    num_cols = df.select_dtypes(include=np.number).columns.tolist()
    num_cols = [c for c in num_cols if c != target_col]
    corrs = {}
    for col in num_cols:
        valid = df[[col, target_col]].dropna()
        if len(valid) > 10:
            corrs[col] = float(valid[col].corr(valid[target_col]))

    # Top 10 by absolute correlation
    top_corr = sorted(corrs.items(), key=lambda x: abs(x[1]), reverse=True)[:10]
    corr_chart = {
        "features": [c[0] for c in top_corr],
        "corr":     [round(c[1], 4) for c in top_corr],
    }

    # ── Descriptive stats ─────────────────────────────────────────────────────
    stats = {}
    for col in ["T2M_mean", "RH2M_mean", "PRECTOTCORR_sum", "cases"]:
        if col in df.columns:
            s = df[col].describe()
            stats[col] = {
                "mean":  round(float(s["mean"]), 2),
                "std":   round(float(s["std"]),  2),
                "min":   round(float(s["min"]),  2),
                "max":   round(float(s["max"]),  2),
                "q25":   round(float(s["25%"]),  2),
                "q75":   round(float(s["75%"]),  2),
            }

    return {
        "temp_vs_cases":  temp_vs_cases,
        "hum_vs_cases":   hum_vs_cases,
        "precip_dist":    precip_dist,
        "epi_week_chart": epi_week_chart,
        "corr_chart":     corr_chart,
        "stats":          stats,
        "row_count":      len(df),
    }


# ── Pair plot endpoint ────────────────────────────────────────────────────────
@router.get("/insights/pair_plot")
def get_pair_plot():
    """
    Generates a seaborn pair plot of the key features vs dengue cases,
    returns it as a base64-encoded PNG string.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")   # non-interactive backend — must be set before pyplot
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        raise HTTPException(status_code=503, detail="matplotlib/seaborn not installed")

    try:
        df = _load_df()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # Select features for the pair plot (keep it readable)
    pair_cols = ["T2M_mean", "RH2M_mean", "PRECTOTCORR_sum", "t1_cases", "cases"]
    pair_cols = [c for c in pair_cols if c in df.columns]

    sub = df[pair_cols].dropna().sample(min(600, len(df)), random_state=42)

    # Bin cases into severity for hue coloring
    bins   = [-1, 2, 5, 9, sub["cases"].max() + 1]
    labels = ["Low", "Medium", "High", "Severe"]
    sub    = sub.copy()
    sub["Severity"] = pd.cut(sub["cases"], bins=bins, labels=labels)

    palette = {
        "Low":    "#10b981",
        "Medium": "#f59e0b",
        "High":   "#ea580c",
        "Severe": "#dc2626",
    }

    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=0.9)

    g = sns.pairplot(
        sub,
        vars     = pair_cols[:-1] + ["cases"],  # keep "cases" as the last variable
        hue      = "Severity",
        palette  = palette,
        plot_kws = {"alpha": 0.4, "s": 15},
        diag_kind= "kde",
        corner   = False,
    )
    g.fig.suptitle("Pair Plot — Climate Features vs Dengue Cases", y=1.01, fontsize=12)

    buf = io.BytesIO()
    g.fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="white")
    plt.close("all")
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode("utf-8")

    return {"image_base64": img_b64, "mime": "image/png"}