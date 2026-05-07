// Hacker News stories.

const FEED_LABELS = {
  topstories: "Top",
  newstories: "New",
  beststories: "Best",
  askstories: "Ask HN",
  showstories: "Show HN",
};

function hostname(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

export default function render(host, ctx) {
  const { size, options } = ctx.cell;
  const { data } = ctx;
  const feedLabel = FEED_LABELS[options.feed] || "Top";
  const stories = data && data.stories ? data.stories : [];
  const error = data && data.error;

  const visible = size === "sm" ? 4 : size === "md" ? 8 : 12;

  host.innerHTML = `
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <link rel="stylesheet" href="/plugins/hn/client.css">
    <div class="hn hn--${size}">
      <div class="header">
        <span class="title"><i class="ph ph-flame-fill"></i> HN · ${feedLabel}</span>
        <span class="count">${stories.length} stories</span>
      </div>
      ${error
        ? `<div class="error"><i class="ph ph-warning-circle"></i> ${error}</div>`
        : stories.length === 0
          ? `<div class="empty">No stories.</div>`
          : `<ol class="list">
              ${stories
                .slice(0, visible)
                .map(
                  (s, i) => `
                    <li>
                      <span class="rank">${i + 1}</span>
                      <div class="entry">
                        <div class="title">${escapeHtml(s.title)}</div>
                        <div class="meta">
                          <span class="score"><i class="ph ph-arrow-fat-up-fill"></i> ${s.score}</span>
                          <span class="host"><i class="ph ph-link"></i> ${s.url ? hostname(s.url) : "news.ycombinator.com"}</span>
                          <span class="comments"><i class="ph ph-chat-circle"></i> ${s.comments}</span>
                        </div>
                      </div>
                    </li>
                  `
                )
                .join("")}
            </ol>`}
    </div>
  `;

  host.host.dataset.rendered = "true";
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
