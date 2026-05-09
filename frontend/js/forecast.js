/* ═══════════════════════════════════════════
   Dengue Predictor — Forecast / Home Page Logic
═══════════════════════════════════════════ */

// ── CONFIG ───────────────────────────────────────────────
const TEAL = "#0D9488",
  BLUE = "#0284C7",
  SLATE = "#64748B",
  AMBER = "#F59E0B",
  ROSE = "#F43F5E";
const plotConfig = { responsive: true, displayModeBar: false };
const baseLayout = {
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  margin: { t: 10, r: 10, b: 40, l: 50 },
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

// ── LOADING SCREEN ───────────────────────────────────────
const loadingScreen = document.getElementById("loading-screen");
const mainContent = document.getElementById("main-content");
const loaderStatus = document.getElementById("loaderStatus");
const statusMessages = [
  "Loading models...",
  "Loading district boundaries...",
  "Connecting to surveillance data...",
  "Ready to launch",
];
let statusIndex = 0;

function cycleStatus() {
  if (statusIndex < statusMessages.length) {
    loaderStatus.innerHTML =
      statusMessages[statusIndex] +
      '<span class="dot">.</span><span class="dot">.</span><span class="dot">.</span>';
    statusIndex++;
    setTimeout(cycleStatus, 600);
  }
}
setTimeout(cycleStatus, 2400);

function hideLoading() {
  loadingScreen.classList.add("hidden");
  mainContent.style.opacity = "1";
  renderAllCharts();
}
setTimeout(hideLoading, 5000);

window.replayLoading = function () {
  loadingScreen.classList.remove("hidden");
  mainContent.style.opacity = "0";
  statusIndex = 0;
  const bar = loadingScreen.querySelector(".loader-bar");
  bar.style.animation = "none";
  bar.offsetHeight;
  bar.style.animation = "";
  setTimeout(hideLoading, 5000);
};

// ── NAVBAR SCROLL ────────────────────────────────────────
const navbar = document.getElementById("navbar");
window.addEventListener("scroll", () => {
  navbar.classList.toggle("scrolled", window.scrollY > 50);
});

// ── SCROLL REVEAL ────────────────────────────────────────
const revealObs = new IntersectionObserver(
  (entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) e.target.classList.add("visible");
    });
  },
  { threshold: 0.1, rootMargin: "0px 0px -50px 0px" },
);
document.querySelectorAll(".reveal").forEach((el) => revealObs.observe(el));

// ── COUNT UP ─────────────────────────────────────────────
const countObs = new IntersectionObserver(
  (entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        const el = e.target,
          target = parseInt(el.dataset.count),
          start = performance.now();
        function upd(now) {
          const p = Math.min((now - start) / 1500, 1),
            ease = 1 - Math.pow(1 - p, 3);
          el.textContent = Math.round(ease * target);
          if (p < 1) requestAnimationFrame(upd);
        }
        requestAnimationFrame(upd);
        countObs.unobserve(el);
      }
    });
  },
  { threshold: 0.5 },
);
document.querySelectorAll("[data-count]").forEach((el) => countObs.observe(el));

// ── TABS ─────────────────────────────────────────────────
window.switchTab = function (id) {
  document
    .querySelectorAll(".ins-tab")
    .forEach((t) => t.classList.remove("active"));
  document
    .querySelectorAll(".tab-panel")
    .forEach((p) => p.classList.remove("active"));
  event.target.classList.add("active");
  document.getElementById("tab-" + id).classList.add("active");
  if (id === "model") renderModelCharts();
  if (id === "eda") renderEdaCharts();
};

// ── PREDICTION SIM ───────────────────────────────────────
function animateCounter(el, target, dur = 1200) {
  const s = performance.now();
  function upd(now) {
    const p = Math.min((now - s) / dur, 1),
      e = 1 - Math.pow(1 - p, 3);
    el.textContent = Math.round(e * target);
    if (p < 1) requestAnimationFrame(upd);
  }
  requestAnimationFrame(upd);
}

window.simulatePrediction = function () {
  const ra = document.getElementById("resultArea"),
    es = document.getElementById("emptyState"),
    cnt = document.getElementById("caseCount");
  es.style.display = "none";
  ra.style.display = "block";
  ra.classList.add("visible");
  cnt.textContent = "0";
  setTimeout(() => animateCounter(cnt, 247), 100);
};

window.toggleSeverity = function () {
  const b = document.getElementById("severityBadge");
  const dot =
    '<span style="width:8px;height:8px;border-radius:50%;background:currentColor;display:inline-block"></span>';
  if (b.classList.contains("sev-high")) {
    b.classList.replace("sev-high", "sev-critical");
    b.innerHTML = dot + " CRITICAL RISK";
  } else {
    b.classList.replace("sev-critical", "sev-high");
    b.innerHTML = dot + " HIGH RISK";
  }
};

// ═══════════════════════════════════════════════════════
// PLOTLY CHARTS
// ═══════════════════════════════════════════════════════
let chartsRendered = false;
function renderAllCharts() {
  if (chartsRendered) return;
  chartsRendered = true;
  renderEdaCharts();
}

// ── EDA Charts ───────────────────────────────────────────
function renderEdaCharts() {
  if (document.getElementById("chart-temp").children.length > 0) return;

  const tempVals = [
    22, 24, 25, 26, 27, 28, 28, 29, 30, 30, 31, 31, 32, 32, 33, 33, 34, 34, 35,
    35, 36, 36, 37, 38, 39, 40, 20, 21, 23, 24, 25, 26, 28, 30, 31, 32, 33, 34,
    35, 36,
  ];
  const caseVals = [
    2, 3, 4, 5, 8, 14, 18, 25, 40, 55, 70, 90, 120, 150, 210, 280, 320, 300,
    260, 240, 200, 180, 140, 100, 60, 30, 1, 1, 3, 4, 7, 12, 20, 45, 80, 130,
    190, 270, 310, 230,
  ];
  const sizes = caseVals.map((v) => Math.max(5, Math.sqrt(v) * 1.8));

  Plotly.newPlot(
    "chart-temp",
    [
      {
        x: tempVals,
        y: caseVals,
        mode: "markers",
        type: "scatter",
        marker: {
          color: tempVals,
          colorscale: [
            [0, "#CCFBF1"],
            [0.5, TEAL],
            [1, "#0F766E"],
          ],
          size: sizes,
          opacity: 0.75,
          line: { color: "white", width: 0.5 },
        },
        hovertemplate:
          "<b>Temp:</b> %{x}°C<br><b>Cases:</b> %{y}<extra></extra>",
      },
    ],
    {
      ...baseLayout,
      xaxis: { ...baseLayout.xaxis, title: "Average Temperature (°C)" },
      yaxis: { ...baseLayout.yaxis, title: "Weekly Cases" },
    },
    plotConfig,
  );

  const humVals = [
    35, 40, 45, 50, 52, 55, 58, 60, 62, 64, 66, 68, 70, 72, 74, 76, 78, 80, 82,
    84, 86, 88, 90, 92, 94, 95, 40, 50, 60, 65, 70, 75, 80, 82, 85, 88, 90, 92,
    94, 95,
  ];
  Plotly.newPlot(
    "chart-humidity",
    [
      {
        x: humVals,
        y: caseVals,
        mode: "markers",
        type: "scatter",
        marker: {
          color: humVals,
          colorscale: [
            [0, "#E0F2FE"],
            [0.5, BLUE],
            [1, "#075985"],
          ],
          size: sizes,
          opacity: 0.75,
          line: { color: "white", width: 0.5 },
        },
        hovertemplate: "<b>RH:</b> %{x}%<br><b>Cases:</b> %{y}<extra></extra>",
      },
    ],
    {
      ...baseLayout,
      xaxis: { ...baseLayout.xaxis, title: "Relative Humidity (%)" },
      yaxis: { ...baseLayout.yaxis, title: "Weekly Cases" },
    },
    plotConfig,
  );

  const precipData = [];
  for (let i = 0; i < 300; i++) {
    const v = Math.random() < 0.6 ? Math.random() * 8 : Math.random() * 80 + 8;
    precipData.push(parseFloat(v.toFixed(1)));
  }
  Plotly.newPlot(
    "chart-precip",
    [
      {
        x: precipData,
        type: "histogram",
        nbinsx: 30,
        marker: {
          color: BLUE,
          opacity: 0.75,
          line: { color: "white", width: 0.5 },
        },
        name: "Frequency",
      },
    ],
    {
      ...baseLayout,
      xaxis: { ...baseLayout.xaxis, title: "Weekly Precipitation (mm)" },
      yaxis: { ...baseLayout.yaxis, title: "Frequency" },
      bargap: 0.05,
    },
    plotConfig,
  );

  const weeks = Array.from({ length: 52 }, (_, i) => i + 1);
  const avgCases = weeks.map((w) => {
    const peak = 38,
      sigma = 10;
    return Math.max(
      0,
      Math.round(
        280 * Math.exp(-0.5 * Math.pow((w - peak) / sigma, 2)) +
          Math.random() * 8,
      ),
    );
  });
  Plotly.newPlot(
    "chart-epiweek",
    [
      {
        x: weeks,
        y: avgCases,
        type: "bar",
        marker: {
          color: weeks.map((w) => (w >= 30 && w <= 46 ? TEAL : BLUE)),
          opacity: 0.8,
        },
        hovertemplate: "<b>Week %{x}</b><br>Avg cases: %{y}<extra></extra>",
      },
    ],
    {
      ...baseLayout,
      xaxis: { ...baseLayout.xaxis, title: "Epidemiological Week" },
      yaxis: { ...baseLayout.yaxis, title: "Avg Weekly Cases" },
      shapes: [
        {
          type: "rect",
          x0: 30,
          x1: 46,
          y0: 0,
          y1: 300,
          fillcolor: "rgba(13,148,136,.05)",
          line: { width: 0 },
        },
      ],
      annotations: [
        {
          x: 38,
          y: 290,
          text: "Peak Season<br>Wks 30–46",
          showarrow: false,
          font: { color: TEAL, size: 10 },
        },
      ],
    },
    plotConfig,
  );

  const features = [
    "t1_cases",
    "t2_cases",
    "PRECTOTCORR_lag1",
    "RH2M_mean",
    "PRECTOTCORR_sum",
    "water_proxy",
    "T2M_mean",
    "T2M_lag1",
    "momentum",
    "WS10M_mean",
  ];
  const corrs = [0.82, 0.71, 0.58, 0.52, 0.48, 0.45, 0.38, 0.35, 0.31, -0.12];
  const colors = corrs.map((c) => (c > 0 ? TEAL : ROSE));
  Plotly.newPlot(
    "chart-corr",
    [
      {
        x: corrs,
        y: features,
        type: "bar",
        orientation: "h",
        marker: {
          color: colors,
          opacity: 0.85,
          line: { color: "white", width: 0.5 },
        },
        text: corrs.map((c) => (c > 0 ? "+" : "") + c.toFixed(2)),
        textposition: "outside",
        hovertemplate: "<b>%{y}</b><br>r = %{x:.3f}<extra></extra>",
      },
    ],
    {
      ...baseLayout,
      margin: { t: 10, r: 60, b: 40, l: 160 },
      xaxis: {
        ...baseLayout.xaxis,
        title: "Pearson r with Cases",
        range: [-0.25, 1.0],
        zeroline: true,
        zerolinecolor: "#E2E8F0",
      },
      yaxis: { ...baseLayout.yaxis, autorange: "reversed" },
    },
    plotConfig,
  );
}

// ── Model Charts ─────────────────────────────────────────
function renderModelCharts() {
  if (document.getElementById("chart-learning").children.length > 0) return;

  const nSamples = [50, 100, 160, 220, 280, 340, 400, 460, 520, 580];
  const lrTrain = [0.62, 0.63, 0.63, 0.62, 0.62, 0.62, 0.61, 0.61, 0.61, 0.61];
  const lrVal = [0.38, 0.44, 0.48, 0.51, 0.53, 0.55, 0.57, 0.58, 0.59, 0.6];
  const rfTrain = [0.98, 0.97, 0.96, 0.95, 0.94, 0.93, 0.92, 0.91, 0.91, 0.9];
  const rfVal = [0.55, 0.62, 0.66, 0.69, 0.71, 0.73, 0.74, 0.75, 0.76, 0.77];
  const xgTrain = [0.95, 0.93, 0.91, 0.89, 0.88, 0.87, 0.86, 0.86, 0.85, 0.85];
  const xgVal = [0.52, 0.59, 0.63, 0.67, 0.69, 0.71, 0.72, 0.73, 0.74, 0.75];

  Plotly.newPlot(
    "chart-learning",
    [
      {
        x: nSamples,
        y: lrTrain,
        mode: "lines",
        name: "LR Train",
        line: { color: SLATE, dash: "dot", width: 2 },
      },
      {
        x: nSamples,
        y: lrVal,
        mode: "lines",
        name: "LR Val",
        line: { color: SLATE, width: 2 },
      },
      {
        x: nSamples,
        y: rfTrain,
        mode: "lines",
        name: "RF Train",
        line: { color: TEAL, dash: "dot", width: 2 },
      },
      {
        x: nSamples,
        y: rfVal,
        mode: "lines",
        name: "RF Val",
        line: { color: TEAL, width: 2 },
      },
      {
        x: nSamples,
        y: xgTrain,
        mode: "lines",
        name: "XGB Train",
        line: { color: BLUE, dash: "dot", width: 2 },
      },
      {
        x: nSamples,
        y: xgVal,
        mode: "lines",
        name: "XGB Val",
        line: { color: BLUE, width: 2 },
      },
    ],
    {
      ...baseLayout,
      xaxis: { ...baseLayout.xaxis, title: "Training Samples" },
      yaxis: { ...baseLayout.yaxis, title: "R² Score", range: [0.3, 1.0] },
    },
    plotConfig,
  );

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
    "month_sin",
  ];
  const imps = [0.28, 0.19, 0.12, 0.1, 0.08, 0.07, 0.06, 0.04, 0.03, 0.03];
  Plotly.newPlot(
    "chart-importance",
    [
      {
        x: imps,
        y: feats,
        type: "bar",
        orientation: "h",
        marker: {
          color: imps.map((_, i) => (i < 3 ? TEAL : BLUE)),
          opacity: 0.85,
          line: { color: "white", width: 0.5 },
        },
        text: imps.map((v) => (v * 100).toFixed(1) + "%"),
        textposition: "outside",
        hovertemplate: "<b>%{y}</b><br>Importance: %{x:.3f}<extra></extra>",
      },
    ],
    {
      ...baseLayout,
      margin: { t: 10, r: 55, b: 40, l: 150 },
      xaxis: { ...baseLayout.xaxis, title: "Importance", range: [0, 0.35] },
      yaxis: { ...baseLayout.yaxis, autorange: "reversed" },
    },
    plotConfig,
  );

  const rounds = Array.from({ length: 200 }, (_, i) => i + 1);
  const trainRmse = rounds.map(
    (r) => 30 * Math.exp(-r / 60) + 8 + Math.random() * 0.5,
  );
  const valRmse = rounds.map(
    (r) => 30 * Math.exp(-r / 80) + 14 + Math.random() * 0.8,
  );
  const bestIter = 142;
  Plotly.newPlot(
    "chart-xgb",
    [
      {
        x: rounds,
        y: trainRmse,
        mode: "lines",
        name: "Train RMSE",
        line: { color: TEAL, width: 2 },
        hovertemplate: "Round %{x}<br>Train RMSE: %{y:.2f}<extra></extra>",
      },
      {
        x: rounds,
        y: valRmse,
        mode: "lines",
        name: "Val RMSE",
        line: { color: ROSE, width: 2 },
        hovertemplate: "Round %{x}<br>Val RMSE: %{y:.2f}<extra></extra>",
      },
    ],
    {
      ...baseLayout,
      xaxis: { ...baseLayout.xaxis, title: "Boosting Round" },
      yaxis: { ...baseLayout.yaxis, title: "RMSE" },
      shapes: [
        {
          type: "line",
          x0: bestIter,
          x1: bestIter,
          y0: 0,
          y1: 45,
          line: { color: "#10B981", dash: "dash", width: 1.5 },
        },
      ],
      annotations: [
        {
          x: bestIter,
          y: 42,
          text: `Best: round ${bestIter}`,
          showarrow: false,
          font: { color: "#10B981", size: 11 },
        },
      ],
    },
    plotConfig,
  );
}
