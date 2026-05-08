import { LitElement, html, css } from "lit";

export class IdTabBar extends LitElement {
  static properties = {
    tabs: { type: Array },
    selected: { type: String, reflect: true },
  };

  static styles = css`
    :host {
      display: block;
    }
    .bar {
      display: flex;
      gap: 4px;
      border-bottom: 1px solid var(--id-divider, #c8b89b);
      overflow-x: auto;
      /* Hide the persistent macOS-style scrollbar; tabs still scroll if they
         overflow. */
      scrollbar-width: none;
    }
    .bar::-webkit-scrollbar {
      display: none;
    }
    button {
      min-height: 44px;
      padding: 0 16px;
      border: 0;
      background: transparent;
      color: var(--id-fg-soft, #5a4f44);
      font: inherit;
      font-weight: 500;
      cursor: pointer;
      border-bottom: 2px solid transparent;
      margin-bottom: -1px;
      white-space: nowrap;
    }
    button[aria-selected="true"] {
      color: var(--id-accent, #d97757);
      border-bottom-color: var(--id-accent, #d97757);
    }
    button:hover:not([aria-selected="true"]) {
      color: var(--id-fg, #1a1612);
    }
  `;

  constructor() {
    super();
    this.tabs = [];
    this.selected = "";
  }

  _select(id) {
    this.selected = id;
    this.dispatchEvent(
      new CustomEvent("change", {
        detail: { selected: id },
        bubbles: true,
        composed: true,
      })
    );
  }

  render() {
    return html`<div class="bar" role="tablist">
      ${this.tabs.map(
        (tab) => html`
          <button
            role="tab"
            aria-selected=${this.selected === tab.id ? "true" : "false"}
            @click=${() => this._select(tab.id)}
          >
            ${tab.label}
          </button>
        `
      )}
    </div>`;
  }
}

customElements.define("id-tab-bar", IdTabBar);
