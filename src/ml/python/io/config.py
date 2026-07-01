from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

ML_CONFIG_SECTIONS = ("data", "model", "loss", "optimizer", "runtime")
PATH_CONFIG_KEYS = {"geometry_config"}


def default_ml_config_path() -> Path:
    return Path(__file__).resolve().parents[4] / "configs" / "ml" / "default.yaml"


def load_training_config_file(path: str | Path | None) -> dict[str, Any]:
    if path is None:
        return {}

    path_text = str(path).strip()
    if path_text.lower() in ("", "none", "false", "0", "off"):
        return {}

    payload = _load_yaml_with_includes(Path(path_text).expanduser().resolve(), seen=set())
    return flatten_training_config(payload)


def flatten_training_config(payload: Mapping[str, Any]) -> dict[str, Any]:
    config: dict[str, Any] = {}
    for key, value in payload.items():
        if key in ML_CONFIG_SECTIONS:
            if not isinstance(value, Mapping):
                raise ValueError(f"ML config section must be a mapping: {key}")
            config.update(value)
        elif key != "include":
            config[key] = value
    return config


def _load_yaml_with_includes(path: Path, *, seen: set[Path]) -> dict[str, Any]:
    if path in seen:
        raise ValueError(f"Recursive ML config include detected: {path}")
    if not path.is_file():
        raise ValueError(f"ML config file not found: {path}")

    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyYAML is required to load ML YAML configs") from exc

    seen.add(path)
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    if not isinstance(payload, Mapping):
        raise ValueError(f"ML config file must contain a mapping: {path}")

    merged: dict[str, Any] = {}
    for include in _include_paths(path, payload.get("include", [])):
        merged = _deep_merge(merged, _load_yaml_with_includes(include, seen=seen))

    local_payload = dict(payload)
    local_payload.pop("include", None)
    local_payload = _resolve_path_config_values(local_payload, path.parent)
    merged = _deep_merge(merged, local_payload)
    seen.remove(path)
    return merged


def _include_paths(path: Path, includes: Any) -> list[Path]:
    if includes in (None, ""):
        return []
    if isinstance(includes, (str, Path)):
        includes = [includes]
    if not isinstance(includes, list):
        raise ValueError(f"include must be a string or list in ML config: {path}")

    paths = []
    for include in includes:
        include_path = Path(str(include)).expanduser()
        if not include_path.is_absolute():
            include_path = path.parent / include_path
        paths.append(include_path.resolve())
    return paths


def _resolve_path_config_values(payload: Mapping[str, Any], base_dir: Path) -> dict[str, Any]:
    resolved: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, Mapping):
            resolved[key] = _resolve_path_config_values(value, base_dir)
        elif key in PATH_CONFIG_KEYS:
            resolved[key] = _resolve_optional_path(value, base_dir)
        else:
            resolved[key] = value
    return resolved


def _resolve_optional_path(value: Any, base_dir: Path) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    if text.lower() in ("", "none", "false", "0", "off", "null"):
        return value
    path = Path(text).expanduser()
    if path.is_absolute():
        return str(path)
    return str((base_dir / path).resolve())


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(merged.get(key), Mapping) and isinstance(value, Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
