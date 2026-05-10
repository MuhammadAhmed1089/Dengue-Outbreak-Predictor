"""
GET /api/insights/eda          — Real EDA statistics from processed CSV
GET /api/insights/pair_plot    — Original pair plot (kept for compatibility)
GET /api/insights/plot/lag     — Pair plot: Cases & Lag Features
GET /api/insights/plot/weather — Pair plot: Cases & Weather Features
GET /api/insights/plot/precip  — Pair plot: Cases & Precipitation Features
GET /api/insights/plot/cyclic  — Pair plot: Cases & Cyclical Features
GET /api/insights/plot/key     — Pair plot: Key Features (hue by case level)
GET /api/insights/plot/heatmap — Full Feature Correlation Heatmap
GET /api/insights/plots_meta   — Metadata list of all available plot endpoints
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


# ── Shared helper: render a seaborn figure → base64 PNG ──────────────────────
def _fig_to_b64(fig, dpi=110) -> dict:
    import matplotlib.pyplot as plt
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close("all")
    buf.seek(0)
    return {"image_base64": base64.b64encode(buf.read()).decode("utf-8"), "mime": "image/png"}


def _ensure_mpl():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
        return plt, sns
    except ImportError:
        raise HTTPException(status_code=503, detail="matplotlib/seaborn not installed")


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


# ── Original pair plot endpoint (kept for back-compat) ────────────────────────
@router.get("/insights/pair_plot")
def get_pair_plot():
    return get_plot_key()


# ── Plots metadata ────────────────────────────────────────────────────────────
@router.get("/insights/plots_meta")
def get_plots_meta():
    return [
        {
            "id": "lag",
            "title": "Cases & Lag Features",
            "subtitle": "Core temporal autocorrelation — how this week's cases predict next week's outbreak through T-1 and T-2 lag windows.",
            "icon": "⏱️",
            "endpoint": "/api/insights/plot/lag",
        },
        {
            "id": "weather",
            "title": "Cases & Weather Features",
            "subtitle": "Environmental drivers — temperature, relative humidity, precipitation and wind speed plotted pairwise against case counts.",
            "icon": "🌡️",
            "endpoint": "/api/insights/plot/weather",
        },
        {
            "id": "precip",
            "title": "Cases & Precipitation Features",
            "subtitle": "Water-related features including current precipitation, 1-week lag, 2-week lag and water proxy index.",
            "icon": "🌧️",
            "endpoint": "/api/insights/plot/precip",
        },
        {
            "id": "cyclic",
            "title": "Cases & Cyclical Features",
            "subtitle": "Sine/cosine encoded month and week features that capture annual and intra-annual seasonality patterns.",
            "icon": "📅",
            "endpoint": "/api/insights/plot/cyclic",
        },
        {
            "id": "key",
            "title": "Key Features — Coloured by Case Level",
            "subtitle": "Compact all-in-one scatter matrix of the five most predictive features, coloured by Low / Medium / High case severity.",
            "icon": "🔑",
            "endpoint": "/api/insights/plot/key",
        },
        {
            "id": "heatmap",
            "title": "Feature Correlation Matrix",
            "subtitle": "Full lower-triangle Pearson correlation heatmap across all numeric features — reveals multicollinearity and redundant predictors.",
            "icon": "🗺️",
            "endpoint": "/api/insights/plot/heatmap",
        },
    ]


# ── PLOT 1: Cases & Lag Features ─────────────────────────────────────────────
@router.get("/insights/plot/lag")
def get_plot_lag():
    plt, sns = _ensure_mpl()
    try:
        df = _load_df()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    cols = [c for c in ["cases", "t1_cases", "t2_cases", "T2M_mean", "T2M_lag1"] if c in df.columns]
    sub  = df[cols].dropna().sample(min(600, len(df)), random_state=42)

    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=0.85)
    g = sns.pairplot(sub, diag_kind="kde",
                     plot_kws={"alpha": 0.45, "s": 18, "color": "#0284C7"},
                     diag_kws={"fill": True, "color": "#F87171"})
    g.fig.suptitle("Pair Plot: Cases & Lag Features", y=1.02, fontsize=13, fontweight="bold")
    return _fig_to_b64(g.fig)


# ── PLOT 2: Cases & Weather Features ─────────────────────────────────────────
@router.get("/insights/plot/weather")
def get_plot_weather():
    plt, sns = _ensure_mpl()
    try:
        df = _load_df()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    cols = [c for c in ["cases", "T2M_mean", "RH2M_mean", "PRECTOTCORR_sum", "WS10M_mean"] if c in df.columns]
    sub  = df[cols].dropna().sample(min(600, len(df)), random_state=42)

    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=0.85)
    g = sns.pairplot(sub, diag_kind="kde",
                     plot_kws={"alpha": 0.45, "s": 18, "color": "#0D9488"},
                     diag_kws={"fill": True, "color": "#FCD34D"})
    g.fig.suptitle("Pair Plot: Cases & Weather Features", y=1.02, fontsize=13, fontweight="bold")
    return _fig_to_b64(g.fig)


# ── PLOT 3: Cases & Precipitation Features ───────────────────────────────────
@router.get("/insights/plot/precip")
def get_plot_precip():
    plt, sns = _ensure_mpl()
    try:
        df = _load_df()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    cols = [c for c in ["cases", "PRECTOTCORR_sum", "PRECTOTCORR_lag1", "PRECTOTCORR_lag2", "water_proxy"] if c in df.columns]
    sub  = df[cols].dropna().sample(min(600, len(df)), random_state=42)

    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=0.85)
    g = sns.pairplot(sub, diag_kind="kde",
                     plot_kws={"alpha": 0.45, "s": 18, "color": "#1E40AF"},
                     diag_kws={"fill": True, "color": "#93C5FD"})
    g.fig.suptitle("Pair Plot: Cases & Precipitation Features", y=1.02, fontsize=13, fontweight="bold")
    return _fig_to_b64(g.fig)


# ── PLOT 4: Cases & Cyclical Features ────────────────────────────────────────
@router.get("/insights/plot/cyclic")
def get_plot_cyclic():
    plt, sns = _ensure_mpl()
    try:
        df = _load_df()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    cols = [c for c in ["cases", "month_sin", "month_cos", "week_sin", "week_cos"] if c in df.columns]
    sub  = df[cols].dropna().sample(min(600, len(df)), random_state=42)

    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=0.85)
    g = sns.pairplot(sub, diag_kind="kde",
                     plot_kws={"alpha": 0.45, "s": 18, "color": "#7C3AED"},
                     diag_kws={"fill": True, "color": "#DDD6FE"})
    g.fig.suptitle("Pair Plot: Cases & Cyclical Features", y=1.02, fontsize=13, fontweight="bold")
    return _fig_to_b64(g.fig)


# ── PLOT 5: Key Features coloured by case level ───────────────────────────────
@router.get("/insights/plot/key")
def get_plot_key():
    plt, sns = _ensure_mpl()
    try:
        df = _load_df()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    key_cols = [c for c in ["cases", "T2M_mean", "RH2M_mean", "PRECTOTCORR_sum", "t1_cases"] if c in df.columns]
    sub = df[key_cols].dropna().sample(min(600, len(df)), random_state=42).copy()

    bins   = [-1, 10, 50, max(51, sub["cases"].max() + 1)]
    labels = ["Low", "Medium", "High"]
    sub["Case Level"] = pd.cut(sub["cases"], bins=bins, labels=labels)

    palette = {"Low": "#10B981", "Medium": "#F59E0B", "High": "#EF4444"}

    sns.set_style("whitegrid")
    sns.set_context("notebook", font_scale=0.85)
    g = sns.pairplot(sub, vars=key_cols, hue="Case Level", palette=palette,
                     diag_kind="kde",
                     plot_kws={"alpha": 0.5, "s": 22},
                     diag_kws={"fill": True, "alpha": 0.45})
    g.fig.suptitle("Pair Plot: Key Features (Coloured by Case Level)", y=1.02, fontsize=13, fontweight="bold")
    return _fig_to_b64(g.fig)


# ── PLOT 6: Full Correlation Heatmap ─────────────────────────────────────────
@router.get("/insights/plot/heatmap")
def get_plot_heatmap():
    plt, sns = _ensure_mpl()
    try:
        df = _load_df()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    numeric_cols = df.select_dtypes(include=np.number).columns
    corr_matrix  = df[numeric_cols].corr()
    mask = np.triu(np.ones_like(corr_matrix, dtype=bool))

    n = len(numeric_cols)
    fig_size = max(14, n * 0.7)
    fig, ax = plt.subplots(figsize=(fig_size, fig_size * 0.85))

    sns.set_style("white")
    sns.heatmap(
        corr_matrix, mask=mask, annot=(n <= 20), fmt=".2f",
        cmap="RdBu_r", center=0, square=True,
        linewidths=0.4, cbar_kws={"shrink": 0.75},
        ax=ax, annot_kws={"size": 7},
    )
    ax.set_title("Feature Correlation Matrix", fontsize=15, fontweight="bold", pad=18)
    fig.tight_layout()
    return _fig_to_b64(fig, dpi=100)

