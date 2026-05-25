"""Tests for transmitter v1 data model construction."""

from __future__ import annotations

import pytest

from rfeh_sim.models import ActionInstance, ChunkEvent, NetworkTransaction, TxEvent


def test_action_instance_construction() -> None:
    """ActionInstance captures a concrete app/action occurrence."""
    action = ActionInstance(
        start_s=1.0,
        app_id="video_app",
        action_id="play_video",
        instance_id=3,
        label="video_session",
    )

    assert action.start_s == pytest.approx(1.0)
    assert action.app_id == "video_app"
    assert action.action_id == "play_video"
    assert action.instance_id == 3
    assert action.label == "video_session"
    assert action.device_id == "mobile"


def test_action_instance_device_id_construction() -> None:
    """ActionInstance can identify the mobile device that owns the action."""
    action = ActionInstance(
        device_id="phone_1",
        start_s=1.0,
        app_id="video",
        action_id="play",
        instance_id=3,
        label="phone_1/video/play#3",
    )

    assert action.device_id == "phone_1"


def test_network_transaction_construction() -> None:
    """NetworkTransaction stores simplified UL/DL byte counts."""
    transaction = NetworkTransaction(
        start_s=1.1,
        duration_s=0.5,
        ul_bytes=800,
        dl_bytes=12000,
        protocol="quic_like",
        label="initial_buffer",
        action_instance_id=3,
    )

    assert transaction.start_s == pytest.approx(1.1)
    assert transaction.duration_s == pytest.approx(0.5)
    assert transaction.ul_bytes == 800
    assert transaction.dl_bytes == 12000
    assert transaction.protocol == "quic_like"
    assert transaction.action_instance_id == 3
    assert transaction.device_id == "mobile"


def test_network_transaction_device_id_construction() -> None:
    """NetworkTransaction preserves the mobile device owner."""
    transaction = NetworkTransaction(
        device_id="phone_1",
        start_s=1.1,
        duration_s=0.5,
        ul_bytes=800,
        dl_bytes=12000,
        protocol="quic_like",
        label="initial_buffer",
        action_instance_id=3,
    )

    assert transaction.device_id == "phone_1"


def test_chunk_event_construction() -> None:
    """ChunkEvent represents a simplified uplink or downlink payload chunk."""
    chunk = ChunkEvent(
        start_s=1.2,
        payload_bytes=1500,
        direction="downlink",
        transaction_label="initial_buffer",
        action_instance_id=3,
    )

    assert chunk.start_s == pytest.approx(1.2)
    assert chunk.payload_bytes == 1500
    assert chunk.direction == "downlink"
    assert chunk.transaction_label == "initial_buffer"
    assert chunk.action_instance_id == 3
    assert chunk.device_id == "mobile"


def test_chunk_event_device_id_construction() -> None:
    """ChunkEvent preserves the mobile device owner."""
    chunk = ChunkEvent(
        device_id="phone_1",
        start_s=1.2,
        payload_bytes=1500,
        direction="downlink",
        transaction_label="initial_buffer",
        action_instance_id=3,
    )

    assert chunk.device_id == "phone_1"


def test_tx_event_extended_fields_are_available() -> None:
    """TxEvent carries optional transmitter-v1 Wi-Fi metadata."""
    event = TxEvent(
        source_id="ap",
        start_s=1.2,
        duration_s=0.001,
        eirp_w=0.1,
        center_freq_hz=2.437e9,
        label="downlink_data",
        bandwidth_hz=20e6,
        frame_type="data",
        direction="downlink",
        payload_bytes=1500,
        phy_rate_bps=54e6,
    )

    assert event.source_id == "ap"
    assert event.source_type == "ap"
    assert event.device_id is None
    assert event.target_device_id is None
    assert event.bandwidth_hz == pytest.approx(20e6)
    assert event.frame_type == "data"
    assert event.direction == "downlink"
    assert event.payload_bytes == 1500
    assert event.phy_rate_bps == pytest.approx(54e6)


def test_tx_event_old_constructor_shape_still_works() -> None:
    """Existing TxEvent keyword construction remains backward-compatible."""
    event = TxEvent(
        source_id="mobile",
        start_s=0.1,
        duration_s=0.2,
        eirp_w=0.01,
        center_freq_hz=2.437e9,
        label="legacy",
    )

    assert event.bandwidth_hz is None
    assert event.source_type == "mobile"
    assert event.device_id == "mobile"
    assert event.target_device_id is None
    assert event.frame_type == "data"
    assert event.direction == "uplink"
    assert event.payload_bytes is None
    assert event.phy_rate_bps is None


def test_tx_event_mobile_uplink_identity_fields() -> None:
    """Mobile uplink TxEvents can carry source and AP target identity."""
    event = TxEvent(
        source_id="phone_1",
        source_type="mobile",
        device_id="phone_1",
        target_device_id="ap_0",
        start_s=0.1,
        duration_s=0.2,
        eirp_w=0.01,
        center_freq_hz=2.437e9,
        label="phone_1_uplink",
        direction="uplink",
    )

    assert event.source_id == "phone_1"
    assert event.source_type == "mobile"
    assert event.device_id == "phone_1"
    assert event.target_device_id == "ap_0"


def test_tx_event_ap_downlink_identity_fields() -> None:
    """AP downlink TxEvents can identify their target mobile device."""
    event = TxEvent(
        source_id="ap_0",
        source_type="ap",
        device_id="phone_1",
        target_device_id="phone_1",
        start_s=0.1,
        duration_s=0.2,
        eirp_w=0.1,
        center_freq_hz=2.437e9,
        label="ap_downlink",
        direction="downlink",
    )

    assert event.source_id == "ap_0"
    assert event.source_type == "ap"
    assert event.device_id == "phone_1"
    assert event.target_device_id == "phone_1"


def test_tx_event_invalid_source_type_raises() -> None:
    """TxEvent source_type is constrained to mobile or AP."""
    with pytest.raises(ValueError, match="source_type"):
        TxEvent(
            source_id="bad",
            source_type="sensor",  # type: ignore[arg-type]
            start_s=0.1,
            duration_s=0.2,
            eirp_w=0.01,
            center_freq_hz=2.437e9,
            label="bad_source_type",
        )
