"""Smoke tests for the runnable v0 example."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from examples.run_v0 import print_diagnostic_summary, run_example
from rfeh_sim.io import TRACE_COLUMNS
from rfeh_sim.config import load_config
from rfeh_sim.engine import run_simulation


def test_run_v0_example_writes_expected_outputs(tmp_path: Path) -> None:
    """The v0 example writes a trace CSV and plot image files."""
    (
        csv_path,
        vcap_path,
        received_power_path,
        boost_state_path,
        small_scale_gain_path,
    ) = run_example(
        config_path=Path("configs/default_v0.yaml"),
        output_dir=tmp_path,
    )

    assert csv_path.exists()
    assert vcap_path.exists()
    assert received_power_path.exists()
    assert boost_state_path.exists()
    assert small_scale_gain_path.exists()
    assert vcap_path.stat().st_size > 0
    assert received_power_path.stat().st_size > 0
    assert boost_state_path.stat().st_size > 0
    assert small_scale_gain_path.stat().st_size > 0

    trace = pd.read_csv(csv_path)
    assert list(trace.columns) == TRACE_COLUMNS
    assert not trace.empty


def test_run_v0_example_writes_small_scale_gain_when_enabled(tmp_path: Path) -> None:
    """The fading example writes small-scale gain diagnostics to CSV and PNG."""
    csv_path, *_, small_scale_gain_path = run_example(
        config_path=Path("configs/small_scale_fading_v0.yaml"),
        output_dir=tmp_path,
    )

    trace = pd.read_csv(csv_path)
    assert "small_scale_gain_mobile" in trace.columns
    assert small_scale_gain_path.exists()
    assert small_scale_gain_path.stat().st_size > 0


def test_diagnostic_summary_runs_without_error(capsys: pytest.CaptureFixture[str]) -> None:
    """The example diagnostic summary prints fading and received-power stats."""
    config = load_config(Path("configs/small_scale_fading_v0.yaml"))
    result = run_simulation(config)

    print_diagnostic_summary(config, result)

    output = capsys.readouterr().out
    assert "Small-scale model: rician" in output
    assert "Mean received power:" in output
