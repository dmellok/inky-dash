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
      min-height: var(--id-control-h, 40px);
      padding: 0 16px;
      border-radius: var(--id-radius, 8px);
      border: 1px solid var(--id-divider, #c8b89b);
      background: var(--id-surface, #ffffff);
      color: var(--id-fg, #1a1612);
      font: inherit;
      font-weight: 500;
      cursor: pointer;
      white-space: nowrap;
      transition: transform 80ms ease, background 120ms ease, border-color 120ms ease;
    }
    button:hover:not([disabled]) {
      background: var(--id-surface2, #f5e8d8);
      border-color: var(--id-fg-soft, #5a4f44);
    }
    button:active:not([disabled]) {
      transform: scale(0.98);
    }
    button[disabled] {
      opacity: 0.5;
      cursor: not-allowed;
    }
    :host([variant="primary"]) button {
      background: var(--id-accent, #4f46e5);
      border-color: transparent;
      color: var(--id-accent-fg, #ffffff);
    }
    :host([variant="primary"]) button:hover:not([disabled]) {
      background: var(--id-accent-soft, #4338ca);
    }
    :host([variant="danger"]) button {
      border-color: var(--id-danger, #dc2626);
      color: var(--id-danger, #dc2626);
    }
    :host([variant="danger"]) button:hover:not([disabled]) {
      background: color-mix(in srgb, var(--id-danger, #dc2626) 10%, transparent);
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
