// Clock — digital time, optional date and seconds. Layout adapts per breakpoint.

function formatTime(now, format, showSeconds) {
  const opts = {
    hour: "2-digit",
    minute: "2-digit",
    hour12: format === "12h",
  };
  if (showSeconds) opts.second = "2-digit";
  return new Intl.DateTimeFormat("en-US", opts).format(now);
}

function formatDate(now, size) {
  const opts =
    size === "lg"
      ? { weekday: "long", month: "long", day: "numeric" }
      : { weekday: "short", month: "short", day: "numeric" };
  return new Intl.DateTimeFormat("en-US", opts).format(now);
}

export default function render(host, ctx) {
  const { size, options } = ctx.cell;
  const format = options.format || "24h";
  const showSeconds = options.show_seconds === true;
  const showDate = options.show_date !== false && size !== "xs";

  host.innerHTML = `
    <link rel="stylesheet" href="/plugins/clock/client.css">
    <div class="clock clock--${size}">
      <div class="time" aria-label="time"></div>
      ${showDate ? `<div class="date" aria-label="date"></div>` : ""}
    </div>
  `;

  const timeEl = host.querySelector(".time");
  const dateEl = host.querySelector(".date");

  function tick() {
    const now = new Date();
    timeEl.textContent = formatTime(now, format, showSeconds);
    if (dateEl) dateEl.textContent = formatDate(now, size);
  }

  tick();
  const intervalMs = showSeconds ? 1000 : 30_000;
  const handle = setInterval(tick, intervalMs);
  host.__inkyCleanup = () => clearInterval(handle);

  host.host.dataset.rendered = "true";
}

export function cleanup(host) {
  if (host.__inkyCleanup) host.__inkyCleanup();
}
