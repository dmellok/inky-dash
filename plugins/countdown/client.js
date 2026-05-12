// Countdown — header strip, big day count, unit, target label.
// Days-only — flips at local midnight.

function diffDays(target) {
  const now = new Date();
  const t = new Date(target);
  const a = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const b = new Date(t.getFullYear(), t.getMonth(), t.getDate());
  return Math.round((b - a) / 86_400_000);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function formatTarget(iso) {
  try {
    return new Date(iso).toLocaleDateString("en-GB", {
      weekday: "short",
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

export default function render(host, ctx) {
  const { options } = ctx.cell;
  const target = options.target_date || "2026-12-31";
  const userLabel = options.label || "Countdown";

  function paint() {
    const days = diffDays(target);
    const absolute = Math.abs(days);
    const unit = absolute === 1 ? "day" : "days";
    let prefix;
    let stateClass;
    if (days > 0) {
      prefix = "UNTIL";
      stateClass = "future";
    } else if (days < 0) {
      prefix = "SINCE";
      stateClass = "past";
    } else {
      prefix = "TODAY";
      stateClass = "now";
    }
    host.innerHTML = `
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/countdown/client.css">
      <div class="cd cd--${stateClass}">
        <div class="head">
          <i class="ph ph-calendar-blank head-icon"></i>
          <span class="head-title">${prefix}</span>
          <span class="head-place">${escapeHtml(userLabel.toUpperCase())}</span>
        </div>
        <div class="hero">
          <div class="hero-num">${absolute}</div>
          <div class="hero-unit">${unit}</div>
        </div>
        <div class="footer">
          <i class="ph ph-clock"></i>
          ${escapeHtml(formatTarget(target))}
        </div>
      </div>
    `;
  }

  paint();
  host.host.dataset.rendered = "true";

  // Tick once an hour — days flip only at midnight, no need to be precise.
  const interval = setInterval(paint, 3600 * 1000);
  host.__inkyCleanup = () => clearInterval(interval);
}

export function cleanup(host) {
  if (host.__inkyCleanup) host.__inkyCleanup();
}
