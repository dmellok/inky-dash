// Countdown widget — display the days/hours/minutes until a target date.
// The server pre-computes the delta; the client just paints it.

export default function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="cd error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
    return;
  }

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const icon = (opts.icon || "ph-hourglass").trim();
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";

  const days = Math.abs(d.days || 0);
  const hours = Math.abs(d.hours || 0);
  const minutes = Math.abs(d.minutes || 0);
  const elapsed = !!d.elapsed;
  // Headline number is days when there are any; otherwise hours; otherwise
  // minutes — keeps the hero readable on a glance whatever the magnitude.
  let heroValue, heroUnit;
  if (days >= 1) { heroValue = days; heroUnit = days === 1 ? "day" : "days"; }
  else if (hours >= 1) { heroValue = hours; heroUnit = hours === 1 ? "hour" : "hours"; }
  else { heroValue = minutes; heroUnit = minutes === 1 ? "minute" : "minutes"; }

  // Secondary line gives the breakdown for granularity beyond the headline.
  const breakdown = days >= 1
    ? `${hours}h ${minutes}m`
    : (hours >= 1 ? `${minutes}m` : "");

  const verb = elapsed ? "since" : "until";
  const labelText = (d.label || "Until").trim();

  host.innerHTML = `
    <article class="cd ${sizeClass} ${elapsed ? "elapsed" : "future"}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ${escapeHtml(icon)}"></i>
        <span class="label">COUNTDOWN</span>
        <span class="meta">${escapeHtml(d.target_pretty || "")}</span>
      </header>` : ""}

      <div class="body">
        <div class="title">${escapeHtml(labelText)}</div>
        <div class="hero">
          <span class="num">${heroValue}</span>
          <span class="unit">${heroUnit}</span>
        </div>
        <div class="footer">
          <span class="verb">${verb}</span>
          <span class="when">${escapeHtml(d.target_pretty || "")}</span>
          ${breakdown ? `<span class="breakdown">+ ${breakdown}</span>` : ""}
        </div>
      </div>
    </article>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
