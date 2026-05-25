"""Tests for the v0 end-to-end simulation engine."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from rfeh_sim.config import load_config
from rfeh_sim.engine import run_simulation
from rfeh_sim.transmitter import generate_tx_events_for_simulation


def test_run_simulation_returns_arrays_of_matching_length() -> None:
    """The engine returns aligned time, RF power, harvested power, and VCAP traces."""
    config = load_config(Path("configs/default_v0.yaml"))
    result = run_simulation(config)

    expected_shape = result.time_s.shape
    assert result.received_power_w.shape == expected_shape
    assert result.received_power_by_source
    assert result.received_power_by_source["phone_1"].shape == expected_shape
    assert result.harvested_power_w.shape == expected_shape
    assert result.v_cap.shape == expected_shape
    assert result.boost_state.shape == expected_shape
    assert result.capacitor_energy_j.shape == expected_shape
    assert result.net_capacitor_power_w.shape == expected_shape
    assert set(result.small_scale_gain_by_source) == {"phone_1", "ap"}
    assert result.traffic_bursts == []
    assert result.action_instances
    assert result.network_transactions
    assert result.chunk_events
    assert result.tx_events


def test_run_simulation_reconstructs_total_received_power_from_sources() -> None:
    """Per-source received traces sum to the total trace after adding ambient."""
    config = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    result = run_simulation(config)

    reconstructed = np.full(
        result.time_s.shape,
        config.channel.ambient_power_w,
        dtype=float,
    )
    for source_power_w in result.received_power_by_source.values():
        reconstructed += source_power_w

    assert set(result.received_power_by_source) == {"phone_1", "ap"}
    np.testing.assert_allclose(result.received_power_w, reconstructed)


def test_closer_source_has_higher_equal_eirp_contribution() -> None:
    """Different source distances are visible in per-source received power."""
    base = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    config = replace(
        base,
        simulation=replace(base.simulation, duration_s=1.0),
        scenario=replace(
            base.scenario,
            ap=None,
            mobile_devices=(),
            mobile_distance_m=0.3,
            ap_distance_m=1.0,
            source_distances_m={},
        ),
        channel=replace(base.channel, small_scale=replace(base.channel.small_scale, enabled=False, model="none")),
    )
    time_s = np.array([0.0])

    from rfeh_sim.channel import received_power_by_source_trace
    from rfeh_sim.models import TxEvent
    from rfeh_sim.units import dbm_to_watt

    by_source = received_power_by_source_trace(
        [
            TxEvent(
                source_id="mobile",
                start_s=0.0,
                duration_s=1.0,
                eirp_w=dbm_to_watt(15.0),
                center_freq_hz=2.437e9,
                label="mobile_equal_eirp",
            ),
            TxEvent(
                source_id="ap",
                start_s=0.0,
                duration_s=1.0,
                eirp_w=dbm_to_watt(15.0),
                center_freq_hz=2.437e9,
                label="ap_equal_eirp",
            ),
        ],
        time_s,
        config.scenario,
        config.channel,
    )

    assert by_source["mobile"][0] > by_source["ap"][0]


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


def test_fading_enabled_result_contains_small_scale_gain() -> None:
    """Fading-enabled configs expose per-source small-scale gain traces."""
    config = load_config(Path("configs/small_scale_fading_v0.yaml"))
    result = run_simulation(config)

    assert set(result.small_scale_gain_by_source) == {"mobile"}
    gain = result.small_scale_gain_by_source["mobile"]
    assert gain.shape == result.time_s.shape
    assert np.mean(gain) == pytest.approx(1.0)


def test_burst_transmitter_model_still_works() -> None:
    """The default burst transmitter path remains available."""
    config = load_config(Path("configs/periodic_transmitter_v0.yaml"))
    result = run_simulation(config)

    assert config.transmitter.model == "burst"
    assert result.traffic_bursts
    assert result.tx_events
    assert {event.source_id for event in result.tx_events} == {"mobile"}


def test_transaction_transmitter_model_produces_tx_events() -> None:
    """The transaction transmitter path produces RF TxEvents."""
    config = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    result = run_simulation(config)

    assert config.transmitter.model == "transaction"
    assert result.action_instances
    assert result.network_transactions
    assert result.chunk_events
    assert result.tx_events


def test_transaction_transmitter_includes_mobile_and_ap_sources() -> None:
    """Transaction mode produces both mobile and AP source IDs."""
    config = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    result = run_simulation(config)

    source_ids = {event.source_id for event in result.tx_events}
    assert "phone_1" in source_ids
    assert "ap" in source_ids


def test_video_play_has_more_ap_data_airtime_than_mobile_data_airtime() -> None:
    """Video playback is downlink-heavy in transaction mode."""
    base = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    config = replace(
        base,
        scenario=replace(base.scenario, app_id="video_app", action_id="play_video"),
    )
    result = run_simulation(config)

    ap_data_airtime = sum(
        event.duration_s
        for event in result.tx_events
        if event.source_id == "ap" and event.frame_type == "data"
    )
    mobile_data_airtime = sum(
        event.duration_s
        for event in result.tx_events
        if event.source_type == "mobile" and event.frame_type == "data"
    )

    assert ap_data_airtime > mobile_data_airtime


def test_social_share_has_more_mobile_uplink_airtime_than_like() -> None:
    """Social sharing is uplink-heavier than a social like."""
    base = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    like_config = replace(
        base,
        scenario=replace(base.scenario, app_id="social_app", action_id="like"),
    )
    share_config = replace(
        base,
        scenario=replace(base.scenario, app_id="social_app", action_id="share"),
    )
    like_result = run_simulation(like_config)
    share_result = run_simulation(share_config)

    like_mobile_data_airtime = sum(
        event.duration_s
        for event in like_result.tx_events
        if event.source_type == "mobile" and event.frame_type == "data"
    )
    share_mobile_data_airtime = sum(
        event.duration_s
        for event in share_result.tx_events
        if event.source_type == "mobile" and event.frame_type == "data"
    )

    assert share_mobile_data_airtime > like_mobile_data_airtime


def test_transaction_tx_events_appear_after_30s() -> None:
    """Periodic transaction mode emits TxEvents late in a 60 s simulation."""
    config = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    result = run_simulation(config)

    assert any(event.start_s > 30.0 for event in result.tx_events)


def test_engine_returns_vcap_with_transaction_transmitter() -> None:
    """The full simulator completes with transaction transmitter mode."""
    config = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    result = run_simulation(config)

    assert result.v_cap.shape == result.time_s.shape
    assert np.all(np.isfinite(result.v_cap))
    assert np.all(result.v_cap >= 0.0)


def test_transaction_transmitter_pipeline_is_deterministic() -> None:
    """Same seed reproduces all transaction transmitter intermediates and TxEvents."""
    config = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    first = generate_tx_events_for_simulation(config)
    second = generate_tx_events_for_simulation(config)

    assert first.action_instances == second.action_instances
    assert first.network_transactions == second.network_transactions
    assert first.chunk_events == second.chunk_events
    assert first.tx_events == second.tx_events


def test_transaction_transmitter_source_counts_are_representative() -> None:
    """Video transaction mode produces many AP events and mobile ACK/data events."""
    config = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    result = run_simulation(config)

    ap_count = sum(event.source_id == "ap" for event in result.tx_events)
    mobile_count = sum(event.source_type == "mobile" for event in result.tx_events)
    assert ap_count > 0
    assert mobile_count > 0
    assert ap_count > mobile_count * 0.25


def test_transaction_tx_events_core_invariants() -> None:
    """Transaction-mode TxEvents have valid timing, sources, and durations."""
    config = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    result = run_simulation(config)

    assert result.tx_events
    for event in result.tx_events:
        assert event.source_id
        assert event.source_id in {"phone_1", "ap"}
        assert event.source_type in {"mobile", "ap"}
        assert event.start_s >= 0.0
        assert event.start_s + event.duration_s <= config.simulation.duration_s
        assert event.duration_s > 0.0
