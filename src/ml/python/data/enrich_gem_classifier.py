from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from .derived import DEFAULT_EDGE_BAND_MM, DEFAULT_NEAR_BAND_MM, build_feature_frame, build_target_frame, load_geometry_config

DETECTORS = ("bhc", "bhd", "gem0")
DEFAULT_DERIVED_FEATURES = tuple(
    item
    for detector in DETECTORS
    for item in (
        f"x_at_{detector}_mm",
        f"y_at_{detector}_mm",
        f"x_local_at_{detector}_mm",
        f"y_local_at_{detector}_mm",
        f"r_at_{detector}_mm",
        f"{detector}_edge_margin_mm",
        f"{detector}_edge_margin_norm",
        f"geom_outside_{detector}",
        f"geom_edge_{detector}",
        f"geom_near_{detector}",
        f"geom_core_{detector}",
    )
) + ("path_scale_z",)
DEFAULT_DERIVED_TARGETS = tuple(
    item
    for detector in DETECTORS
    for item in (
        f"miss_{detector}_primary",
        f"residual_miss_{detector}_primary",
    )
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write an enriched GEM classifier table with geometry regimes and diagnostics.")
    parser.add_argument("--input-csv", required=True)
    parser.add_argument("--output-parquet", required=True)
    parser.add_argument("--geometry-config", required=True)
    parser.add_argument("--diagnostics-json", default=None)
    parser.add_argument("--chunksize", type=int, default=500000)
    parser.add_argument("--edge-band-mm", type=float, default=DEFAULT_EDGE_BAND_MM)
    parser.add_argument("--near-band-mm", type=float, default=DEFAULT_NEAR_BAND_MM)
    args = parser.parse_args(argv)

    geometry = load_geometry_config(args.geometry_config)
    output_path = Path(args.output_parquet)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path = Path(args.diagnostics_json) if args.diagnostics_json else output_path.with_suffix(".diagnostics.json")

    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ModuleNotFoundError as exc:
        raise RuntimeError("pyarrow is required to write enriched parquet output") from exc

    writer = None
    diagnostics = init_diagnostics()
    try:
        for chunk in pd.read_csv(args.input_csv, chunksize=args.chunksize):
            features = build_feature_frame(
                chunk,
                DEFAULT_DERIVED_FEATURES,
                geometry,
                edge_band_mm=args.edge_band_mm,
                near_band_mm=args.near_band_mm,
            )
            targets = build_target_frame(
                chunk,
                DEFAULT_DERIVED_TARGETS,
                geometry,
                edge_band_mm=args.edge_band_mm,
                near_band_mm=args.near_band_mm,
            )
            enriched = pd.concat([chunk.reset_index(drop=True), features.reset_index(drop=True), targets.reset_index(drop=True)], axis=1)
            update_diagnostics(diagnostics, enriched)
            table = pa.Table.from_pandas(enriched, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(output_path, table.schema)
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()

    diagnostics_path.parent.mkdir(parents=True, exist_ok=True)
    diagnostics_path.write_text(json.dumps(finalize_diagnostics(diagnostics), indent=2, sort_keys=True) + "\n")
    print(f"wrote {output_path}")
    print(f"wrote {diagnostics_path}")
    return 0


def init_diagnostics() -> dict[str, Any]:
    return {
        detector: {
            "rows": 0,
            "miss": 0,
            "outside": 0,
            "edge": 0,
            "near": 0,
            "core": 0,
            "outside_miss": 0,
            "edge_miss": 0,
            "near_miss": 0,
            "core_miss": 0,
            "outside_hit": 0,
        }
        for detector in DETECTORS
    }


def update_diagnostics(diagnostics: dict[str, Any], frame: pd.DataFrame) -> None:
    for detector in DETECTORS:
        miss = frame[f"miss_{detector}_primary"] > 0.5
        hit = ~miss
        stats = diagnostics[detector]
        stats["rows"] += int(len(frame))
        stats["miss"] += int(miss.sum())
        for regime in ("outside", "edge", "near", "core"):
            mask = frame[f"geom_{regime}_{detector}"] > 0.5
            stats[regime] += int(mask.sum())
            stats[f"{regime}_miss"] += int((mask & miss).sum())
        outside = frame[f"geom_outside_{detector}"] > 0.5
        stats["outside_hit"] += int((outside & hit).sum())


def finalize_diagnostics(diagnostics: dict[str, Any]) -> dict[str, Any]:
    payload = {"detectors": diagnostics}
    for detector, stats in diagnostics.items():
        rows = max(int(stats["rows"]), 1)
        miss = max(int(stats["miss"]), 1)
        stats["miss_rate"] = stats["miss"] / rows
        stats["outside_rate"] = stats["outside"] / rows
        stats["outside_miss_fraction_of_misses"] = stats["outside_miss"] / miss
        stats["core_residual_miss_rate"] = stats["core_miss"] / max(int(stats["core"]), 1)
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
