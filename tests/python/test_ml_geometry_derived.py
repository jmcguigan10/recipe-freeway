from __future__ import annotations

import pandas as pd

from src.ml.python.data.derived import build_feature_frame, build_target_frame


def test_geometry_regimes_and_residual_targets_use_configured_bands():
    geometry = {
        "detectors": {
            "gem0": {
                "z_mm": 0.0,
                "center_x_mm": 0.0,
                "center_y_mm": 0.0,
                "shape": "rect",
                "half_width_mm": 10.0,
                "half_height_mm": 10.0,
            }
        }
    }
    frame = pd.DataFrame(
        {
            "x0_mm": [11.0, 9.0, 6.0, 0.0],
            "y0_mm": [0.0, 0.0, 0.0, 0.0],
            "z0_mm": [0.0, 0.0, 0.0, 0.0],
            "xprime": [0.0, 0.0, 0.0, 0.0],
            "yprime": [0.0, 0.0, 0.0, 0.0],
            "hit_gem0_primary": [1.0, 0.0, 0.0, 0.0],
        }
    )

    features = build_feature_frame(
        frame,
        (
            "gem0_edge_margin_mm",
            "geom_outside_gem0",
            "geom_edge_gem0",
            "geom_near_gem0",
            "geom_core_gem0",
        ),
        geometry,
        edge_band_mm=2.0,
        near_band_mm=5.0,
    )
    targets = build_target_frame(
        frame,
        ("miss_gem0_primary", "residual_miss_gem0_primary"),
        geometry,
        edge_band_mm=2.0,
        near_band_mm=5.0,
    )

    assert features["gem0_edge_margin_mm"].tolist() == [-1.0, 1.0, 4.0, 10.0]
    assert features["geom_outside_gem0"].tolist() == [1.0, 0.0, 0.0, 0.0]
    assert features["geom_edge_gem0"].tolist() == [0.0, 1.0, 0.0, 0.0]
    assert features["geom_near_gem0"].tolist() == [0.0, 0.0, 1.0, 0.0]
    assert features["geom_core_gem0"].tolist() == [0.0, 0.0, 0.0, 1.0]
    assert targets["miss_gem0_primary"].tolist() == [0.0, 1.0, 1.0, 1.0]
    assert targets["residual_miss_gem0_primary"].tolist() == [0.0, 0.0, 0.0, 1.0]
