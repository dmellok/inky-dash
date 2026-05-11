// World clock — list of timezone rows, each with the day-progress bar.
// Renders entirely client-side (Intl.DateTimeFormat) and re-ticks every
// minute. Zones are parsed from a textarea cell_option in Label|TZ form;
// "local" maps to whatever the browser thinks the local zone is.

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function parseZones(raw) {
  if (!raw) return [];
  return String(raw)
    .split(/[\n,]+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [label, tz] = line.split("|").map((s) => (s || "").trim());
      return { label: label || tz || "Local", tz: tz || "local" };
    });
}

function resolveTz(tz) {
  if (!tz || tz.toLowerCase() === "local") {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone;
    } catch {
      return "UTC";
    }
  }
  return tz;
}

// Returns { date, time, dateLabel, dayMinutes, utcOffset }
function snapshot(now, tz, format) {
  const resolved = resolveTz(tz);
  const opts = { timeZone: resolved, hour12: format === "12h", hour: "2-digit", minute: "2-digit" };
  const time = new Intl.DateTimeFormat("en-GB", opts).format(now);

  const dateOpts = { timeZone: resolved, weekday: "short", day: "numeric", month: "short" };
  const dateLabel = new Intl.DateTimeFormat("en-GB", dateOpts).format(now);

  // Extract numeric H/M for the timeline bar position.
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: resolved, hour: "2-digit", minute: "2-digit", hour12: false,
  }).formatToParts(now);
  const h = parseInt(parts.find((p) => p.type === "hour")?.value || "0", 10);
  const m = parseInt(parts.find((p) => p.type === "minute")?.value || "0", 10);
  const dayMinutes = (h * 60 + m) / (24 * 60);

  // UTC offset: format the timestamp with longOffset and pull "GMT±HH:MM".
  let utcOffset = "";
  try {
    const fmt = new Intl.DateTimeFormat("en-GB", {
      timeZone: resolved, timeZoneName: "longOffset",
    }).formatToParts(now);
    const part = fmt.find((p) => p.type === "timeZoneName")?.value || "";
    utcOffset = part.replace(/^GMT/, "UTC").replace(/^UTC$/, "UTC+00:00");
  } catch { /* unsupported */ }

  return { time, dateLabel, dayMinutes, utcOffset };
}

export default function render(host, ctx) {
  const opts = (ctx.cell && ctx.cell.options) || {};
  const zones = parseZones(opts.zones || "Local|local");
  const format = opts.format || "24h";

  function renderRows() {
    const now = new Date();
    const rows = zones.map((z) => {
      const s = snapshot(now, z.tz, format);
      const pct = (s.dayMinutes * 100).toFixed(2);
      return `
        <div class="row">
          <div class="row-head">
            <div class="zone-name">${escapeHtml(z.label)}</div>
            <div class="zone-time">${escapeHtml(s.time)}</div>
          </div>
          <div class="zone-meta">${escapeHtml(s.dateLabel)} · ${escapeHtml(s.utcOffset)}</div>
          <div class="track">
            <div class="track-axis">
              <span>00</span><span>06</span><span>12</span><span>18</span>
            </div>
            <div class="track-bar">
              <div class="day-window" style="left: 25%; right: 25%;"></div>
              <div class="now" style="left: ${pct}%;"></div>
            </div>
          </div>
        </div>
      `;
    }).join("");
    return rows;
  }

  function paint() {
    host.querySelector(".clocks").innerHTML = renderRows();
  }

  host.innerHTML = `
    <link rel="stylesheet" href="/plugins/world_clock/client.css">
    <div class="wc">
      <div class="clocks">${renderRows()}</div>
    </div>
  `;
  host.host.dataset.rendered = "true";

  // Re-tick at the top of every minute so the bars + times stay accurate.
  const tickAtMinute = () => {
    paint();
    const now = new Date();
    const msToNextMinute = 60_000 - (now.getSeconds() * 1000 + now.getMilliseconds());
    timer = setTimeout(tickAtMinute, msToNextMinute);
  };
  let timer = setTimeout(tickAtMinute, 60_000 - new Date().getSeconds() * 1000);
  host.__inkyCleanup = () => clearTimeout(timer);
}

export function cleanup(host) {
  if (host.__inkyCleanup) host.__inkyCleanup();
}
