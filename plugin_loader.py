from __future__ import annotations

import importlib.util
import inspect
import json
import os
import sys
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from flask import Blueprint, Flask, abort, send_from_directory

from config import Config
from state.widget_settings import WidgetSettings

VALID_KINDS = {"widget", "admin", "theme", "font"}

ROOT = Path(__file__).resolve().parent

SYSTEM_FONT_FALLBACK = (
    'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
)


# -----------------------------------------------------------------------------
# Data model
# -----------------------------------------------------------------------------


@dataclass
class ThemeEntry:
    id: str
    label: str
    palette: dict[str, str]
    source_plugin: str
    font: str | None = None  # font_id this theme prefers (page.font wins if set)


@dataclass
class FontEntry:
    id: str
    family: str
    fallback_stack: str
    weights: dict[str, str]
    source_plugin: str
    is_system: bool = False


@dataclass
class NavLink:
    label: str
    icon: str | None
    endpoint: str
    plugin_id: str


@dataclass
class SettingsField:
    key: str
    label: str
    type: str
    default: Any = None
    choices: list[dict] | None = None
    choices_from: str | None = None


@dataclass
class SettingsSection:
    plugin_id: str
    title: str
    fields: list[SettingsField]


@dataclass
class PluginManifest:
    id: str
    label: str
    icon: str | None
    version: str
    kinds: list[str]
    cell_options: list[dict]
    settings: SettingsSection | None
    admin_nav: NavLink | None
    choice_providers: list[str]
    themes: list[ThemeEntry]
    fonts: list[FontEntry]


@dataclass
class LoadedPlugin:
    manifest: PluginManifest
    path: Path
    module: ModuleType | None
    has_client_js: bool
    has_client_css: bool
    enabled: bool = True
    error: str | None = None

    @property
    def id(self) -> str:
        return self.manifest.id

    @property
    def kinds(self) -> list[str]:
        return self.manifest.kinds


# -----------------------------------------------------------------------------
# Manifest parsing
# -----------------------------------------------------------------------------


def _parse_settings(plugin_id: str, raw: dict) -> SettingsSection | None:
    if not raw:
        return None
    fields = []
    for f in raw.get("fields", []) or []:
        if "key" not in f:
            continue
        fields.append(
            SettingsField(
                key=f["key"],
                label=f.get("label", f["key"]),
                type=f.get("type", "text"),
                default=f.get("default"),
                choices=f.get("choices"),
                choices_from=f.get("choices_from"),
            )
        )
    return SettingsSection(
        plugin_id=plugin_id,
        title=raw.get("title", plugin_id),
        fields=fields,
    )


def _parse_admin_nav(plugin_id: str, raw: dict) -> NavLink | None:
    if not raw or "label" not in raw or "endpoint" not in raw:
        return None
    return NavLink(
        label=raw["label"],
        icon=raw.get("icon"),
        endpoint=raw["endpoint"],
        plugin_id=plugin_id,
    )


def _parse_themes(plugin_id: str, raw: list) -> list[ThemeEntry]:
    out: list[ThemeEntry] = []
    for t in raw or []:
        if "id" not in t or "palette" not in t:
            continue
        font = t.get("font")
        out.append(
            ThemeEntry(
                id=t["id"],
                label=t.get("label", t["id"]),
                palette=dict(t["palette"]),
                source_plugin=plugin_id,
                font=str(font) if isinstance(font, str) and font else None,
            )
        )
    return out


def _parse_fonts(plugin_id: str, raw: list) -> list[FontEntry]:
    out: list[FontEntry] = []
    for f in raw or []:
        if "id" not in f or "family" not in f:
            continue
        out.append(
            FontEntry(
                id=f["id"],
                family=f["family"],
                fallback_stack=f.get("fallback_stack", SYSTEM_FONT_FALLBACK),
                weights=dict(f.get("weights", {})),
                source_plugin=plugin_id,
            )
        )
    return out


def _parse_manifest(plugin_id: str, data: dict) -> PluginManifest:
    declared_id = data.get("id")
    if declared_id and declared_id != plugin_id:
        # Folder name wins so /plugins/<folder>/ URLs match disk layout.
        print(
            f"[plugins] {plugin_id}: manifest id '{declared_id}' "
            f"differs from folder; using folder name",
            file=sys.stderr,
        )
    kinds = data.get("kinds") or []
    if not isinstance(kinds, list):
        raise ValueError(f"kinds must be a list, got {type(kinds).__name__}")
    bad = [k for k in kinds if k not in VALID_KINDS]
    if bad:
        raise ValueError(f"unknown kinds: {bad}; valid = {sorted(VALID_KINDS)}")

    cell_options = data.get("cell_options") or []
    if not isinstance(cell_options, list):
        raise ValueError("cell_options must be a list")

    return PluginManifest(
        id=plugin_id,
        label=data.get("label", plugin_id),
        icon=data.get("icon"),
        version=str(data.get("version", "0")),
        kinds=list(kinds),
        cell_options=cell_options,
        settings=_parse_settings(plugin_id, data.get("settings") or {}),
        admin_nav=_parse_admin_nav(plugin_id, data.get("admin_nav") or {}),
        choice_providers=list(data.get("choice_providers") or []),
        themes=_parse_themes(plugin_id, data.get("themes") or []),
        fonts=_parse_fonts(plugin_id, data.get("fonts") or []),
    )


# -----------------------------------------------------------------------------
# server.py import
# -----------------------------------------------------------------------------


def _ensure_namespace_package() -> None:
    """Create a synthetic `inky_plugins` package so plugin server modules can
    be imported under `inky_plugins.<id>.server` and use relative imports."""
    if "inky_plugins" not in sys.modules:
        pkg = ModuleType("inky_plugins")
        pkg.__path__ = []  # type: ignore[attr-defined]
        sys.modules["inky_plugins"] = pkg


def _import_server(path: Path, plugin_id: str) -> ModuleType | None:
    server_py = path / "server.py"
    if not server_py.exists():
        return None
    _ensure_namespace_package()
    pkg_name = f"inky_plugins.{plugin_id}"
    if pkg_name not in sys.modules:
        pkg = ModuleType(pkg_name)
        pkg.__path__ = [str(path)]  # type: ignore[attr-defined]
        sys.modules[pkg_name] = pkg
    mod_name = f"{pkg_name}.server"
    spec = importlib.util.spec_from_file_location(
        mod_name,
        server_py,
        submodule_search_locations=[str(path)],
    )
    if not spec or not spec.loader:
        raise ImportError(f"cannot create spec for {server_py}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


# -----------------------------------------------------------------------------
# Zip unpack
# -----------------------------------------------------------------------------


def _unzip_pending(plugins_dir: Path) -> None:
    for zp in sorted(plugins_dir.glob("*.zip")):
        try:
            with zipfile.ZipFile(zp) as zf:
                names = [n for n in zf.namelist() if n]
                top_level = {n.split("/", 1)[0] for n in names}
                if len(top_level) == 1 and any("/" in n for n in names):
                    target_name = next(iter(top_level))
                    if (plugins_dir / target_name).exists():
                        continue
                    zf.extractall(plugins_dir)
                else:
                    target = plugins_dir / zp.stem
                    if target.exists():
                        continue
                    zf.extractall(target)
        except Exception as exc:
            print(f"[plugins] unzip {zp.name} failed: {exc}", file=sys.stderr)


# -----------------------------------------------------------------------------
# Settings env coercion
# -----------------------------------------------------------------------------


def _coerce_setting(raw: str, type_: str) -> Any:
    if type_ == "int":
        try:
            return int(raw)
        except ValueError:
            return None
    if type_ == "float":
        try:
            return float(raw)
        except ValueError:
            return None
    if type_ == "bool":
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return raw


# -----------------------------------------------------------------------------
# Registry
# -----------------------------------------------------------------------------


@dataclass
class PluginRegistry:
    plugins: dict[str, LoadedPlugin] = field(default_factory=dict)
    _enabled_overrides: dict[str, bool] = field(default_factory=dict)
    _settings: "WidgetSettings | None" = None

    def is_enabled(self, plugin_id: str) -> bool:
        plugin = self.plugins.get(plugin_id)
        if plugin is None or plugin.error:
            return False
        return self._enabled_overrides.get(plugin_id, plugin.enabled)

    def set_enabled(self, plugin_id: str, enabled: bool) -> bool:
        """Toggle a plugin on/off at runtime. Persists to disk and updates the
        in-memory override so subsequent registry queries see the new state.
        Returns False if the plugin isn't loaded."""
        if plugin_id not in self.plugins:
            return False
        self._enabled_overrides[plugin_id] = bool(enabled)
        if self._settings is not None:
            self._settings.set_enabled(plugin_id, bool(enabled))
        return True

    def reload_user_themes(self, themes_dir: Path) -> int:
        """Re-scan `data/themes/*.json` and replace the synthetic user_themes
        entry. Used by the theme_builder plugin so that saving a theme takes
        effect without restarting the app. Returns the number of user themes."""
        plugin = _user_themes_plugin(themes_dir)
        if plugin:
            self.plugins["user_themes"] = plugin
            return len(plugin.manifest.themes)
        # No user themes anymore — drop the synthetic entry.
        self.plugins.pop("user_themes", None)
        return 0

    # --- queries ------------------------------------------------------------

    def widgets(self, *, include_disabled: bool = False) -> list[LoadedPlugin]:
        return [
            p
            for p in self.plugins.values()
            if "widget" in p.kinds and (include_disabled or self.is_enabled(p.id))
        ]

    def widget(self, plugin_id: str) -> LoadedPlugin | None:
        p = self.plugins.get(plugin_id)
        return p if (p and "widget" in p.kinds) else None

    def themes(self) -> list[ThemeEntry]:
        out: list[ThemeEntry] = []
        seen: set[str] = set()
        for p in self.plugins.values():
            if not self.is_enabled(p.id):
                continue
            for t in p.manifest.themes:
                if t.id in seen:
                    continue
                seen.add(t.id)
                out.append(t)
        return out

    def theme(self, theme_id: str) -> ThemeEntry | None:
        for t in self.themes():
            if t.id == theme_id:
                return t
        return None

    def fonts(self) -> list[FontEntry]:
        out: list[FontEntry] = [
            FontEntry(
                id="system",
                family="System UI",
                fallback_stack=SYSTEM_FONT_FALLBACK,
                weights={},
                source_plugin="_system",
                is_system=True,
            )
        ]
        seen: set[str] = {"system"}
        for p in self.plugins.values():
            if not self.is_enabled(p.id):
                continue
            for f in p.manifest.fonts:
                if f.id in seen:
                    continue
                seen.add(f.id)
                out.append(f)
        return out

    def font(self, font_id: str) -> FontEntry | None:
        for f in self.fonts():
            if f.id == font_id:
                return f
        return None

    def nav_links(self) -> list[NavLink]:
        out: list[NavLink] = []
        for p in self.plugins.values():
            if not self.is_enabled(p.id):
                continue
            if p.manifest.admin_nav:
                out.append(p.manifest.admin_nav)
        return out

    def settings_sections(self) -> list[SettingsSection]:
        out: list[SettingsSection] = []
        for p in self.plugins.values():
            if not self.is_enabled(p.id):
                continue
            if p.manifest.settings and p.manifest.settings.fields:
                out.append(p.manifest.settings)
        return out

    def collect_settings(self, plugin: LoadedPlugin) -> dict[str, Any]:
        section = plugin.manifest.settings
        if not section:
            return {}
        out: dict[str, Any] = {}
        for f in section.fields:
            raw = os.environ.get(f.key)
            if raw is None or raw == "":
                out[f.key] = f.default
            else:
                out[f.key] = _coerce_setting(raw, f.type)
        return out

    # --- actions ------------------------------------------------------------

    def fetch_widget_data(
        self,
        plugin_id: str,
        options: dict,
        *,
        panel_w: int,
        panel_h: int,
        preview: bool = False,
    ) -> dict:
        plugin = self.widget(plugin_id)
        if not plugin or not plugin.module:
            return {}
        if not self.is_enabled(plugin_id):
            return {}
        fetch = getattr(plugin.module, "fetch", None)
        if not callable(fetch):
            return {}
        settings = self.collect_settings(plugin)
        kwargs: dict[str, Any] = {"panel_w": panel_w, "panel_h": panel_h}
        try:
            params = inspect.signature(fetch).parameters
        except (TypeError, ValueError):
            params = {}
        if "preview" in params or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
        ):
            kwargs["preview"] = preview
        return fetch(options, settings, **kwargs)

    def choices(self, name: str) -> list[dict]:
        for p in self.plugins.values():
            if not self.is_enabled(p.id) or not p.module:
                continue
            if name not in p.manifest.choice_providers:
                continue
            fn = getattr(p.module, "choices", None)
            if not callable(fn):
                continue
            try:
                result = fn(name)
            except Exception as exc:
                print(
                    f"[plugins] choices({name}) on {p.id} failed: {exc}",
                    file=sys.stderr,
                )
                continue
            if isinstance(result, list):
                return result
        return []


# -----------------------------------------------------------------------------
# Synthetic sources
# -----------------------------------------------------------------------------


def _user_themes_plugin(themes_dir: Path) -> LoadedPlugin | None:
    if not themes_dir.exists():
        return None
    entries: list[ThemeEntry] = []
    for f in sorted(themes_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[themes] bad theme {f.name}: {exc}", file=sys.stderr)
            continue
        if "id" not in data or "palette" not in data:
            continue
        font = data.get("font")
        entries.append(
            ThemeEntry(
                id=data["id"],
                label=data.get("label", data["id"]),
                palette=dict(data["palette"]),
                source_plugin="user_themes",
                font=str(font) if isinstance(font, str) and font else None,
            )
        )
    if not entries:
        return None
    manifest = PluginManifest(
        id="user_themes",
        label="User themes",
        icon=None,
        version="0",
        kinds=["theme"],
        cell_options=[],
        settings=None,
        admin_nav=None,
        choice_providers=[],
        themes=entries,
        fonts=[],
    )
    return LoadedPlugin(
        manifest=manifest,
        path=themes_dir,
        module=None,
        has_client_js=False,
        has_client_css=False,
    )


# -----------------------------------------------------------------------------
# Asset blueprint (serves /plugins/<id>/client.js, client.css, static/*)
# -----------------------------------------------------------------------------


def _make_asset_blueprint(registry: PluginRegistry) -> Blueprint:
    bp = Blueprint("inky_plugin_assets", __name__, url_prefix="/plugins")

    def _resolve(plugin_id: str) -> LoadedPlugin:
        plugin = registry.plugins.get(plugin_id)
        if not plugin or not registry.is_enabled(plugin_id):
            abort(404)
        return plugin

    @bp.route("/<plugin_id>/client.js")
    def client_js(plugin_id):
        plugin = _resolve(plugin_id)
        if not plugin.has_client_js:
            abort(404)
        return send_from_directory(
            plugin.path, "client.js", mimetype="text/javascript"
        )

    @bp.route("/<plugin_id>/client.css")
    def client_css(plugin_id):
        plugin = _resolve(plugin_id)
        if not plugin.has_client_css:
            abort(404)
        return send_from_directory(
            plugin.path, "client.css", mimetype="text/css"
        )

    @bp.route("/<plugin_id>/static/<path:filename>")
    def plugin_static(plugin_id, filename):
        plugin = _resolve(plugin_id)
        return send_from_directory(plugin.path / "static", filename)

    return bp


# -----------------------------------------------------------------------------
# Boot
# -----------------------------------------------------------------------------


def init_plugins(app: Flask, config: Config) -> PluginRegistry:
    plugins_dir = ROOT / "plugins"
    plugins_dir.mkdir(parents=True, exist_ok=True)

    _unzip_pending(plugins_dir)

    settings = WidgetSettings(config.data_dir / "widget_settings.json")
    registry = PluginRegistry(_settings=settings)
    registry._enabled_overrides = settings.load_state()

    for entry in sorted(plugins_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith(("_", ".")):
            continue
        manifest_path = entry / "plugin.json"
        if not manifest_path.exists():
            continue

        plugin_id = entry.name
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = _parse_manifest(plugin_id, data)
            module = _import_server(entry, plugin_id)
            plugin = LoadedPlugin(
                manifest=manifest,
                path=entry,
                module=module,
                has_client_js=(entry / "client.js").exists(),
                has_client_css=(entry / "client.css").exists(),
            )
        except Exception as exc:
            print(f"[plugins] {plugin_id} failed: {exc}", file=sys.stderr)
            stub = PluginManifest(
                id=plugin_id,
                label=plugin_id,
                icon=None,
                version="0",
                kinds=[],
                cell_options=[],
                settings=None,
                admin_nav=None,
                choice_providers=[],
                themes=[],
                fonts=[],
            )
            plugin = LoadedPlugin(
                manifest=stub,
                path=entry,
                module=None,
                has_client_js=False,
                has_client_css=False,
                enabled=False,
                error=str(exc),
            )

        registry.plugins[plugin_id] = plugin

        # Always register the plugin's blueprint when one is provided. The
        # per-blueprint before_request gate consults registry.is_enabled at
        # request time, so toggling enable/disable from /widgets is hot for
        # both author-defined routes and the asset routes.
        if plugin.module:
            _register_plugin_blueprint(app, plugin, registry)

    user_themes = _user_themes_plugin(config.data_dir / "themes")
    if user_themes:
        registry.plugins[user_themes.id] = user_themes

    app.register_blueprint(_make_asset_blueprint(registry))
    app.config["PLUGINS"] = registry
    return registry


def _register_plugin_blueprint(app: Flask, plugin: LoadedPlugin, registry: PluginRegistry) -> None:
    factory = getattr(plugin.module, "blueprint", None)
    if not callable(factory):
        return
    try:
        bp = factory()
    except Exception as exc:
        print(f"[plugins] {plugin.id} blueprint() raised: {exc}", file=sys.stderr)
        plugin.error = str(exc)
        return
    if bp is None:
        return
    if not isinstance(bp, Blueprint):
        plugin.error = f"blueprint() returned {type(bp).__name__}, not Blueprint"
        print(f"[plugins] {plugin.id}: {plugin.error}", file=sys.stderr)
        return

    # Closure captures the local plugin.id from this call frame, not the
    # iteration variable in init_plugins (which would bind to the last plugin).
    plugin_id = plugin.id

    @bp.before_request
    def _gate_on_enabled():
        if not registry.is_enabled(plugin_id):
            abort(404)

    try:
        app.register_blueprint(bp, url_prefix=f"/plugins/{plugin.id}")
    except Exception as exc:
        plugin.error = f"register_blueprint failed: {exc}"
        print(f"[plugins] {plugin.id}: {plugin.error}", file=sys.stderr)
