import { LitElement, html, css } from "lit";

export class IdButton extends LitElement {
  static properties = {
    variant: { type: String, reflect: true },
    disabled: { type: Boolean, reflect: true },
    type: { type: String },
  };

  static styles = css`
    :host {
      display: inline-block;
    }
    button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      min-height: 44px;
      padding: 0 18px;
      border-radius: 8px;
      border: 1px solid var(--id-divider, #c8b89b);
      background: var(--id-surface, #ffffff);
      color: var(--id-fg, #1a1612);
      font: inherit;
      font-weight: 500;
      cursor: pointer;
      transition: transform 80ms ease, background 120ms ease;
    }
    button:hover:not([disabled]) {
      background: var(--id-surface2, #f5e8d8);
    }
    button:active:not([disabled]) {
      transform: scale(0.98);
    }
    button[disabled] {
      opacity: 0.5;
      cursor: not-allowed;
    }
    :host([variant="primary"]) button {
      background: var(--id-accent, #d97757);
      border-color: transparent;
      color: #ffffff;
    }
    :host([variant="primary"]) button:hover:not([disabled]) {
      background: var(--id-accent-soft, #aa5a3f);
    }
    :host([variant="danger"]) button {
      border-color: var(--id-danger, #c97c70);
      color: var(--id-danger, #c97c70);
    }
  `;

  constructor() {
    super();
    this.variant = "default";
    this.disabled = false;
    this.type = "button";
  }

  render() {
    return html`<button type=${this.type} ?disabled=${this.disabled}>
      <slot></slot>
    </button>`;
  }
}

customElements.define("id-button", IdButton);
