"""Tests for the v0 end-to-end simulation engine."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np

from rfeh_sim.config import load_config
from rfeh_sim.engine import run_simulation


def test_run_simulation_returns_arrays_of_matching_length() -> None:
    """The engine returns aligned time, RF power, harvested power, and VCAP traces."""
    config = load_config(Path("configs/default_v0.yaml"))
    result = run_simulation(config)

    expected_shape = result.time_s.shape
    assert result.received_power_w.shape == expected_shape
    assert result.harvested_power_w.shape == expected_shape
    assert result.v_cap.shape == expected_shape
    assert result.boost_state.shape == expected_shape
    assert result.capacitor_energy_j.shape == expected_shape
    assert result.net_capacitor_power_w.shape == expected_shape
    assert result.traffic_bursts
    assert result.tx_events


def test_run_simulation_vcap_contains_finite_values() -> None:
    """The end-to-end VCAP trace contains only finite numeric values."""
    config = load_config(Path("configs/default_v0.yaml"))
    result = run_simulation(config)

    assert np.all(np.isfinite(result.v_cap))
    assert np.all(result.v_cap >= 0.0)
    assert np.all(np.isfinite(result.capacitor_energy_j))
    assert np.all(np.isfinite(result.net_capacitor_power_w))


def test_same_config_seed_gives_deterministic_vcap() -> None:
    """Running the same configuration twice produces identical VCAP traces."""
    config = load_config(Path("configs/default_v0.yaml"))
    first = run_simulation(config)
    second = run_simulation(config)

    np.testing.assert_allclose(first.v_cap, second.v_cap)


def test_different_app_action_templates_produce_different_vcap_traces() -> None:
    """Different traffic templates should create measurably different VCAP traces."""
    config = load_config(Path("configs/default_v0.yaml"))
    social_scenario = replace(
        config.scenario,
        app_id="social_app",
        action_id="like",
    )
    social_config = replace(config, scenario=social_scenario)

    video_result = run_simulation(config)
    social_result = run_simulation(social_config)

    assert not np.allclose(video_result.v_cap, social_result.v_cap)


def test_periodic_default_generates_tx_events_across_full_duration() -> None:
    """Periodic default config creates TxEvents near start, middle, and end."""
    config = load_config(Path("configs/default_v0.yaml"))
    result = run_simulation(config)
    event_starts = np.array([event.start_s for event in result.tx_events])

    assert np.any(event_starts < 2.0)
    assert np.any((event_starts >= 25.0) & (event_starts <= 35.0))
    assert np.any((event_starts >= 55.0) & (event_starts < 60.0))


def test_periodic_default_tx_events_do_not_exceed_duration() -> None:
    """Generated TxEvents stay within the simulation time horizon."""
    config = load_config(Path("configs/default_v0.yaml"))
    result = run_simulation(config)

    for event in result.tx_events:
        assert 0.0 <= event.start_s < config.simulation.duration_s
        assert event.duration_s > 0.0
        assert event.start_s + event.duration_s <= config.simulation.duration_s


def test_received_power_above_ambient_during_late_periodic_events() -> None:
    """Repeated late TxEvents raise received RF power above ambient."""
    config = load_config(Path("configs/default_v0.yaml"))
    result = run_simulation(config)
    late = result.time_s > config.simulation.duration_s / 2.0

    assert np.any(result.received_power_w[late] > config.channel.ambient_power_w)
