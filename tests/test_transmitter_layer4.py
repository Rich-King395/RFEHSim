"""Tests for Transmitter v1 Layer 4 Wi-Fi TxEvent generation."""

from __future__ import annotations

import numpy as np

from rfeh_sim.channel import received_power_trace
from rfeh_sim.models import (
    ActionInstance,
    ChannelConfig,
    ChunkEvent,
    ScenarioConfig,
    TransmitterConfig,
    WifiConfig,
)
from rfeh_sim.transmitter import (
    chunks_to_tx_events,
    generate_network_transactions,
    transactions_to_chunks,
)
from rfeh_sim.units import dbm_to_watt


def _transmitter_config(std_db: float = 0.0) -> TransmitterConfig:
    """Create transmitter config for Layer 4 tests."""
    return TransmitterConfig(
        default_eirp_w=dbm_to_watt(15.0),
        model="transaction",
        mobile_eirp_w_mean=dbm_to_watt(15.0),
        mobile_eirp_dbm_std=std_db,
        ap_eirp_w_mean=dbm_to_watt(20.0),
        ap_eirp_dbm_std=std_db,
    )


def _wifi_config(
    *,
    mobile_phy_rate_bps: float = 54e6,
    ap_phy_rate_bps: float = 54e6,
    mac_ack_enabled: bool = False,
    transport_ack_enabled: bool = False,
    transport_ack_ratio: float = 0.0,
) -> WifiConfig:
    """Create Wi-Fi config for Layer 4 tests."""
    return WifiConfig(
        center_freq_hz=2.437e9,
        bandwidth_hz=20e6,
        chunk_payload_bytes=1500,
        mac_overhead_bytes=64,
        preamble_s=4.0e-5,
        mobile_phy_rate_bps=mobile_phy_rate_bps,
        ap_phy_rate_bps=ap_phy_rate_bps,
        mac_ack_enabled=mac_ack_enabled,
        sifs_s=1.6e-5,
        mac_ack_duration_s=4.0e-5,
        mac_ack_eirp_w=dbm_to_watt(10.0),
        transport_ack_enabled=transport_ack_enabled,
        transport_ack_ratio=transport_ack_ratio,
    )


def _chunk(
    *,
    start_s: float = 0.1,
    payload_bytes: int = 1500,
    direction: str = "uplink",
) -> ChunkEvent:
    """Create a ChunkEvent for Layer 4 tests."""
    return ChunkEvent(
        start_s=start_s,
        payload_bytes=payload_bytes,
        direction=direction,
        transaction_label="test_transaction",
        action_instance_id=0,
    )


def test_uplink_chunk_creates_mobile_tx_event() -> None:
    """Uplink chunks become mobile data TxEvents."""
    events = chunks_to_tx_events(
        [_chunk(direction="uplink")],
        _transmitter_config(),
        _wifi_config(),
        seed=42,
    )

    assert len(events) == 1
    assert events[0].source_id == "mobile"
    assert events[0].direction == "uplink"
    assert events[0].frame_type == "data"


def test_downlink_chunk_creates_ap_tx_event() -> None:
    """Downlink chunks become AP data TxEvents."""
    events = chunks_to_tx_events(
        [_chunk(direction="downlink")],
        _transmitter_config(),
        _wifi_config(),
        seed=42,
    )

    assert len(events) == 1
    assert events[0].source_id == "ap"
    assert events[0].direction == "downlink"
    assert events[0].frame_type == "data"


def test_tx_event_duration_increases_with_payload_bytes() -> None:
    """Larger payload chunks produce longer TxEvent airtime."""
    events = chunks_to_tx_events(
        [
            _chunk(payload_bytes=500, start_s=0.1),
            _chunk(payload_bytes=1500, start_s=0.2),
        ],
        _transmitter_config(),
        _wifi_config(),
        seed=42,
    )

    assert events[1].duration_s > events[0].duration_s


def test_higher_phy_rate_produces_shorter_duration() -> None:
    """Higher PHY rate reduces the simplified airtime."""
    chunk = _chunk(payload_bytes=1500)
    slow = chunks_to_tx_events(
        [chunk],
        _transmitter_config(),
        _wifi_config(mobile_phy_rate_bps=6e6),
        seed=42,
    )[0]
    fast = chunks_to_tx_events(
        [chunk],
        _transmitter_config(),
        _wifi_config(mobile_phy_rate_bps=54e6),
        seed=42,
    )[0]

    assert fast.duration_s < slow.duration_s


def test_eirp_is_positive_and_in_watts() -> None:
    """Layer 4 EIRP values are positive Watt-scale powers."""
    events = chunks_to_tx_events(
        [_chunk(direction="uplink"), _chunk(direction="downlink", start_s=0.2)],
        _transmitter_config(),
        _wifi_config(),
        seed=42,
    )

    assert all(event.eirp_w > 0.0 for event in events)
    assert all(event.eirp_w < 1.0 for event in events)


def test_same_seed_gives_identical_tx_events() -> None:
    """Layer 4 EIRP jitter is deterministic for the same seed."""
    chunks = [_chunk(direction="uplink"), _chunk(direction="downlink", start_s=0.2)]
    first = chunks_to_tx_events(chunks, _transmitter_config(std_db=1.0), _wifi_config(), seed=7)
    second = chunks_to_tx_events(chunks, _transmitter_config(std_db=1.0), _wifi_config(), seed=7)

    assert first == second


def test_different_seed_changes_eirp_when_std_positive() -> None:
    """Different seeds change sampled EIRP when EIRP std is positive."""
    chunks = [_chunk(direction="uplink"), _chunk(direction="downlink", start_s=0.2)]
    first = chunks_to_tx_events(chunks, _transmitter_config(std_db=1.0), _wifi_config(), seed=7)
    second = chunks_to_tx_events(chunks, _transmitter_config(std_db=1.0), _wifi_config(), seed=8)

    assert [event.eirp_w for event in first] != [event.eirp_w for event in second]


def test_tx_events_are_sorted_by_start_time() -> None:
    """Layer 4 returns TxEvents sorted by start time."""
    events = chunks_to_tx_events(
        [
            _chunk(start_s=0.3, direction="downlink"),
            _chunk(start_s=0.1, direction="uplink"),
            _chunk(start_s=0.2, direction="downlink"),
        ],
        _transmitter_config(),
        _wifi_config(),
        seed=42,
    )

    assert [event.start_s for event in events] == sorted(event.start_s for event in events)


def test_existing_channel_can_consume_layer4_tx_events() -> None:
    """The existing channel accepts source-aware Layer 4 TxEvents."""
    events = chunks_to_tx_events(
        [_chunk(direction="uplink"), _chunk(direction="downlink", start_s=0.2)],
        _transmitter_config(),
        _wifi_config(),
        seed=42,
    )
    scenario = ScenarioConfig(
        app_id="video_app",
        action_id="play_video",
        distance_m=0.5,
        frequency_hz=2.437e9,
    )
    channel = ChannelConfig(
        path_loss_exponent=2.2,
        reference_distance_m=1.0,
        shadowing_db=0.0,
        ambient_power_w=dbm_to_watt(-30.0),
    )
    trace = received_power_trace(events, np.linspace(0.0, 1.0, 1001), scenario, channel)

    assert trace.shape == (1001,)
    assert np.all(trace >= channel.ambient_power_w)


def test_ap_downlink_event_generates_mobile_mac_ack_when_enabled() -> None:
    """AP downlink data induces a mobile MAC ACK when enabled."""
    events = chunks_to_tx_events(
        [_chunk(direction="downlink")],
        _transmitter_config(),
        _wifi_config(mac_ack_enabled=True),
        seed=42,
    )

    assert any(event.source_id == "ap" and event.frame_type == "data" for event in events)
    mac_acks = [event for event in events if event.frame_type == "mac_ack"]
    assert len(mac_acks) == 1
    assert mac_acks[0].source_id == "mobile"
    assert mac_acks[0].direction == "control"


def test_no_mac_ack_when_disabled() -> None:
    """MAC ACK generation is optional and disabled by default."""
    events = chunks_to_tx_events(
        [_chunk(direction="downlink")],
        _transmitter_config(),
        _wifi_config(mac_ack_enabled=False),
        seed=42,
    )

    assert all(event.frame_type != "mac_ack" for event in events)


def test_mac_ack_start_time_is_after_ap_event_end() -> None:
    """MAC ACK starts after AP downlink event end plus SIFS."""
    wifi = _wifi_config(mac_ack_enabled=True)
    events = chunks_to_tx_events(
        [_chunk(direction="downlink")],
        _transmitter_config(),
        wifi,
        seed=42,
    )
    ap_event = next(event for event in events if event.source_id == "ap")
    ack_event = next(event for event in events if event.frame_type == "mac_ack")

    assert ack_event.start_s == ap_event.start_s + ap_event.duration_s + wifi.sifs_s


def test_transport_ack_increases_mobile_airtime_for_downlink_chunks() -> None:
    """Transport ACKs add mobile uplink airtime for downlink-heavy chunks."""
    chunks = [_chunk(direction="downlink", payload_bytes=1500)]
    without_ack = chunks_to_tx_events(
        chunks,
        _transmitter_config(),
        _wifi_config(transport_ack_enabled=False),
        seed=42,
    )
    with_ack = chunks_to_tx_events(
        chunks,
        _transmitter_config(),
        _wifi_config(transport_ack_enabled=True, transport_ack_ratio=0.02),
        seed=42,
    )

    mobile_airtime_without = sum(
        event.duration_s for event in without_ack if event.source_id == "mobile"
    )
    mobile_airtime_with = sum(
        event.duration_s for event in with_ack if event.source_id == "mobile"
    )

    assert mobile_airtime_with > mobile_airtime_without
    assert any(event.frame_type == "transport_ack" for event in with_ack)


def test_video_play_produces_ap_data_and_mobile_ack_events() -> None:
    """Video playback downlink chunks produce AP data and mobile ACK TxEvents."""
    action = ActionInstance(
        start_s=0.0,
        app_id="video_app",
        action_id="play_video",
        instance_id=0,
        label="video_app/play_video#0",
    )
    transactions = generate_network_transactions([action], seed=42)
    chunks = transactions_to_chunks(transactions, _wifi_config(), duration_s=10.0, seed=43)
    events = chunks_to_tx_events(
        chunks,
        _transmitter_config(),
        _wifi_config(mac_ack_enabled=True, transport_ack_enabled=True, transport_ack_ratio=0.02),
        seed=44,
        duration_s=10.0,
    )

    assert any(event.source_id == "ap" and event.frame_type == "data" for event in events)
    assert any(event.source_id == "mobile" and event.frame_type == "mac_ack" for event in events)
    assert any(
        event.source_id == "mobile" and event.frame_type == "transport_ack"
        for event in events
    )


def test_ack_tx_events_remain_sorted() -> None:
    """Data and ACK TxEvents are returned sorted by start time."""
    events = chunks_to_tx_events(
        [
            _chunk(start_s=0.3, direction="downlink"),
            _chunk(start_s=0.1, direction="downlink"),
            _chunk(start_s=0.2, direction="uplink"),
        ],
        _transmitter_config(),
        _wifi_config(mac_ack_enabled=True, transport_ack_enabled=True, transport_ack_ratio=0.02),
        seed=42,
    )

    assert [event.start_s for event in events] == sorted(event.start_s for event in events)


def test_ack_tx_events_have_no_negative_durations() -> None:
    """Generated data and ACK TxEvents have non-negative durations."""
    events = chunks_to_tx_events(
        [_chunk(direction="downlink")],
        _transmitter_config(),
        _wifi_config(mac_ack_enabled=True, transport_ack_enabled=True, transport_ack_ratio=0.02),
        seed=42,
    )

    assert all(event.duration_s >= 0.0 for event in events)


def test_ack_events_do_not_extend_beyond_duration_when_provided() -> None:
    """ACK events outside the optional simulation duration are discarded."""
    events = chunks_to_tx_events(
        [_chunk(start_s=0.999, direction="downlink", payload_bytes=1500)],
        _transmitter_config(),
        _wifi_config(mac_ack_enabled=True, transport_ack_enabled=True, transport_ack_ratio=0.02),
        seed=42,
        duration_s=1.0,
    )

    assert all(event.start_s + event.duration_s <= 1.0 for event in events)


def test_zero_payload_chunk_produces_no_data_tx_event() -> None:
    """Zero-payload chunks are ignored by Layer 4 data event generation."""
    events = chunks_to_tx_events(
        [_chunk(payload_bytes=0, direction="uplink")],
        _transmitter_config(),
        _wifi_config(),
        seed=42,
    )

    assert events == []


def test_tx_event_core_invariants() -> None:
    """Layer 4 TxEvents have valid source IDs, starts, and positive durations."""
    events = chunks_to_tx_events(
        [
            _chunk(start_s=0.1, direction="uplink"),
            _chunk(start_s=0.2, direction="downlink"),
        ],
        _transmitter_config(),
        _wifi_config(mac_ack_enabled=True, transport_ack_enabled=True, transport_ack_ratio=0.02),
        seed=42,
    )

    assert events
    for event in events:
        assert event.source_id in {"mobile", "ap"}
        assert event.start_s >= 0.0
        assert event.duration_s > 0.0
        assert event.eirp_w > 0.0
