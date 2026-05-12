// Reddit widget — matches the HN / news card pattern: big accent rank
// on the left, title + meta in the middle, score pill on the right.
// Header strip shows the subreddit + the active sort.

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function fmtAge(seconds) {
  if (seconds == null || seconds < 0) return "";
  if (seconds < 60) return "just now";
  const mins = Math.round(seconds / 60);
  if (mins < 60) return `${mins}m`;
  const hours = Math.round(mins / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.round(hours / 24);
  return `${days}d`;
}

function fmtScore(n) {
  if (n >= 1000) {
    const k = (n / 1000).toFixed(1).replace(/\.0$/, "");
    return `${k}k`;
  }
  return String(n);
}

const SORT_LABELS = { hot: "HOT", new: "NEW", top: "TOP", rising: "RISING" };
const VISIBLE_BY_SIZE = { sm: 3, md: 5, lg: 8 };

export default function render(host, ctx) {
  const { size } = ctx.cell;
  const data = ctx.data || {};
  const opts = ctx.cell?.options || {};

  if (data.error) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="widget">
        <div class="state-error">
          <i class="ph ph-reddit-logo"></i>
          <div class="msg">${escapeHtml(data.error)}</div>
        </div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const subreddit = (data.subreddit || opts.subreddit || "popular").toLowerCase();
  const sortLabel = SORT_LABELS[data.sort] || SORT_LABELS[opts.sort] || "HOT";
  const visible = VISIBLE_BY_SIZE[size] ?? 5;
  const posts = (data.posts || []).slice(0, visible);

  const cards = posts
    .map((p, i) => {
      const metaParts = [
        `${p.comments} comments`,
        p.author ? `u/${escapeHtml(p.author)}` : null,
        p.is_self ? `r/${escapeHtml(p.subreddit)}` : escapeHtml(p.domain),
        fmtAge(p.age_seconds),
      ].filter(Boolean);
      return `
        <article class="card">
          <span class="rank">${i + 1}</span>
          <div class="card-body">
            <div class="card-title">${escapeHtml(p.title)}</div>
            <div class="card-meta">${metaParts.join(" · ")}</div>
          </div>
          <span class="score-pill">
            <i class="ph ph-arrow-fat-up"></i> ${fmtScore(p.score)}
          </span>
        </article>
      `;
    })
    .join("");

  const empty = posts.length === 0
    ? `<div class="state-empty"><i class="ph ph-reddit-logo"></i><span class="msg">No posts.</span></div>`
    : "";

  const note = data.note
    ? `<div class="reddit-note"><i class="ph ph-warning"></i> ${escapeHtml(data.note)}</div>`
    : "";

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/reddit/client.css">
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <div class="widget reddit reddit--${size}">
      <div class="head">
        <i class="ph ph-reddit-logo head-icon"></i>
        <span class="head-title">r/${escapeHtml(subreddit)}</span>
        <span class="head-place">${escapeHtml(sortLabel)}</span>
      </div>
      ${note}
      ${posts.length ? `<div class="cards">${cards}</div>` : empty}
    </div>
  `;
  host.host.dataset.rendered = "true";
}
