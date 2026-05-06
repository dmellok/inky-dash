export default async function render(host, ctx) {
  const d = ctx.data || {};
  if (d.error) {
    host.innerHTML = `<div class="cal-error">${escapeHtml(d.error)}</div>`;
    return;
  }
  const W = ctx.width || 600, H = ctx.height || 400;
  const sizeClass =
    H < 200 ? "h-xs" :
    H < 400 ? "h-sm" :
    H < 700 ? "h-md" :
    H < 1100 ? "h-lg" : "h-xl";

  const today = d.today || [];
  const upcoming = d.upcoming || [];
  const nothing = today.length === 0 && upcoming.length === 0;

  const showHead = sizeClass !== "h-xs";
  const totalEvents = (d.today || []).length + (d.upcoming || []).length;

  if (nothing) {
    const nx = d.next_after_window;
    host.innerHTML = `
      <div class="cal ${sizeClass}">
        ${showHead ? `
        <header class="widget-head">
          <i class="ph ph-calendar-blank"></i>
          <span class="label">Calendar</span>
        </header>` : ""}
        <div class="cal-empty">
          <p class="lead">Clear ahead</p>
          <p class="muted">Nothing scheduled${d.lookahead_days ? ` for the next ${d.lookahead_days} day${d.lookahead_days === 1 ? "" : "s"}` : ""}.</p>
          ${nx ? `
            <div class="cal-next-after">
              <span class="when">Next · ${formatDateTime(nx.start, nx.all_day)}</span>
              <span class="title">${escapeHtml(nx.summary)}</span>
              ${nx.location ? `<span class="muted">${escapeHtml(nx.location)}</span>` : ""}
            </div>
          ` : ""}
        </div>
      </div>`;
    return;
  }

  // Cap events by tier so smaller cells aren't overflowing — today wins.
  const cap = sizeClass === "h-xs" ? 1
            : sizeClass === "h-sm" ? 3
            : sizeClass === "h-md" ? 6
            : sizeClass === "h-lg" ? 10
            : 100;
  const todayCap = Math.min(today.length, cap);
  const upcomingCap = Math.max(0, cap - todayCap);

  host.innerHTML = `
    <div class="cal ${sizeClass}">
      ${showHead ? `
      <header class="widget-head">
        <i class="ph ph-calendar-blank"></i>
        <span class="label">Calendar</span>
        <span class="meta">${totalEvents} event${totalEvents === 1 ? "" : "s"}</span>
      </header>` : ""}
      ${today.length ? `
        <section class="group">
          <h3>Today</h3>
          <ul>${today.slice(0, todayCap).map(eventLi).join("")}</ul>
        </section>` : ""}
      ${upcoming.length && upcomingCap > 0 ? `
        <section class="group">
          <h3>Upcoming</h3>
          <ul>${upcoming.slice(0, upcomingCap).map(eventLi).join("")}</ul>
        </section>` : ""}
    </div>`;
}

function eventLi(ev) {
  return `
    <li class="ev">
      <span class="bar" aria-hidden="true"></span>
      <span class="title">${escapeHtml(ev.summary)}</span>
      <span class="when">${formatWhen(ev.start, ev.all_day)}</span>
      ${ev.location ? `<span class="loc"><i class="ph ph-map-pin"></i>${escapeHtml(ev.location)}</span>` : ""}
    </li>`;
}

function formatWhen(iso, allDay) {
  // Compact time-only label for the chip — "All day" or "14:30".
  if (!iso) return "";
  if (allDay) return "All day";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });
}

function formatDateTime(iso, allDay) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  if (allDay) {
    return d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
  }
  return d.toLocaleString(undefined, {
    weekday: "short", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit", hour12: false,
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
