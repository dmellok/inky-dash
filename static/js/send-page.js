// Send page controller.
//
// Three image sources (file / URL / webpage) plus a Dash tab to push saved
// dashboards and a History tab. Each source produces a "ready" id that the
// shared push button consumes; the only branch is which API endpoint we POST
// to (push-image vs push-webpage).

let lockoutTimer = null;

const sendPageEl = document.querySelector(".send-page");

// Rotate is always 0-relative from the user's perspective. The push pipeline
// adds an extra +90° base for portrait panels, so a user-set 0 still lands
// in the right orientation on the device.
const state = {
  source: "file",          // "file" | "url" | "webpage"
  imageId: null,           // present when source ∈ {file, url} after upload/fetch
  imageUrl: null,          // local URL for the most recent file/URL upload (preview)
  webpageReady: false,     // present when source = "webpage" + URL filled
  options: { rotate: 0, scale: "fit", bg: "white", saturation: 0.5 },
  selectedDashId: null,    // currently-previewed dashboard (Dash tab)
  selectedHistoryId: null, // currently-previewed history row (History tab)
  historyRows: [],         // last fetched list (for click → preview)
};

const sendBtn = document.getElementById("send-btn");
const dashPushBtn = document.getElementById("dash-push-btn");
const imagePreview = document.getElementById("image-preview");
const dashPreview = document.getElementById("dash-preview");
const historyPreview = document.getElementById("history-preview");
const previewPane = document.querySelector(".send-preview-pane");

// Pull native panel pixel dimensions once. The CSS variables on .send-page
// are set by the template from `panel_width`/`panel_height`.
const PANEL_W = parseFloat(getComputedStyle(sendPageEl).getPropertyValue("--panel-w")) || 800;
const PANEL_H = parseFloat(getComputedStyle(sendPageEl).getPropertyValue("--panel-h")) || 480;

initPrimaryTabs();
initSourceTabs();
initDropzone();
initUrlSource();
initWebpageSource();
initOptionFields();
initSendButton();
initDashPush();
initHistoryControls();
updateImagePreview();
applyPreviewVisibility("image");

window.addEventListener("resize", rescaleAllPreviews);
if (typeof ResizeObserver !== "undefined" && previewPane) {
  new ResizeObserver(rescaleAllPreviews).observe(previewPane);
}
rescaleAllPreviews();

// ---------- Native-pixel iframe scaling ---------------------------------
// The dashboard editor uses this trick: render the iframe at panel native
// pixels so widgets see the actual viewport, then `transform: scale()` it
// down to fit the column. Quad Pulse and other layout-sensitive dashboards
// rely on this — at column-fit dimensions they reflow incorrectly.
function rescaleAllPreviews() {
  rescaleCanvas(document.getElementById("image-preview-canvas"));
  rescaleCanvas(document.getElementById("dash-preview-canvas"));
  rescaleCanvas(document.getElementById("history-preview-canvas"));
  // Re-apply image rotation transform — the inner scale depends on the
  // canvas's measured size, which changes with the column width.
  if (state.source !== "webpage" && state.imageUrl) updateImagePreview();
}

function rescaleCanvas(canvas) {
  if (!canvas) return;
  const w = canvas.clientWidth;
  const h = canvas.clientHeight;
  if (!w || !h) return;
  const scale = Math.min(w / PANEL_W, h / PANEL_H);
  canvas.style.setProperty("--preview-scale", String(scale));
}

function applyPreviewVisibility(tab) {
  if (!previewPane) return;
  previewPane.dataset.activeTab = tab;
  imagePreview.hidden = tab !== "image";
  dashPreview.hidden = tab !== "dash";
  if (historyPreview) historyPreview.hidden = tab !== "history";
  // Defer until the layout settles, then size the canvas content.
  requestAnimationFrame(rescaleAllPreviews);
}

// ---------- primary tabs (Image / Dash / History) ----------------------

function initPrimaryTabs() {
  document.querySelectorAll(".primary-tabs .tab").forEach((t) => {
    t.addEventListener("click", () => {
      const tab = t.dataset.tab;
      document.querySelectorAll(".primary-tabs .tab").forEach((x) =>
        x.classList.toggle("active", x === t));
      document.querySelectorAll("[data-panel]").forEach((p) => {
        p.hidden = p.dataset.panel !== tab;
      });
      applyPreviewVisibility(tab);
      if (tab === "dash") loadDashboards();
      if (tab === "history") loadHistory();
    });
  });
}

// ---------- source sub-tabs (file / URL / webpage) ----------------------

function initSourceTabs() {
  document.querySelectorAll(".source-tabs .tab").forEach((t) => {
    t.addEventListener("click", () => {
      const src = t.dataset.source;
      state.source = src;
      document.querySelectorAll(".source-tabs .tab").forEach((x) =>
        x.classList.toggle("active", x === t));
      document.querySelectorAll(".source-pane").forEach((p) => {
        p.hidden = p.dataset.source !== src;
      });
      updateSendButtonState();
      updateImagePreview();
      setStatus("", "");
    });
  });
}

// ---------- file source -------------------------------------------------

function initDropzone() {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const filePick = document.getElementById("file-pick");
  filePick.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    if (fileInput.files[0]) uploadFile(fileInput.files[0]);
  });
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
    const f = e.dataTransfer?.files?.[0];
    if (f) uploadFile(f);
  });
}

async function uploadFile(file) {
  const data = new FormData();
  data.append("file", file);
  setStatus("saving", `Uploading ${file.name}…`);
  try {
    const r = await fetch("/api/uploads", { method: "POST", body: data });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
    state.imageId = body.id;
    state.imageUrl = URL.createObjectURL(file);
    const meta = document.getElementById("file-meta");
    meta.hidden = false;
    meta.textContent = `${file.name} → ${body.id} (${formatBytes(body.size)})`;
    setStatus("", "");
    updateSendButtonState();
    updateImagePreview();
  } catch (err) {
    setStatus("error", `Upload failed: ${err.message}`);
  }
}

// ---------- URL source --------------------------------------------------

function initUrlSource() {
  const input = document.getElementById("url-input");
  const fetchBtn = document.getElementById("url-fetch");
  fetchBtn.addEventListener("click", () => fetchFromUrl(input.value.trim()));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); fetchFromUrl(input.value.trim()); }
  });
  input.addEventListener("input", () => {
    // typing invalidates the previously-fetched id until refetch
    if (state.source === "url" && state.imageId) {
      state.imageId = null;
      state.imageUrl = null;
      updateSendButtonState();
      updateImagePreview();
    }
  });
}

async function fetchFromUrl(url) {
  if (!url) return;
  const status = document.getElementById("url-status");
  status.textContent = "Fetching…";
  setStatus("saving", "Fetching URL…");
  try {
    const r = await fetch("/api/uploads/from-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
    state.imageId = body.id;
    state.imageUrl = url;
    status.textContent = `Saved as ${body.id} (${formatBytes(body.size)})`;
    setStatus("", "");
    updateSendButtonState();
    updateImagePreview();
  } catch (err) {
    status.textContent = "";
    setStatus("error", `Fetch failed: ${err.message}`);
  }
}

// ---------- Webpage source ----------------------------------------------

function initWebpageSource() {
  const input = document.getElementById("webpage-url-input");
  const apply = () => {
    state.webpageReady = !!input.value.trim();
    updateSendButtonState();
    updateImagePreview();
  };
  input.addEventListener("input", apply);
  input.addEventListener("change", apply);
}

// ---------- shared options (rotate/scale/bg/saturation) -----------------

function initOptionFields() {
  document.querySelectorAll('select[name]').forEach((sel) => {
    if (!(sel.name in state.options)) return;
    sel.value = String(state.options[sel.name]);
    sel.addEventListener("change", () => {
      const v = sel.value;
      state.options[sel.name] = (sel.name === "rotate") ? parseInt(v, 10) : v;
      updateImagePreview();
    });
  });
  const sat = document.querySelector('input[name="saturation"]');
  const readout = document.querySelector('[data-readout="saturation"]');
  const apply = () => {
    const v = parseFloat(sat.value);
    state.options.saturation = v;
    readout.textContent = v.toFixed(2);
    updateImagePreview();
  };
  sat.addEventListener("input", apply);
  apply();
}

// ---------- send button state machine -----------------------------------

function updateSendButtonState() {
  if (lockoutTimer) return;  // countdown owns the button
  let ready = false;
  if (state.source === "file" || state.source === "url") {
    ready = !!state.imageId;
  } else if (state.source === "webpage") {
    ready = !!state.webpageReady;
  }
  sendBtn.disabled = !ready;
}

function initSendButton() {
  sendBtn.addEventListener("click", async () => {
    if (sendBtn.disabled) return;
    setStatus("saving", "Rendering & pushing…");
    sendBtn.disabled = true;
    try {
      let r;
      if (state.source === "file" || state.source === "url") {
        r = await fetch(`/api/push-image/${encodeURIComponent(state.imageId)}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(state.options),
        });
      } else if (state.source === "webpage") {
        const url = document.getElementById("webpage-url-input").value.trim();
        const extraWait = parseInt(document.getElementById("extra-wait").value, 10) || 0;
        r = await fetch(`/api/push-webpage`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url, extra_wait_ms: extraWait, ...state.options }),
        });
      } else {
        throw new Error("unknown source");
      }
      const body = await r.json().catch(() => ({}));
      if (r.status === 409) {
        setStatus("error", body.error || "A push is already in progress");
      } else if (!r.ok) {
        throw new Error(body.error || `HTTP ${r.status}`);
      } else {
        const dur = body.duration_s ? body.duration_s.toFixed(2) : "?";
        setStatus("saved", `Pushed · history #${body.history_id} · ${dur}s`);
        startLockoutCountdown();
      }
    } catch (err) {
      setStatus("error", `Push failed: ${err.message}`);
    } finally {
      if (!lockoutTimer) updateSendButtonState();
    }
  });
}

async function startLockoutCountdown() {
  let secs = 30;
  try {
    const s = await fetch("/api/push/state").then((r) => r.json());
    if (Number.isFinite(s.lockout_seconds)) secs = s.lockout_seconds;
  } catch (_) { /* keep default */ }
  sendBtn.disabled = true;
  let remaining = secs;
  if (lockoutTimer) clearInterval(lockoutTimer);
  const baseHTML = `<i class="ph ph-upload-simple"></i> Push to panel`;
  sendBtn.innerHTML = `<i class="ph ph-clock"></i> Wait ${remaining}s…`;
  lockoutTimer = setInterval(() => {
    remaining -= 1;
    if (remaining > 0) {
      sendBtn.innerHTML = `<i class="ph ph-clock"></i> Wait ${remaining}s…`;
    } else {
      clearInterval(lockoutTimer);
      lockoutTimer = null;
      sendBtn.innerHTML = baseHTML;
      updateSendButtonState();
    }
  }, 1000);
}

// ---------- Live preview ------------------------------------------------

// Image-tab preview: show the currently-selected image (file or URL) or the
// configured webpage URL, applying CSS approximations of rotate/scale/bg/
// saturation. Server-side push will render at panel resolution; this is just
// a visual cue for what's about to be sent.
function updateImagePreview() {
  if (!imagePreview) return;
  const img = imagePreview.querySelector(".send-preview-img");
  const bgImg = imagePreview.querySelector(".send-preview-bg");
  const iframe = imagePreview.querySelector(".send-preview-iframe");
  const { rotate, scale, bg, saturation } = state.options;

  if (state.source === "webpage") {
    img.hidden = true;
    img.removeAttribute("src");
    if (bgImg) { bgImg.hidden = true; bgImg.removeAttribute("src"); }
    const url = document.getElementById("webpage-url-input")?.value.trim();
    if (url) {
      if (iframe.src !== url) iframe.src = url;
      iframe.hidden = false;
      imagePreview.dataset.empty = "false";
    } else {
      iframe.hidden = true;
      iframe.removeAttribute("src");
      imagePreview.dataset.empty = "true";
    }
    imagePreview.removeAttribute("data-bg");
    return;
  }

  iframe.hidden = true;
  iframe.removeAttribute("src");
  if (state.imageUrl) {
    if (img.src !== state.imageUrl) img.src = state.imageUrl;
    img.hidden = false;
    imagePreview.dataset.empty = "false";
    imagePreview.dataset.bg = bg;
    // Blurred background: show a sibling <img> sized to cover the canvas
    // with a heavy CSS blur. Same saturation as the foreground so the tint
    // matches.
    if (bgImg) {
      if (bg === "blurred") {
        if (bgImg.src !== state.imageUrl) bgImg.src = state.imageUrl;
        bgImg.style.filter = `blur(24px) saturate(${saturation * 1.1})`;
        bgImg.hidden = false;
      } else {
        bgImg.hidden = true;
        bgImg.removeAttribute("src");
      }
    }
    img.style.objectFit = scaleToObjectFit(scale);
    // For 90/270 the post-rotation bounding box is the canvas with axes
    // swapped; we scale by the smaller of (canvasW/canvasH) / (canvasH/canvasW)
    // so the rotated image stays inside the visible frame instead of
    // overflowing. Canvas is W=100% H=100% by definition; we use its actual
    // pixel size to compute the ratio.
    const canvas = document.getElementById("image-preview-canvas");
    let extra = "";
    if ((rotate === 90 || rotate === 270) && canvas) {
      const w = canvas.clientWidth || 1;
      const h = canvas.clientHeight || 1;
      const fit = Math.min(w / h, h / w);
      extra = ` scale(${fit})`;
    }
    img.style.transform = `rotate(${rotate}deg)${extra}`;
    img.style.filter = `saturate(${saturation})`;
  } else {
    img.hidden = true;
    img.removeAttribute("src");
    if (bgImg) { bgImg.hidden = true; bgImg.removeAttribute("src"); }
    imagePreview.dataset.empty = "true";
    imagePreview.removeAttribute("data-bg");
  }
}

function scaleToObjectFit(scale) {
  switch (scale) {
    case "fill":   return "cover";
    case "stretch":return "fill";
    case "center": return "none";
    default:       return "contain"; // "fit"
  }
}

// Dash-tab preview: render the selected dashboard via the existing /compose
// route in an iframe. This is the same renderer used for push, so the preview
// is WYSIWYG.
function selectDashboard(pageId) {
  state.selectedDashId = pageId;
  document.querySelectorAll("#dash-list .row").forEach((el) => {
    el.classList.toggle("selected", el.dataset.pageId === pageId);
  });
  const iframe = dashPreview.querySelector(".send-preview-iframe");
  if (pageId) {
    const url = `/compose/${encodeURIComponent(pageId)}`;
    if (iframe.src !== window.location.origin + url) iframe.src = url;
    iframe.hidden = false;
    dashPreview.dataset.empty = "false";
  } else {
    iframe.hidden = true;
    iframe.removeAttribute("src");
    dashPreview.dataset.empty = "true";
  }
  dashPushBtn.disabled = !pageId;
}

// ---------- Dash tab ----------------------------------------------------

async function loadDashboards() {
  const list = document.getElementById("dash-list");
  try {
    const r = await fetch("/api/pages");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const { pages } = await r.json();
    list.innerHTML = "";
    if (!pages.length) {
      list.innerHTML = `<li class="muted small">No saved dashboards yet.</li>`;
      selectDashboard(null);
      return;
    }
    for (const p of pages) {
      const li = document.createElement("li");
      li.className = "row";
      li.dataset.pageId = p.id;
      const icon = p.icon || "ph-frame-corners";
      li.innerHTML = `
        <i class="ph ${escapeHtml(icon)} row-icon" aria-hidden="true"></i>
        <div class="meta">
          <strong>${escapeHtml(p.name)}</strong>
          <span class="muted">${escapeHtml(p.layout)} · ${p.cells.length} cell${p.cells.length === 1 ? "" : "s"}${p.theme ? " · " + escapeHtml(p.theme) : ""}</span>
        </div>
        <span class="row-check" aria-hidden="true"></span>
      `;
      li.addEventListener("click", () => selectDashboard(p.id));
      list.appendChild(li);
    }
    // Auto-select the first dashboard so the preview isn't empty.
    if (!state.selectedDashId || !pages.some((p) => p.id === state.selectedDashId)) {
      selectDashboard(pages[0].id);
    } else {
      selectDashboard(state.selectedDashId);
    }
  } catch (err) {
    list.innerHTML = `<li class="muted small">Failed to load: ${err.message}</li>`;
    selectDashboard(null);
  }
}

function initDashPush() {
  dashPushBtn.addEventListener("click", () => {
    if (state.selectedDashId) pushDashboard(state.selectedDashId);
  });
}

async function pushDashboard(pageId) {
  setStatus("saving", `Pushing ${pageId}…`);
  dashPushBtn.disabled = true;
  try {
    const r = await fetch(`/api/push/${encodeURIComponent(pageId)}`, { method: "POST" });
    const body = await r.json().catch(() => ({}));
    if (r.status === 409) {
      setStatus("error", body.error || "A push is already in progress");
    } else if (!r.ok) {
      throw new Error(body.error || `HTTP ${r.status}`);
    } else {
      setStatus("saved", `Pushed ${pageId} · history #${body.history_id} · ${body.duration_s.toFixed(2)}s`);
    }
  } catch (err) {
    setStatus("error", `Push failed: ${err.message}`);
  } finally {
    dashPushBtn.disabled = !state.selectedDashId;
  }
}

// ---------- History tab -------------------------------------------------

function initHistoryControls() {
  document.getElementById("history-refresh").addEventListener("click", loadHistory);
  document.getElementById("history-clear").addEventListener("click", clearAllHistory);
}

async function loadHistory() {
  const list = document.getElementById("history-list");
  try {
    const r = await fetch("/api/history?limit=50");
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const { history } = await r.json();
    state.historyRows = history;
    renderHistory(history);
    document.getElementById("history-clear").disabled = !history.length;
    // Auto-preview the most recent successful push.
    const firstOk = history.find((h) => h.result === "ok");
    if (firstOk && (!state.selectedHistoryId || !history.some((h) => h.id === state.selectedHistoryId))) {
      selectHistoryRow(firstOk.id);
    } else if (state.selectedHistoryId) {
      selectHistoryRow(state.selectedHistoryId);
    } else {
      selectHistoryRow(null);
    }
  } catch (err) {
    list.innerHTML = `<li class="muted small">Failed to load: ${err.message}</li>`;
  }
}

function renderHistory(rows) {
  const list = document.getElementById("history-list");
  list.innerHTML = "";
  if (!rows.length) {
    list.innerHTML = `<li class="muted small">No pushes yet.</li>`;
    return;
  }
  for (const r of rows) {
    const li = document.createElement("li");
    li.className = "history-row" + (r.result === "error" ? " error" : "");
    li.dataset.historyId = String(r.id);
    if (state.selectedHistoryId === r.id) li.classList.add("selected");
    const localUrl = `/renders/${r.render_filename}`;
    const ts = formatTs(r.ts);
    const wp = r.wire_payload || {};
    const summary = wp.scale
      ? `${wp.scale} · ${wp.bg} · rotate ${wp.rotate}° · sat ${wp.saturation}`
      : (r.error || "(no wire payload)");
    const thumb = r.result === "ok"
      ? `<img src="${localUrl}" alt="" loading="lazy">`
      : `<span class="thumb-fallback">${r.result}</span>`;
    li.innerHTML = `
      <button type="button" class="thumb-btn" data-png="${localUrl}" ${r.result !== "ok" ? "disabled" : ""}>
        ${thumb}
      </button>
      <div class="history-meta">
        <div class="row-1">
          <strong>${r.source}</strong>
          <span class="muted small">#${r.id} · ${ts}</span>
        </div>
        <div class="row-2">${escapeHtml(summary)}</div>
      </div>
      <div class="history-actions">
        <button type="button" class="btn ghost" data-replay="${r.id}" ${r.result !== "ok" ? "disabled" : ""} title="Replay">
          <i class="ph ph-arrow-clockwise"></i> Replay
        </button>
        <button type="button" class="btn ghost row-delete" data-delete="${r.id}" title="Delete">
          <i class="ph ph-trash"></i>
        </button>
      </div>
    `;
    list.appendChild(li);
  }
  list.querySelectorAll("[data-replay]").forEach((b) => {
    if (b.disabled) return;
    b.addEventListener("click", (ev) => { ev.stopPropagation(); replay(parseInt(b.dataset.replay, 10)); });
  });
  list.querySelectorAll("[data-delete]").forEach((b) => {
    b.addEventListener("click", (ev) => { ev.stopPropagation(); deleteHistoryRow(parseInt(b.dataset.delete, 10)); });
  });
  list.querySelectorAll(".thumb-btn").forEach((b) => {
    if (b.disabled) return;
    b.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const id = parseInt(b.closest(".history-row").dataset.historyId, 10);
      selectHistoryRow(id);
    });
  });
  // Whole-row click also selects, except when the click came from a button
  // inside the row (replay / delete have their own handlers and stop
  // propagation; this is a belt-and-braces guard).
  list.querySelectorAll(".history-row").forEach((row) => {
    row.addEventListener("click", (ev) => {
      if (ev.target.closest("button")) return;
      const id = parseInt(row.dataset.historyId, 10);
      const r = state.historyRows.find((h) => h.id === id);
      if (!r || r.result !== "ok") return;
      selectHistoryRow(id);
    });
  });
}

function selectHistoryRow(historyId) {
  state.selectedHistoryId = historyId;
  document.querySelectorAll("#history-list .history-row").forEach((el) => {
    el.classList.toggle("selected", parseInt(el.dataset.historyId, 10) === historyId);
  });
  if (!historyPreview) return;
  const img = historyPreview.querySelector(".history-preview-img");
  const meta = document.getElementById("history-preview-meta");
  const row = state.historyRows.find((h) => h.id === historyId);
  if (!row || row.result !== "ok") {
    img.hidden = true;
    img.removeAttribute("src");
    historyPreview.dataset.empty = "true";
    if (meta) meta.textContent = row && row.result !== "ok" ? (row.error || "(failed push)") : "";
    return;
  }
  img.src = `/renders/${row.render_filename}`;
  img.hidden = false;
  historyPreview.dataset.empty = "false";
  if (meta) {
    const ts = formatTs(row.ts);
    const dur = row.duration_s ? `${row.duration_s.toFixed(2)}s` : "?";
    meta.textContent = `#${row.id} · ${row.source} · ${ts} · ${dur}`;
  }
}

async function deleteHistoryRow(historyId) {
  if (!confirm(`Delete history #${historyId}?`)) return;
  setStatus("saving", `Deleting #${historyId}…`);
  try {
    const r = await fetch(`/api/history/${historyId}`, { method: "DELETE" });
    if (!r.ok && r.status !== 204) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.error || `HTTP ${r.status}`);
    }
    setStatus("saved", `Deleted #${historyId}`);
    if (state.selectedHistoryId === historyId) state.selectedHistoryId = null;
    await loadHistory();
  } catch (err) {
    setStatus("error", `Delete failed: ${err.message}`);
  }
}

async function clearAllHistory() {
  if (!confirm("Delete all history? This cannot be undone.")) return;
  setStatus("saving", "Clearing history…");
  try {
    const r = await fetch("/api/history", { method: "DELETE" });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.error || `HTTP ${r.status}`);
    }
    const body = await r.json().catch(() => ({}));
    setStatus("saved", `Cleared ${body.deleted || 0} entries`);
    state.selectedHistoryId = null;
    await loadHistory();
  } catch (err) {
    setStatus("error", `Clear failed: ${err.message}`);
  }
}

async function replay(historyId) {
  setStatus("saving", `Replaying #${historyId}…`);
  try {
    const r = await fetch(`/api/replay/${historyId}`, { method: "POST" });
    const body = await r.json().catch(() => ({}));
    if (r.status === 410) { setStatus("error", body.error); return; }
    if (!r.ok) throw new Error(body.error || `HTTP ${r.status}`);
    setStatus("saved", `Replayed → history #${body.history_id}`);
    await loadHistory();
  } catch (err) {
    setStatus("error", `Replay failed: ${err.message}`);
  }
}

// ---------- helpers -----------------------------------------------------

function setStatus(kind, msg) {
  window.inkyStatus(kind, msg);
}

function formatBytes(n) {
  if (n < 1024) return `${n}B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)}KB`;
  return `${(n / 1024 / 1024).toFixed(2)}MB`;
}

function formatTs(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
  }[c]));
}
