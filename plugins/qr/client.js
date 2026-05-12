// QR code widget — renders an SVG QR encoding a URL, WiFi credentials,
// or arbitrary text. Encoding happens client-side in the shadow DOM via
// the vendored qrcodegen library; nothing leaves the panel.
//
// The composer screenshots the rendered shadow tree, so the SVG must be
// fully laid out before we set ``data-rendered=true``. Encoding is
// synchronous and finishes within the same frame, so a single render
// pass is enough.

import { qrcodegen } from "./static/qrcodegen.js";

const ECC_LEVELS = {
  L: qrcodegen.QrCode.Ecc.LOW,
  M: qrcodegen.QrCode.Ecc.MEDIUM,
  Q: qrcodegen.QrCode.Ecc.QUARTILE,
  H: qrcodegen.QrCode.Ecc.HIGH,
};

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

// MECARD-style escaping for the WIFI: payload — backslash, semicolon,
// comma, colon and quote each prefix with a backslash. Without this,
// passwords containing those characters silently produce a malformed
// payload that scanners reject.
function escapeWifiField(s) {
  return String(s).replace(/([\\;,:"])/g, "\\$1");
}

function buildPayload(opts) {
  const mode = opts.mode || "url";
  if (mode === "wifi") {
    const ssid = (opts.wifi_ssid || "").trim();
    if (!ssid) return { payload: "", error: "WiFi SSID is required." };
    const security = opts.wifi_security || "WPA";
    const password = security === "nopass" ? "" : (opts.wifi_password || "");
    const hidden = opts.wifi_hidden ? "true" : "false";
    const payload =
      `WIFI:T:${security};S:${escapeWifiField(ssid)};` +
      (password ? `P:${escapeWifiField(password)};` : "") +
      `H:${hidden};;`;
    return { payload };
  }
  if (mode === "text") {
    const text = (opts.text || "").trim();
    if (!text) return { payload: "", error: "Text is required." };
    return { payload: text };
  }
  // URL — the default.
  const url = (opts.url || "").trim();
  if (!url) return { payload: "", error: "URL is required." };
  return { payload: url };
}

function deriveCaption(opts) {
  if (opts.caption) return opts.caption;
  const mode = opts.mode || "url";
  if (mode === "wifi") return opts.wifi_ssid || "WiFi";
  if (mode === "url") {
    try {
      const u = new URL(opts.url);
      // Drop the protocol for a cleaner human-readable caption; keep the
      // path so the user can sanity-check what they're sharing.
      return u.host + (u.pathname === "/" ? "" : u.pathname);
    } catch {
      return opts.url || "";
    }
  }
  return "";
}

function iconFor(mode) {
  if (mode === "wifi") return "ph-wifi-high";
  if (mode === "text") return "ph-text-aa";
  return "ph-link";
}

function labelFor(mode) {
  if (mode === "wifi") return "Scan to join";
  if (mode === "text") return "Scan to read";
  return "Scan to open";
}

// Convert a QrCode object to a tightly-fitting SVG string. Modules are
// 1×1 in SVG user units; the host element scales the SVG to fill its
// container via the wrapper's CSS. A 2-module quiet zone is included
// (the spec recommends 4 but on a small e-ink cell that wastes space —
// 2 still scans reliably from typical viewing distances).
function qrToSvg(qr, dark, light) {
  const border = 2;
  const size = qr.size + border * 2;
  let parts = "";
  for (let y = 0; y < qr.size; y++) {
    for (let x = 0; x < qr.size; x++) {
      if (qr.getModule(x, y)) {
        parts += `M${x + border},${y + border}h1v1h-1z`;
      }
    }
  }
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${size} ${size}" ` +
    `shape-rendering="crispEdges" preserveAspectRatio="xMidYMid meet">` +
    `<rect width="100%" height="100%" fill="${light}"/>` +
    `<path d="${parts}" fill="${dark}"/>` +
    `</svg>`
  );
}

export default function render(host, ctx) {
  const opts = ctx.cell?.options || {};
  const { payload, error } = buildPayload(opts);
  const mode = opts.mode || "url";

  if (error) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="widget">
        <div class="state-error">
          <i class="ph ph-qr-code"></i>
          <div class="msg">${escapeHtml(error)}</div>
        </div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  let svg;
  try {
    const ecl = ECC_LEVELS[opts.error_correction] || ECC_LEVELS.M;
    const qr = qrcodegen.QrCode.encodeText(payload, ecl);
    // Dark = theme fg, light = theme bg. Pulling tokens from the cell
    // host's computed style lets the QR follow per-cell theme overrides
    // (e.g. a "white" sub-theme cell shows pure black-on-white modules
    // regardless of the page's default palette).
    const cs = getComputedStyle(host.host);
    const dark = cs.getPropertyValue("--theme-fg").trim() || "#000000";
    const light = cs.getPropertyValue("--theme-bg").trim() || "#ffffff";
    svg = qrToSvg(qr, dark, light);
  } catch (e) {
    host.innerHTML = `
      <link rel="stylesheet" href="/static/style/widget-base.css">
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <div class="widget">
        <div class="state-error">
          <i class="ph ph-qr-code"></i>
          <div class="msg">${escapeHtml("QR: " + (e.message || e))}</div>
        </div>
      </div>
    `;
    host.host.dataset.rendered = "true";
    return;
  }

  const caption = deriveCaption(opts);
  const icon = iconFor(mode);
  const label = labelFor(mode);

  host.innerHTML = `
    <link rel="stylesheet" href="/static/style/widget-base.css">
    <link rel="stylesheet" href="/plugins/qr/client.css">
    <link rel="stylesheet" href="/static/icons/phosphor.css">
    <div class="widget qr">
      <div class="qr-label">
        <i class="ph ${icon}"></i>
        <span>${escapeHtml(label)}</span>
      </div>
      <div class="qr-frame">${svg}</div>
      ${caption ? `<div class="qr-caption">${escapeHtml(caption)}</div>` : ""}
    </div>
  `;
  host.host.dataset.rendered = "true";
}
