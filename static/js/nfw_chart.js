// static/js/nfw_chart.js
// Renders the NFW dark matter density profile using Chart.js.

let chart = null;

const R_SUN_KPC = 8.0;

function nfwDensity(r_kpc, rho0, rs_kpc) {
  if (rho0 === 0) return 0;
  const x = r_kpc / rs_kpc;
  return rho0 / (x * Math.pow(1 + x, 2));
}

export function initNFWChart(canvasEl) {
  chart = new Chart(canvasEl, {
    type: "line",
    data: { datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          type: "logarithmic",
          title: { display: true, text: "r (kpc)", color: "#aaa" },
          ticks: { color: "#aaa" },
          grid: { color: "#333" },
        },
        y: {
          type: "logarithmic",
          title: { display: true, text: "ρ (GeV/cm³)", color: "#aaa" },
          ticks: { color: "#aaa" },
          grid: { color: "#333" },
        },
      },
      plugins: {
        legend: { labels: { color: "#ddd" } },
        annotation: {
          annotations: {
            sunLine: {
              type: "line",
              xMin: R_SUN_KPC, xMax: R_SUN_KPC,
              borderColor: "rgba(255, 221, 68, 0.6)",
              borderWidth: 1,
              borderDash: [5, 5],
              label: {
                content: "太陽系",
                display: true,
                color: "#ffdd44",
                position: "start",
              },
            },
          },
        },
      },
      backgroundColor: "#111",
    },
  });
}

export function updateNFWChart(datasets) {
  // datasets: array of { name, rho0, rs, color }
  if (!chart) return;

  const rValues = [];
  for (let i = -1; i <= 2.5; i += 0.05) {
    rValues.push(Math.pow(10, i));  // 0.1 to ~316 kpc
  }

  chart.data.datasets = datasets.map((ds) => ({
    label: ds.name,
    data: rValues.map((r) => ({
      x: r,
      y: nfwDensity(r, ds.rho0, ds.rs),
    })).filter((p) => p.y > 0),
    borderColor: ds.color,
    borderWidth: 2,
    pointRadius: 0,
    fill: false,
  }));

  chart.update();
}
