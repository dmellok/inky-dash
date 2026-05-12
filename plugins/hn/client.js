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
    <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/hn/client.css">
    <div class="widget hn">
      <div class="head">
        <i class="ph ph-flame head-icon"></i>
        <span class="head-title">HACKER NEWS</span>
        <span class="head-place">${escapeHtml(feedLabel)}</span>
        <span class="head-time">${escapeHtml(now)}</span>
      </div>
      ${error
        ? `<div class="state-error"><i class="ph ph-warning-circle"></i><span class="msg">${escapeHtml(error)}</span></div>`
        : stories.length === 0
          ? `<div class="state-empty"><i class="ph ph-flame"></i><span class="msg">No stories.</span></div>`
          : `<div class="cards">
              ${stories.slice(0, visible).map((s, i) => {
                const host = s.url ? hostname(s.url) : "news.ycombinator.com";
                const metaParts = [
                  `${s.score} pts`,
                  `${s.comments} comments`,
                  s.by ? `by ${escapeHtml(s.by)}` : null,
                  escapeHtml(host),
                ].filter(Boolean);
                return `
                  <article class="card">
                    <span class="rank">${i + 1}</span>
                    <div class="card-body">
                      <div class="card-title">${escapeHtml(s.title)}</div>
                      <div class="card-meta">${metaParts.join(" · ")}</div>
                    </div>
                    <span class="score-pill">
                      <i class="ph ph-arrow-fat-up"></i> ${s.score}
                    </span>
                  </article>
                `;
              }).join("")}
            </div>`}
    </div>
  `;

  host.host.dataset.rendered = "true";
}
