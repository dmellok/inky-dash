import { LitElement, html, css } from "lit";

export class IdCard extends LitElement {
  static properties = {
    heading: { type: String },
    subheading: { type: String },
  };

  static styles = css`
    :host {
      display: block;
      margin-bottom: 16px;
    }
    :host(:last-child) {
      margin-bottom: 0;
    }
    .card {
      background: var(--id-surface, #ffffff);
      color: var(--id-fg, #0f172a);
      border: 1px solid var(--id-divider, #e2e8f0);
      border-radius: 12px;
      padding: 16px;
      box-shadow: var(--id-shadow-sm, 0 1px 2px rgb(15 23 42 / 0.06));
    }
    .header {
      margin-bottom: 12px;
    }
    .header:empty {
      display: none;
    }
    h3 {
      margin: 0;
      font-size: 16px;
      font-weight: 600;
      color: var(--id-fg, #1a1612);
    }
    p {
      margin: 4px 0 0;
      font-size: 13px;
      color: var(--id-fg-soft, #5a4f44);
    }
    ::slotted([slot="footer"]) {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
      margin-top: 16px;
      padding-top: 12px;
      border-top: 1px solid var(--id-divider, #c8b89b);
    }
  `;

  render() {
    return html`<div class="card">
      <div class="header">
        ${this.heading ? html`<h3>${this.heading}</h3>` : null}
        ${this.subheading ? html`<p>${this.subheading}</p>` : null}
      </div>
      <slot></slot>
      <slot name="footer"></slot>
    </div>`;
  }
}

customElements.define("id-card", IdCard);
