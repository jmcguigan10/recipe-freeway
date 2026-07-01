from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pandas as pd


DETECTORS = ("bhc", "bhd", "gem0")
DEFAULT_EDGE_BAND_MM = 5.0
DEFAULT_NEAR_BAND_MM = 20.0
MISS_TARGET_SOURCES = {
    "miss_bhc_primary": "hit_bhc_primary",
    "miss_bhd_primary": "hit_bhd_primary",
    "miss_gem0_primary": "hit_gem0_primary",
}
RESIDUAL_MISS_TARGETS = {
    "residual_miss_bhc_primary": "bhc",
    "residual_miss_bhd_primary": "bhd",
    "residual_miss_gem0_primary": "gem0",
}


def load_geometry_config(raw: str | Path | Mapping[str, Any] | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, Mapping):
        return normalize_geometry_config(raw)

    text = str(raw).strip()
    if text.lower() in ("", "none", "false", "0", "off", "null"):
        return None

    path = resolve_geometry_path(text)
    if not path.is_file():
        raise ValueError(f"Geometry config file not found: {path}")

    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyYAML is required to load geometry configs") from exc

    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}
    return normalize_geometry_config(payload)


def resolve_geometry_path(path_text: str) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path

    candidates = [
        (Path.cwd() / path).resolve(),
        (Path(__file__).resolve().parents[4] / path).resolve(),
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[-1]


def normalize_geometry_config(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("Geometry config must be a mapping")

    raw_detectors = payload.get("detectors", payload)
    if not isinstance(raw_detectors, Mapping):
        raise ValueError("Geometry config 'detectors' must be a mapping")

    detectors: dict[str, dict[str, float | str]] = {}
    for raw_name, raw_config in raw_detectors.items():
        name = str(raw_name).strip().lower()
        if name not in DETECTORS:
            raise ValueError(f"Unsupported detector geometry key: {raw_name}")
        if not isinstance(raw_config, Mapping):
            raise ValueError(f"detectors.{name} must be a mapping")

        detector: dict[str, float | str] = {
            "z_mm": required_float(raw_config, "z_mm", f"detectors.{name}.z_mm"),
        }
        shape = raw_config.get("shape")
        if shape is None:
            if "radius_mm" in raw_config:
                shape = "circle"
            elif "half_width_mm" in raw_config or "half_height_mm" in raw_config:
                shape = "rect"

        if shape is not None:
            parsed_shape = str(shape).strip().lower()
            if parsed_shape in ("rectangle", "rectangular"):
                parsed_shape = "rect"
            if parsed_shape not in ("rect", "circle"):
                raise ValueError(f"detectors.{name}.shape must be 'rect' or 'circle': {shape}")
            detector["shape"] = parsed_shape

        for key in ("half_width_mm", "half_height_mm", "radius_mm", "center_x_mm", "center_y_mm"):
            if key in raw_config:
                detector[key] = float(raw_config[key])
        detectors[name] = detector

    return {"detectors": detectors}


def build_feature_frame(
    frame: pd.DataFrame,
    feature_columns: Sequence[str],
    geometry: Mapping[str, Any] | None,
    *,
    edge_band_mm: float = DEFAULT_EDGE_BAND_MM,
    near_band_mm: float = DEFAULT_NEAR_BAND_MM,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            column: feature_series(
                frame,
                column,
                geometry,
                edge_band_mm=edge_band_mm,
                near_band_mm=near_band_mm,
            )
            for column in feature_columns
        },
        index=frame.index,
    )


def build_target_frame(
    frame: pd.DataFrame,
    target_columns: Sequence[str],
    geometry: Mapping[str, Any] | None = None,
    *,
    edge_band_mm: float = DEFAULT_EDGE_BAND_MM,
    near_band_mm: float = DEFAULT_NEAR_BAND_MM,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            column: target_series(
                frame,
                column,
                geometry,
                edge_band_mm=edge_band_mm,
                near_band_mm=near_band_mm,
            )
            for column in target_columns
        },
        index=frame.index,
    )


def feature_series(
    frame: pd.DataFrame,
    column: str,
    geometry: Mapping[str, Any] | None,
    *,
    edge_band_mm: float = DEFAULT_EDGE_BAND_MM,
    near_band_mm: float = DEFAULT_NEAR_BAND_MM,
) -> pd.Series:
    if column in frame.columns:
        return frame[column]

    if column == "path_scale_z":
        require_source_columns(frame, ("dir_z",), column)
        return 1.0 / frame["dir_z"].abs().clip(lower=1e-6)

    for detector in DETECTORS:
        if column == f"x_at_{detector}_mm":
            return projected_position(frame, geometry, detector, column, "x")
        if column == f"y_at_{detector}_mm":
            return projected_position(frame, geometry, detector, column, "y")
        if column == f"x_local_at_{detector}_mm":
            x_at = projected_position(frame, geometry, detector, column, "x")
            detector_geometry = require_detector_geometry(geometry, detector, column)
            return x_at - float(detector_geometry.get("center_x_mm", 0.0))
        if column == f"y_local_at_{detector}_mm":
            y_at = projected_position(frame, geometry, detector, column, "y")
            detector_geometry = require_detector_geometry(geometry, detector, column)
            return y_at - float(detector_geometry.get("center_y_mm", 0.0))
        if column == f"r_at_{detector}_mm":
            x_at = projected_position(frame, geometry, detector, column, "x")
            y_at = projected_position(frame, geometry, detector, column, "y")
            return (x_at.pow(2) + y_at.pow(2)).pow(0.5)
        if column == f"{detector}_edge_margin_mm":
            return edge_margin(frame, geometry, detector, column)
        if column == f"{detector}_edge_margin_norm":
            margin = edge_margin(frame, geometry, detector, column)
            scale = detector_size_scale(require_detector_geometry(geometry, detector, column), detector, column)
            return margin / max(scale, 1e-6)
        if column == f"geom_outside_{detector}":
            return regime_mask(frame, geometry, detector, "outside", edge_band_mm=edge_band_mm, near_band_mm=near_band_mm).astype("float32")
        if column == f"geom_edge_{detector}":
            return regime_mask(frame, geometry, detector, "edge", edge_band_mm=edge_band_mm, near_band_mm=near_band_mm).astype("float32")
        if column == f"geom_near_{detector}":
            return regime_mask(frame, geometry, detector, "near", edge_band_mm=edge_band_mm, near_band_mm=near_band_mm).astype("float32")
        if column == f"geom_core_{detector}":
            return regime_mask(frame, geometry, detector, "core", edge_band_mm=edge_band_mm, near_band_mm=near_band_mm).astype("float32")

    raise ValueError(f"Missing feature column or unsupported derived feature: {column}")


def target_series(
    frame: pd.DataFrame,
    column: str,
    geometry: Mapping[str, Any] | None = None,
    *,
    edge_band_mm: float = DEFAULT_EDGE_BAND_MM,
    near_band_mm: float = DEFAULT_NEAR_BAND_MM,
) -> pd.Series:
    if column in frame.columns:
        return frame[column]

    source = MISS_TARGET_SOURCES.get(column)
    if source is not None:
        require_source_columns(frame, (source,), column)
        return 1.0 - frame[source].astype("float32")

    detector = RESIDUAL_MISS_TARGETS.get(column)
    if detector is not None:
        miss = target_series(
            frame,
            f"miss_{detector}_primary",
            geometry,
            edge_band_mm=edge_band_mm,
            near_band_mm=near_band_mm,
        ).astype("float32")
        core = regime_mask(
            frame,
            geometry,
            detector,
            "core",
            edge_band_mm=edge_band_mm,
            near_band_mm=near_band_mm,
        ).astype("float32")
        return miss * core

    for detector_name in DETECTORS:
        if column == f"geom_outside_{detector_name}":
            return regime_mask(frame, geometry, detector_name, "outside", edge_band_mm=edge_band_mm, near_band_mm=near_band_mm).astype("float32")
        if column == f"geom_edge_{detector_name}":
            return regime_mask(frame, geometry, detector_name, "edge", edge_band_mm=edge_band_mm, near_band_mm=near_band_mm).astype("float32")
        if column == f"geom_near_{detector_name}":
            return regime_mask(frame, geometry, detector_name, "near", edge_band_mm=edge_band_mm, near_band_mm=near_band_mm).astype("float32")
        if column == f"geom_core_{detector_name}":
            return regime_mask(frame, geometry, detector_name, "core", edge_band_mm=edge_band_mm, near_band_mm=near_band_mm).astype("float32")

    raise ValueError(f"Missing target column or unsupported derived target: {column}")


def projected_position(
    frame: pd.DataFrame,
    geometry: Mapping[str, Any] | None,
    detector: str,
    feature_name: str,
    axis: str,
) -> pd.Series:
    source_columns = ("x0_mm", "y0_mm", "z0_mm", "xprime", "yprime")
    require_source_columns(frame, source_columns, feature_name)
    detector_geometry = require_detector_geometry(geometry, detector, feature_name)
    delta_z = float(detector_geometry["z_mm"]) - frame["z0_mm"]
    if axis == "x":
        return frame["x0_mm"] + frame["xprime"] * delta_z
    if axis == "y":
        return frame["y0_mm"] + frame["yprime"] * delta_z
    raise ValueError(f"Unsupported projection axis: {axis}")


def edge_margin(
    frame: pd.DataFrame,
    geometry: Mapping[str, Any] | None,
    detector: str,
    feature_name: str,
) -> pd.Series:
    detector_geometry = require_detector_geometry(geometry, detector, feature_name)
    shape = detector_geometry.get("shape")
    if shape is None:
        raise ValueError(f"{feature_name} requires detectors.{detector}.shape")

    x_at = projected_position(frame, geometry, detector, feature_name, "x")
    y_at = projected_position(frame, geometry, detector, feature_name, "y")
    center_x = float(detector_geometry.get("center_x_mm", 0.0))
    center_y = float(detector_geometry.get("center_y_mm", 0.0))
    x_local = x_at - center_x
    y_local = y_at - center_y
    if shape == "rect":
        half_width = require_detector_float(detector_geometry, "half_width_mm", detector, feature_name)
        half_height = require_detector_float(detector_geometry, "half_height_mm", detector, feature_name)
        margins = pd.DataFrame(
            {
                "x": half_width - x_local.abs(),
                "y": half_height - y_local.abs(),
            },
            index=frame.index,
        )
        return margins.min(axis=1)
    if shape == "circle":
        radius = require_detector_float(detector_geometry, "radius_mm", detector, feature_name)
        r_local = (x_local.pow(2) + y_local.pow(2)).pow(0.5)
        return radius - r_local

    raise ValueError(f"{feature_name} has unsupported detector shape: {shape}")


def regime_mask(
    frame: pd.DataFrame,
    geometry: Mapping[str, Any] | None,
    detector: str,
    regime: str,
    *,
    edge_band_mm: float = DEFAULT_EDGE_BAND_MM,
    near_band_mm: float = DEFAULT_NEAR_BAND_MM,
) -> pd.Series:
    edge_band_mm, near_band_mm = validate_regime_bands(edge_band_mm, near_band_mm)
    margin = edge_margin(frame, geometry, detector, f"geom_{regime}_{detector}")
    if regime == "outside":
        return margin <= 0.0
    if regime == "edge":
        return (margin > 0.0) & (margin <= edge_band_mm)
    if regime == "near":
        return (margin > edge_band_mm) & (margin <= near_band_mm)
    if regime == "core":
        return margin > near_band_mm
    raise ValueError(f"Unsupported geometry regime: {regime}")


def validate_regime_bands(edge_band_mm: float, near_band_mm: float) -> tuple[float, float]:
    edge = float(edge_band_mm)
    near = float(near_band_mm)
    if edge <= 0.0:
        raise ValueError(f"edge_band_mm must be positive: {edge_band_mm}")
    if near <= edge:
        raise ValueError(f"near_band_mm must be greater than edge_band_mm: {near} <= {edge}")
    return edge, near


def detector_size_scale(detector_geometry: Mapping[str, Any], detector: str, feature_name: str) -> float:
    shape = detector_geometry.get("shape")
    if shape == "rect":
        return min(
            require_detector_float(detector_geometry, "half_width_mm", detector, feature_name),
            require_detector_float(detector_geometry, "half_height_mm", detector, feature_name),
        )
    if shape == "circle":
        return require_detector_float(detector_geometry, "radius_mm", detector, feature_name)
    raise ValueError(f"{feature_name} has unsupported detector shape: {shape}")


def require_detector_geometry(
    geometry: Mapping[str, Any] | None,
    detector: str,
    feature_name: str,
) -> Mapping[str, Any]:
    if geometry is None:
        raise ValueError(f"{feature_name} requires --geometry-config with detectors.{detector}")
    detectors = geometry.get("detectors")
    if not isinstance(detectors, Mapping):
        raise ValueError(f"{feature_name} requires geometry config with a detectors mapping")
    detector_geometry = detectors.get(detector)
    if not isinstance(detector_geometry, Mapping):
        raise ValueError(f"{feature_name} requires geometry config detectors.{detector}")
    if "z_mm" not in detector_geometry:
        raise ValueError(f"{feature_name} requires detectors.{detector}.z_mm")
    return detector_geometry


def require_detector_float(
    detector_geometry: Mapping[str, Any],
    key: str,
    detector: str,
    feature_name: str,
) -> float:
    if key not in detector_geometry:
        raise ValueError(f"{feature_name} requires detectors.{detector}.{key}")
    return float(detector_geometry[key])


def required_float(payload: Mapping[str, Any], key: str, path: str) -> float:
    if key not in payload:
        raise ValueError(f"{path} is required")
    return float(payload[key])


def require_source_columns(frame: pd.DataFrame, columns: Sequence[str], context: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"{context} requires source column(s): {', '.join(missing)}")
