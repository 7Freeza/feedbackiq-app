/** Gráficas Chart.js — estilo Vacío numérico */

import {
  Chart,
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Filler,
  Tooltip,
  Legend,
} from 'chart.js';

Chart.register(
  BarController,
  BarElement,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  CategoryScale,
  Filler,
  Tooltip,
  Legend,
);

const INK = '#E8E6E1';
const MINT = '#7FD8BE';
const AMBER = '#D9A15B';
const MUTE = '#8A93A6';
const GRID = 'rgba(255,255,255,0.06)';

const baseOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: {
        color: MUTE,
        boxWidth: 10,
        font: { family: 'Inter', size: 11 },
      },
    },
    tooltip: {
      backgroundColor: '#0B0C10',
      titleColor: INK,
      bodyColor: MUTE,
      borderColor: GRID,
      borderWidth: 1,
      titleFont: { family: 'JetBrains Mono', size: 12 },
      bodyFont: { family: 'JetBrains Mono', size: 11 },
      padding: 10,
    },
  },
  scales: {
    x: {
      ticks: { color: MUTE, font: { family: 'Inter', size: 10 } },
      grid: { color: GRID, drawBorder: false },
      border: { display: false },
    },
    y: {
      ticks: { color: MUTE, font: { family: 'JetBrains Mono', size: 10 } },
      grid: { color: GRID, drawBorder: false },
      border: { display: false },
    },
  },
};

/** @type {Chart[]} */
const live = [];

export function destroyCharts() {
  while (live.length) {
    const c = live.pop();
    try {
      c.destroy();
    } catch {
      /* ignore */
    }
  }
}

export function renderModelCostChart(canvas, models) {
  if (!canvas || !models?.length) return;
  const labels = models.map((m) => m.model);
  const orig = models.map((m) => m.cost_original_usd);
  const opt = models.map((m) => m.cost_optimized_usd);

  const chart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels,
      datasets: [
        {
          label: 'Sin optimización',
          data: orig,
          backgroundColor: 'rgba(217, 161, 91, 0.55)',
          borderWidth: 0,
          barPercentage: 0.7,
        },
        {
          label: 'Con optimización',
          data: opt,
          backgroundColor: 'rgba(127, 216, 190, 0.7)',
          borderWidth: 0,
          barPercentage: 0.7,
        },
      ],
    },
    options: {
      ...baseOptions,
      plugins: {
        ...baseOptions.plugins,
        legend: { ...baseOptions.plugins.legend, position: 'bottom' },
      },
    },
  });
  live.push(chart);
}

export function renderProjectionChart(canvas, series) {
  if (!canvas || !series?.length) return;
  const chart = new Chart(canvas, {
    type: 'line',
    data: {
      labels: series.map((s) => String(s.day)),
      datasets: [
        {
          label: 'Ahorro acumulado (USD)',
          data: series.map((s) => s.cumulative_savings_usd),
          borderColor: MINT,
          backgroundColor: 'rgba(127, 216, 190, 0.08)',
          fill: true,
          tension: 0.25,
          pointRadius: 0,
          pointHoverRadius: 3,
          borderWidth: 1.5,
        },
      ],
    },
    options: {
      ...baseOptions,
      plugins: {
        ...baseOptions.plugins,
        legend: { display: false },
      },
      scales: {
        ...baseOptions.scales,
        x: {
          ...baseOptions.scales.x,
          title: { display: true, text: 'Día', color: MUTE, font: { size: 10 } },
        },
      },
    },
  });
  live.push(chart);
}

export function renderStageChart(canvas, stages) {
  if (!canvas || !stages?.length) return;
  const filtered = stages.filter((s) => s.stage !== 'Total núcleo');
  const chart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: filtered.map((s) => s.stage),
      datasets: [
        {
          label: 'ms',
          data: filtered.map((s) => s.ms),
          backgroundColor: 'rgba(138, 147, 166, 0.45)',
          borderWidth: 0,
        },
      ],
    },
    options: {
      ...baseOptions,
      indexAxis: 'y',
      plugins: {
        ...baseOptions.plugins,
        legend: { display: false },
      },
    },
  });
  live.push(chart);
}

export function renderTypeChart(canvas, distribution) {
  if (!canvas || !distribution) return;
  const entries = Object.entries(distribution).sort((a, b) => b[1] - a[1]).slice(0, 10);
  if (!entries.length) return;
  const chart = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: entries.map(([k]) => k),
      datasets: [
        {
          data: entries.map(([, v]) => v),
          backgroundColor: 'rgba(127, 216, 190, 0.5)',
          borderWidth: 0,
        },
      ],
    },
    options: {
      ...baseOptions,
      plugins: {
        ...baseOptions.plugins,
        legend: { display: false },
      },
    },
  });
  live.push(chart);
}

// silence unused
void AMBER;
