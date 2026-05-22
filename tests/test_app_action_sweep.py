"""Tests for the expanded app/action sweep runner."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from examples.run_app_action_sweep import (
    SUMMARY_COLUMNS,
    run_sweep,
    supported_app_actions,
)


def test_supported_app_action_pairs_has_length_20() -> None:
    """The sweep covers all 20 canonical app/action pairs."""
    pairs = supported_app_actions()

    assert len(pairs) == 20
    assert len(set(pairs)) == 20


def test_batch_runner_small_subset_writes_summary(tmp_path: Path) -> None:
    """The sweep runner can execute a small test subset and save summary CSV."""
    subset = [
        ("video", "play"),
        ("social_media", "thumb_up"),
        ("communication", "send_videos"),
    ]
    summary = run_sweep(
        config_path=Path("configs/app_action_sweep_base.yaml"),
        output_dir=tmp_path,
        app_actions=subset,
        save_individual_plots=False,
        save_comparison_plots=False,
    )

    summary_path = tmp_path / "summary.csv"
    assert summary_path.exists()
    reloaded = pd.read_csv(summary_path)
    assert list(summary.columns) == SUMMARY_COLUMNS
    assert list(reloaded.columns) == SUMMARY_COLUMNS
    assert len(summary) == len(subset)
    for app_id, action_id in subset:
        assert (tmp_path / app_id / action_id / "trace.csv").exists()


def test_sweep_summary_preserves_expected_relative_traffic_weights(tmp_path: Path) -> None:
    """Summary metrics expose expected heavy uplink and downlink actions."""
    subset = [
        ("video", "play"),
        ("social_media", "thumb_up"),
        ("communication", "send_text"),
        ("communication", "send_videos"),
    ]
    summary = run_sweep(
        config_path=Path("configs/app_action_sweep_base.yaml"),
        output_dir=tmp_path,
        app_actions=subset,
        save_individual_plots=False,
        save_comparison_plots=False,
    ).set_index(["app_id", "action_id"])

    assert (
        summary.loc[("video", "play"), "total_dl_bytes"]
        > summary.loc[("social_media", "thumb_up"), "total_dl_bytes"]
    )
    assert (
        summary.loc[("communication", "send_videos"), "total_ul_bytes"]
        > summary.loc[("communication", "send_text"), "total_ul_bytes"]
    )
