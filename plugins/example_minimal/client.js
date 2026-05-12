// The bare minimum: a default-export function that paints into the cell's
// shadow-DOM host. ``ctx.cell.size`` is one of xs/sm/md/lg; ``ctx.theme``
// has the resolved palette tokens; ``ctx.cell.options`` carries whatever
// the manifest's ``cell_options`` declared (none here).
//
// Setting ``host.host.dataset.rendered = "true"`` tells the screenshot
// pipeline the cell is ready to capture — skip it and the panel push
// will fire before the cell has painted.
export default function render(host, ctx) {
  host.innerHTML = `
    <div style="
      height: 100%;
      display: grid;
      place-items: center;
      background: var(--theme-bg);
      color: var(--theme-fg);
      font: 800 12cqh/1 inherit;
      letter-spacing: -0.03em;
    ">
      Hello, ${ctx.cell.size}!
    </div>
  `;
  host.host.dataset.rendered = "true";
}
