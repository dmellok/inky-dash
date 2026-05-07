import { LitElement, html, css } from "lit";

export class IdSlider extends LitElement {
  static properties = {
    label: { type: String },
    value: { type: Number },
    min: { type: Number },
    max: { type: Number },
    step: { type: Number },
    suffix: { type: String },
  };

  static styles = css`
    :host {
      display: block;
    }
    .row {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 6px;
      color: var(--id-fg, #1a1612);
    }
    label {
      font-size: 13px;
      font-weight: 500;
    }
    .value {
      font-variant-numeric: tabular-nums;
      color: var(--id-fg-soft, #5a4f44);
      font-size: 13px;
    }
    input[type="range"] {
      -webkit-appearance: none;
      appearance: none;
      width: 100%;
      height: 24px;
      background: transparent;
      cursor: pointer;
    }
    input[type="range"]::-webkit-slider-runnable-track {
      height: 4px;
      border-radius: 2px;
      background: var(--id-divider, #c8b89b);
    }
    input[type="range"]::-webkit-slider-thumb {
      -webkit-appearance: none;
      appearance: none;
      width: 22px;
      height: 22px;
      border-radius: 50%;
      background: var(--id-accent, #d97757);
      margin-top: -9px;
      border: 2px solid var(--id-bg, #ffffff);
      box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
    }
  `;

  constructor() {
    super();
    this.value = 0;
    this.min = 0;
    this.max = 100;
    this.step = 1;
    this.suffix = "";
  }

  _onInput(e) {
    this.value = Number(e.target.value);
    this.dispatchEvent(
      new CustomEvent("change", {
        detail: { value: this.value },
        bubbles: true,
        composed: true,
      })
    );
  }

  render() {
    return html`
      <div class="row">
        <label>${this.label}</label>
        <span class="value">${this.value}${this.suffix}</span>
      </div>
      <input
        type="range"
        min=${this.min}
        max=${this.max}
        step=${this.step}
        .value=${String(this.value)}
        @input=${this._onInput}
      />
    `;
  }
}

customElements.define("id-slider", IdSlider);
