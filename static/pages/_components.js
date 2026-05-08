// Shared bundle: registers every <id-*> custom element (id-nav, id-button, …)
// without mounting any page-level component. Used by plugin admin HTML pages
// so they can drop `<id-nav>` into a server-rendered shell.
import "../components/index.js";
