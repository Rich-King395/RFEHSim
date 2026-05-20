"""Tests for the v0 fixed-distance wireless channel model."""

from __future__ import annotations

import numpy as np
import pytest

from rfeh_sim.channel import (
    free_space_path_loss_db,
    log_distance_path_loss_db,
    received_power_trace,
)
from rfeh_sim.models import ChannelConfig, ScenarioConfig, TxEvent
from rfeh_sim.units import db_to_linear, dbm_to_watt


def _scenario_config(distance_m: float = 1.5) -> ScenarioConfig:
    """Create a representative fixed-distance scenario."""
    return ScenarioConfig(
        app_id="video_app",
        action_id="play_video",
        distance_m=distance_m,
        frequency_hz=2.437e9,
    )


def _channel_config() -> ChannelConfig:
    """Create a representative log-distance channel config."""
    return ChannelConfig(
        path_loss_exponent=2.2,
        reference_distance_m=1.0,
        shadowing_db=0.0,
        ambient_power_w=dbm_to_watt(-30.0),
    )


def _tx_event() -> TxEvent:
    """Create a representative active TxEvent."""
    return TxEvent(
        source_id="mobile",
        start_s=0.20,
        duration_s=0.30,
        eirp_w=dbm_to_watt(15.0),
        center_freq_hz=2.437e9,
        label="request",
    )


def test_path_loss_increases_with_distance() -> None:
    """Log-distance path loss should grow as transmitter distance increases."""
    near_loss_db = log_distance_path_loss_db(
        distance_m=1.0,
        frequency_hz=2.437e9,
        reference_distance_m=1.0,
        path_loss_exponent=2.2,
    )
    far_loss_db = log_distance_path_loss_db(
        distance_m=3.0,
        frequency_hz=2.437e9,
        reference_distance_m=1.0,
        path_loss_exponent=2.2,
    )

    assert far_loss_db > near_loss_db


def test_free_space_path_loss_doubles_distance_by_six_db() -> None:
    """Free-space path loss follows the expected 20 log10(d) law."""
    loss_1m_db = free_space_path_loss_db(distance_m=1.0, frequency_hz=2.437e9)
    loss_2m_db = free_space_path_loss_db(distance_m=2.0, frequency_hz=2.437e9)

    assert loss_2m_db - loss_1m_db == pytest.approx(20.0 * np.log10(2.0))


def test_path_gain_decreases_with_distance() -> None:
    """The linear path gain implied by path loss decreases with distance."""
    near_loss_db = log_distance_path_loss_db(
        distance_m=1.0,
        frequency_hz=2.437e9,
        reference_distance_m=1.0,
        path_loss_exponent=2.2,
    )
    far_loss_db = log_distance_path_loss_db(
        distance_m=3.0,
        frequency_hz=2.437e9,
        reference_distance_m=1.0,
        path_loss_exponent=2.2,
    )

    assert db_to_linear(-far_loss_db) < db_to_linear(-near_loss_db)


def test_received_power_without_tx_events_equals_ambient() -> None:
    """With no active transmitter, the channel returns ambient RF power only."""
    channel_config = _channel_config()
    time_s = np.linspace(0.0, 1.0, 11)
    trace = received_power_trace(
        [],
        time_s,
        _scenario_config(),
        channel_config,
    )

    np.testing.assert_allclose(trace, channel_config.ambient_power_w)


def test_received_power_is_at_least_ambient_power() -> None:
    """The received trace includes ambient RF power as a lower bound."""
    channel_config = _channel_config()
    time_s = np.linspace(0.0, 1.0, 11)
    trace = received_power_trace(
        [_tx_event()],
        time_s,
        _scenario_config(),
        channel_config,
    )

    assert np.all(trace >= channel_config.ambient_power_w)


def test_received_power_increases_during_active_tx_event() -> None:
    """Active TxEvents add received RF power above the ambient level."""
    channel_config = _channel_config()
    time_s = np.array([0.1, 0.25, 0.35, 0.6])
    trace = received_power_trace(
        [_tx_event()],
        time_s,
        _scenario_config(),
        channel_config,
    )

    assert trace[0] == pytest.approx(channel_config.ambient_power_w)
    assert trace[1] > channel_config.ambient_power_w
    assert trace[2] > channel_config.ambient_power_w
    assert trace[3] == pytest.approx(channel_config.ambient_power_w)


def test_received_power_trace_shape_matches_time_shape() -> None:
    """The output trace shape follows the input time grid shape."""
    time_s = np.linspace(0.0, 1.0, 101)
    trace = received_power_trace(
        [_tx_event()],
        time_s,
        _scenario_config(),
        _channel_config(),
    )

    assert trace.shape == time_s.shape


def test_received_power_rejects_non_finite_time_values() -> None:
    """Non-finite time samples are rejected before trace calculations."""
    with pytest.raises(ValueError, match="time_s"):
        received_power_trace(
            [_tx_event()],
            np.array([0.0, np.nan]),
            _scenario_config(),
            _channel_config(),
        )
