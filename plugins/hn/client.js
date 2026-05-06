// Hacker News widget — list of top/new/best/ask/show stories.

const FEED_LABEL = {
  top: "TOP",
  new: "NEW",
  best: "BEST",
  ask: "ASK HN",
  show: "SHOW HN",
};

export default function render(host, ctx) {
  const d = ctx.data || {};
  const opts = ctx.options || {};
  const W = ctx.width || 800;
  const H = ctx.height || 480;

  if (d.error) {
    host.innerHTML = `<article class="hn error"><div class="msg">${escapeHtml(d.error)}</div></article>`;
    return;
  }

  const showHeader = opts.show_header !== false && !ctx.has_page_header;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 360 ? "h-sm" :
    H < 600 ? "h-md" :
    H < 900 ? "h-lg" : "h-xl";
  const stories = Array.isArray(d.stories) ? d.stories : [];
  const feedLabel = FEED_LABEL[d.feed] || "HN";

  host.innerHTML = `
    <article class="hn ${sizeClass}">
      ${showHeader ? `
      <header class="widget-head">
        <i class="ph ph-flame"></i>
        <span class="label">HACKER NEWS</span>
        <span class="meta">${escapeHtml(feedLabel)}</span>
      </header>` : ""}

      ${stories.length === 0
        ? `<div class="empty">No stories</div>`
        : `<ol class="story-list">
            ${stories.map((s, i) => storyRow(s, i + 1)).join("")}
          </ol>`}
    </article>
  `;
}

function storyRow(s, rank) {
  const meta = [
    `${s.score} pts`,
    `${s.comments} comments`,
    s.author ? `by ${s.author}` : null,
    s.domain && !s.self ? s.domain : null,
  ].filter(Boolean).join(" · ");
  return `
    <li class="story">
      <span class="rank">${rank}</span>
      <div class="body">
        <div class="title">${escapeHtml(s.title || "")}</div>
        <div class="meta">${escapeHtml(meta)}</div>
      </div>
      <span class="score-chip">
        <i class="ph ph-arrow-fat-up" aria-hidden="true"></i>
        <span>${s.score}</span>
      </span>
    </li>
  `;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
