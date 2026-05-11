// Hacker News stories — header strip + numbered story rows.

const FEED_LABELS = {
  topstories: "TOP",
  newstories: "NEW",
  beststories: "BEST",
  askstories: "ASK HN",
  showstories: "SHOW HN",
};

function hostname(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function formatTime(now) {
  return now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false });
}

export default function render(host, ctx) {
  const { size, options } = ctx.cell;
  const { data } = ctx;
  const feedLabel = FEED_LABELS[options.feed] || "TOP";
  const stories = data && data.stories ? data.stories : [];
  const error = data && data.error;
  const visible = size === "sm" ? 4 : size === "md" ? 8 : 14;
  const now = formatTime(new Date());

  host.innerHTML = `
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <link rel="stylesheet" href="/plugins/hn/client.css">
    <div class="hn">
      <div class="head">
        <i class="ph ph-flame head-icon"></i>
        <span class="head-title">HACKER NEWS</span>
        <span class="head-place">${escapeHtml(feedLabel)}</span>
        <span class="head-time">${escapeHtml(now)}</span>
      </div>
      ${error
        ? `<div class="hn-error"><i class="ph ph-warning-circle"></i> ${escapeHtml(error)}</div>`
        : stories.length === 0
          ? `<div class="hn-empty">No stories.</div>`
          : `<ol class="list">
              ${stories.slice(0, visible).map((s, i) => `
                <li class="row">
                  <span class="rank">${i + 1}</span>
                  <div class="entry">
                    <div class="entry-title">${escapeHtml(s.title)}</div>
                    <div class="entry-meta">
                      <span class="meta-score"><i class="ph ph-arrow-fat-up"></i> ${s.score}</span>
                      <span class="meta-host"><i class="ph ph-link"></i> ${escapeHtml(s.url ? hostname(s.url) : "news.ycombinator.com")}</span>
                      <span class="meta-comments"><i class="ph ph-chat-circle"></i> ${s.comments}</span>
                    </div>
                  </div>
                </li>
              `).join("")}
            </ol>`}
    </div>
  `;

  host.host.dataset.rendered = "true";
}
