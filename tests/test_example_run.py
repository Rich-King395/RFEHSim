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
    (tmp_path / "boost_state.png").write_text("stale", encoding="utf-8")
    (tmp_path / "small_scale_gain.png").write_text("stale", encoding="utf-8")

    (
        settings_path,
        csv_path,
        tx_events_csv_path,
        vcap_path,
        received_power_path,
        per_source_received_power_path,
        tx_events_timeline_path,
    ) = run_example(
        config_path=Path("configs/default_v0.yaml"),
        output_dir=tmp_path,
    )

    assert settings_path.exists()
    assert csv_path.exists()
    assert tx_events_csv_path.exists()
    assert vcap_path.exists()
    assert received_power_path.exists()
    assert per_source_received_power_path.exists()
    assert tx_events_timeline_path.exists()
    assert settings_path.stat().st_size > 0
    assert tx_events_csv_path.stat().st_size > 0
    assert vcap_path.stat().st_size > 0
    assert received_power_path.stat().st_size > 0
    assert per_source_received_power_path.stat().st_size > 0
    assert tx_events_timeline_path.stat().st_size > 0
    assert not (tmp_path / "boost_state.png").exists()
    assert not (tmp_path / "small_scale_gain.png").exists()

    settings_text = settings_path.read_text(encoding="utf-8")
    assert "Number of mobile devices: 1" in settings_text
    assert "simulation.duration_s:" in settings_text
    assert "scenario.mobile_devices[0].device_id:" not in settings_text
    assert "YAML settings: start" in settings_text

    trace = pd.read_csv(csv_path)
    assert list(trace.columns) == TRACE_COLUMNS + [
        "received_power_ap_w",
        "received_power_phone_1_w",
    ]
    assert "boost_state" not in trace.columns
    assert not any(column.startswith("small_scale_gain_") for column in trace.columns)
    assert not trace.empty

    tx_events = pd.read_csv(tx_events_csv_path)
    assert list(tx_events.columns) == [
        "source_id",
        "source_type",
        "device_id",
        "target_device_id",
        "start_s",
        "duration_s",
        "eirp_w",
        "direction",
        "frame_type",
        "payload_bytes",
        "phy_rate_bps",
        "label",
    ]
    assert not tx_events.empty


def test_run_v0_example_omits_small_scale_gain_when_enabled(tmp_path: Path) -> None:
    """The fading example omits small-scale gain from user-facing outputs."""
    _, csv_path, *_ = run_example(
        config_path=Path("configs/small_scale_fading_v0.yaml"),
        output_dir=tmp_path,
    )

    trace = pd.read_csv(csv_path)
    assert "received_power_mobile_w" in trace.columns
    assert "small_scale_gain_mobile" not in trace.columns
    assert not (tmp_path / "small_scale_gain.png").exists()


def test_run_v0_example_writes_mobile_ap_source_diagnostics(tmp_path: Path) -> None:
    """Transaction mode writes per-source CSV columns and plot diagnostics."""
    (
        settings_path,
        csv_path,
        tx_events_csv_path,
        *_,
        per_source_received_power_path,
        tx_events_timeline_path,
    ) = run_example(
        config_path=Path("configs/transaction_transmitter_v1.yaml"),
        output_dir=tmp_path,
    )

    assert settings_path.exists()
    trace = pd.read_csv(csv_path)
    assert "received_power_phone_1_w" in trace.columns
    assert "received_power_ap_w" in trace.columns
    tx_events = pd.read_csv(tx_events_csv_path)
    assert set(tx_events["source_id"]) >= {"phone_1", "ap"}
    assert per_source_received_power_path.exists()
    assert per_source_received_power_path.stat().st_size > 0
    assert tx_events_timeline_path.exists()


def test_run_v0_example_writes_multi_mobile_diagnostics(tmp_path: Path) -> None:
    """The example writes multi-mobile CSV columns, TxEvents, and plots."""
    (
        settings_path,
        csv_path,
        tx_events_csv_path,
        _,
        _,
        per_source_received_power_path,
        tx_events_timeline_path,
    ) = run_example(
        config_path=Path("configs/multi_mobile_v1.yaml"),
        output_dir=tmp_path,
    )

    settings_text = settings_path.read_text(encoding="utf-8")
    assert "Number of mobile devices: 3" in settings_text
    assert "scenario.mobile_devices[0].device_id: phone_1" in settings_text
    assert "scenario.mobile_devices[1].device_id: phone_2" in settings_text
    assert "scenario.mobile_devices[2].device_id: phone_3" in settings_text

    trace = pd.read_csv(csv_path)
    assert "received_power_phone_1_w" in trace.columns
    assert "received_power_phone_2_w" in trace.columns
    assert "received_power_phone_3_w" in trace.columns
    assert "received_power_ap_0_w" in trace.columns

    tx_events = pd.read_csv(tx_events_csv_path)
    assert {"phone_1", "phone_2", "phone_3", "ap_0"}.issubset(
        set(tx_events["source_id"])
    )
    assert per_source_received_power_path.exists()
    assert per_source_received_power_path.stat().st_size > 0
    assert tx_events_timeline_path.exists()
    assert tx_events_timeline_path.stat().st_size > 0


def test_diagnostic_summary_runs_without_error(capsys: pytest.CaptureFixture[str]) -> None:
    """The example diagnostic summary prints fading and received-power stats."""
    config = load_config(Path("configs/small_scale_fading_v0.yaml"))
    result = run_simulation(config)

    print_diagnostic_summary(config, result)

    output = capsys.readouterr().out
    assert "Mobile devices:" in output
    assert "Small-scale model: rician" in output
    assert "TxEvent sources: mobile" in output
    assert "Source: mobile" in output
    assert "Mean receiver total RF power:" in output
    assert "Final V_CAP:" in output


def test_multi_mobile_diagnostic_summary_runs_without_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The diagnostic summary reports multi-mobile transmitter details."""
    config = load_config(Path("configs/multi_mobile_v1.yaml"))
    result = run_simulation(config)

    print_diagnostic_summary(config, result)

    output = capsys.readouterr().out
    assert "Mobile devices: 3" in output
    assert "Device IDs: phone_1, phone_2, phone_3" in output
    assert "Source: phone_1" in output
    assert "Source: phone_2" in output
    assert "Source: phone_3" in output
    assert "Source: ap_0" in output
    assert "Device payload bytes: phone_1" in output
    assert "Device payload bytes: phone_2" in output
    assert "Device payload bytes: phone_3" in output
