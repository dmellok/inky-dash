// Chart.js shared loader — any widget that wants charts can do:
//
//   import { loadChart } from "/static/vendor/chartjs/loader.js";
//   const Chart = await loadChart();
//
// One UMD bundle is fetched per page (cached on `window.Chart`); subsequent
// callers (different cells, different widgets) reuse the already-loaded
// global. Plugins inside a shadow root still need to inject the <canvas>
// they're charting on; only the library itself is shared.

const SRC = "/static/vendor/chartjs/chart.umd.min.js";
let cached = null;
let pending = null;

export async function loadChart() {
  if (cached) return cached;
  if (window.Chart) {
    cached = window.Chart;
    return cached;
  }
  // Coalesce concurrent calls — multiple widgets booting in parallel
  // must not each kick off a separate <script> insertion.
  if (!pending) {
    pending = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = SRC;
      s.onload = () => resolve(window.Chart);
      s.onerror = () => reject(new Error("failed to load chart.js"));
      document.head.appendChild(s);
    });
  }
  cached = await pending;
  return cached;
}
