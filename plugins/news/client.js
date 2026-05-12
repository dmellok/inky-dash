// Generic RSS/Atom feed reader — header strip + entry rows.

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function fmtAge(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const mins = Math.round((Date.now() - d.getTime()) / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours}h`;
  return `${Math.round(hours / 24)}d`;
}

function formatTime(now) {
  return now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false });
}

export default function render(host, ctx) {
  const { size } = ctx.cell;
  const { data } = ctx;
  const items = data && data.items ? data.items : [];
  const error = data && data.error;
  const title = (data && data.title) || "News";
  const visible = size === "sm" ? 3 : size === "md" ? 6 : 10;
  const now = formatTime(new Date());

  host.innerHTML = `
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/news/client.css">
    <div class="widget news">
      <div class="head">
        <i class="ph ph-newspaper head-icon"></i>
        <span class="head-title">NEWS</span>
        <span class="head-place">${escapeHtml(title)}</span>
        <span class="head-time">${escapeHtml(now)}</span>
      </div>
      ${error
        ? `<div class="state-error"><i class="ph ph-warning-circle"></i><span class="msg">${escapeHtml(error)}</span></div>`
        : items.length === 0
          ? `<div class="state-empty"><i class="ph ph-newspaper"></i><span class="msg">No items.</span></div>`
          : `<div class="cards">
              ${items.slice(0, visible).map((item, i) => {
                const age = fmtAge(item.published);
                const metaParts = [
                  item.author ? `by ${escapeHtml(item.author)}` : null,
                  item.source ? escapeHtml(item.source) : null,
                ].filter(Boolean);
                return `
                  <article class="card">
                    <span class="rank">${i + 1}</span>
                    <div class="card-body">
                      <div class="card-title">${escapeHtml(item.title)}</div>
                      ${metaParts.length
                        ? `<div class="card-meta">${metaParts.join(" · ")}</div>`
                        : ""}
                    </div>
                    ${age
                      ? `<span class="score-pill"><i class="ph ph-clock"></i> ${escapeHtml(age)}</span>`
                      : ""}
                  </article>
                `;
              }).join("")}
            </div>`}
    </div>
  `;

  host.host.dataset.rendered = "true";
}
