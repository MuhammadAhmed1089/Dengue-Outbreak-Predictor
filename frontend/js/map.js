/* ═══════════════════════════════════════════
   Dengue Predictor — Interactive Risk Map
   Wired to /api/cluster; falls back to demo data if backend is down.
═══════════════════════════════════════════ */

const API_BASE = "http://localhost:8000"; // keep in sync with forecast.js

// Demo district data shown when backend is unavailable
const DEMO_DISTRICTS = [
  { name: "Lahore", pos: [31.5204, 74.3587], tier: "critical", cases: 312 },
  { name: "Rawalpindi", pos: [33.5651, 73.0169], tier: "high", cases: 198 },
  { name: "Faisalabad", pos: [31.418, 73.079], tier: "high", cases: 156 },
  { name: "Multan", pos: [30.1575, 71.5249], tier: "high", cases: 142 },
  { name: "Gujranwala", pos: [32.1877, 74.1945], tier: "moderate", cases: 89 },
  { name: "Sialkot", pos: [32.4945, 74.5229], tier: "moderate", cases: 76 },
  { name: "Bahawalpur", pos: [29.3544, 71.6911], tier: "moderate", cases: 64 },
  { name: "Sargodha", pos: [32.0836, 72.6711], tier: "low", cases: 41 },
  { name: "Sheikhupura", pos: [31.7131, 73.9783], tier: "moderate", cases: 58 },
  { name: "Jhang", pos: [31.2681, 72.3181], tier: "low", cases: 33 },
  { name: "Dera Ghazi Khan", pos: [30.0321, 70.6403], tier: "low", cases: 27 },
  { name: "Sahiwal", pos: [30.6774, 73.1065], tier: "low", cases: 35 },
];

const TIER_COLORS = {
  critical: "#dc2626",
  high: "#ea580c",
  moderate: "#f59e0b",
  low: "#10b981",
};

document.addEventListener("DOMContentLoaded", async () => {
  // Center on Punjab, Pakistan
  const map = L.map("map-container").setView([31.0, 72.5], 7);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 18,
  }).addTo(map);

  // Try to load live data from backend
  let districts = null;
  try {
    const res = await fetch(`${API_BASE}/api/cluster`);
    if (res.ok) {
      const data = await res.json();
      // API returns { districts: [{name, lat, lng, tier, color, avg_cases}], summary: {...} }
      districts = data.districts.map((d) => ({
        name: d.name,
        pos: [d.lat, d.lng],
        tier: d.tier,
        cases: d.avg_cases,
      }));
    }
  } catch (_) {}

  // Fall back to demo data
  if (!districts || districts.length === 0) {
    districts = DEMO_DISTRICTS;
  }

  // ── Populate Risk Tier Summary table from KMeans summary ─────────────────
  const tbody = document.getElementById("risk-tier-tbody");
  if (tbody) {
    // Build summary from live district data if no backend summary available
    const KEY_DRIVERS = {
      critical:
        "High temp + humidity, dense population, prior outbreak history",
      high: "Monsoon rainfall peaks, moderate urban density",
      moderate: "Seasonal spikes, lower population density",
      low: "Arid climate, sparse population, limited breeding sites",
    };

    // Group districts by tier from live data
    const grouped = { critical: [], high: [], moderate: [], low: [] };
    districts.forEach((d) => {
      if (grouped[d.tier]) grouped[d.tier].push(d);
    });

    const tierOrder = ["critical", "high", "moderate", "low"];
    tbody.innerHTML = tierOrder
      .map((tier) => {
        const color = TIER_COLORS[tier] || "#94a3b8";
        const label = tier.charAt(0).toUpperCase() + tier.slice(1);
        const distList = grouped[tier] || [];
        const names = distList.map((d) => d.name).join(", ") || "—";
        const avgCases = distList.length
          ? Math.round(
              distList.reduce((s, d) => s + (d.cases || 0), 0) /
                distList.length,
            )
          : 0;

        return `<tr>
        <td>
          <span class="model-badge">
            <span class="model-dot" style="background:${color}"></span>${label}
          </span>
        </td>
        <td>${names}</td>
        <td><span class="mono">${avgCases}</span></td>
        <td>${KEY_DRIVERS[tier] || "—"}</td>
      </tr>`;
      })
      .join("");
  }

  // Render markers
  districts.forEach((d) => {
    const color = TIER_COLORS[d.tier] || "#94a3b8";
    const radius = 8 + Math.sqrt(Math.max(d.cases || 0, 1));

    const marker = L.circleMarker(d.pos, {
      radius,
      fillColor: color,
      color: "#fff",
      weight: 2,
      opacity: 1,
      fillOpacity: 0.75,
    }).addTo(map);

    marker.bindPopup(`
      <div style="font-family:Outfit,sans-serif;min-width:160px;">
        <div style="font-weight:700;font-size:1rem;margin-bottom:4px;">${d.name}</div>
        <div style="font-size:0.8rem;color:#475569;margin-bottom:6px;">
          Risk: <span style="color:${color};font-weight:700;text-transform:uppercase;">${d.tier}</span>
        </div>
        <div style="font-size:0.85rem;font-weight:600;">${d.cases} predicted cases</div>
      </div>`);
  });

  // Scroll-reveal
  const revObs = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) e.target.classList.add("visible");
      });
    },
    { threshold: 0.08 },
  );
  document.querySelectorAll(".reveal").forEach((el) => revObs.observe(el));
});
