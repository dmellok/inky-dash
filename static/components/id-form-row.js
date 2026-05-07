import { LitElement, html, css } from "lit";

export class IdFormRow extends LitElement {
  static properties = {
    label: { type: String },
    hint: { type: String },
    forId: { type: String, attribute: "for-id" },
  };

  static styles = css`
    :host {
      display: block;
    }
    .row {
      display: grid;
      grid-template-columns: 1fr;
      gap: 6px;
      padding: 12px 0;
      border-bottom: 1px solid var(--id-divider, #c8b89b);
    }
    @media (min-width: 700px) {
      .row {
        grid-template-columns: 220px 1fr;
        gap: 16px;
        align-items: center;
      }
    }
    label {
      font-size: 14px;
      font-weight: 500;
      color: var(--id-fg, #1a1612);
    }
    .hint {
      display: block;
      font-size: 12px;
      color: var(--id-fg-soft, #5a4f44);
      margin-top: 2px;
    }
    .control {
      min-width: 0;
    }
  `;

  render() {
    return html`<div class="row">
      <div>
        <label for=${this.forId || ""}>${this.label}</label>
        ${this.hint ? html`<span class="hint">${this.hint}</span>` : null}
      </div>
      <div class="control">
        <slot></slot>
      </div>
    </div>`;
  }
}

customElements.define("id-form-row", IdFormRow);
