from __future__ import annotations

import pandas as pd

from src.ml.python.training.residual_rates import residual_core_rate_tables


def test_residual_rate_tables_filter_to_core_and_compare_model_to_rate_baseline():
    label = "residual_miss_gem0_primary"
    frame = pd.DataFrame(
        {
            f"target__{label}": [1.0, 0.0, 0.0, 1.0, 0.0, 1.0],
            f"prob__{label}": [0.8, 0.2, 0.1, 0.7, 0.3, 0.9],
            f"regime__{label}": ["core", "core", "near", "core", "core", "outside"],
            "beam_p_mev": [100.0, 110.0, 120.0, 130.0, 140.0, 150.0],
            "xprime": [-0.2, -0.1, 0.0, 0.1, 0.2, 0.3],
            "yprime": [0.3, 0.2, 0.1, 0.0, -0.1, -0.2],
            "path_scale_z": [1.0, 1.1, 1.2, 1.3, 1.4, 1.5],
        }
    )

    metrics, rates = residual_core_rate_tables(frame, (label,), quantile_bins=2, smoothing=0.5, min_bin_count=1)

    assert metrics.loc[0, "label"] == label
    assert metrics.loc[0, "detector"] == "gem0"
    assert metrics.loc[0, "count"] == 4
    assert metrics.loc[0, "positives"] == 2
    assert "model_brier" in metrics.columns
    assert "rate_baseline_brier" in metrics.columns
    assert not rates.empty
    assert set(rates["label"]) == {label}
    assert rates["count"].sum() == 4
    assert "beam_p_mev_bin" in rates.columns
