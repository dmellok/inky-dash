(function () {
  // ---- Compact-mode nav drawer ----------------------------------------
  // The CSS handles layout; this only toggles the [data-nav-open] flag on
  // <body> and wires close-on-scrim / close-on-link / close-on-Escape.
  const navToggle = document.getElementById("nav-toggle");
  const navClose = document.getElementById("nav-close");
  const navScrim = document.getElementById("nav-scrim");
  const navEl = document.getElementById("app-nav");
  if (navToggle && navScrim && navEl) {
    const setOpen = (open) => {
      document.body.toggleAttribute("data-nav-open", open);
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
      navScrim.hidden = !open;
    };
    navToggle.addEventListener("click", () => {
      setOpen(!document.body.hasAttribute("data-nav-open"));
    });
    if (navClose) navClose.addEventListener("click", () => setOpen(false));
    navScrim.addEventListener("click", () => setOpen(false));
    // Clicking a nav link closes the drawer (theme toggle is a button, leave open).
    navEl.addEventListener("click", (ev) => {
      if (ev.target.closest("a")) setOpen(false);
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && document.body.hasAttribute("data-nav-open")) {
        setOpen(false);
        navToggle.focus();
      }
    });
  }

  // ---- Global flash status (footer-left, fade in/out) -----------------
  // Any page-level setStatus(state, msg) routes through here so the chrome
  // owns the lifecycle: opacity transition for fade, auto-clear timer for
  // transient states. setStatus("", "") clears immediately.
  const flash = document.getElementById("app-flash");
  let flashTimer = null;
  // Default linger durations per state. "saving"/"restarting" stay pinned
  // (caller is expected to follow up with a terminal state).
  const FLASH_LINGER = { saved: 3000, error: 6000 };

  window.inkyStatus = function (state, msg, opts) {
    if (!flash) return;
    if (flashTimer) { clearTimeout(flashTimer); flashTimer = null; }
    flash.classList.remove("flash-leaving");
    if (!state) {
      // Fade out then clear text once invisible (~200ms transition).
      flash.classList.add("flash-leaving");
      flashTimer = setTimeout(() => {
        flash.classList.remove("flash-leaving");
        flash.dataset.state = "";
        flash.textContent = "";
      }, 220);
      return;
    }
    flash.dataset.state = state;
    flash.textContent = msg || "";
    const linger = (opts && Number.isFinite(opts.linger))
      ? opts.linger
      : (FLASH_LINGER[state] || 0);
    if (linger > 0) {
      flashTimer = setTimeout(() => window.inkyStatus("", ""), linger);
    }
  };

  // ---- Listener pill (header) -----------------------------------------
  const pill = document.getElementById("status-pill");
  const dump = document.getElementById("status-json");

  function pillState(s) {
    if (!s.online) return "offline";
    if (s.stale) return "stale";
    if (s.state === "rendering") return "rendering";
    return "online";
  }

  function pillLabel(state, s) {
    if (state === "offline") return "Listener offline";
    if (state === "stale") return "Listener stale";
    if (state === "rendering") return "Rendering…";
    return s.state ? `Online · ${s.state}` : "Online";
  }

  async function tick() {
    try {
      const r = await fetch("/api/status", { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const s = await r.json();
      if (pill) {
        const state = pillState(s);
        pill.dataset.state = state;
        pill.textContent = pillLabel(state, s);
      }
      if (dump) dump.textContent = JSON.stringify(s, null, 2);
    } catch (e) {
      if (pill) {
        pill.dataset.state = "offline";
        pill.textContent = "API error";
      }
      if (dump) dump.textContent = String(e);
    }
  }

  tick();
  setInterval(tick, 5000);
})();
