// Composer bootstrap. For each .cell on the page, attach a shadow DOM, inject
// the default theme variables, and call the plugin's default-export render
// function with the documented ctx shape (see docs/v4-plugins.md).
//
// Themes and fonts arrive in M5; this file ships defaults so plugins can
// render today without those subsystems.

const SIZE_THRESHOLDS = [
  { size: "xs", max: 200 },
  { size: "sm", max: 400 },
  { size: "md", max: 700 },
];

function resolveSize(w, h) {
  const longer = Math.max(w, h);
  for (const { size, max } of SIZE_THRESHOLDS) {
    if (longer <= max) return size;
  }
  return "lg";
}

const DEFAULT_THEME = {
  bg: "#ffffff",
  fg: "#1a1612",
  fgSoft: "#5a4f44",
  surface: "#f5e8d8",
  surface2: "#ebd9c0",
  muted: "#8b7e70",
  accent: "#d97757",
  accentSoft: "#aa5a3f",
  divider: "#c8b89b",
  danger: "#c97c70",
  warn: "#d4a957",
  ok: "#7da670",
};

const DEFAULT_FONT = {
  family: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
  weight: 400,
};

const THEME_VAR_NAMES = {
  bg: "--theme-bg",
  fg: "--theme-fg",
  fgSoft: "--theme-fgSoft",
  surface: "--theme-surface",
  surface2: "--theme-surface2",
  muted: "--theme-muted",
  accent: "--theme-accent",
  accentSoft: "--theme-accentSoft",
  divider: "--theme-divider",
  danger: "--theme-danger",
  warn: "--theme-warn",
  ok: "--theme-ok",
};

function applyTheme(host, theme) {
  for (const [key, varName] of Object.entries(THEME_VAR_NAMES)) {
    host.style.setProperty(varName, theme[key]);
  }
}

function applyFont(host, font) {
  host.style.setProperty("font-family", font.family);
  host.style.setProperty("font-weight", String(font.weight));
}

function reportError(cell, shadow, pluginId, err) {
  cell.classList.add("error");
  cell.dataset.error = err.message || String(err);
  shadow.innerHTML = `
    <style>
      .error { color: #c97c70; padding: 8px; font: 12px/1.4 monospace; }
    </style>
    <div class="error">${pluginId}: ${err.message || err}</div>
  `;
  // eslint-disable-next-line no-console
  console.error(`[composer] plugin ${pluginId} failed:`, err);
}

async function mountCell(cell) {
  const w = Number(cell.dataset.cellW);
  const h = Number(cell.dataset.cellH);
  const panelW = Number(cell.dataset.panelW);
  const panelH = Number(cell.dataset.panelH);
  const pluginId = cell.dataset.plugin;
  let options = {};
  try {
    options = JSON.parse(cell.dataset.options || "{}");
  } catch {
    options = {};
  }

  applyTheme(cell, DEFAULT_THEME);
  applyFont(cell, DEFAULT_FONT);

  const shadow = cell.attachShadow({ mode: "open" });

  const ctx = {
    cell: { w, h, size: resolveSize(w, h), options },
    panel: { w: panelW, h: panelH, portrait: panelH > panelW },
    theme: { ...DEFAULT_THEME },
    font: { ...DEFAULT_FONT },
    data: null,
    preview: new URLSearchParams(location.search).get("preview") === "1",
  };

  try {
    const mod = await import(`/plugins/${pluginId}/client.js`);
    if (typeof mod.default !== "function") {
      throw new Error("plugin module has no default export");
    }
    await mod.default(shadow, ctx);
  } catch (err) {
    reportError(cell, shadow, pluginId, err);
  }
}

const cells = document.querySelectorAll(".cell[data-plugin]");
await Promise.all(Array.from(cells).map(mountCell));
