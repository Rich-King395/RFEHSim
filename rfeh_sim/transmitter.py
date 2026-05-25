"""V0 transmitter model converting traffic bursts into RF TxEvents."""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from rfeh_sim.app_templates import generate_traffic_bursts
from rfeh_sim.models import (
    ActionInstance,
    AppTrafficConfig,
    ChunkEvent,
    FullConfig,
    NetworkTransaction,
    ScenarioConfig,
    TrafficBurst,
    TransmitterConfig,
    TransmitterResult,
    TxEvent,
    WifiConfig,
)
from rfeh_sim.template_loader import TransactionSpec, get_transaction_specs
from rfeh_sim.units import dbm_to_watt


def generate_tx_events_for_simulation(config: FullConfig) -> TransmitterResult:
    """Generate transmitter intermediates and TxEvents for a full simulation config."""
    if config.transmitter.model == "burst":
        traffic_bursts = generate_traffic_bursts(
            app_id=config.scenario.app_id,
            action_id=config.scenario.action_id,
            duration_s=config.simulation.duration_s,
            seed=config.simulation.seed,
            app_traffic_config=config.app_traffic,
        )
        tx_events = bursts_to_tx_events(
            bursts=traffic_bursts,
            transmitter_config=config.transmitter,
            scenario_config=config.scenario,
            seed=config.simulation.seed + 1,
        )
        return TransmitterResult(
            traffic_bursts=traffic_bursts,
            action_instances=[],
            network_transactions=[],
            chunk_events=[],
            tx_events=tx_events,
        )

    if config.transmitter.model != "transaction":
        raise ValueError(
            "Transmitter model must be 'burst' or 'transaction'."
        )

    action_instances, network_transactions = _generate_device_actions_and_transactions(
        config,
    )
    chunk_events = transactions_to_chunks(
        transactions=network_transactions,
        wifi_config=config.wifi,
        duration_s=config.simulation.duration_s,
        seed=config.simulation.seed + 2,
    )
    tx_events = chunks_to_tx_events(
        chunks=chunk_events,
        transmitter_config=config.transmitter,
        wifi_config=config.wifi,
        seed=config.simulation.seed + 3,
        duration_s=config.simulation.duration_s,
        scenario_config=config.scenario,
    )
    return TransmitterResult(
        traffic_bursts=[],
        action_instances=action_instances,
        network_transactions=network_transactions,
        chunk_events=chunk_events,
        tx_events=tx_events,
    )


def _generate_device_actions_and_transactions(
    config: FullConfig,
) -> tuple[list[ActionInstance], list[NetworkTransaction]]:
    """Generate Layer 1 and 2 outputs for each configured mobile device."""
    devices = config.scenario.mobile_devices
    if not devices:
        action_instances = generate_action_instances(
            app_id=config.scenario.app_id,
            action_id=config.scenario.action_id,
            duration_s=config.simulation.duration_s,
            app_traffic_config=config.app_traffic,
            seed=config.simulation.seed,
        )
        network_transactions = generate_network_transactions(
            action_instances=action_instances,
            seed=config.simulation.seed + 1,
        )
        return action_instances, network_transactions

    all_actions: list[ActionInstance] = []
    all_transactions: list[NetworkTransaction] = []
    next_instance_id = 0
    for device_index, device in enumerate(devices):
        app_id = device.app_id
        action_id = device.action_id
        if (
            len(devices) == 1
            and device.device_id == "phone_1"
            and (config.scenario.app_id, config.scenario.action_id)
            != (device.app_id, device.action_id)
        ):
            app_id = config.scenario.app_id
            action_id = config.scenario.action_id

        device_traffic = replace(
            config.app_traffic,
            start_offset_s=config.app_traffic.start_offset_s + device.start_offset_s,
        )
        seed_offset = 0 if len(devices) == 1 else 1000 * (device_index + 1)
        device_actions = generate_action_instances(
            app_id=app_id,
            action_id=action_id,
            duration_s=config.simulation.duration_s,
            app_traffic_config=device_traffic,
            seed=config.simulation.seed + seed_offset,
            device_id=device.device_id,
        )
        reindexed_actions = [
            replace(action, instance_id=next_instance_id + offset)
            for offset, action in enumerate(device_actions)
        ]
        next_instance_id += len(reindexed_actions)

        device_transactions = generate_network_transactions(
            action_instances=reindexed_actions,
            seed=config.simulation.seed + 1 + seed_offset,
        )
        all_actions.extend(reindexed_actions)
        all_transactions.extend(device_transactions)

    return (
        sorted(all_actions, key=lambda action: (action.start_s, action.device_id)),
        sorted(
            all_transactions,
            key=lambda transaction: (transaction.start_s, transaction.device_id),
        ),
    )


def generate_action_instances(
    app_id: str,
    action_id: str,
    duration_s: float,
    app_traffic_config: AppTrafficConfig,
    seed: int,
    device_id: str = "mobile",
) -> list[ActionInstance]:
    """Generate Layer 1 app/action instances for transmitter v1.

    This layer only schedules repeated high-level action occurrences. It does
    not validate app/action support and does not generate transactions,
    chunks, or RF events.
    """
    if duration_s <= 0.0:
        raise ValueError("Simulation duration must be positive.")
    if seed < 0:
        raise ValueError("Random seed must be non-negative.")
    if app_traffic_config.start_offset_s < 0.0:
        raise ValueError("app_traffic_config.start_offset_s must be non-negative.")

    if app_traffic_config.repeat_mode == "none":
        start_s = min(app_traffic_config.start_offset_s, duration_s)
        return [
            ActionInstance(
                start_s=start_s,
                app_id=app_id,
                action_id=action_id,
                instance_id=0,
                label=f"{app_id}/{action_id}#0",
                device_id=device_id,
            )
        ]

    if app_traffic_config.repeat_mode != "periodic":
        raise ValueError(
            "Layer 1 currently supports repeat_mode='none' and 'periodic' only. "
            "TODO: add renewal action scheduling."
        )
    if app_traffic_config.period_s <= 0.0:
        raise ValueError("Periodic action period_s must be positive.")
    if app_traffic_config.jitter_s < 0.0:
        raise ValueError("Periodic action jitter_s must be non-negative.")

    rng = np.random.default_rng(seed)
    actions: list[ActionInstance] = []
    period_index = 0
    while True:
        nominal_start_s = (
            app_traffic_config.start_offset_s
            + period_index * app_traffic_config.period_s
        )
        if nominal_start_s > duration_s:
            break

        jitter_s = 0.0
        if app_traffic_config.jitter_s > 0.0:
            jitter_s = float(
                rng.uniform(-app_traffic_config.jitter_s, app_traffic_config.jitter_s)
            )
        start_s = nominal_start_s + jitter_s
        if 0.0 <= start_s <= duration_s:
            instance_id = len(actions)
            actions.append(
                ActionInstance(
                    start_s=start_s,
                    app_id=app_id,
                    action_id=action_id,
                    instance_id=instance_id,
                    label=f"{app_id}/{action_id}#{instance_id}",
                    device_id=device_id,
                )
            )

        period_index += 1
        if not app_traffic_config.repeat_until_end:
            break

    return actions


def generate_network_transactions(
    action_instances: list[ActionInstance],
    seed: int,
) -> list[NetworkTransaction]:
    """Generate Layer 2 network transactions from action instances.

    This layer uses hard-coded coarse templates. It does not model TCP/QUIC
    packets and does not generate chunks or RF transmissions.
    """
    if seed < 0:
        raise ValueError("Random seed must be non-negative.")

    rng = np.random.default_rng(seed)
    transactions: list[NetworkTransaction] = []
    for action in action_instances:
        templates = get_transaction_specs(action.app_id, action.action_id)
        for template in templates:
            transactions.extend(_sample_transactions_from_spec(action, template, rng))

    return sorted(transactions, key=lambda transaction: transaction.start_s)


def _sample_transactions_from_spec(
    action: ActionInstance,
    template: TransactionSpec,
    rng: np.random.Generator,
) -> list[NetworkTransaction]:
    """Sample NetworkTransactions for one action/template spec."""
    if template.probability < 1.0 and float(rng.random()) > template.probability:
        return []

    repeat_count = 1
    if template.repeat_count is not None:
        repeat_count = int(
            rng.integers(template.repeat_count[0], template.repeat_count[1] + 1)
        )

    transactions: list[NetworkTransaction] = []
    repeated_offset_s = 0.0
    for repeat_index in range(repeat_count):
        if repeat_index > 0 and template.repeat_interval_s is not None:
            repeated_offset_s += float(rng.uniform(*template.repeat_interval_s))

        start_delay_s = float(rng.uniform(*template.start_delay_s)) + repeated_offset_s
        duration_s = float(rng.uniform(*template.duration_s))
        ul_bytes = int(rng.integers(template.ul_bytes[0], template.ul_bytes[1] + 1))
        dl_bytes = int(rng.integers(template.dl_bytes[0], template.dl_bytes[1] + 1))
        if duration_s <= 0.0:
            raise ValueError("Generated NetworkTransaction duration must be positive.")
        if ul_bytes < 0 or dl_bytes < 0:
            raise ValueError("Generated NetworkTransaction bytes must be non-negative.")

        transactions.append(
            NetworkTransaction(
                start_s=action.start_s + start_delay_s,
                duration_s=duration_s,
                ul_bytes=ul_bytes,
                dl_bytes=dl_bytes,
                protocol=template.protocol,
                label=template.label,
                action_instance_id=action.instance_id,
                device_id=action.device_id,
            )
        )

    return transactions


def transactions_to_chunks(
    transactions: list[NetworkTransaction],
    wifi_config: WifiConfig,
    duration_s: float,
    seed: int,
) -> list[ChunkEvent]:
    """Convert Layer 2 transactions into timed uplink/downlink chunks.

    This layer splits byte volumes into coarse chunks. It does not model
    TCP/QUIC packets, congestion control, or RF transmissions.
    """
    if duration_s <= 0.0:
        raise ValueError("Simulation duration must be positive.")
    if seed < 0:
        raise ValueError("Random seed must be non-negative.")
    if wifi_config.chunk_payload_bytes <= 0:
        raise ValueError("wifi_config.chunk_payload_bytes must be positive.")

    rng = np.random.default_rng(seed)
    chunks: list[ChunkEvent] = []
    for transaction in transactions:
        if transaction.duration_s <= 0.0:
            raise ValueError("NetworkTransaction duration_s must be positive.")
        if transaction.ul_bytes < 0 or transaction.dl_bytes < 0:
            raise ValueError("NetworkTransaction byte counts must be non-negative.")

        chunks.extend(
            _bytes_to_direction_chunks(
                total_bytes=transaction.ul_bytes,
                direction="uplink",
                transaction=transaction,
                wifi_config=wifi_config,
                simulation_duration_s=duration_s,
                rng=rng,
            )
        )
        chunks.extend(
            _bytes_to_direction_chunks(
                total_bytes=transaction.dl_bytes,
                direction="downlink",
                transaction=transaction,
                wifi_config=wifi_config,
                simulation_duration_s=duration_s,
                rng=rng,
            )
        )

    return sorted(chunks, key=lambda chunk: chunk.start_s)


def chunks_to_tx_events(
    chunks: list[ChunkEvent],
    transmitter_config: TransmitterConfig,
    wifi_config: WifiConfig,
    seed: int,
    duration_s: float | None = None,
    scenario_config: ScenarioConfig | None = None,
) -> list[TxEvent]:
    """Convert Layer 3 chunks into simplified source-aware Wi-Fi TxEvents."""
    if seed < 0:
        raise ValueError("Random seed must be non-negative.")
    if duration_s is not None and duration_s <= 0.0:
        raise ValueError("duration_s must be positive when provided.")
    _validate_wifi_tx_config(wifi_config)
    if transmitter_config.mobile_eirp_w_mean <= 0.0:
        raise ValueError("transmitter_config.mobile_eirp_w_mean must be positive.")
    if transmitter_config.ap_eirp_w_mean <= 0.0:
        raise ValueError("transmitter_config.ap_eirp_w_mean must be positive.")
    if transmitter_config.mobile_eirp_dbm_std < 0.0:
        raise ValueError("transmitter_config.mobile_eirp_dbm_std must be non-negative.")
    if transmitter_config.ap_eirp_dbm_std < 0.0:
        raise ValueError("transmitter_config.ap_eirp_dbm_std must be non-negative.")

    rng = np.random.default_rng(seed)
    ap_id = _ap_source_id(scenario_config)
    data_events: list[TxEvent] = []
    for chunk in chunks:
        if chunk.payload_bytes < 0:
            raise ValueError("ChunkEvent payload_bytes must be non-negative.")
        if chunk.payload_bytes == 0:
            continue
        if chunk.direction == "uplink":
            source_id = chunk.device_id
            source_type = "mobile"
            device_id = chunk.device_id
            target_device_id = ap_id
            phy_rate_bps = wifi_config.mobile_phy_rate_bps
            mobile_eirp_w_mean, mobile_eirp_dbm_std = _mobile_eirp_params(
                chunk.device_id,
                transmitter_config,
                scenario_config,
            )
            eirp_w = _sample_eirp_w(
                mobile_eirp_w_mean,
                mobile_eirp_dbm_std,
                rng,
            )
        elif chunk.direction == "downlink":
            source_id = ap_id
            source_type = "ap"
            device_id = chunk.device_id
            target_device_id = chunk.device_id
            phy_rate_bps = wifi_config.ap_phy_rate_bps
            ap_eirp_w_mean, ap_eirp_dbm_std = _ap_eirp_params(
                transmitter_config,
                scenario_config,
            )
            eirp_w = _sample_eirp_w(
                ap_eirp_w_mean,
                ap_eirp_dbm_std,
                rng,
            )
        else:
            raise ValueError("ChunkEvent direction must be 'uplink' or 'downlink'.")

        airtime_s = _wifi_airtime_s(
            payload_bytes=chunk.payload_bytes,
            wifi_config=wifi_config,
            phy_rate_bps=phy_rate_bps,
        )
        event = TxEvent(
            source_id=source_id,
            start_s=chunk.start_s,
            duration_s=airtime_s,
            eirp_w=eirp_w,
            center_freq_hz=wifi_config.center_freq_hz,
            label=chunk.transaction_label,
            source_type=source_type,
            device_id=device_id,
            target_device_id=target_device_id,
            bandwidth_hz=wifi_config.bandwidth_hz,
            frame_type="data",
            direction=chunk.direction,
            payload_bytes=chunk.payload_bytes,
            phy_rate_bps=phy_rate_bps,
        )
        if _event_within_duration(event, duration_s):
            data_events.append(event)

    ack_events = generate_ack_tx_events(
        data_events,
        wifi_config,
        transmitter_config,
        duration_s=duration_s,
        scenario_config=scenario_config,
    )
    return schedule_tx_events(
        [*data_events, *ack_events],
        wifi_config,
        duration_s=duration_s,
    )


def generate_ack_tx_events(
    tx_events: list[TxEvent],
    wifi_config: WifiConfig,
    transmitter_config: TransmitterConfig,
    duration_s: float | None = None,
    scenario_config: ScenarioConfig | None = None,
) -> list[TxEvent]:
    """Generate simplified mobile ACK TxEvents for AP downlink data events."""
    if duration_s is not None and duration_s <= 0.0:
        raise ValueError("duration_s must be positive when provided.")
    _validate_wifi_tx_config(wifi_config)

    ack_events: list[TxEvent] = []
    for event in tx_events:
        if not (
            event.source_type == "ap"
            and event.direction == "downlink"
            and event.frame_type == "data"
        ):
            continue
        ack_source_id = event.target_device_id or event.device_id or "mobile"
        if (
            scenario_config is not None
            and len(scenario_config.mobile_devices) > 1
            and ack_source_id == "mobile"
        ):
            raise ValueError(
                "AP downlink TxEvents in multi-mobile scenarios must set "
                "target_device_id before ACK generation."
            )
        mobile_eirp_w_mean, _ = _mobile_eirp_params(
            ack_source_id,
            transmitter_config,
            scenario_config,
        )

        if wifi_config.mac_ack_enabled:
            mac_ack = TxEvent(
                source_id=ack_source_id,
                start_s=event.start_s + event.duration_s + wifi_config.sifs_s,
                duration_s=wifi_config.mac_ack_duration_s,
                eirp_w=wifi_config.mac_ack_eirp_w,
                center_freq_hz=wifi_config.center_freq_hz,
                label=f"mac_ack_for_{event.label}",
                source_type="mobile",
                device_id=ack_source_id,
                target_device_id=event.source_id,
                bandwidth_hz=wifi_config.bandwidth_hz,
                frame_type="mac_ack",
                direction="control",
                payload_bytes=0,
                phy_rate_bps=wifi_config.mobile_phy_rate_bps,
            )
            if _event_within_duration(mac_ack, duration_s):
                ack_events.append(mac_ack)

        if wifi_config.transport_ack_enabled:
            downlink_payload_bytes = event.payload_bytes or 0
            ack_bytes = int(np.ceil(downlink_payload_bytes * wifi_config.transport_ack_ratio))
            if ack_bytes > 0:
                transport_duration_s = _wifi_airtime_s(
                    payload_bytes=ack_bytes,
                    wifi_config=wifi_config,
                    phy_rate_bps=wifi_config.mobile_phy_rate_bps,
                )
                transport_ack = TxEvent(
                    source_id=ack_source_id,
                    start_s=event.start_s + event.duration_s + wifi_config.sifs_s,
                    duration_s=transport_duration_s,
                    eirp_w=mobile_eirp_w_mean,
                    center_freq_hz=wifi_config.center_freq_hz,
                    label=f"transport_ack_for_{event.label}",
                    source_type="mobile",
                    device_id=ack_source_id,
                    target_device_id=event.source_id,
                    bandwidth_hz=wifi_config.bandwidth_hz,
                    frame_type="transport_ack",
                    direction="uplink",
                    payload_bytes=ack_bytes,
                    phy_rate_bps=wifi_config.mobile_phy_rate_bps,
                )
                if _event_within_duration(transport_ack, duration_s):
                    ack_events.append(transport_ack)

    return sorted(ack_events, key=lambda event: event.start_s)


def _wifi_airtime_s(
    payload_bytes: int,
    wifi_config: WifiConfig,
    phy_rate_bps: float,
) -> float:
    """Compute simplified Wi-Fi airtime for one frame."""
    return (
        wifi_config.preamble_s
        + 8.0 * (payload_bytes + wifi_config.mac_overhead_bytes) / phy_rate_bps
    )


def schedule_tx_events(
    tx_events: list[TxEvent],
    wifi_config: WifiConfig,
    duration_s: float | None = None,
) -> list[TxEvent]:
    """Apply a deterministic simplified medium-access scheduler to TxEvents."""
    if duration_s is not None and duration_s <= 0.0:
        raise ValueError("duration_s must be positive when provided.")
    if wifi_config.guard_time_s < 0.0:
        raise ValueError("wifi_config.guard_time_s must be non-negative.")

    model = wifi_config.medium_access_model
    if model == "independent":
        return sorted(tx_events, key=_tx_event_sort_key)
    if model == "ap_serial":
        ap_events = [event for event in tx_events if event.source_type == "ap"]
        other_events = [event for event in tx_events if event.source_type != "ap"]
        scheduled = [
            *other_events,
            *_serialize_tx_events(ap_events, wifi_config.guard_time_s),
        ]
        return _filter_and_sort_scheduled_events(scheduled, duration_s)
    if model == "shared_medium_serial":
        scheduled = _serialize_tx_events(tx_events, wifi_config.guard_time_s)
        return _filter_and_sort_scheduled_events(scheduled, duration_s)
    raise ValueError(
        "wifi_config.medium_access_model must be 'independent', 'ap_serial', "
        "or 'shared_medium_serial'."
    )


def _serialize_tx_events(
    tx_events: list[TxEvent],
    guard_time_s: float,
) -> list[TxEvent]:
    """Serialize events by requested start time using a simple free-time cursor."""
    serialized: list[TxEvent] = []
    channel_free_time = -float("inf")
    for event in sorted(tx_events, key=_tx_event_sort_key):
        requested_start_s = event.start_s
        earliest_start_s = channel_free_time + guard_time_s
        start_s = max(requested_start_s, earliest_start_s)
        if start_s != requested_start_s:
            event = replace(
                event,
                start_s=start_s,
                original_start_s=(
                    event.original_start_s
                    if event.original_start_s is not None
                    else requested_start_s
                ),
            )
        serialized.append(event)
        channel_free_time = event.start_s + event.duration_s
    return serialized


def _filter_and_sort_scheduled_events(
    tx_events: list[TxEvent],
    duration_s: float | None,
) -> list[TxEvent]:
    """Drop scheduled events outside the optional duration and sort them."""
    return sorted(
        [event for event in tx_events if _event_within_duration(event, duration_s)],
        key=_tx_event_sort_key,
    )


def _tx_event_sort_key(event: TxEvent) -> tuple[float, str, str, str, str]:
    """Stable deterministic sort key for TxEvents with identical requested starts."""
    return (
        event.start_s,
        event.source_id,
        event.frame_type,
        event.direction,
        event.label,
    )


def _event_within_duration(event: TxEvent, duration_s: float | None) -> bool:
    """Return true if an event is fully inside the optional simulation duration."""
    if duration_s is None:
        return True
    return 0.0 <= event.start_s and event.start_s + event.duration_s <= duration_s


def _sample_eirp_w(
    mean_w: float,
    std_db: float,
    rng: np.random.Generator,
) -> float:
    """Sample EIRP in Watts using Gaussian jitter in dB around a Watt mean."""
    if std_db == 0.0:
        return mean_w
    mean_dbm = 10.0 * np.log10(mean_w / 1e-3)
    return dbm_to_watt(float(rng.normal(mean_dbm, std_db)))


def _ap_source_id(scenario_config: ScenarioConfig | None) -> str:
    """Return the configured AP source ID, preserving legacy defaults."""
    if scenario_config is not None and scenario_config.ap is not None:
        return scenario_config.ap.ap_id
    return "ap"


def _ap_eirp_params(
    transmitter_config: TransmitterConfig,
    scenario_config: ScenarioConfig | None,
) -> tuple[float, float]:
    """Return AP EIRP mean in Watts and dB standard deviation."""
    if scenario_config is not None and scenario_config.ap is not None:
        return (
            scenario_config.ap.eirp_w_mean,
            scenario_config.ap.eirp_dbm_std,
        )
    return (
        transmitter_config.ap_eirp_w_mean,
        transmitter_config.ap_eirp_dbm_std,
    )


def _mobile_eirp_params(
    device_id: str,
    transmitter_config: TransmitterConfig,
    scenario_config: ScenarioConfig | None,
) -> tuple[float, float]:
    """Return mobile EIRP mean in Watts and dB standard deviation for a device."""
    if scenario_config is not None:
        for device in scenario_config.mobile_devices:
            if device.device_id == device_id:
                return (device.eirp_w_mean, device.eirp_dbm_std)
    return (
        transmitter_config.mobile_eirp_w_mean,
        transmitter_config.mobile_eirp_dbm_std,
    )


def _validate_wifi_tx_config(wifi_config: WifiConfig) -> None:
    """Validate Wi-Fi settings needed by Layer 4 airtime calculation."""
    if wifi_config.center_freq_hz <= 0.0:
        raise ValueError("wifi_config.center_freq_hz must be positive.")
    if wifi_config.bandwidth_hz <= 0.0:
        raise ValueError("wifi_config.bandwidth_hz must be positive.")
    if wifi_config.mac_overhead_bytes < 0:
        raise ValueError("wifi_config.mac_overhead_bytes must be non-negative.")
    if wifi_config.preamble_s < 0.0:
        raise ValueError("wifi_config.preamble_s must be non-negative.")
    if wifi_config.mobile_phy_rate_bps <= 0.0:
        raise ValueError("wifi_config.mobile_phy_rate_bps must be positive.")
    if wifi_config.ap_phy_rate_bps <= 0.0:
        raise ValueError("wifi_config.ap_phy_rate_bps must be positive.")


def _bytes_to_direction_chunks(
    total_bytes: int,
    direction: str,
    transaction: NetworkTransaction,
    wifi_config: WifiConfig,
    simulation_duration_s: float,
    rng: np.random.Generator,
) -> list[ChunkEvent]:
    """Split one transaction byte direction into timed ChunkEvents."""
    if total_bytes == 0:
        return []

    max_payload_bytes = wifi_config.chunk_payload_bytes
    num_chunks = int(np.ceil(total_bytes / max_payload_bytes))
    transaction_end_s = transaction.start_s + transaction.duration_s
    if transaction_end_s < 0.0 or transaction.start_s > simulation_duration_s:
        return []

    spacing_s = transaction.duration_s / max(num_chunks, 1)
    jitter_limit_s = min(0.25 * spacing_s, 0.005)
    chunks: list[ChunkEvent] = []
    for chunk_index in range(num_chunks):
        remaining_bytes = total_bytes - chunk_index * max_payload_bytes
        payload_bytes = min(max_payload_bytes, remaining_bytes)
        nominal_start_s = transaction.start_s + chunk_index * spacing_s
        jitter_s = float(rng.uniform(-jitter_limit_s, jitter_limit_s))
        start_s = min(max(transaction.start_s, nominal_start_s + jitter_s), transaction_end_s)
        if start_s < 0.0 or start_s > simulation_duration_s:
            continue
        chunks.append(
            ChunkEvent(
                start_s=start_s,
                payload_bytes=payload_bytes,
                direction=direction,
                transaction_label=transaction.label,
                action_instance_id=transaction.action_instance_id,
                device_id=transaction.device_id,
            )
        )

    return chunks


def bursts_to_tx_events(
    bursts: list[TrafficBurst],
    transmitter_config: TransmitterConfig,
    scenario_config: ScenarioConfig,
    seed: int,
) -> list[TxEvent]:
    """Convert coarse traffic bursts into coarse RF transmission events.

    V0 intentionally avoids packet-level and Wi-Fi MAC/PHY details. Each burst
    becomes one mobile-originated RF event whose EIRP is based on the configured
    default EIRP in Watts multiplied by the burst power scale, with a small
    deterministic seeded jitter.

    Args:
        bursts: Traffic bursts generated from an app/action template.
        transmitter_config: Transmitter settings using internal Watt units.
        scenario_config: Scenario settings providing center frequency.
        seed: Random seed controlling small event jitter.

    Returns:
        A list of coarse transmission events.

    Raises:
        ValueError: If the configured EIRP or center frequency is invalid.
    """
    if transmitter_config.default_eirp_w <= 0.0:
        raise ValueError("Transmitter default EIRP must be positive.")
    if scenario_config.frequency_hz <= 0.0:
        raise ValueError("Scenario center frequency must be positive.")
    if seed < 0:
        raise ValueError("Random seed must be non-negative.")

    rng = np.random.default_rng(seed)
    tx_events: list[TxEvent] = []
    for burst in bursts:
        if burst.duration_s <= 0.0:
            continue

        duration_scale = min(1.0, max(0.70, 1.0 + float(rng.normal(0.0, 0.04))))
        eirp_scale = max(0.10, 1.0 + float(rng.normal(0.0, 0.03)))
        duration_s = burst.duration_s * duration_scale
        eirp_w = transmitter_config.default_eirp_w * burst.power_scale * eirp_scale

        tx_events.append(
            TxEvent(
                source_id="mobile",
                start_s=burst.start_s,
                duration_s=duration_s,
                eirp_w=eirp_w,
                center_freq_hz=scenario_config.frequency_hz,
                label=burst.label,
                source_type="mobile",
                device_id="mobile",
            )
        )

    return tx_events
