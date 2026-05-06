// Clock widget — digital, analog, or both. Renders the server snapshot at
// push time; in preview/editor contexts (not for_push) it ticks live so the
// face moves while the user edits.

export default function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  const style = opts.style || "digital";
  const format = opts.format || "24h";
  const showSeconds = !!opts.show_seconds;
  const showDate = opts.show_date !== false;
  const showHeader = opts.show_header !== false && !ctx.has_page_header;

  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";

  // Frame the dual-style layout: when "both" is chosen we want the analog
  // face to sit alongside the digital readout if there's room; on small
  // cells we fall back to digital-only to keep it legible.
  let effectiveStyle = style;
  if (style === "analog" && (W < 220 || H < 220)) effectiveStyle = "digital";
  if (style === "both" && (W < 420 || H < 240)) effectiveStyle = "digital";

  function renderOnce(now) {
    const timeStr = formatTime(now, format, showSeconds);
    const ampm = format === "12h" ? (now.getHours() < 12 ? "AM" : "PM") : "";
    const dateStr = d.date_long || now.toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" });
    const weekday = d.weekday || now.toLocaleDateString(undefined, { weekday: "long" });

    host.innerHTML = `
      <article class="clk ${sizeClass} style-${effectiveStyle}">
        ${showHeader ? `
        <header class="widget-head">
          <i class="ph ph-clock"></i>
          <span class="label">CLOCK</span>
          <span class="meta">${escapeHtml(weekday)}</span>
        </header>` : ""}
        <div class="body">
          ${effectiveStyle !== "analog" ? `
          <div class="digital">
            <div class="time"><span class="t">${escapeHtml(timeStr)}</span>${ampm ? `<span class="ampm">${ampm}</span>` : ""}</div>
            ${showDate ? `<div class="date">${escapeHtml(dateStr)}</div>` : ""}
          </div>` : ""}
          ${effectiveStyle !== "digital" ? renderAnalog(now, showSeconds) : ""}
        </div>
      </article>
    `;
  }

  // Initial render from the server's snapshot — guarantees push captures
  // the correct "frozen" face.
  const initial = d.iso ? new Date(d.iso) : new Date();
  renderOnce(initial);

  // For non-push contexts (editor preview), tick on the largest cadence
  // visible in the UI so the clock doesn't look frozen.
  if (ctx.for_push) return null;
  const tickMs = showSeconds ? 1000 : 60_000;
  const interval = setInterval(() => renderOnce(new Date()), tickMs);
  // Cleanup function — composer will call it on cell teardown.
  return () => clearInterval(interval);
}

function formatTime(d, format, showSeconds) {
  let h = d.getHours();
  const m = d.getMinutes();
  const s = d.getSeconds();
  if (format === "12h") {
    h = h % 12;
    if (h === 0) h = 12;
  }
  const pad = (n) => String(n).padStart(2, "0");
  const main = `${format === "12h" ? h : pad(h)}:${pad(m)}`;
  return showSeconds ? `${main}:${pad(s)}` : main;
}

function renderAnalog(now, showSeconds) {
  const h = now.getHours() % 12;
  const m = now.getMinutes();
  const s = now.getSeconds();
  const hourAngle = (h + m / 60) * 30;            // 360/12
  const minuteAngle = (m + s / 60) * 6;            // 360/60
  const secondAngle = s * 6;
  const ticks = Array.from({ length: 12 }, (_, i) => {
    const angle = i * 30;
    return `<line class="tick" x1="50" y1="6" x2="50" y2="${i % 3 === 0 ? 12 : 9}" transform="rotate(${angle} 50 50)" />`;
  }).join("");
  return `
    <svg class="analog" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-label="Analog clock face">
      <circle class="face" cx="50" cy="50" r="46" />
      <g class="ticks">${ticks}</g>
      <line class="hand hour"   x1="50" y1="50" x2="50" y2="22" transform="rotate(${hourAngle} 50 50)" />
      <line class="hand minute" x1="50" y1="50" x2="50" y2="12" transform="rotate(${minuteAngle} 50 50)" />
      ${showSeconds ? `<line class="hand second" x1="50" y1="55" x2="50" y2="10" transform="rotate(${secondAngle} 50 50)" />` : ""}
      <circle class="pin" cx="50" cy="50" r="3" />
    </svg>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
