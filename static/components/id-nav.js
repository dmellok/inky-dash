import { LitElement, html, css } from "lit";

const LINKS = [
  { href: "/", id: "home", label: "Home", icon: "ph-house" },
  { href: "/send", id: "send", label: "Send", icon: "ph-paper-plane" },
  { href: "/editor", id: "editor", label: "Dashboards", icon: "ph-cube" },
  { href: "/schedules", id: "schedules", label: "Schedules", icon: "ph-clock-clockwise" },
  { href: "/themes", id: "themes", label: "Themes", icon: "ph-palette" },
  { href: "/settings", id: "settings", label: "Settings", icon: "ph-gear" },
];

const NARROW_BP = 720;

export class IdNav extends LitElement {
  static properties = {
    current: { type: String },
    open: { state: true },
    pluginsOpen: { state: true },
    adminPages: { state: true },
    isDark: { state: true },
  };

  static styles = css`
    :host {
      display: block;
      border-bottom: 1px solid var(--id-divider, #c8b89b);
      background: var(--id-surface, #ffffff);
      position: sticky;
      top: 0;
      z-index: 10;
    }
    nav {
      max-width: 1200px;
      margin: 0 auto;
      padding: 0 16px;
      display: flex;
      align-items: center;
      gap: 16px;
    }
    .brand {
      font-weight: 700;
      font-size: 16px;
      color: var(--id-fg, #1a1612);
      text-decoration: none;
      padding: 14px 0;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      white-space: nowrap;
    }
    .brand .ph {
      color: var(--id-accent, #d97757);
      font-size: 20px;
    }
    .spacer { flex: 1; }
    .links {
      display: flex;
      gap: 2px;
      align-items: stretch;
    }
    a.link, button.link {
      padding: 14px 10px;
      color: var(--id-fg-soft, #5a4f44);
      text-decoration: none;
      font-size: 14px;
      line-height: 1;
      font-weight: 500;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 0;
      border-bottom: 2px solid transparent;
      margin-bottom: -1px;
      white-space: nowrap;
      background: transparent;
      cursor: pointer;
      font-family: inherit;
      box-sizing: border-box;
    }
    a.link:hover, button.link:hover {
      color: var(--id-fg, #1a1612);
    }
    a.link[data-current="true"], button.link[data-current="true"] {
      color: var(--id-accent, #d97757);
      border-bottom-color: var(--id-accent, #d97757);
    }
    /* Normalise icon glyph metrics — Phosphor's vertical centre varies a hair
       per glyph, so explicit size + line-height keeps the baseline stable. */
    a.link .ph, button.link .ph {
      font-size: 16px;
      line-height: 1;
      display: inline-block;
    }
    button.link .caret {
      font-size: 11px;
      transition: transform 150ms ease;
    }
    button.link[aria-expanded="true"] .caret {
      transform: rotate(180deg);
    }

    .dropdown {
      position: relative;
    }
    .dropdown-panel {
      position: absolute;
      top: calc(100% + 1px);
      left: 0;
      min-width: 200px;
      background: var(--id-surface, #ffffff);
      border: 1px solid var(--id-divider, #c8b89b);
      border-radius: 8px;
      box-shadow: 0 8px 20px rgba(0, 0, 0, 0.12);
      padding: 6px;
      z-index: 20;
      display: grid;
      gap: 2px;
    }
    .dropdown-item {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 10px;
      color: var(--id-fg, #1a1612);
      text-decoration: none;
      border-radius: 5px;
      font-size: 14px;
      white-space: nowrap;
    }
    .dropdown-item:hover {
      background: var(--id-surface2, #f5e8d8);
    }
    .dropdown-item .ph {
      color: var(--id-fg-soft, #5a4f44);
      font-size: 16px;
    }

    .hamburger,
    .theme-toggle {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 40px;
      height: 40px;
      border: 0;
      background: transparent;
      color: var(--id-fg, #1a1612);
      cursor: pointer;
      font-size: 18px;
      padding: 0;
      border-radius: 8px;
      transition: background 100ms ease, color 100ms ease;
    }
    .hamburger {
      display: none;
      width: 44px;
      height: 44px;
      font-size: 22px;
      border-radius: 6px;
    }
    .hamburger:hover,
    .theme-toggle:hover {
      background: var(--id-surface2, #f5e8d8);
      color: var(--id-accent, #d97757);
    }

    .backdrop {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.35);
      opacity: 0;
      pointer-events: none;
      transition: opacity 200ms ease;
      z-index: 99;
    }
    .backdrop.open {
      opacity: 1;
      pointer-events: auto;
    }

    aside.drawer {
      position: fixed;
      top: 0;
      right: 0;
      bottom: 0;
      width: min(300px, 86vw);
      background: var(--id-surface, #ffffff);
      box-shadow: -8px 0 24px rgba(0, 0, 0, 0.15);
      transform: translateX(100%);
      transition: transform 240ms cubic-bezier(0.2, 0.8, 0.3, 1);
      z-index: 100;
      display: flex;
      flex-direction: column;
    }
    aside.drawer.open {
      transform: translateX(0);
    }
    .drawer-head {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      border-bottom: 1px solid var(--id-divider, #c8b89b);
    }
    .drawer-head strong {
      font-size: 16px;
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .drawer-head strong .ph {
      color: var(--id-accent, #d97757);
      font-size: 20px;
    }
    .drawer-links {
      padding: 8px 0;
      overflow-y: auto;
      flex: 1;
    }
    a.drawer-link {
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 14px 16px;
      color: var(--id-fg, #1a1612);
      text-decoration: none;
      font-size: 15px;
      font-weight: 500;
      border-left: 3px solid transparent;
    }
    a.drawer-link:hover {
      background: var(--id-surface2, #f5e8d8);
    }
    a.drawer-link[data-current="true"] {
      color: var(--id-accent, #d97757);
      background: var(--id-surface2, #f5e8d8);
      border-left-color: var(--id-accent, #d97757);
    }
    a.drawer-link.nested {
      padding-left: 32px;
      font-size: 14px;
      font-weight: 400;
      color: var(--id-fg-soft, #5a4f44);
    }
    a.drawer-link.nested:hover {
      color: var(--id-fg, #1a1612);
    }
    a.drawer-link .ph {
      font-size: 20px;
      color: var(--id-fg-soft, #5a4f44);
    }
    a.drawer-link[data-current="true"] .ph {
      color: var(--id-accent, #d97757);
    }
    .drawer-section {
      padding: 16px 16px 6px;
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--id-fg-soft, #5a4f44);
      border-top: 1px solid var(--id-divider, #c8b89b);
      margin-top: 8px;
    }

    @media (max-width: ${NARROW_BP}px) {
      .links {
        display: none;
      }
      .hamburger {
        display: inline-flex;
      }
    }
  `;

  constructor() {
    super();
    this.current = "";
    this.open = false;
    this.pluginsOpen = false;
    this.adminPages = [];
    this.isDark = document.documentElement.dataset.theme === "dark";
    this._onKeydown = this._onKeydown.bind(this);
    this._onDocClick = this._onDocClick.bind(this);
    this._onThemeChange = this._onThemeChange.bind(this);
  }

  async connectedCallback() {
    super.connectedCallback();
    document.addEventListener("keydown", this._onKeydown);
    document.addEventListener("click", this._onDocClick);
    // Sync if some other tab toggled the theme via storage event, or if
    // another component flips data-theme directly.
    window.addEventListener("storage", this._onThemeChange);
    this._mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    this._mediaQuery.addEventListener?.("change", this._onThemeChange);
    try {
      const res = await fetch("/api/plugins/admin-pages");
      this.adminPages = await res.json();
    } catch {
      this.adminPages = [];
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    document.removeEventListener("keydown", this._onKeydown);
    document.removeEventListener("click", this._onDocClick);
    window.removeEventListener("storage", this._onThemeChange);
    this._mediaQuery?.removeEventListener?.("change", this._onThemeChange);
  }

  _onThemeChange() {
    this.isDark = document.documentElement.dataset.theme === "dark";
  }

  _toggleTheme() {
    // Cycle: any current state → opposite. Persist explicitly (so picking
    // dark on a system that's set to light overrides "auto").
    const next = this.isDark ? "light" : "dark";
    try {
      localStorage.setItem("inky_theme", next);
    } catch {
      /* ignore */
    }
    if (next === "dark") {
      document.documentElement.dataset.theme = "dark";
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
    this.isDark = next === "dark";
    // Best-effort cross-device persistence (settings page is the canonical
    // sync surface; this is a convenience).
    fetch("/api/app/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ appearance: { theme: next } }),
    }).catch(() => {});
  }

  _onKeydown(event) {
    if (event.key === "Escape") {
      if (this.open) this.open = false;
      if (this.pluginsOpen) this.pluginsOpen = false;
    }
  }

  _onDocClick(event) {
    // Close the dropdown when clicking outside the nav element entirely.
    // (Clicks inside the shadow root use stopPropagation on the trigger.)
    if (!this.pluginsOpen) return;
    const path = event.composedPath();
    if (!path.includes(this)) {
      this.pluginsOpen = false;
    }
  }

  _toggleDrawer() {
    this.open = !this.open;
  }

  _closeDrawer() {
    this.open = false;
  }

  _togglePlugins(event) {
    event.stopPropagation();
    this.pluginsOpen = !this.pluginsOpen;
  }

  render() {
    const hasPlugins = this.adminPages.length > 0;
    return html`
      <link rel="stylesheet" href="/static/icons/phosphor.css">
      <nav>
        <a href="/" class="brand">
          <i class="ph ph-monitor-play"></i>Inky Dash
        </a>
        <div class="links">
          ${LINKS.filter((l) => l.id !== "home" && l.id !== "settings").map(
            (l) => html`
              <a
                href=${l.href}
                class="link"
                data-current=${this.current === l.id ? "true" : "false"}
              >
                <i class="ph ${l.icon}"></i>
                <span>${l.label}</span>
              </a>
            `
          )}
          ${hasPlugins
            ? html`
                <div class="dropdown">
                  <button
                    class="link"
                    aria-haspopup="true"
                    aria-expanded=${this.pluginsOpen ? "true" : "false"}
                    @click=${this._togglePlugins}
                  >
                    <i class="ph ph-puzzle-piece"></i>
                    <span>Plugins</span>
                    <i class="ph ph-caret-down caret"></i>
                  </button>
                  ${this.pluginsOpen
                    ? html`
                        <div class="dropdown-panel" role="menu">
                          ${this.adminPages.map(
                            (p) => html`
                              <a href=${p.url} class="dropdown-item" role="menuitem">
                                <i class="ph ${p.icon || "ph-puzzle-piece"}"></i>
                                <span>${p.name}</span>
                              </a>
                            `
                          )}
                        </div>
                      `
                    : null}
                </div>
              `
            : null}
          ${LINKS.filter((l) => l.id === "settings").map(
            (l) => html`
              <a
                href=${l.href}
                class="link"
                data-current=${this.current === l.id ? "true" : "false"}
              >
                <i class="ph ${l.icon}"></i>
                <span>${l.label}</span>
              </a>
            `
          )}
        </div>
        <span class="spacer"></span>
        <button
          class="theme-toggle"
          @click=${this._toggleTheme}
          aria-label=${this.isDark ? "Switch to light mode" : "Switch to dark mode"}
          title=${this.isDark ? "Switch to light mode" : "Switch to dark mode"}
        >
          <i class="ph ${this.isDark ? "ph-sun" : "ph-moon"}"></i>
        </button>
        <button
          class="hamburger"
          @click=${this._toggleDrawer}
          aria-label="Open menu"
          aria-expanded=${this.open ? "true" : "false"}
        >
          <i class="ph ${this.open ? "ph-x" : "ph-list"}"></i>
        </button>
      </nav>

      <div
        class="backdrop ${this.open ? "open" : ""}"
        @click=${this._closeDrawer}
      ></div>
      <aside
        class="drawer ${this.open ? "open" : ""}"
        aria-hidden=${this.open ? "false" : "true"}
      >
        <div class="drawer-head">
          <strong>
            <i class="ph ph-monitor-play"></i> Inky Dash
          </strong>
          <button class="hamburger" @click=${this._closeDrawer} aria-label="Close menu" style="display: inline-flex;">
            <i class="ph ph-x"></i>
          </button>
        </div>
        <div class="drawer-links">
          ${LINKS.filter((l) => l.id !== "settings").map(
            (l) => html`
              <a
                href=${l.href}
                class="drawer-link"
                data-current=${this.current === l.id ? "true" : "false"}
                @click=${this._closeDrawer}
              >
                <i class="ph ${l.icon}"></i>
                <span>${l.label}</span>
              </a>
            `
          )}
          ${hasPlugins
            ? html`
                <div class="drawer-section">Plugins</div>
                ${this.adminPages.map(
                  (p) => html`
                    <a
                      href=${p.url}
                      class="drawer-link nested"
                      @click=${this._closeDrawer}
                    >
                      <i class="ph ${p.icon || "ph-puzzle-piece"}"></i>
                      <span>${p.name}</span>
                    </a>
                  `
                )}
              `
            : null}
          ${LINKS.filter((l) => l.id === "settings").map(
            (l) => html`
              <a
                href=${l.href}
                class="drawer-link"
                data-current=${this.current === l.id ? "true" : "false"}
                @click=${this._closeDrawer}
              >
                <i class="ph ${l.icon}"></i>
                <span>${l.label}</span>
              </a>
            `
          )}
        </div>
      </aside>
    `;
  }
}

customElements.define("id-nav", IdNav);
