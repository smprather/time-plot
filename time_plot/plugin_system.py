from __future__ import annotations

from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys
from types import ModuleType
from typing import Callable

from time_plot.models import SeriesData


IdentifyFn = Callable[[Path], bool]
ParseFn = Callable[[Path, dict[str, str]], list[SeriesData]]


@dataclass(slots=True)
class ParserPlugin:
    module_name: str
    plugin_name: str
    identify: IdentifyFn
    parse: ParseFn
    path: Path


def discover_plugins(plugins_dir: Path) -> list[ParserPlugin]:
    if not plugins_dir.exists():
        return []

    plugins: list[ParserPlugin] = []
    for candidate in sorted(plugins_dir.iterdir()):
        if candidate.name.startswith("_"):
            continue
        plugin_file = _plugin_entrypoint(candidate)
        if plugin_file is None:
            continue
        try:
            module = _load_module(plugin_file)
            plugins.append(_plugin_from_module(module, candidate))
        except Exception as exc:  # pragma: no cover - startup robustness
            print(
                f"Skipping plugin {candidate.name}: {exc}",
                file=sys.stderr,
            )
    return plugins


def select_plugin(data_file: Path, plugins: list[ParserPlugin]) -> ParserPlugin:
    for plugin in plugins:
        if plugin.identify(data_file):
            return plugin
    msg = f"No plugin recognized file: {data_file}"
    raise LookupError(msg)


def _load_module(plugin_file: Path) -> ModuleType:
    if plugin_file.name == "__init__.py":
        package_dir = plugin_file.parent
        module_name = f"time_plot_dynamic_plugin_{package_dir.name}"
        spec = spec_from_file_location(
            module_name,
            plugin_file,
            submodule_search_locations=[str(package_dir)],
        )
    else:
        module_name = f"time_plot_dynamic_plugin_{plugin_file.stem}"
        spec = spec_from_file_location(module_name, plugin_file)
    if spec is None or spec.loader is None:
        msg = f"Could not load plugin spec for {plugin_file}"
        raise ImportError(msg)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _plugin_from_module(module: ModuleType, path: Path) -> ParserPlugin:
    identify = getattr(module, "identify", None)
    parse = getattr(module, "parse", None)
    plugin_name_fn = getattr(module, "plugin_name", None)

    if not callable(identify):
        msg = "missing callable identify(path) -> bool"
        raise TypeError(msg)
    if not callable(parse):
        msg = "missing callable parse(path, options) -> list[SeriesData]"
        raise TypeError(msg)
    if callable(plugin_name_fn):
        plugin_name = str(plugin_name_fn())
    else:
        plugin_name = path.stem

    return ParserPlugin(
        module_name=module.__name__,
        plugin_name=plugin_name,
        identify=identify,
        parse=parse,
        path=path,
    )


def _plugin_entrypoint(candidate: Path) -> Path | None:
    if candidate.is_file() and candidate.suffix == ".py":
        return candidate
    if candidate.is_dir():
        init_file = candidate / "__init__.py"
        if init_file.exists():
            return init_file
    return None
