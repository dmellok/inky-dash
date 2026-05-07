// Sun & moon — SVG-rendered: an arc showing the sun's position for the day,
// plus a moon disc with an actual lit/dark phase boundary.

// Synodic month constants (J2000 reference new moon).
const KNOWN_NEW_MOON = Date.UTC(2000, 0, 6, 18, 14) / 1000;
const SYNODIC_DAYS = 29.530588853;

function moonPhase(date) {
  const days = (date.getTime() / 1000 - KNOWN_NEW_MOON) / 86400;
  const cycle = ((days % SYNODIC_DAYS) + SYNODIC_DAYS) % SYNODIC_DAYS;
  const fraction = cycle / SYNODIC_DAYS; // 0..1
  const illuminationPct = Math.round(
    (1 - Math.cos(2 * Math.PI * fraction)) * 50
  );
  let label;
  if (fraction < 0.03 || fraction > 0.97) label = "New";
  else if (fraction < 0.22) label = "Waxing crescent";
  else if (fraction < 0.28) label = "First quarter";
  else if (fraction < 0.47) label = "Waxing gibbous";
  else if (fraction < 0.53) label = "Full";
  else if (fraction < 0.72) label = "Waning gibbous";
  else if (fraction < 0.78) label = "Last quarter";
  else label = "Waning crescent";
  return { fraction, label, illuminationPct };
}

// Build the SVG path for the LIT portion of the moon. Background circle is
// drawn separately as the dark side.
function moonLitPath(phase, cx = 50, cy = 50, R = 42) {
  const cos = Math.cos(phase * Math.PI * 2);
  const illum = (1 - cos) / 2;
  const waxing = phase < 0.5;
  const a = Math.abs(cos) * R;
  const outerSweep = waxing ? 1 : 0;
  // Crescent: terminator bows toward lit side (same sweep as outer).
  // Gibbous: terminator bows toward shadow (opposite sweep).
  const terminatorSweep = illum < 0.5 ? outerSweep : 1 - outerSweep;
  return (
    `M ${cx},${cy - R} ` +
    `A ${R},${R} 0 0,${outerSweep} ${cx},${cy + R} ` +
    `A ${a},${R} 0 0,${terminatorSweep} ${cx},${cy - R} Z`
  );
}

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function dayLength(sunrise, sunset) {
  if (!sunrise || !sunset) return "—";
  const ms = new Date(sunset) - new Date(sunrise);
  if (Number.isNaN(ms) || ms <= 0) return "—";
  const total = Math.round(ms / 60000);
  const h = Math.floor(total / 60);
  const m = total % 60;
  return `${h}h ${m}m`;
}

function sunProgress(now, sunrise, sunset) {
  if (!sunrise || !sunset) return null;
  const r = new Date(sunrise).getTime();
  const s = new Date(sunset).getTime();
  const t = now.getTime();
  if (s <= r) return null;
  return (t - r) / (s - r);
}

export default function render(host, ctx) {
  const { size, options } = ctx.cell;
  const { data } = ctx;
  const placeLabel = options.label || "";
  const moon = moonPhase(new Date());
  const sunrise = data && data.sunrise;
  const sunset = data && data.sunset;
  const error = data && data.error;

  if (error) {
    host.innerHTML = `
      <link rel="stylesheet" href="/plugins/sun_moon/client.css">
      <div class="sm sm--${size}">
        <div class="error-block"><div class="error">${error}</div></div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  // Sun arc geometry. SVG viewBox is 200×100; horizon at y=80, peak at y=8.
  const progress = sunProgress(new Date(), sunrise, sunset);
  const arcLeft = 18;
  const arcRight = 182;
  const horizonY = 80;
  const peakY = 8;
  const clampedProgress = progress == null ? null : Math.max(0, Math.min(1, progress));
  const sunX =
    clampedProgress == null
      ? null
      : arcLeft + (arcRight - arcLeft) * clampedProgress;
  const sunY =
    clampedProgress == null
      ? null
      : horizonY - (horizonY - peakY) * Math.sin(Math.PI * clampedProgress);

  // Sun rays angled around the disc.
  const rays = [];
  const rayCount = 8;
  for (let i = 0; i < rayCount; i++) {
    const angle = (i / rayCount) * 2 * Math.PI;
    const x1 = Math.cos(angle) * 9;
    const y1 = Math.sin(angle) * 9;
    const x2 = Math.cos(angle) * 13.5;
    const y2 = Math.sin(angle) * 13.5;
    rays.push(
      `<line x1="${x1.toFixed(1)}" y1="${y1.toFixed(1)}" x2="${x2.toFixed(1)}" y2="${y2.toFixed(1)}" />`
    );
  }

  const sunSvg = `
    <svg viewBox="0 0 200 100" preserveAspectRatio="xMidYMid meet" class="sun-svg">
      <line class="horizon" x1="10" y1="${horizonY}" x2="190" y2="${horizonY}" />
      <path class="arc" d="M ${arcLeft},${horizonY} Q 100,${peakY - 10} ${arcRight},${horizonY}" />
      ${
        sunX !== null
          ? `<g class="sun" transform="translate(${sunX.toFixed(1)},${sunY.toFixed(1)})">
              <g class="rays">${rays.join("")}</g>
              <circle cx="0" cy="0" r="6.5" />
            </g>`
          : `<text class="sun-out" x="100" y="${horizonY + 12}" text-anchor="middle">Sun is below the horizon</text>`
      }
      <g class="endpoints">
        <circle cx="${arcLeft}" cy="${horizonY}" r="2" />
        <circle cx="${arcRight}" cy="${horizonY}" r="2" />
      </g>
      <text class="time-label" x="${arcLeft}" y="${horizonY + 12}" text-anchor="middle">${fmtTime(sunrise)}</text>
      <text class="time-label" x="${arcRight}" y="${horizonY + 12}" text-anchor="middle">${fmtTime(sunset)}</text>
    </svg>
  `;

  const moonSvg = `
    <svg viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet" class="moon-svg">
      <circle class="moon-dark" cx="50" cy="50" r="42" />
      <path class="moon-lit" d="${moonLitPath(moon.fraction)}" />
      <circle class="moon-outline" cx="50" cy="50" r="42" />
    </svg>
  `;

  host.innerHTML = `
    <link rel="stylesheet" href="/plugins/sun_moon/client.css">
    <div class="sm sm--${size}">
      ${placeLabel ? `<div class="place">${placeLabel}</div>` : ""}
      <div class="sun-row">${sunSvg}</div>
      ${
        size !== "sm"
          ? `<div class="day-length">Day length · ${dayLength(sunrise, sunset)}</div>`
          : ""
      }
      <div class="moon-row">
        ${moonSvg}
        <div class="moon-meta">
          <div class="moon-label">${moon.label}</div>
          <div class="moon-illum">${moon.illuminationPct}% illuminated</div>
        </div>
      </div>
    </div>
  `;

  host.host.dataset.rendered = "true";
}
