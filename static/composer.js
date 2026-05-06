// Composer runtime. Same DOM is loaded by the editor's preview iframe AND by
// Playwright at push time — that's the architectural payoff: WYSIWYG push.
//
// Reads <script id="page-config"> for the page model, lays out cells from
// fractional rects, dynamic-imports each widget plugin's client.js inside a
// shadow root, and signals window.__inkyReady once all cells settle.

(async () => {
  const config = JSON.parse(document.getElementById("page-config").textContent);
  const panel = document.getElementById("panel");
  const params = new URLSearchParams(location.search);
  const isPreview = params.get("preview") === "1";
  const isPush = params.get("for_push") === "1";

  const [W, H] = config.panel;
  panel.style.width = W + "px";
  panel.style.height = H + "px";
  panel.style.background = config.bg_color;

  // Single-cell pages render edge-to-edge — gap/radius/header ignored per brief.
  const isSingle = config.single_cell;
  const gap = isSingle ? 0 : config.cell_gap;
  const half = gap / 2;
  const innerRadius = isSingle ? 0 : config.cell_radius;

  // ---- header strip (multi-cell only) -----------------------------------
  let cellsTop = half;
  if (config.header_height > 0 && !isSingle) {
    const hdr = document.createElement("header");
    hdr.className = "panel-header";
    applyTheme(hdr, config.header_theme);
    hdr.style.left = gap + "px";
    hdr.style.top = gap + "px";
    hdr.style.width = (W - 2 * gap) + "px";
    hdr.style.height = config.header_height + "px";
    hdr.style.borderRadius = config.cell_radius + "px";
    hdr.innerHTML = [
      config.icon ? `<i class="icon ph ph-${escapeHtml(config.icon)}" aria-hidden="true"></i>` : "",
      `<h1>${escapeHtml(config.name || "")}</h1>`,
      `<time>${formatTime(new Date())}</time>`,
    ].filter(Boolean).join("");
    panel.appendChild(hdr);
    // Cells area top: header bottom + a full `gap` of breathing room.
    cellsTop = gap + config.header_height + half;
  }

  // ---- cells container (panel inset by half on all sides) ---------------
  // Half-margin trick: each cell's pixel rect is inset by `half` on every side.
  // Cells touching the area edge get half + half = gap from the panel edge;
  // adjacent cells get half + half = gap between them.
  const areaX = half;
  const areaY = cellsTop;
  const areaW = W - gap;
  const areaH = H - half - areaY;

  // ---- per-cell init -----------------------------------------------------
  const renderPromises = config.cells.map((cell) =>
    initCell(cell).catch((err) => {
      console.error(`[composer] cell ${cell.index} failed:`, err);
      return null;
    })
  );

  // Wait for every cell to settle, then double-rAF to flush layout/paint
  // before signalling readiness.
  await Promise.all(renderPromises);
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  window.__inkyReady = true;

  // ====== helpers ========================================================

  async function initCell(cell) {
    const [fx, fy, fw, fh] = cell.rect;
    let cellX, cellY, cellW, cellH;
    if (isSingle) {
      cellX = 0; cellY = 0; cellW = W; cellH = H;
    } else {
      // Fractional rect mapped into the cells area, then half-margin inset
      // on all sides so neighbour cells end up `gap` apart and outermost
      // cells end up `gap` from the panel edge.
      cellX = areaX + fx * areaW + half;
      cellY = areaY + fy * areaH + half;
      cellW = fw * areaW - gap;
      cellH = fh * areaH - gap;
    }

    const wrapper = document.createElement("div");
    wrapper.className = "cell";
    wrapper.dataset.widget = cell.widget_id;
    wrapper.dataset.index = String(cell.index);
    wrapper.style.left = cellX + "px";
    wrapper.style.top = cellY + "px";
    wrapper.style.width = cellW + "px";
    wrapper.style.height = cellH + "px";
    wrapper.style.borderRadius = innerRadius + "px";
    applyTheme(wrapper, cell.theme);
    panel.appendChild(wrapper);

    if (cell.missing) {
      wrapper.classList.add("placeholder");
      wrapper.dataset.message = `Missing widget: ${cell.widget_id}`;
      return null;
    }
    if (!cell.is_widget) {
      wrapper.classList.add("placeholder");
      wrapper.dataset.message = `Not a widget: ${cell.widget_id}`;
      return null;
    }
    if (!cell.enabled) {
      wrapper.classList.add("placeholder");
      wrapper.dataset.message = `Disabled: ${cell.widget_id}`;
      return null;
    }

    // Fetch per-cell data
    const url = `${config.data_url_base}/${cell.index}${isPreview ? "?preview=1" : ""}`;
    let payload;
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      payload = await res.json();
    } catch (err) {
      wrapper.classList.add("error");
      wrapper.dataset.message = `Fetch failed: ${err.message}`;
      return null;
    }
    if (payload.error) {
      wrapper.classList.add("error");
      wrapper.dataset.message = payload.error;
      return null;
    }

    // Shadow root + content area (inner padding scales with radius)
    const shadow = wrapper.attachShadow({ mode: "open" });
    if (cell.client_css_url) {
      const link = document.createElement("link");
      link.rel = "stylesheet";
      link.href = cell.client_css_url;
      shadow.appendChild(link);
    }
    const baseStyle = document.createElement("style");
    baseStyle.textContent = `
      :host { display: block; width: 100%; height: 100%; }
      .content {
        width: 100%; height: 100%;
        padding: ${innerRadius}px;
        box-sizing: border-box;
        overflow: hidden;
      }
    `;
    shadow.appendChild(baseStyle);
    const content = document.createElement("div");
    content.className = "content";
    shadow.appendChild(content);

    if (!cell.client_js_url) {
      content.innerHTML = `<pre style="margin:0;font-size:11px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;">${escapeHtml(JSON.stringify(payload.data, null, 2))}</pre>`;
      return null;
    }

    // Dynamic import + render
    const renderArea = {
      width: cellW - 2 * innerRadius,
      height: cellH - 2 * innerRadius,
    };
    try {
      const mod = await import(cell.client_js_url);
      if (typeof mod.default !== "function") {
        throw new Error("plugin client.js: no default export");
      }
      const cleanup = await mod.default(content, {
        data: payload.data,
        theme: payload.theme,
        options: payload.options,
        width: renderArea.width,
        height: renderArea.height,
        compact: !!payload.options?.compact,
        preview: isPreview,
        for_push: isPush,
        // Multi-cell pages render a page-level header with the page name +
        // clock. Widgets check this and suppress their own clock so the
        // chrome doesn't double up.
        has_page_header: !isSingle,
        signal: new AbortController().signal,
      });
      return typeof cleanup === "function" ? cleanup : null;
    } catch (err) {
      console.error(`[composer] cell ${cell.index} render error:`, err);
      content.innerHTML = "";
      wrapper.classList.add("error");
      wrapper.dataset.message = `${err.name}: ${err.message}`;
      return null;
    }
  }

  function applyTheme(el, palette) {
    if (!palette) return;
    for (const [k, v] of Object.entries(palette)) {
      el.style.setProperty(`--theme-${k}`, v);
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;",
    }[c]));
  }

  function formatTime(d) {
    const h = String(d.getHours()).padStart(2, "0");
    const m = String(d.getMinutes()).padStart(2, "0");
    return `${h}:${m}`;
  }
})();
