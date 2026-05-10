/* ═══════════════════════════════════════════════════════
   Dengue Predictor — EDA Pair Plots Page Logic
   Fetches all 6 plot images from the FastAPI backend.
═══════════════════════════════════════════════════════ */

const API_BASE = "http://localhost:8000";

const PLOTS = ["lag", "weather", "precip", "cyclic", "key", "heatmap"];

// ── Navbar scroll effect ──────────────────────────────
const navbar = document.getElementById("navbar");
if (navbar) {
  window.addEventListener("scroll", () => {
    navbar.classList.toggle("scrolled", window.scrollY > 50);
  });
}

// ── Quick-jump nav ────────────────────────────────────
document.querySelectorAll(".eda-jump-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = document.getElementById(btn.dataset.target);
    if (target) {
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    document.querySelectorAll(".eda-jump-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
  });
});

// Highlight jump button on scroll
const sectionIds = PLOTS.map((id) => "plot-" + id);
const observerOpts = { threshold: 0.25, rootMargin: "-80px 0px 0px 0px" };
const jumpObserver = new IntersectionObserver((entries) => {
  entries.forEach((e) => {
    if (e.isIntersecting) {
      const id = e.target.id.replace("plot-", "");
      document.querySelectorAll(".eda-jump-btn").forEach((b) => {
        b.classList.toggle("active", b.dataset.target === e.target.id);
      });
    }
  });
}, observerOpts);
sectionIds.forEach((id) => {
  const el = document.getElementById(id);
  if (el) jumpObserver.observe(el);
});

// ── Plot loader ───────────────────────────────────────
async function loadPlot(plotId) {
  const spinner = document.getElementById("spinner-" + plotId);
  const img     = document.getElementById("img-" + plotId);
  const errBox  = document.getElementById("error-" + plotId);

  if (!spinner || !img || !errBox) return;

  spinner.style.display = "flex";
  img.style.display     = "none";
  errBox.style.display  = "none";
  img.src               = "";

  try {
    const res = await fetch(`${API_BASE}/api/insights/plot/${plotId}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    img.src = `data:${data.mime};base64,${data.image_base64}`;
    img.onload = () => {
      spinner.style.display = "none";
      img.style.display     = "block";
    };
    img.onerror = () => {
      spinner.style.display = "none";
      errBox.style.display  = "flex";
    };
  } catch (err) {
    spinner.style.display = "none";
    errBox.style.display  = "flex";
    // Fill in the API hint if present
    const hint = document.getElementById("api-hint-" + plotId);
    if (hint) hint.textContent = API_BASE;
  }
}

// ── Lazy load: only start fetching a plot when its section
//    enters the viewport (avoids hammering the backend all at once) ──
const lazyObs = new IntersectionObserver(
  (entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) {
        const id = e.target.id.replace("plot-", "");
        loadPlot(id);
        lazyObs.unobserve(e.target); // only fetch once
      }
    });
  },
  { threshold: 0.05, rootMargin: "200px 0px 0px 0px" }
);

sectionIds.forEach((id) => {
  const el = document.getElementById(id);
  if (el) lazyObs.observe(el);
});
