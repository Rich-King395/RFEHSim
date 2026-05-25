"""Tests for the v0 transmitter model."""

from __future__ import annotations

import pytest

from rfeh_sim.models import ScenarioConfig, TrafficBurst, TransmitterConfig, TxEvent
from rfeh_sim.transmitter import bursts_to_tx_events
from rfeh_sim.units import dbm_to_watt


def _sample_bursts() -> list[TrafficBurst]:
    """Create representative synthetic traffic bursts for transmitter tests."""
    return [
        TrafficBurst(
            start_s=0.10,
            duration_s=0.25,
            power_scale=1.0,
            direction="uplink",
            label="request",
        ),
        TrafficBurst(
            start_s=0.50,
            duration_s=0.40,
            power_scale=0.6,
            direction="mixed",
            label="sync",
        ),
    ]


def _transmitter_config() -> TransmitterConfig:
    """Create a transmitter config with a dBm boundary converted to Watts."""
    return TransmitterConfig(default_eirp_w=dbm_to_watt(15.0))


def _scenario_config() -> ScenarioConfig:
    """Create a scenario config with a valid RF center frequency."""
    return ScenarioConfig(
        app_id="chat_app",
        action_id="send_message",
        distance_m=1.5,
        frequency_hz=2.437e9,
    )


def test_tx_events_are_generated_for_each_burst() -> None:
    """The v0 transmitter emits one RF event for each traffic burst."""
    bursts = _sample_bursts()
    events = bursts_to_tx_events(
        bursts,
        _transmitter_config(),
        _scenario_config(),
        seed=42,
    )

    assert len(events) == len(bursts)
    assert all(isinstance(event, TxEvent) for event in events)
    assert all(event.source_id == "mobile" for event in events)


def test_tx_event_eirp_is_positive_and_in_watts() -> None:
    """Generated EIRP values are positive Watt-scale powers."""
    events = bursts_to_tx_events(
        _sample_bursts(),
        _transmitter_config(),
        _scenario_config(),
        seed=42,
    )

    for event in events:
        assert event.eirp_w > 0.0
        assert event.eirp_w == pytest.approx(event.eirp_w)
        assert event.eirp_w < 1.0


def test_same_seed_gives_deterministic_events() -> None:
    """Transmitter jitter is deterministic for the same input seed."""
    first = bursts_to_tx_events(
        _sample_bursts(),
        _transmitter_config(),
        _scenario_config(),
        seed=7,
    )
    second = bursts_to_tx_events(
        _sample_bursts(),
        _transmitter_config(),
        _scenario_config(),
        seed=7,
    )

    assert first == second


def test_event_timing_stays_within_burst_timing() -> None:
    """TxEvents stay inside their source TrafficBurst timing windows."""
    bursts = _sample_bursts()
    events = bursts_to_tx_events(
        bursts,
        _transmitter_config(),
        _scenario_config(),
        seed=123,
    )

    for burst, event in zip(bursts, events, strict=True):
        assert event.start_s >= burst.start_s
        assert event.duration_s > 0.0
        assert event.start_s + event.duration_s <= burst.start_s + burst.duration_s
