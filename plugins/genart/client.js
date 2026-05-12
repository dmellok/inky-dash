// Generative art — deterministic, full-bleed. Six styles, picked by the
// seed string. Drawn into an SVG so it scales cleanly to the panel grid.
//
// Each style is a pure (rng) → SVG string function. The seed is hashed
// down to a small PRNG state and threaded through; same seed always
// produces the same piece. Picking "auto" rotates the style each day
// alongside the colours.

const STYLES = ["stella", "bauhaus", "kandinsky", "mondrian", "rays", "flowfield"];

// 32-bit string hash → uint32. Used to seed the PRNG.
function hashStr(str) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < str.length; i++) {
    h = Math.imul(h ^ str.charCodeAt(i), 16777619);
  }
  return h >>> 0;
}

// Tiny PRNG (mulberry32). Stable, deterministic, plenty good for art.
function makeRng(seedNum) {
  let state = seedNum >>> 0;
  return function () {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const between = (rng, a, b) => a + rng() * (b - a);
const pick = (rng, arr) => arr[Math.floor(rng() * arr.length)];

// Theme-aware palettes. Most pieces use the theme's accent + fg over the
// theme bg, with a few discordant accents for variety. We let CSS variables
// flow through via stroke="currentColor" / fill="var(--theme-accent)" so
// any theme on the panel re-skins the whole piece.
function paletteFor(rng) {
  return {
    bg: "var(--theme-bg)",
    surface: "var(--theme-surface)",
    surface2: "var(--theme-surface2, var(--theme-surface))",
    accent: "var(--theme-accent)",
    fg: "var(--theme-fg)",
    fgSoft: "var(--theme-fgSoft)",
    divider: "var(--theme-divider)",
    // Bonus colours that may or may not actually be in the panel's gamut;
    // dithering handles it. Pulled from a tiny curated set so the pieces
    // don't feel like random web1 swatches.
    extras: pick(rng, [
      ["#d97757", "#7ea16b", "#3c6e91", "#dab64a"],
      ["#c97c70", "#5a9591", "#a18cd1", "#dab64a"],
      ["#9b3838", "#3a6e6e", "#d68a3c", "#1f4f8b"],
      ["#2a3a4d", "#b34a5a", "#e0b13a", "#7ea16b"],
    ]),
  };
}

// 1. Concentric — Frank Stella. Nested squares or arcs from corner.
function stella(rng, w, h, P) {
  const corner = pick(rng, ["tl", "tr", "bl", "br", "center"]);
  const stripes = 14 + Math.floor(rng() * 8);
  const maxR = Math.hypot(w, h);
  let out = `<rect width="${w}" height="${h}" fill="${P.bg}"/>`;
  const colours = [P.fg, P.accent, P.surface, P.fgSoft, ...P.extras];
  for (let i = stripes; i >= 0; i--) {
    const r = (i / stripes) * maxR;
    const c = colours[i % colours.length];
    if (corner === "center") {
      out += `<circle cx="${w / 2}" cy="${h / 2}" r="${r * 0.6}" fill="${c}"/>`;
    } else {
      const cx = corner.includes("r") ? w : 0;
      const cy = corner.includes("b") ? h : 0;
      out += `<circle cx="${cx}" cy="${cy}" r="${r}" fill="${c}"/>`;
    }
  }
  return out;
}

// 2. Bauhaus grid — uneven rows + cols, blocks tinted from palette.
function bauhaus(rng, w, h, P) {
  const cols = 3 + Math.floor(rng() * 3); // 3..5
  const rows = 3 + Math.floor(rng() * 3);
  const colW = [];
  const rowH = [];
  let total = 0;
  for (let i = 0; i < cols; i++) {
    const x = 0.5 + rng();
    colW.push(x);
    total += x;
  }
  for (let i = 0; i < cols; i++) colW[i] = (colW[i] / total) * w;
  total = 0;
  for (let i = 0; i < rows; i++) {
    const x = 0.5 + rng();
    rowH.push(x);
    total += x;
  }
  for (let i = 0; i < rows; i++) rowH[i] = (rowH[i] / total) * h;
  const colours = [P.bg, P.surface, P.surface2, P.accent, P.fg, ...P.extras];
  let out = `<rect width="${w}" height="${h}" fill="${P.bg}"/>`;
  let y = 0;
  for (let r = 0; r < rows; r++) {
    let x = 0;
    for (let c = 0; c < cols; c++) {
      const cw = colW[c];
      const ch = rowH[r];
      const fill = pick(rng, colours);
      out += `<rect x="${x}" y="${y}" width="${cw}" height="${ch}" fill="${fill}"/>`;
      // Half the time, drop a circle or diagonal into a cell for variety.
      if (rng() < 0.25) {
        const r2 = Math.min(cw, ch) * 0.35;
        out += `<circle cx="${x + cw / 2}" cy="${y + ch / 2}" r="${r2}" fill="${pick(rng, colours)}"/>`;
      } else if (rng() < 0.1) {
        out += `<line x1="${x}" y1="${y}" x2="${x + cw}" y2="${y + ch}" stroke="${P.fg}" stroke-width="${Math.min(cw, ch) * 0.04}"/>`;
      }
      x += cw;
    }
    y += rowH[r];
  }
  return out;
}

// 3. Kandinsky — floating shapes: circles, triangles, lines on plain ground.
function kandinsky(rng, w, h, P) {
  const colours = [P.accent, P.fg, P.fgSoft, ...P.extras];
  let out = `<rect width="${w}" height="${h}" fill="${P.bg}"/>`;
  const count = 18 + Math.floor(rng() * 14);
  for (let i = 0; i < count; i++) {
    const x = between(rng, w * 0.05, w * 0.95);
    const y = between(rng, h * 0.05, h * 0.95);
    const s = between(rng, w * 0.04, w * 0.22);
    const c = pick(rng, colours);
    const t = rng();
    if (t < 0.45) {
      out += `<circle cx="${x}" cy="${y}" r="${s / 2}" fill="${c}" opacity="${between(rng, 0.5, 1)}"/>`;
    } else if (t < 0.75) {
      const x2 = x + s * 0.866;
      const y2 = y + s / 2;
      const x3 = x;
      const y3 = y + s;
      out += `<polygon points="${x},${y} ${x2},${y2} ${x3},${y3}" fill="${c}"/>`;
    } else {
      const ang = rng() * Math.PI * 2;
      const x2 = x + Math.cos(ang) * s * 2;
      const y2 = y + Math.sin(ang) * s * 2;
      out += `<line x1="${x}" y1="${y}" x2="${x2}" y2="${y2}" stroke="${c}" stroke-width="${between(rng, w * 0.004, w * 0.012)}"/>`;
    }
  }
  return out;
}

// 4. Mondrian — black grid, primary blocks. Recursive horizontal/vertical
// splits filled with palette colours.
function mondrian(rng, w, h, P) {
  // Slightly off-black borders for warmer paper look on Spectra.
  const stroke = P.fg;
  const strokeW = Math.max(2, Math.min(w, h) * 0.018);
  const fills = [P.bg, P.bg, P.bg, P.bg, P.accent, P.surface2, ...P.extras];
  const rects = [{ x: 0, y: 0, w, h }];
  // Number of splits — more = denser.
  const splits = 5 + Math.floor(rng() * 4);
  for (let i = 0; i < splits; i++) {
    // Pick a rect (bias toward larger ones).
    rects.sort((a, b) => b.w * b.h - a.w * a.h);
    const idx = Math.floor(Math.pow(rng(), 2) * Math.min(rects.length, 4));
    const r = rects.splice(idx, 1)[0];
    if (r.w < w * 0.18 || r.h < h * 0.18) {
      rects.push(r);
      continue;
    }
    if (r.w > r.h ? rng() < 0.7 : rng() < 0.3) {
      // Vertical split
      const cut = between(rng, r.w * 0.3, r.w * 0.7);
      rects.push({ x: r.x, y: r.y, w: cut, h: r.h });
      rects.push({ x: r.x + cut, y: r.y, w: r.w - cut, h: r.h });
    } else {
      const cut = between(rng, r.h * 0.3, r.h * 0.7);
      rects.push({ x: r.x, y: r.y, w: r.w, h: cut });
      rects.push({ x: r.x, y: r.y + cut, w: r.w, h: r.h - cut });
    }
  }
  let out = "";
  for (const r of rects) {
    out += `<rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}" fill="${pick(rng, fills)}" stroke="${stroke}" stroke-width="${strokeW}"/>`;
  }
  return out;
}

// 5. Sun rays — radial fan from a corner or bottom edge.
function rays(rng, w, h, P) {
  const colours = [P.accent, P.fg, P.fgSoft, ...P.extras];
  const cx = between(rng, w * 0.2, w * 0.8);
  const cy = h + h * 0.05; // anchor below bottom
  const rays = 18 + Math.floor(rng() * 10);
  const maxR = Math.hypot(w, h) * 1.2;
  let out = `<rect width="${w}" height="${h}" fill="${P.bg}"/>`;
  for (let i = 0; i < rays; i++) {
    const a0 = (-Math.PI) + (i / rays) * Math.PI;
    const a1 = (-Math.PI) + ((i + 1) / rays) * Math.PI;
    const x0 = cx + Math.cos(a0) * maxR;
    const y0 = cy + Math.sin(a0) * maxR;
    const x1 = cx + Math.cos(a1) * maxR;
    const y1 = cy + Math.sin(a1) * maxR;
    out += `<polygon points="${cx},${cy} ${x0},${y0} ${x1},${y1}" fill="${colours[i % colours.length]}"/>`;
  }
  // Big sun disc above the anchor.
  out += `<circle cx="${cx}" cy="${cy}" r="${h * 0.25}" fill="${P.accent}"/>`;
  return out;
}

// 6. Flow field — Perlin-ish lines following a vector field.
function flowfield(rng, w, h, P) {
  const colours = [P.fg, P.accent, P.fgSoft, ...P.extras];
  let out = `<rect width="${w}" height="${h}" fill="${P.bg}"/>`;
  // Two random Gaussian "magnets" steer the field.
  const m = [
    { x: between(rng, 0, w), y: between(rng, 0, h), s: between(rng, -1, 1) },
    { x: between(rng, 0, w), y: between(rng, 0, h), s: between(rng, -1, 1) },
  ];
  const fieldAt = (x, y) => {
    let dx = 0;
    let dy = 0;
    for (const k of m) {
      const ddx = x - k.x;
      const ddy = y - k.y;
      const r2 = ddx * ddx + ddy * ddy + 1;
      dx += (k.s * ddy) / r2;
      dy -= (k.s * ddx) / r2;
    }
    const len = Math.hypot(dx, dy) || 1;
    return [dx / len, dy / len];
  };
  const lines = 70 + Math.floor(rng() * 50);
  for (let i = 0; i < lines; i++) {
    let x = rng() * w;
    let y = rng() * h;
    const c = pick(rng, colours);
    const sw = between(rng, w * 0.002, w * 0.006);
    let path = `M${x.toFixed(1)},${y.toFixed(1)}`;
    const steps = 60 + Math.floor(rng() * 50);
    const stepSize = Math.min(w, h) * 0.012;
    for (let s = 0; s < steps; s++) {
      const [vx, vy] = fieldAt(x, y);
      x += vx * stepSize;
      y += vy * stepSize;
      if (x < -10 || x > w + 10 || y < -10 || y > h + 10) break;
      path += `L${x.toFixed(1)},${y.toFixed(1)}`;
    }
    out += `<path d="${path}" stroke="${c}" stroke-width="${sw}" fill="none" stroke-linecap="round"/>`;
  }
  return out;
}

const RENDERERS = { stella, bauhaus, kandinsky, mondrian, rays, flowfield };

export default function render(host, ctx) {
  const data = ctx.data || {};
  const userSeed = (ctx.cell?.options?.seed || "").trim();
  const styleOpt = ctx.cell?.options?.style || "auto";

  const seedStr = userSeed || `daily-${data.date || ""}`;
  const seedNum = hashStr(seedStr);
  const rng = makeRng(seedNum);

  const style =
    styleOpt === "auto"
      ? STYLES[seedNum % STYLES.length]
      : RENDERERS[styleOpt]
        ? styleOpt
        : "stella";

  const fn = RENDERERS[style] || stella;
  const palette = paletteFor(rng);

  // Square-ish virtual canvas. SVG scales to the host via viewBox.
  const W = 1000;
  const H = 1000;
  const inner = fn(rng, W, H, palette);

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/plugins/genart/client.css">
    <div class="genart">
      <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid slice" width="100%" height="100%">
        ${inner}
      </svg>
    </div>
  `;
  host.host.dataset.rendered = "true";
}
