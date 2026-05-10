"""
POST /api/predict
Runs the full hybrid prediction pipeline:
  1. Encode district
  2. Engineer features (waterProxy, momentum, cyclical encoding)
  3. Outbreak classifier → route to endemic or outbreak expert
  4. Regressor predicts case count
  5. DynamicBinner classifies severity
  6. SHAP TreeExplainer computes feature attributions
"""

import math
import sys
import types
from pathlib import Path
from functools import lru_cache

import joblib
import numpy as np
import pandas as pd
import shap
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


# ── DynamicBinner (must match notebook definition for pickle to work) ─────────
class DynamicBinner:
    """Custom severity binner — must match the notebook definition."""

    def transform(self, X):
        X = np.asarray(X)
        result = np.zeros(len(X), dtype=int)
        for i, x in enumerate(X):
            thresholds = getattr(self, 'thresholds', [2, 5, 9])
            if x <= thresholds[0]:
                result[i] = 0
            elif x <= thresholds[1]:
                result[i] = 1
            elif x <= thresholds[2]:
                result[i] = 2
            else:
                result[i] = 3
        return result


# Register in __main__ so pickle can find the class
if '__main__' not in sys.modules:
    sys.modules['__main__'] = types.ModuleType('__main__')
sys.modules['__main__'].DynamicBinner = DynamicBinner

router = APIRouter()

# ── PATHS ────────────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from config import MODELS_DIR, DATA_DIR


# ── LAZY MODEL LOADER (cached after first call) ───────────────────────────────
@lru_cache(maxsize=1)
def _load_artifacts():
    """Load all pkl files once and cache them in memory."""
    def _load(name):
        p = MODELS_DIR / name
        if not p.exists():
            raise FileNotFoundError(f"Model file not found: {p}")
        return joblib.load(p)

    return {
        "scaler":                      _load("scaler.pkl"),
        "district_encoder":            _load("district_encoder.pkl"),
        "outbreak_classifier":         _load("outbreak_classifier.pkl"),
        "rf_regressor":                _load("rf_regressor.pkl"),
        "xgboost_regressor":           _load("xgboost_regressor.pkl"),
        "rf_regressor_outbreak":       _load("rf_regressor_outbreak.pkl"),
        "xgboost_regressor_outbreak":  _load("xgboost_regressor_Outbreak.pkl"),
        "severity_classifier":         _load("severity_classifier.pkl"),
        "dynamic_binner":              _load("dynamic_binner.pkl"),
    }


@lru_cache(maxsize=1)
def _load_processed_data() -> pd.DataFrame:
    """Load the processed dataset for lag-feature lookups."""
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
        f"Processed data not found. Looked in: {[str(c) for c in candidates]}"
    )


# ── FEATURE NAMES (must match training order exactly) ────────────────────────
REGRESSOR_FEATURES = [
    "district_encoded", "T2M_mean", "RH2M_mean", "PRECTOTCORR_sum", "WS10M_mean",
    "T2M_lag1", "PRECTOTCORR_lag1", "PRECTOTCORR_lag2",
    "t1_cases", "t2_cases",
    "waterProxy",
    "month_sin", "week_cos", "momentum", "isOutbreak",
]

# Matches the classifier trained in modelTraining.ipynb (Cell 10 / Cell 12)
CLASSIFIER_FEATURES = [
    "district_encoded", "T2M_mean", "RH2M_mean", "PRECTOTCORR_sum",
    "waterProxy", "t1_cases", "t2_cases", "momentum",
    "cases_acceleration", "t1_cases_zscore", "month_sin", "week_cos",
]

SEVERITY_LABEL_NAMES = ["Low", "Medium", "High", "Severe"]
SEVERITY_COLORS = {
    "Low":    "#10b981",
    "Medium": "#f59e0b",
    "High":   "#ea580c",
    "Severe": "#dc2626",
}


# ── EPI-WEEK → MONTH helper ───────────────────────────────────────────────────
def _epi_week_to_month(epi_week: int) -> int:
    """Approximate epi-week to calendar month (1–12)."""
    return max(1, min(12, math.ceil(epi_week / 4.33)))


# ── REQUEST / RESPONSE SCHEMAS ────────────────────────────────────────────────
class PredictRequest(BaseModel):
    district:         str   = Field(...,       example="Lahore")
    epi_week:         int   = Field(...,       ge=1, le=52, example=32)
    T2M_mean:         float = Field(...,       example=33.2)
    RH2M_mean:        float = Field(...,       example=72.0)
    PRECTOTCORR_sum:  float = Field(...,       example=8.3)
    WS10M_mean:       float = Field(...,       example=2.8)
    t1_cases:         float = Field(0.0, ge=0, example=45.0)
    t2_cases:         float = Field(0.0, ge=0, example=30.0)
    # Optional climate lags — looked up from data if not provided
    T2M_lag1:         float | None = Field(None, example=32.5)
    PRECTOTCORR_lag1: float | None = Field(None, example=5.2)
    PRECTOTCORR_lag2: float | None = Field(None, example=3.1)


class ShapEntry(BaseModel):
    feature:    str
    shap_value: float
    raw_value:  float


class PredictResponse(BaseModel):
    district:            str
    epi_week:            int
    predicted_cases:     float
    predicted_cases_int: int
    severity:            str
    severity_color:      str
    model_used:          str
    is_outbreak:         bool
    shap_values:         list[ShapEntry]
    confidence_low:      float
    confidence_high:     float


# ── HELPERS ──────────────────────────────────────────────────────────────────
def _get_lag_climate(district_encoded: int, epi_week: int, df: pd.DataFrame):
    """Look up last week's T2M and 1-2 week lag precip from processed data."""
    sub = df[df["district_encoded"] == district_encoded].copy()
    if sub.empty:
        return 0.0, 0.0, 0.0

    target_week = epi_week - 1 if epi_week > 1 else 52
    row1 = sub[sub["epi_week"] == target_week]
    if row1.empty:
        row1 = sub.sort_values("epi_week").iloc[[-1]]

    T2M_lag1         = float(row1["T2M_mean"].values[0])        if "T2M_mean"        in row1 else 0.0
    PRECTOTCORR_lag1 = float(row1["PRECTOTCORR_sum"].values[0]) if "PRECTOTCORR_sum" in row1 else 0.0

    target_week2 = epi_week - 2 if epi_week > 2 else 51
    row2 = sub[sub["epi_week"] == target_week2]
    if row2.empty:
        row2 = row1
    PRECTOTCORR_lag2 = float(row2["PRECTOTCORR_sum"].values[0]) if "PRECTOTCORR_sum" in row2 else 0.0

    return T2M_lag1, PRECTOTCORR_lag1, PRECTOTCORR_lag2


def _build_regressor_row(req: PredictRequest, district_encoded: int,
                          df: pd.DataFrame) -> pd.DataFrame:
    """Assemble a single-row DataFrame matching REGRESSOR_FEATURES order."""
    week      = req.epi_week
    month     = _epi_week_to_month(week)
    month_sin = math.sin(2 * math.pi * month / 12)
    week_cos  = math.cos(2 * math.pi * week  / 52)

    water_proxy = req.PRECTOTCORR_sum * (req.RH2M_mean / 100.0)
    momentum    = req.t1_cases - req.t2_cases
    is_outbreak = int(req.t1_cases >= 40)

    if req.T2M_lag1 is not None:
        T2M_lag1         = req.T2M_lag1
        PRECTOTCORR_lag1 = req.PRECTOTCORR_lag1 or 0.0
        PRECTOTCORR_lag2 = req.PRECTOTCORR_lag2 or 0.0
    else:
        T2M_lag1, PRECTOTCORR_lag1, PRECTOTCORR_lag2 = _get_lag_climate(
            district_encoded, week, df
        )

    row = {
        "district_encoded":  district_encoded,
        "T2M_mean":          req.T2M_mean,
        "RH2M_mean":         req.RH2M_mean,
        "PRECTOTCORR_sum":   req.PRECTOTCORR_sum,
        "WS10M_mean":        req.WS10M_mean,
        "T2M_lag1":          T2M_lag1,
        "PRECTOTCORR_lag1":  PRECTOTCORR_lag1,
        "PRECTOTCORR_lag2":  PRECTOTCORR_lag2,
        "t1_cases":          req.t1_cases,
        "t2_cases":          req.t2_cases,
        "waterProxy":        water_proxy,
        "month_sin":         month_sin,
        "week_cos":          week_cos,
        "momentum":          momentum,
        "isOutbreak":        is_outbreak,
    }
    return pd.DataFrame([row])[REGRESSOR_FEATURES]


def _build_classifier_row(req: PredictRequest, district_encoded: int,
                           df: pd.DataFrame) -> pd.DataFrame:
    """
    Assemble a single-row DataFrame matching CLASSIFIER_FEATURES order.
    Replicates applyFeatureEngineering() from modelTraining.ipynb:
      - t1_cases_zscore: z-score of t1_cases relative to district's distribution
      - cases_acceleration: change in momentum (momentum - prev_momentum)
    """
    week      = req.epi_week
    month     = _epi_week_to_month(week)
    month_sin = math.sin(2 * math.pi * month / 12)
    week_cos  = math.cos(2 * math.pi * week  / 52)

    water_proxy = req.PRECTOTCORR_sum * (req.RH2M_mean / 100.0)
    momentum    = req.t1_cases - req.t2_cases

    # t1_cases_zscore — use per-district stats from the processed CSV
    district_rows = df[df["district_encoded"] == district_encoded]["t1_cases"].dropna()
    d_mean = float(district_rows.mean()) if len(district_rows) else 0.0
    d_std  = float(district_rows.std())  if len(district_rows) > 1 else 1.0
    t1_cases_zscore = (req.t1_cases - d_mean) / (d_std + 1e-6)

    # cases_acceleration — momentum change; best approximation at inference time
    # is momentum - (t2_cases - t3_cases). Without t3, use t2 as previous momentum.
    prev_momentum      = req.t2_cases - 0.0   # approximate: assume t3=0
    cases_acceleration = momentum - prev_momentum

    row = {
        "district_encoded":   district_encoded,
        "T2M_mean":           req.T2M_mean,
        "RH2M_mean":          req.RH2M_mean,
        "PRECTOTCORR_sum":    req.PRECTOTCORR_sum,
        "waterProxy":         water_proxy,
        "t1_cases":           req.t1_cases,
        "t2_cases":           req.t2_cases,
        "momentum":           momentum,
        "cases_acceleration": cases_acceleration,
        "t1_cases_zscore":    t1_cases_zscore,
        "month_sin":          month_sin,
        "week_cos":           week_cos,
    }
    return pd.DataFrame([row])[CLASSIFIER_FEATURES]


def _compute_shap(model, X_row: pd.DataFrame) -> list[dict]:
    """Compute SHAP values using TreeExplainer; return top-10 sorted list."""
    try:
        explainer = shap.TreeExplainer(model)
        shap_vals = explainer.shap_values(X_row)
        sv_flat   = shap_vals[0] if shap_vals.ndim > 1 else shap_vals.flatten()
        entries = [
            {"feature": feat, "shap_value": float(sv), "raw_value": float(rv)}
            for feat, sv, rv in zip(REGRESSOR_FEATURES, sv_flat, X_row.values[0])
        ]
        entries.sort(key=lambda x: abs(x["shap_value"]), reverse=True)
        return entries[:10]
    except Exception:
        return []


# ── ENDPOINT ─────────────────────────────────────────────────────────────────
@router.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    try:
        artifacts = _load_artifacts()
        df        = _load_processed_data()
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # ── 1. Encode district ────────────────────────────────────────────────────
    encoder  = artifacts["district_encoder"]
    district = req.district.strip()   # keep original casing — encoder trained on Title Case
    try:
        # OrdinalEncoder expects a 2-D array: [["Lahore"]]
        district_encoded = int(encoder.transform([[district]])[0][0])
    except Exception:
        if isinstance(encoder, dict):
            # Try exact → title-case → case-insensitive scan
            match = (
                encoder.get(district)
                or encoder.get(district.title())
                or next((v for k, v in encoder.items()
                         if k.lower() == district.lower()), None)
            )
            if match is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown district: {req.district}"
                )
            district_encoded = match
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown district: {req.district}"
            )

    # ── 2. Build regressor feature row ───────────────────────────────────────
    X = _build_regressor_row(req, district_encoded, df)

    # ── 3. Build classifier feature row & predict outbreak ───────────────────
    X_clf            = _build_classifier_row(req, district_encoded, df)
    clf              = artifacts["outbreak_classifier"]
    is_outbreak_pred = bool(clf.predict(X_clf)[0])

    # ── 4. Regression ─────────────────────────────────────────────────────────
    if is_outbreak_pred:
        model      = artifacts["rf_regressor_outbreak"]
        model_name = "RF Outbreak Expert"
    else:
        model      = artifacts["rf_regressor"]
        model_name = "Random Forest (Endemic)"

    predicted_raw   = float(model.predict(X)[0])
    predicted_cases = max(0.0, round(predicted_raw, 2))

    # ── 5. Confidence interval (~20%) ─────────────────────────────────────────
    ci_half         = max(1.0, predicted_cases * 0.20)
    confidence_low  = max(0.0, round(predicted_cases - ci_half, 1))
    confidence_high = round(predicted_cases + ci_half, 1)

    # ── 6. Severity classification ────────────────────────────────────────────
    binner = artifacts["dynamic_binner"]
    try:
        sev_label_idx = int(binner.transform([predicted_cases])[0])
        severity = SEVERITY_LABEL_NAMES[sev_label_idx]
    except Exception:
        if   predicted_cases <= 2: severity = "Low"
        elif predicted_cases <= 5: severity = "Medium"
        elif predicted_cases <= 9: severity = "High"
        else:                      severity = "Severe"

    # ── 7. SHAP ───────────────────────────────────────────────────────────────
    shap_entries = _compute_shap(model, X)
    shap_out     = [ShapEntry(**e) for e in shap_entries]

    return PredictResponse(
        district            = req.district,
        epi_week            = req.epi_week,
        predicted_cases     = predicted_cases,
        predicted_cases_int = int(round(predicted_cases)),
        severity            = severity,
        severity_color      = SEVERITY_COLORS.get(severity, "#64748b"),
        model_used          = model_name,
        is_outbreak         = is_outbreak_pred,
        shap_values         = shap_out,
        confidence_low      = confidence_low,
        confidence_high     = confidence_high,
    )