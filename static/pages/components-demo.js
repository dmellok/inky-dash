import { LitElement, html, css } from "lit";
import "../components/index.js";

class ComponentsDemo extends LitElement {
  static properties = {
    sliderValue: { state: true },
    selectedTab: { state: true },
  };

  static styles = css`
    :host {
      display: block;
      max-width: 760px;
      margin: 0 auto;
      padding: 24px 16px;
      font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
    }
    h1 {
      margin: 0 0 4px;
      font-size: 22px;
    }
    p.lede {
      margin: 0 0 24px;
      color: var(--id-fg-soft, #5a4f44);
    }
    section {
      margin-bottom: 28px;
    }
    h2 {
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--id-fg-soft, #5a4f44);
      margin: 0 0 8px;
    }
    .row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
  `;

  constructor() {
    super();
    this.sliderValue = 50;
    this.selectedTab = "all";
  }

  render() {
    return html`
      <h1>Design system</h1>
      <p class="lede">Every admin page builds on these. One example each.</p>

      <section>
        <h2>id-button</h2>
        <div class="row">
          <id-button>Default</id-button>
          <id-button variant="primary">Primary</id-button>
          <id-button variant="danger">Danger</id-button>
          <id-button disabled>Disabled</id-button>
        </div>
      </section>

      <section>
        <h2>id-tab-bar</h2>
        <id-tab-bar
          .tabs=${[
            { id: "all", label: "All" },
            { id: "widgets", label: "Widgets" },
            { id: "themes", label: "Themes" },
            { id: "fonts", label: "Fonts" },
          ]}
          selected=${this.selectedTab}
          @change=${(e) => (this.selectedTab = e.detail.selected)}
        ></id-tab-bar>
      </section>

      <section>
        <h2>id-card</h2>
        <id-card heading="A card" subheading="With a heading and a footer slot">
          <p>Cards are the default container for grouped content.</p>
          <div slot="footer">
            <id-button>Cancel</id-button>
            <id-button variant="primary">Save</id-button>
          </div>
        </id-card>
      </section>

      <section>
        <h2>id-slider</h2>
        <id-card>
          <id-slider
            label="Saturation"
            min="0"
            max="100"
            value=${this.sliderValue}
            suffix="%"
            @change=${(e) => (this.sliderValue = e.detail.value)}
          ></id-slider>
        </id-card>
      </section>

      <section>
        <h2>id-form-row</h2>
        <id-card>
          <id-form-row label="Page name" hint="Shown in the editor list.">
            <input type="text" value="Demo" style="width: 100%; padding: 10px; box-sizing: border-box;" />
          </id-form-row>
          <id-form-row label="Theme">
            <select style="padding: 10px;"><option>default</option></select>
          </id-form-row>
        </id-card>
      </section>
    `;
  }
}

customElements.define("components-demo", ComponentsDemo);

document.body.append(document.createElement("components-demo"));
