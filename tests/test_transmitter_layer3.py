"""Tests for Transmitter v1 Layer 3 chunk event generation."""

from __future__ import annotations

from rfeh_sim.config import load_config
from rfeh_sim.models import ActionInstance, NetworkTransaction, WifiConfig
from rfeh_sim.transmitter import (
    generate_network_transactions,
    transactions_to_chunks,
)


def _wifi_config(chunk_payload_bytes: int = 1500) -> WifiConfig:
    """Create Wi-Fi config for Layer 3 tests."""
    return WifiConfig(
        center_freq_hz=2.437e9,
        bandwidth_hz=20e6,
        chunk_payload_bytes=chunk_payload_bytes,
        mac_overhead_bytes=64,
        preamble_s=4.0e-5,
        mobile_phy_rate_bps=54e6,
        ap_phy_rate_bps=54e6,
        mac_ack_enabled=False,
        sifs_s=1.6e-5,
        mac_ack_duration_s=4.0e-5,
        mac_ack_eirp_w=0.01,
        transport_ack_enabled=False,
        transport_ack_ratio=0.0,
    )


def _transaction(ul_bytes: int = 3500, dl_bytes: int = 5200) -> NetworkTransaction:
    """Create a representative transaction."""
    return NetworkTransaction(
        start_s=1.0,
        duration_s=1.0,
        ul_bytes=ul_bytes,
        dl_bytes=dl_bytes,
        protocol="https",
        label="test_transaction",
        action_instance_id=0,
    )


def _action(app_id: str, action_id: str) -> ActionInstance:
    """Create an action instance for Layer 2 plus Layer 3 tests."""
    return ActionInstance(
        start_s=0.0,
        app_id=app_id,
        action_id=action_id,
        instance_id=0,
        label=f"{app_id}/{action_id}#0",
    )


def test_total_uplink_chunk_payload_equals_transaction_ul_bytes() -> None:
    """Uplink chunks preserve the transaction uplink byte volume."""
    transaction = _transaction(ul_bytes=3500, dl_bytes=0)
    chunks = transactions_to_chunks([transaction], _wifi_config(), duration_s=10.0, seed=42)

    assert sum(chunk.payload_bytes for chunk in chunks if chunk.direction == "uplink") == 3500


def test_total_downlink_chunk_payload_equals_transaction_dl_bytes() -> None:
    """Downlink chunks preserve the transaction downlink byte volume."""
    transaction = _transaction(ul_bytes=0, dl_bytes=5200)
    chunks = transactions_to_chunks([transaction], _wifi_config(), duration_s=10.0, seed=42)

    assert sum(chunk.payload_bytes for chunk in chunks if chunk.direction == "downlink") == 5200


def test_no_chunk_payload_exceeds_configured_payload_size() -> None:
    """Chunk payloads are bounded by wifi.chunk_payload_bytes."""
    chunks = transactions_to_chunks([_transaction()], _wifi_config(1500), duration_s=10.0, seed=42)

    assert chunks
    assert all(chunk.payload_bytes <= 1500 for chunk in chunks)


def test_no_chunk_start_time_is_outside_simulation_duration() -> None:
    """Chunk start times are clipped/discarded to the simulation window."""
    chunks = transactions_to_chunks([_transaction()], _wifi_config(), duration_s=2.0, seed=42)

    assert chunks
    assert all(0.0 <= chunk.start_s <= 2.0 for chunk in chunks)


def test_same_seed_gives_identical_chunk_timing() -> None:
    """Layer 3 chunk jitter is deterministic for the same seed."""
    transaction = _transaction()
    first = transactions_to_chunks([transaction], _wifi_config(), duration_s=10.0, seed=7)
    second = transactions_to_chunks([transaction], _wifi_config(), duration_s=10.0, seed=7)

    assert first == second


def test_video_play_produces_many_downlink_chunks() -> None:
    """Video playback transactions create many downlink chunks."""
    transactions = generate_network_transactions([_action("video_app", "play_video")], seed=42)
    chunks = transactions_to_chunks(transactions, _wifi_config(), duration_s=10.0, seed=43)
    downlink_chunks = [chunk for chunk in chunks if chunk.direction == "downlink"]

    assert len(downlink_chunks) > 100


def test_social_share_produces_more_uplink_chunks_than_like_for_fixed_seed() -> None:
    """The share action creates more uplink chunks than the like action."""
    like_transactions = generate_network_transactions([_action("social_app", "like")], seed=42)
    share_transactions = generate_network_transactions([_action("social_app", "share")], seed=42)
    like_chunks = transactions_to_chunks(like_transactions, _wifi_config(), duration_s=10.0, seed=43)
    share_chunks = transactions_to_chunks(share_transactions, _wifi_config(), duration_s=10.0, seed=43)

    like_uplink_count = sum(chunk.direction == "uplink" for chunk in like_chunks)
    share_uplink_count = sum(chunk.direction == "uplink" for chunk in share_chunks)

    assert share_uplink_count > like_uplink_count


def test_default_config_wifi_can_drive_chunk_generation() -> None:
    """Loaded WifiConfig fields work with Layer 3 chunk generation."""
    config = load_config("configs/default_v0.yaml")
    chunks = transactions_to_chunks([_transaction()], config.wifi, duration_s=10.0, seed=42)

    assert chunks


def test_zero_ul_bytes_generates_no_uplink_chunks() -> None:
    """Zero uplink bytes produce no uplink chunks."""
    chunks = transactions_to_chunks(
        [_transaction(ul_bytes=0, dl_bytes=1500)],
        _wifi_config(),
        duration_s=10.0,
        seed=42,
    )

    assert all(chunk.direction != "uplink" for chunk in chunks)


def test_zero_dl_bytes_generates_no_downlink_chunks() -> None:
    """Zero downlink bytes produce no downlink chunks."""
    chunks = transactions_to_chunks(
        [_transaction(ul_bytes=1500, dl_bytes=0)],
        _wifi_config(),
        duration_s=10.0,
        seed=42,
    )

    assert all(chunk.direction != "downlink" for chunk in chunks)


def test_chunk_byte_sums_match_all_in_window_transactions() -> None:
    """Layer 3 preserves aggregate byte volumes for in-window transactions."""
    transactions = [
        _transaction(ul_bytes=3500, dl_bytes=5200),
        NetworkTransaction(
            start_s=2.0,
            duration_s=0.2,
            ul_bytes=100,
            dl_bytes=2999,
            protocol="https",
            label="short_transaction",
            action_instance_id=1,
        ),
    ]
    chunks = transactions_to_chunks(transactions, _wifi_config(), duration_s=10.0, seed=42)

    assert sum(chunk.payload_bytes for chunk in chunks if chunk.direction == "uplink") == sum(
        transaction.ul_bytes for transaction in transactions
    )
    assert sum(chunk.payload_bytes for chunk in chunks if chunk.direction == "downlink") == sum(
        transaction.dl_bytes for transaction in transactions
    )


def test_very_short_transaction_duration_still_generates_bounded_chunks() -> None:
    """Short transaction durations do not push chunks outside the transaction window."""
    transaction = NetworkTransaction(
        start_s=1.0,
        duration_s=1.0e-6,
        ul_bytes=3000,
        dl_bytes=0,
        protocol="https",
        label="tiny_window",
        action_instance_id=0,
    )
    chunks = transactions_to_chunks([transaction], _wifi_config(), duration_s=10.0, seed=42)

    assert chunks
    for chunk in chunks:
        assert transaction.start_s <= chunk.start_s <= transaction.start_s + transaction.duration_s


def test_transaction_near_simulation_end_discards_out_of_window_chunks() -> None:
    """Chunks with starts beyond the simulation duration are discarded."""
    transaction = NetworkTransaction(
        start_s=9.999,
        duration_s=1.0,
        ul_bytes=3000,
        dl_bytes=3000,
        protocol="https",
        label="late_transaction",
        action_instance_id=0,
    )
    chunks = transactions_to_chunks([transaction], _wifi_config(), duration_s=10.0, seed=42)

    assert all(0.0 <= chunk.start_s <= 10.0 for chunk in chunks)
