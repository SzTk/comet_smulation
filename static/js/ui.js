// static/js/ui.js
// Wires the parameter panel, presets, and run button to the scene and chart.

import { initScene, drawOrbits } from "./scene.js";
import { initNFWChart, updateNFWChart } from "./nfw_chart.js";
import { startSimulation, fetchPresets } from "./api.js";

const CHART_COLORS = ["#ff8800", "#00aaff", "#44ff88", "#ff4466"];

export async function initUI() {
  const canvas3d = document.getElementById("canvas3d");
  const canvasChart = document.getElementById("canvasChart");

  initScene(canvas3d);
  initNFWChart(canvasChart);

  const presets = await fetchPresets();
  _populatePresets(presets);
  _syncChartWithCurrentParams(presets);

  document.getElementById("presetSelect").addEventListener("change", (e) => {
    const preset = presets.find((p) => p.name === e.target.value);
    if (preset) {
      document.getElementById("rho0Input").value = preset.rho0;
      document.getElementById("rsInput").value = preset.rs;
      _syncChartWithCurrentParams(presets);
    }
  });

  ["rho0Input", "rsInput"].forEach((id) => {
    document.getElementById(id).addEventListener("input", () =>
      _syncChartWithCurrentParams(presets)
    );
  });

  document.getElementById("runBtn").addEventListener("click", () => _runSimulation(presets));
}

function _populatePresets(presets) {
  const sel = document.getElementById("presetSelect");
  presets.forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.name;
    opt.textContent = p.name;
    sel.appendChild(opt);
  });
  // Select second preset (標準銀河系ハロー) by default
  if (presets[1]) {
    sel.value = presets[1].name;
    document.getElementById("rho0Input").value = presets[1].rho0;
    document.getElementById("rsInput").value = presets[1].rs;
  }
}

function _syncChartWithCurrentParams(presets) {
  const rho0 = parseFloat(document.getElementById("rho0Input").value) || 0;
  const rs = parseFloat(document.getElementById("rsInput").value) || 20;
  // Show current + all presets on the chart
  const datasets = [
    { name: "現在の設定", rho0, rs, color: CHART_COLORS[0] },
    ...presets.map((p, i) => ({
      name: p.name, rho0: p.rho0, rs: p.rs, color: CHART_COLORS[i + 1] || "#888",
    })),
  ];
  updateNFWChart(datasets);
}

async function _runSimulation(presets) {
  const rho0 = parseFloat(document.getElementById("rho0Input").value) || 0;
  const rs = parseFloat(document.getElementById("rsInput").value) || 20;
  const a = parseFloat(document.getElementById("aInput").value) || 50000;
  const ecc = parseFloat(document.getElementById("eccInput").value) || 0.9999;
  const inc = parseFloat(document.getElementById("incInput").value) || 0;

  const payload = {
    dark_matter: { rho0, rs },
    comet: { semi_major_axis_au: a, eccentricity: ecc, inclination_deg: inc },
    duration_years: null,
    timestep_years: Math.max(10, a * 0.002),  // scale timestep with orbit size
    n_output_points: 5000,
  };

  const runBtn = document.getElementById("runBtn");
  const progressBar = document.getElementById("progressBar");
  const statusText = document.getElementById("statusText");

  runBtn.disabled = true;
  progressBar.style.width = "0%";
  statusText.textContent = "計算中...";

  await startSimulation(
    payload,
    (pct) => {
      progressBar.style.width = `${pct}%`;
    },
    (result) => {
      drawOrbits(result.trajectory_with_dm, result.trajectory_without_dm);
      const meta = result.metadata;
      statusText.textContent =
        `完了 | 軌道周期: ${(meta.period_years / 1e6).toFixed(2)}M年 ` +
        `| 近日点: ${meta.perihelion_au} AU`;
      runBtn.disabled = false;
    },
    (err) => {
      statusText.textContent = `エラー: ${err}`;
      runBtn.disabled = false;
    }
  );
}
