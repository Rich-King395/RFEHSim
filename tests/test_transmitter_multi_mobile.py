"""Tests for multi-mobile transmitter Layer 1 and Layer 2 scheduling."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from rfeh_sim.config import load_config
from rfeh_sim.engine import run_simulation
from rfeh_sim.transmitter import generate_tx_events_for_simulation
from rfeh_sim.units import dbm_to_watt

MULTI_DEVICE_IDS = {"phone_1", "phone_2", "phone_3"}
MULTI_SOURCE_IDS = MULTI_DEVICE_IDS | {"ap_0"}


def test_multi_mobile_config_produces_actions_for_every_device() -> None:
    """Each configured mobile device gets its own ActionInstances."""
    config = load_config(Path("configs/multi_mobile_v1.yaml"))
    result = generate_tx_events_for_simulation(config)

    action_device_ids = {action.device_id for action in result.action_instances}

    assert action_device_ids == MULTI_DEVICE_IDS
    assert all(action.device_id for action in result.action_instances)


def test_multi_mobile_transactions_keep_device_id() -> None:
    """NetworkTransactions inherit the device ID from their ActionInstance."""
    config = load_config(Path("configs/multi_mobile_v1.yaml"))
    result = generate_tx_events_for_simulation(config)

    action_devices_by_id = {
        action.instance_id: action.device_id for action in result.action_instances
    }

    assert result.network_transactions
    for transaction in result.network_transactions:
        assert transaction.device_id in MULTI_DEVICE_IDS
        assert transaction.device_id == action_devices_by_id[transaction.action_instance_id]


def test_multi_mobile_devices_produce_different_transaction_patterns() -> None:
    """Different app/action choices produce different transaction labels and bytes."""
    config = load_config(Path("configs/multi_mobile_v1.yaml"))
    result = generate_tx_events_for_simulation(config)

    phone_1_transactions = [
        transaction
        for transaction in result.network_transactions
        if transaction.device_id == "phone_1"
    ]
    phone_2_transactions = [
        transaction
        for transaction in result.network_transactions
        if transaction.device_id == "phone_2"
    ]

    phone_1_labels = {transaction.label for transaction in phone_1_transactions}
    phone_2_labels = {transaction.label for transaction in phone_2_transactions}
    phone_1_dl_bytes = sum(transaction.dl_bytes for transaction in phone_1_transactions)
    phone_2_dl_bytes = sum(transaction.dl_bytes for transaction in phone_2_transactions)

    assert phone_1_labels != phone_2_labels
    assert phone_1_dl_bytes != phone_2_dl_bytes


def test_legacy_single_mobile_config_still_generates_one_device() -> None:
    """Legacy scenario.app_id/action_id configs synthesize one mobile device."""
    config = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    result = generate_tx_events_for_simulation(config)

    assert {action.device_id for action in result.action_instances} == {"phone_1"}
    assert {transaction.device_id for transaction in result.network_transactions} == {
        "phone_1"
    }


def test_multi_mobile_transaction_generation_is_deterministic() -> None:
    """The same seed reproduces multi-device actions and transactions."""
    config = load_config(Path("configs/multi_mobile_v1.yaml"))

    first = generate_tx_events_for_simulation(config)
    second = generate_tx_events_for_simulation(config)

    assert first.action_instances == second.action_instances
    assert first.network_transactions == second.network_transactions


def test_multi_mobile_end_to_end_hardening_invariants() -> None:
    """Multi-mobile simulation keeps source, channel, and receiver invariants."""
    config = load_config(Path("configs/multi_mobile_v1.yaml"))
    first = run_simulation(config)
    second = run_simulation(config)

    assert MULTI_SOURCE_IDS.issubset({event.source_id for event in first.tx_events})
    assert np.all(np.isfinite(first.v_cap))
    assert np.all(first.v_cap >= 0.0)
    assert np.all(np.isfinite(first.received_power_w))
    assert np.all(first.received_power_w >= 0.0)
    assert np.allclose(first.v_cap, second.v_cap)
    assert first.tx_events == second.tx_events

    uplink_data = [
        event
        for event in first.tx_events
        if event.frame_type == "data" and event.direction == "uplink"
    ]
    downlink_data = [
        event
        for event in first.tx_events
        if event.frame_type == "data" and event.direction == "downlink"
    ]
    ack_events = [
        event
        for event in first.tx_events
        if event.frame_type in {"mac_ack", "transport_ack"}
    ]

    assert uplink_data
    assert downlink_data
    assert ack_events
    assert all(event.source_id == event.device_id for event in uplink_data)
    assert all(event.source_type == "mobile" for event in uplink_data)
    assert all(event.target_device_id == "ap_0" for event in uplink_data)
    assert all(event.source_id == "ap_0" for event in downlink_data)
    assert all(event.source_type == "ap" for event in downlink_data)
    assert all(event.target_device_id in MULTI_DEVICE_IDS for event in downlink_data)
    assert all(event.source_id == event.device_id for event in ack_events)
    assert all(event.source_id in MULTI_DEVICE_IDS for event in ack_events)
    assert all(event.target_device_id == "ap_0" for event in ack_events)

    source_sum = np.full(
        first.time_s.shape,
        config.channel.ambient_power_w,
        dtype=float,
    )
    for source_power_w in first.received_power_by_source.values():
        source_sum += source_power_w

    assert set(first.received_power_by_source) == MULTI_SOURCE_IDS
    assert np.allclose(first.received_power_w, source_sum)
    assert first.received_power_w.shape == first.v_cap.shape


def test_multi_mobile_uplink_chunks_create_per_phone_tx_events() -> None:
    """Uplink data TxEvents use the originating phone as source_id."""
    config = load_config(Path("configs/multi_mobile_v1.yaml"))
    result = generate_tx_events_for_simulation(config)

    uplink_sources = {
        event.source_id
        for event in result.tx_events
        if event.frame_type == "data" and event.direction == "uplink"
    }

    assert "phone_1" in uplink_sources
    assert "phone_2" in uplink_sources
    assert "phone_3" in uplink_sources


def test_multi_mobile_downlink_chunks_use_single_ap_source() -> None:
    """Downlink data TxEvents for all phones use the configured AP source ID."""
    config = load_config(Path("configs/multi_mobile_v1.yaml"))
    result = generate_tx_events_for_simulation(config)

    downlink_events = [
        event
        for event in result.tx_events
        if event.frame_type == "data" and event.direction == "downlink"
    ]

    assert downlink_events
    assert {event.source_id for event in downlink_events} == {"ap_0"}
    assert {event.source_type for event in downlink_events} == {"ap"}
    assert {event.target_device_id for event in downlink_events} == {
        "phone_1",
        "phone_2",
        "phone_3",
    }


def test_multi_mobile_tx_event_eirp_uses_device_and_ap_config() -> None:
    """Layer 4 uses per-device mobile EIRP and AP EIRP when scenario config exists."""
    base = load_config(Path("configs/multi_mobile_v1.yaml"))
    phone_1, phone_2, phone_3 = base.scenario.mobile_devices
    config = replace(
        base,
        scenario=replace(
            base.scenario,
            ap=replace(
                base.scenario.ap,
                eirp_w_mean=dbm_to_watt(25.0),
                eirp_dbm_std=0.0,
            ),
            mobile_devices=(
                replace(phone_1, eirp_w_mean=dbm_to_watt(10.0), eirp_dbm_std=0.0),
                replace(phone_2, eirp_w_mean=dbm_to_watt(20.0), eirp_dbm_std=0.0),
                replace(phone_3, eirp_w_mean=dbm_to_watt(16.0), eirp_dbm_std=0.0),
            ),
        ),
    )

    result = generate_tx_events_for_simulation(config)
    phone_1_uplink = next(
        event
        for event in result.tx_events
        if event.source_id == "phone_1"
        and event.frame_type == "data"
        and event.direction == "uplink"
    )
    phone_2_uplink = next(
        event
        for event in result.tx_events
        if event.source_id == "phone_2"
        and event.frame_type == "data"
        and event.direction == "uplink"
    )
    phone_3_uplink = next(
        event
        for event in result.tx_events
        if event.source_id == "phone_3"
        and event.frame_type == "data"
        and event.direction == "uplink"
    )
    ap_downlink = next(
        event
        for event in result.tx_events
        if event.source_id == "ap_0"
        and event.frame_type == "data"
        and event.direction == "downlink"
    )

    assert phone_1_uplink.eirp_w == pytest.approx(dbm_to_watt(10.0))
    assert phone_2_uplink.eirp_w == pytest.approx(dbm_to_watt(20.0))
    assert phone_3_uplink.eirp_w == pytest.approx(dbm_to_watt(16.0))
    assert ap_downlink.eirp_w == pytest.approx(dbm_to_watt(25.0))
    assert all(event.eirp_w > 0.0 and event.eirp_w < 1.0 for event in result.tx_events)


def test_multi_mobile_tx_events_are_sorted() -> None:
    """Multi-mobile TxEvents are sorted by start time after merging devices."""
    config = load_config(Path("configs/multi_mobile_v1.yaml"))
    result = generate_tx_events_for_simulation(config)

    assert [event.start_s for event in result.tx_events] == sorted(
        event.start_s for event in result.tx_events
    )


def test_legacy_single_mobile_tx_event_sources_still_work() -> None:
    """Legacy single-mobile config emits one synthesized phone and one AP."""
    config = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    result = generate_tx_events_for_simulation(config)

    source_ids = {event.source_id for event in result.tx_events}

    assert "phone_1" in source_ids
    assert "ap" in source_ids


def test_ap_downlink_to_phone_1_generates_ack_from_phone_1() -> None:
    """AP downlink data targeted to phone_1 induces phone_1 MAC ACK events."""
    config = load_config(Path("configs/multi_mobile_v1.yaml"))
    result = generate_tx_events_for_simulation(config)

    assert any(
        event.source_id == "ap_0"
        and event.target_device_id == "phone_1"
        and event.frame_type == "data"
        for event in result.tx_events
    )
    assert any(
        event.source_id == "phone_1"
        and event.source_type == "mobile"
        and event.device_id == "phone_1"
        and event.target_device_id == "ap_0"
        and event.direction == "control"
        and event.frame_type == "mac_ack"
        for event in result.tx_events
    )


def test_ap_downlink_to_phone_2_generates_ack_from_phone_2() -> None:
    """AP downlink data targeted to phone_2 induces phone_2 MAC ACK events."""
    config = load_config(Path("configs/multi_mobile_v1.yaml"))
    result = generate_tx_events_for_simulation(config)

    assert any(
        event.source_id == "ap_0"
        and event.target_device_id == "phone_2"
        and event.frame_type == "data"
        for event in result.tx_events
    )
    assert any(
        event.source_id == "phone_2"
        and event.source_type == "mobile"
        and event.device_id == "phone_2"
        and event.target_device_id == "ap_0"
        and event.direction == "control"
        and event.frame_type == "mac_ack"
        for event in result.tx_events
    )


def test_ap_downlink_to_phone_3_generates_ack_from_phone_3() -> None:
    """AP downlink data targeted to phone_3 induces phone_3 MAC ACK events."""
    config = load_config(Path("configs/multi_mobile_v1.yaml"))
    result = generate_tx_events_for_simulation(config)

    assert any(
        event.source_id == "ap_0"
        and event.target_device_id == "phone_3"
        and event.frame_type == "data"
        for event in result.tx_events
    )
    assert any(
        event.source_id == "phone_3"
        and event.source_type == "mobile"
        and event.device_id == "phone_3"
        and event.target_device_id == "ap_0"
        and event.direction == "control"
        and event.frame_type == "mac_ack"
        for event in result.tx_events
    )


def test_multi_mobile_ack_source_id_is_never_generic_mobile() -> None:
    """Multi-mobile ACK events use the target phone ID, not generic mobile."""
    config = load_config(Path("configs/multi_mobile_v1.yaml"))
    result = generate_tx_events_for_simulation(config)
    ack_events = [
        event
        for event in result.tx_events
        if event.frame_type in {"mac_ack", "transport_ack"}
    ]

    assert ack_events
    assert all(event.source_id != "mobile" for event in ack_events)
    assert {event.source_id for event in ack_events}.issubset(MULTI_DEVICE_IDS)
    assert {event.target_device_id for event in ack_events} == {"ap_0"}


def test_multi_mobile_transport_acks_use_target_phone_source() -> None:
    """Transport ACKs for AP downlink traffic are emitted by the target phone."""
    config = load_config(Path("configs/multi_mobile_v1.yaml"))
    result = generate_tx_events_for_simulation(config)
    transport_acks = [
        event for event in result.tx_events if event.frame_type == "transport_ack"
    ]

    assert transport_acks
    assert {event.source_id for event in transport_acks}.issubset(MULTI_DEVICE_IDS)
    assert {event.source_type for event in transport_acks} == {"mobile"}
    assert {event.target_device_id for event in transport_acks} == {"ap_0"}


def test_disabling_ack_removes_multi_mobile_ack_events() -> None:
    """MAC and transport ACK generation remain optional."""
    base = load_config(Path("configs/multi_mobile_v1.yaml"))
    config = replace(
        base,
        wifi=replace(
            base.wifi,
            mac_ack_enabled=False,
            transport_ack_enabled=False,
        ),
    )

    result = generate_tx_events_for_simulation(config)

    assert all(
        event.frame_type not in {"mac_ack", "transport_ack"}
        for event in result.tx_events
    )


def test_legacy_single_mobile_ack_behavior_still_works() -> None:
    """Legacy single-mobile configs emit ACKs from the synthesized phone."""
    config = load_config(Path("configs/transaction_transmitter_v1.yaml"))
    result = generate_tx_events_for_simulation(config)
    ack_events = [
        event
        for event in result.tx_events
        if event.frame_type in {"mac_ack", "transport_ack"}
    ]

    assert ack_events
    assert {event.source_id for event in ack_events} == {"phone_1"}
    assert {event.source_type for event in ack_events} == {"mobile"}
    assert {event.target_device_id for event in ack_events} == {"ap"}
