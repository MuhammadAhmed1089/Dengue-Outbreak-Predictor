/* ═══════════════════════════════════════════
   Dengue Predictor — Model Comparison Page
   Fixed: implicit `event` global in switchMdTab,
          metrics fetched from /api/models/metrics with demo fallback.
═══════════════════════════════════════════ */

const API_BASE = "http://localhost:8000"; // keep in sync with forecast.js

const TEAL = "#0D9488",
  BLUE = "#0284C7",
  SLATE = "#64748B",
  AMBER = "#F59E0B",
  ROSE = "#F43F5E",
  GREEN = "#10B981";
const cfg = { responsive: true, displayModeBar: false };
const base = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  margin: { t: 10, r: 16, b: 40, l: 50 },
  font: { family: "Outfit,sans-serif", color: "#475569", size: 11 },
  xaxis: {
    gridcolor: "#F1F5F9",
    linecolor: "#E2E8F0",
    tickfont: { color: "#94A3B8" },
  },
  yaxis: {
    gridcolor: "#F1F5F9",
    linecolor: "#E2E8F0",
    tickfont: { color: "#94A3B8" },
  },
  legend: { bgcolor: "transparent", font: { color: "#475569" } },
};

// ── REVEAL ───────────────────────────────────────────────
const observer = new IntersectionObserver(
  (es) => {
    es.forEach((e) => {
      if (e.isIntersecting) e.target.classList.add("visible");
    });
  },
  { threshold: 0.08 },
);
document.querySelectorAll(".reveal").forEach((el) => observer.observe(el));

// ── FALLBACK MODEL DATA (used when API unavailable) ───────
const DEMO_MODELS = {
  rf: {
    name: "Random Forest",
    color: TEAL,
    valR2: 0.79,
    valRmse: 13.2,
    valMae: 7.8,
    testR2: 0.74,
    cvMean: 0.74,
    cvStd: 0.06,
  },
  xgb: {
    name: "XGBoost",
    color: BLUE,
    valR2: 0.76,
    valRmse: 14.1,
    valMae: 8.3,
    testR2: 0.72,
    cvMean: 0.72,
    cvStd: 0.07,
  },
  lr: {
    name: "Linear Regression",
    color: SLATE,
    valR2: 0.61,
    valRmse: 18.4,
    valMae: 11.2,
    testR2: 0.58,
    cvMean: 0.59,
    cvStd: 0.08,
  },
  rfob: {
    name: "RF Outbreak",
    color: AMBER,
    valR2: 0.83,
    valRmse: 11.6,
    valMae: 6.9,
    testR2: 0.41,
    cvMean: 0.79,
    cvStd: 0.09,
  },
};

// Will be populated from API or demo
let models = { ...DEMO_MODELS };
let currentModel = "rf";

// ── FETCH METRICS FROM API ───────────────────────────────
async function loadMetrics() {
  try {
    const res = await fetch(`${API_BASE}/api/models/metrics`);
    if (!res.ok) return;
    const data = await res.json();
    const m = data.models;

    // Map API shape → local shape (gracefully fill nulls with demo values)
    const map = (key, demo) => ({
      name: m[key]?.name ?? demo.name,
      color: m[key]?.color ?? demo.color,
      valR2: m[key]?.val_r2 ?? demo.valR2,
      valRmse: m[key]?.val_rmse ?? demo.valRmse,
      valMae: m[key]?.val_mae ?? demo.valMae,
      testR2: m[key]?.test_r2 ?? demo.testR2,
      cvMean: m[key]?.cv_mean ?? demo.cvMean,
      cvStd: m[key]?.cv_std ?? demo.cvStd,
    });

    models = {
      rf: map("rf", DEMO_MODELS.rf),
      xgb: map("xgb", DEMO_MODELS.xgb),
      lr: map("lr", DEMO_MODELS.lr),
      rfob: map("rfob", DEMO_MODELS.rfob),
    };
  } catch (_) {
    // backend unavailable — keep demo values
  }

  renderMetricCards(currentModel);
}

// ── MODEL SELECTOR ────────────────────────────────────────
window.selectModel = function (id) {
  currentModel = id;
  document
    .querySelectorAll(".model-pill")
    .forEach((p) => p.classList.remove("active"));
  document.getElementById("pill-" + id).classList.add("active");
  renderMetricCards(id);
};

function renderMetricCards(id) {
  const m = models[id];
  const best = id === "rf";

  const fmtR2 = (v) =>
    v == null ? "N/A" : typeof v === "number" ? v.toFixed(2) : v;
  const fmtRmse = (v) =>
    v == null ? "N/A" : typeof v === "number" ? v.toFixed(1) : v;
  const deltaDom = (val, ref, invert = false) => {
    if (val == null) return "";
    const diff = (val - ref) * (invert ? -1 : 1);
    return diff >= 0
      ? `<span style="color:#10b981">↑ +${Math.abs(diff).toFixed(2)}</span>`
      : `<span style="color:#ef4444">↓ ${diff.toFixed(2)}</span>`;
  };

  document.getElementById("metric-cards").innerHTML = `
    <div class="metric-card teal">
      <div class="metric-card-label">Val R² (2019)</div>
      <div class="metric-card-val">${fmtR2(m.valR2)}</div>
      <div class="metric-card-delta">${best ? "↑ Best model" : deltaDom(m.valR2, models.rf.valR2)}</div>
      <div class="metric-card-sub">Outbreak year — harder to predict</div>
    </div>
    <div class="metric-card blue">
      <div class="metric-card-label">Val RMSE</div>
      <div class="metric-card-val">${fmtRmse(m.valRmse)}</div>
      <div class="metric-card-delta ${!best ? "worse" : ""}">${best ? "↑ Lowest error" : "vs RF RF: +" + (m.valRmse - models.rf.valRmse).toFixed(1)}</div>
      <div class="metric-card-sub">Cases/week average error</div>
    </div>
    <div class="metric-card slate">
      <div class="metric-card-label">Test R² (2020)</div>
      <div class="metric-card-val">${fmtR2(m.testR2)}</div>
      <div class="metric-card-delta ${id === "rfob" ? "worse" : ""}">${id === "rfob" ? "↓ Degrades on normal year" : "Generalizes well"}</div>
      <div class="metric-card-sub">Normal year generalization</div>
    </div>
    <div class="metric-card amber">
      <div class="metric-card-label">CV R² Mean</div>
      <div class="metric-card-val">${fmtR2(m.cvMean)} <span style="font-size:1rem;color:var(--text-muted)">±${m.cvStd}</span></div>
      <div class="metric-card-delta">5-fold TimeSeriesSplit</div>
      <div class="metric-card-sub">Temporal cross-validation</div>
    </div>`;
}

// ── TAB SWITCHING ─────────────────────────────────────────
// FIX: receive event as explicit parameter
window.switchMdTab = function (id, event) {
  document
    .querySelectorAll(".md-tab")
    .forEach((t) => t.classList.remove("active"));
  document
    .querySelectorAll(".md-panel")
    .forEach((p) => p.classList.remove("active"));
  event.currentTarget.classList.add("active");
  document.getElementById("md-" + id).classList.add("active");
  renderTab(id);
};

const rendered = {};
function renderTab(id) {
  if (rendered[id]) return;
  rendered[id] = true;
  if (id === "importance") renderImportance();
  if (id === "residuals") renderResiduals();
  if (id === "shap") renderShap();
}

// ── INIT ─────────────────────────────────────────────────
window.addEventListener("load", () => {
  loadMetrics(); // async: fetches from API then re-renders cards
  renderLearningCurves();
  renderCvFolds();
});

// ── CHARTS ───────────────────────────────────────────────
function renderLearningCurves() {
  const n = [50, 100, 160, 220, 280, 340, 400, 460, 520, 580];
  const lrT = [0.62, 0.63, 0.63, 0.62, 0.62, 0.62, 0.61, 0.61, 0.61, 0.61];
  const lrV = [0.38, 0.44, 0.48, 0.51, 0.53, 0.55, 0.57, 0.58, 0.59, 0.6];
  const rfT = [0.98, 0.97, 0.96, 0.95, 0.94, 0.93, 0.92, 0.91, 0.91, 0.9];
  const rfV = [0.55, 0.62, 0.66, 0.69, 0.71, 0.73, 0.74, 0.75, 0.76, 0.77];
  const xgT = [0.95, 0.93, 0.91, 0.89, 0.88, 0.87, 0.86, 0.86, 0.85, 0.85];
  const xgV = [0.52, 0.59, 0.63, 0.67, 0.69, 0.71, 0.72, 0.73, 0.74, 0.75];

  Plotly.newPlot(
    "lc-r2",
    [
      {
        x: n,
        y: rfT,
        mode: "lines",
        name: "RF Train",
        line: { color: TEAL, dash: "dot", width: 1.8 },
      },
      {
        x: n,
        y: rfV,
        mode: "lines",
        name: "RF Val",
        line: { color: TEAL, width: 2.5 },
      },
      {
        x: n,
        y: xgT,
        mode: "lines",
        name: "XGB Train",
        line: { color: BLUE, dash: "dot", width: 1.8 },
      },
      {
        x: n,
        y: xgV,
        mode: "lines",
        name: "XGB Val",
        line: { color: BLUE, width: 2.5 },
      },
      {
        x: n,
        y: lrT,
        mode: "lines",
        name: "LR Train",
        line: { color: SLATE, dash: "dot", width: 1.8 },
      },
      {
        x: n,
        y: lrV,
        mode: "lines",
        name: "LR Val",
        line: { color: SLATE, width: 2.5 },
      },
    ],
    {
      ...base,
      xaxis: { ...base.xaxis, title: "Training Samples" },
      yaxis: { ...base.yaxis, title: "R² Score", range: [0.25, 1.05] },
    },
    cfg,
  );

  Plotly.newPlot(
    "lc-bar",
    [
      {
        x: ["Linear Regression", "Random Forest", "XGBoost", "RF Outbreak"],
        y: [0.61, 0.79, 0.76, 0.83],
        type: "bar",
        name: "Val R²",
        marker: {
          color: [SLATE, TEAL, BLUE, AMBER],
          opacity: 0.85,
          line: { color: "white", width: 1 },
        },
        text: [".61", ".79", ".76", ".83"],
        textposition: "outside",
        hovertemplate: "<b>%{x}</b><br>Val R²: %{y}<extra></extra>",
      },
      {
        x: ["Linear Regression", "Random Forest", "XGBoost", "RF Outbreak"],
        y: [0.58, 0.74, 0.72, 0.41],
        type: "bar",
        name: "Test R²",
        marker: {
          color: [SLATE, TEAL, BLUE, AMBER],
          opacity: 0.45,
          line: { color: "white", width: 1 },
        },
        text: [".58", ".74", ".72", ".41"],
        textposition: "outside",
        hovertemplate: "<b>%{x}</b><br>Test R²: %{y}<extra></extra>",
      },
    ],
    {
      ...base,
      barmode: "group",
      yaxis: { ...base.yaxis, title: "R² Score", range: [0, 1] },
      legend: { ...base.legend, x: 0.6, y: 1 },
      annotations: [
        {
          x: "RF Outbreak",
          y: 0.87,
          text: "Overfits to 2019",
          showarrow: true,
          arrowhead: 2,
          font: { size: 10, color: ROSE },
          arrowcolor: ROSE,
        },
      ],
    },
    cfg,
  );

  const rounds = Array.from({ length: 200 }, (_, i) => i + 1);
  const noise = () => Math.random() * 0.6 - 0.3;
  Plotly.newPlot(
    "xgb-curve",
    [
      {
        x: rounds,
        y: rounds.map((r) => 29 * Math.exp(-r / 60) + 8 + noise()),
        mode: "lines",
        name: "Train RMSE",
        line: { color: TEAL, width: 2 },
      },
      {
        x: rounds,
        y: rounds.map((r) => 28 * Math.exp(-r / 82) + 14.5 + noise()),
        mode: "lines",
        name: "Val RMSE",
        line: { color: ROSE, width: 2 },
      },
    ],
    {
      ...base,
      xaxis: { ...base.xaxis, title: "Boosting Round" },
      yaxis: { ...base.yaxis, title: "RMSE (cases)" },
      shapes: [
        {
          type: "line",
          x0: 142,
          x1: 142,
          y0: 0,
          y1: 40,
          line: { color: GREEN, dash: "dash", width: 1.5 },
        },
      ],
      annotations: [
        {
          x: 142,
          y: 38,
          text: "Best: 142",
          showarrow: false,
          font: { color: GREEN, size: 11 },
        },
      ],
    },
    cfg,
  );
}

function renderImportance() {
  const feats = [
    "t1_cases",
    "t2_cases",
    "water_proxy",
    "PRECTOTCORR_sum",
    "T2M_mean",
    "RH2M_mean",
    "momentum",
    "isOutbreak",
    "week_cos",
    "WS10M_mean",
    "T2M_lag1",
    "PRECTOTCORR_lag1",
    "PRECTOTCORR_lag2",
    "month_sin",
    "district_encoded",
  ];
  const rfImps = [
    0.28, 0.19, 0.12, 0.1, 0.08, 0.07, 0.06, 0.04, 0.02, 0.01, 0.01, 0.01,
    0.005, 0.005, 0.005,
  ];
  const xgImps = [
    0.25, 0.17, 0.11, 0.09, 0.07, 0.06, 0.07, 0.05, 0.03, 0.02, 0.02, 0.02,
    0.01, 0.01, 0.02,
  ];
  const colors = (i) => (i < 2 ? TEAL : i < 5 ? BLUE : SLATE);

  Plotly.newPlot(
    "fi-rf",
    [
      {
        x: rfImps,
        y: feats,
        type: "bar",
        orientation: "h",
        marker: {
          color: feats.map((_, i) => colors(i)),
          opacity: 0.85,
          line: { color: "white", width: 0.5 },
        },
        text: rfImps.map((v) => (v * 100).toFixed(1) + "%"),
        textposition: "outside",
        hovertemplate: "<b>%{y}</b><br>%{x:.3f}<extra></extra>",
      },
    ],
    {
      ...base,
      margin: { t: 10, r: 55, b: 40, l: 155 },
      xaxis: { ...base.xaxis, title: "MDI Importance", range: [0, 0.35] },
      yaxis: { ...base.yaxis, autorange: "reversed" },
    },
    cfg,
  );
  Plotly.newPlot(
    "fi-xgb",
    [
      {
        x: xgImps,
        y: feats,
        type: "bar",
        orientation: "h",
        marker: {
          color: feats.map((_, i) => colors(i)),
          opacity: 0.85,
          line: { color: "white", width: 0.5 },
        },
        text: xgImps.map((v) => (v * 100).toFixed(1) + "%"),
        textposition: "outside",
        hovertemplate: "<b>%{y}</b><br>%{x:.3f}<extra></extra>",
      },
    ],
    {
      ...base,
      margin: { t: 10, r: 55, b: 40, l: 155 },
      xaxis: { ...base.xaxis, title: "Gain Importance", range: [0, 0.32] },
      yaxis: { ...base.yaxis, autorange: "reversed" },
    },
    cfg,
  );
  Plotly.newPlot(
    "fi-group",
    [
      {
        labels: ["Temporal Lags", "Climate", "Engineered", "Seasonal"],
        values: [0.48, 0.26, 0.18, 0.08],
        type: "pie",
        hole: 0.5,
        marker: { colors: [TEAL, BLUE, AMBER, SLATE] },
        textinfo: "label+percent",
        hovertemplate: "<b>%{label}</b><br>%{percent}<extra></extra>",
      },
    ],
    {
      ...base,
      margin: { t: 10, r: 10, b: 10, l: 10 },
      showlegend: true,
      legend: { orientation: "v", x: 1, y: 0.5 },
    },
    cfg,
  );
}

function renderResiduals() {
  const actual = Array.from({ length: 100 }, () =>
    Math.round(Math.random() * 300),
  );
  const predicted = actual.map(
    (a) => a + Math.round((Math.random() - 0.4) * a * 0.4),
  );
  const residuals = actual.map((a, i) => predicted[i] - a);

  Plotly.newPlot(
    "res-scatter",
    [
      {
        x: actual,
        y: predicted,
        mode: "markers",
        type: "scatter",
        marker: {
          color: TEAL,
          opacity: 0.6,
          size: 7,
          line: { color: "white", width: 0.5 },
        },
        name: "Predictions",
        hovertemplate: "Actual: %{x}<br>Pred: %{y}<extra></extra>",
      },
      {
        x: [0, 300],
        y: [0, 300],
        mode: "lines",
        line: { color: ROSE, dash: "dash", width: 1.5 },
        name: "Perfect fit",
      },
    ],
    {
      ...base,
      xaxis: { ...base.xaxis, title: "Actual Cases" },
      yaxis: { ...base.yaxis, title: "Predicted Cases" },
    },
    cfg,
  );

  Plotly.newPlot(
    "res-hist",
    [
      {
        x: residuals,
        type: "histogram",
        nbinsx: 25,
        marker: {
          color: TEAL,
          opacity: 0.75,
          line: { color: "white", width: 0.5 },
        },
        name: "Residuals",
      },
    ],
    {
      ...base,
      xaxis: { ...base.xaxis, title: "Residual (Pred − Actual)" },
      yaxis: { ...base.yaxis, title: "Count" },
      shapes: [
        {
          type: "line",
          x0: 0,
          x1: 0,
          y0: 0,
          y1: 20,
          line: { color: ROSE, dash: "dash", width: 1.5 },
        },
      ],
    },
    cfg,
  );

  const weeks = Array.from({ length: 52 }, (_, i) => i + 1);
  const groundT = weeks.map((w) =>
    Math.max(
      0,
      Math.round(
        280 * Math.exp(-0.5 * Math.pow((w - 38) / 10, 2)) + Math.random() * 15,
      ),
    ),
  );
  const preds = groundT.map((v) =>
    Math.max(0, v + Math.round((Math.random() - 0.4) * v * 0.35)),
  );
  Plotly.newPlot(
    "res-ts",
    [
      {
        x: weeks,
        y: groundT,
        mode: "lines+markers",
        name: "Actual",
        line: { color: ROSE, width: 2 },
        marker: { size: 5 },
      },
      {
        x: weeks,
        y: preds,
        mode: "lines+markers",
        name: "RF Predicted",
        line: { color: TEAL, width: 2, dash: "dot" },
        marker: { size: 5 },
      },
    ],
    {
      ...base,
      xaxis: { ...base.xaxis, title: "Epidemiological Week (2019)" },
      yaxis: { ...base.yaxis, title: "Cases" },
      legend: { ...base.legend, x: 0.02, y: 0.98 },
    },
    cfg,
  );
}

function renderShap() {
  const feats = [
    "t1_cases",
    "t2_cases",
    "water_proxy",
    "RH2M_mean",
    "T2M_mean",
    "PRECTOTCORR_sum",
    "momentum",
    "week_cos",
    "isOutbreak",
    "WS10M_mean",
  ];
  const shapVals = [8.2, 5.9, 3.1, 2.4, 1.8, 1.6, 1.1, 0.8, 0.6, 0.3];
  Plotly.newPlot(
    "shap-global",
    [
      {
        x: shapVals,
        y: feats,
        type: "bar",
        orientation: "h",
        marker: {
          color: TEAL,
          opacity: 0.82,
          line: { color: "white", width: 0.5 },
        },
        text: shapVals.map((v) => v.toFixed(1)),
        textposition: "outside",
        hovertemplate: "<b>%{y}</b><br>Mean |SHAP|: %{x}<extra></extra>",
      },
    ],
    {
      ...base,
      margin: { t: 10, r: 50, b: 40, l: 145 },
      xaxis: { ...base.xaxis, title: "Mean |SHAP value|", range: [0, 10] },
      yaxis: { ...base.yaxis, autorange: "reversed" },
    },
    cfg,
  );

  const tempX = Array.from({ length: 120 }, () => 20 + Math.random() * 20);
  const humColor = tempX.map(() => 40 + Math.random() * 55);
  const shapY = tempX.map(
    (t, i) => (t - 29) * 0.6 + humColor[i] * 0.03 + Math.random() * 0.8 - 2,
  );
  Plotly.newPlot(
    "shap-dep",
    [
      {
        x: tempX,
        y: shapY,
        mode: "markers",
        type: "scatter",
        marker: {
          color: humColor,
          colorscale: [
            [0, "#E0F2FE"],
            [1, "#0284C7"],
          ],
          size: 8,
          opacity: 0.7,
          showscale: true,
          colorbar: { title: "RH%", thickness: 12, len: 0.7 },
        },
        hovertemplate:
          "Temp: %{x:.1f}°C<br>SHAP: %{y:.2f}<br>RH: %{marker.color:.0f}%<extra></extra>",
      },
    ],
    {
      ...base,
      xaxis: { ...base.xaxis, title: "T2M_mean (°C)" },
      yaxis: { ...base.yaxis, title: "SHAP value for Temperature" },
      shapes: [
        {
          type: "line",
          x0: 20,
          x1: 40,
          y0: 0,
          y1: 0,
          line: { color: ROSE, dash: "dash", width: 1 },
        },
      ],
    },
    cfg,
  );
}

function renderCvFolds() {
  const folds = ["Fold 1", "Fold 2", "Fold 3", "Fold 4", "Fold 5"];
  Plotly.newPlot(
    "cv-folds",
    [
      {
        x: folds,
        y: [0.67, 0.63, 0.61, 0.58, 0.54],
        type: "bar",
        name: "Linear Regression",
        marker: { color: SLATE, opacity: 0.8 },
      },
      {
        x: folds,
        y: [0.82, 0.79, 0.77, 0.72, 0.68],
        type: "bar",
        name: "Random Forest",
        marker: { color: TEAL, opacity: 0.8 },
      },
      {
        x: folds,
        y: [0.79, 0.76, 0.74, 0.7, 0.66],
        type: "bar",
        name: "XGBoost",
        marker: { color: BLUE, opacity: 0.8 },
      },
    ],
    {
      ...base,
      barmode: "group",
      yaxis: { ...base.yaxis, title: "R² Score", range: [0, 1] },
      legend: { ...base.legend, x: 0.7, y: 1 },
    },
    cfg,
  );
}
