"""Smoke tests for the runnable v0 example."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from examples.run_v0 import run_example
from rfeh_sim.io import TRACE_COLUMNS


def test_run_v0_example_writes_expected_outputs(tmp_path: Path) -> None:
    """The v0 example writes a trace CSV and plot image files."""
    csv_path, vcap_path, received_power_path, boost_state_path = run_example(
        config_path=Path("configs/default_v0.yaml"),
        output_dir=tmp_path,
    )

    assert csv_path.exists()
    assert vcap_path.exists()
    assert received_power_path.exists()
    assert boost_state_path.exists()
    assert vcap_path.stat().st_size > 0
    assert received_power_path.stat().st_size > 0
    assert boost_state_path.stat().st_size > 0

    trace = pd.read_csv(csv_path)
    assert list(trace.columns) == TRACE_COLUMNS
    assert not trace.empty
