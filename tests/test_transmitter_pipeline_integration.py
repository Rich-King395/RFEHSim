"""Integration tests for all canonical app/action transmitter pipelines."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from rfeh_sim.app_actions import CANONICAL_APP_ACTIONS
from rfeh_sim.config import load_config
from rfeh_sim.engine import run_simulation
from rfeh_sim.models import FullConfig

ALL_APP_ACTIONS = [
    (app_id, action_id)
    for app_id, action_ids in CANONICAL_APP_ACTIONS.items()
    for action_id in action_ids
]

DOWNLINK_HEAVY_ACTIONS = {
    ("video", "play"),
    ("video", "next"),
    ("video", "forward"),
    ("music", "play"),
    ("game", "loading"),
}

UPLINK_HEAVY_ACTIONS = {
    ("communication", "send_images"),
    ("communication", "send_videos"),
    ("communication", "send_voice"),
    ("social_media", "comment"),
    ("social_media", "share"),
}


def _integration_config(app_id: str, action_id: str) -> FullConfig:
    """Create a short deterministic transaction-mode config for one action."""
    base = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    return replace(
        base,
        simulation=replace(
            base.simulation,
            duration_s=30.0,
            dt_s=0.01,
            seed=42,
        ),
        scenario=replace(
            base.scenario,
            app_id=app_id,
            action_id=action_id,
        ),
        app_traffic=replace(
            base.app_traffic,
            repeat_mode="none",
            jitter_s=0.0,
            start_offset_s=0.0,
            repeat_until_end=False,
        ),
        channel=replace(
            base.channel,
            small_scale=replace(base.channel.small_scale, enabled=False, model="none"),
        ),
    )


@pytest.mark.parametrize(("app_id", "action_id"), ALL_APP_ACTIONS)
def test_all_canonical_app_actions_run_end_to_end(
    app_id: str,
    action_id: str,
) -> None:
    """Every canonical app/action reaches Action, Transaction, Chunk, TxEvent, and VCAP."""
    config = _integration_config(app_id, action_id)
    result = run_simulation(config)

    assert result.action_instances
    assert result.network_transactions
    assert result.chunk_events
    assert result.tx_events
    assert result.v_cap.shape == result.time_s.shape
    assert np.all(np.isfinite(result.v_cap))
    assert np.all(result.v_cap >= 0.0)
    assert np.all(result.received_power_w >= 0.0)

    event_starts = [event.start_s for event in result.tx_events]
    assert event_starts == sorted(event_starts)
    for event in result.tx_events:
        assert event.source_id in {"phone_1", "ap"}
        assert event.source_type in {"mobile", "ap"}
        assert event.start_s >= 0.0
        assert event.duration_s > 0.0
        assert event.start_s + event.duration_s <= config.simulation.duration_s


@pytest.mark.parametrize(("app_id", "action_id"), sorted(DOWNLINK_HEAVY_ACTIONS))
def test_downlink_heavy_actions_produce_ap_data_and_mobile_acks(
    app_id: str,
    action_id: str,
) -> None:
    """Downlink-heavy actions create AP data events and mobile ACK events."""
    result = run_simulation(_integration_config(app_id, action_id))

    assert any(
        event.source_id == "ap" and event.frame_type == "data"
        for event in result.tx_events
    )
    assert any(
        event.source_type == "mobile" and event.frame_type in {"mac_ack", "transport_ack"}
        for event in result.tx_events
    )


@pytest.mark.parametrize(("app_id", "action_id"), sorted(UPLINK_HEAVY_ACTIONS))
def test_uplink_heavy_actions_produce_mobile_data_events(
    app_id: str,
    action_id: str,
) -> None:
    """Uplink-heavy actions create mobile data TxEvents."""
    result = run_simulation(_integration_config(app_id, action_id))

    assert any(
        event.source_type == "mobile"
        and event.frame_type == "data"
        and event.direction == "uplink"
        for event in result.tx_events
    )


def test_game_gaming_tx_events_are_distributed_over_time() -> None:
    """Gaming updates produce repeated TxEvents spread over time."""
    result = run_simulation(_integration_config("game", "gaming"))
    data_event_starts = np.array(
        [
            event.start_s
            for event in result.tx_events
            if event.frame_type == "data"
        ]
    )

    assert data_event_starts.size >= 20
    assert np.ptp(data_event_starts) > 1.0
    assert np.unique(np.round(data_event_starts, decimals=3)).size > 10


def test_all_canonical_app_actions_are_deterministic() -> None:
    """The full transmitter pipeline is deterministic for the same seed."""
    config = _integration_config("communication", "send_videos")

    first = run_simulation(config)
    second = run_simulation(config)

    assert first.action_instances == second.action_instances
    assert first.network_transactions == second.network_transactions
    assert first.chunk_events == second.chunk_events
    assert first.tx_events == second.tx_events
    np.testing.assert_allclose(first.v_cap, second.v_cap)
