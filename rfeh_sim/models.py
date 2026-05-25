"""Configuration data models for the v0 simulator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """Global simulation timing and reproducibility settings."""

    duration_s: float
    dt_s: float
    seed: int


@dataclass(frozen=True, slots=True)
class APConfig:
    """Access point transmitter settings for a scenario."""

    ap_id: str
    distance_m: float
    eirp_w_mean: float
    eirp_dbm_std: float


@dataclass(frozen=True, slots=True)
class MobileDeviceConfig:
    """Mobile device app/action, geometry, and RF power settings."""

    device_id: str
    app_id: str
    action_id: str
    distance_m: float
    eirp_w_mean: float
    eirp_dbm_std: float
    start_offset_s: float = 0.0


@dataclass(frozen=True, slots=True)
class ScenarioConfig:
    """Scenario inputs that identify the action and propagation geometry."""

    app_id: str
    action_id: str
    distance_m: float | None
    frequency_hz: float
    receiver_id: str = "rfeh_0"
    ap: APConfig | None = None
    mobile_devices: tuple[MobileDeviceConfig, ...] = ()
    mobile_distance_m: float | None = None
    ap_distance_m: float | None = None
    source_distances_m: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TransmitterConfig:
    """Transmitter settings after conversion to simulator-internal units."""

    default_eirp_w: float
    model: Literal["burst", "transaction"] = "burst"
    mobile_eirp_w_mean: float = 0.0
    mobile_eirp_dbm_std: float = 0.0
    ap_eirp_w_mean: float = 0.0
    ap_eirp_dbm_std: float = 0.0


@dataclass(frozen=True, slots=True)
class WifiConfig:
    """Simplified Wi-Fi timing and framing settings for transmitter v1."""

    center_freq_hz: float
    bandwidth_hz: float
    chunk_payload_bytes: int
    mac_overhead_bytes: int
    preamble_s: float
    mobile_phy_rate_bps: float
    ap_phy_rate_bps: float
    mac_ack_enabled: bool
    sifs_s: float
    mac_ack_duration_s: float
    mac_ack_eirp_w: float
    transport_ack_enabled: bool
    transport_ack_ratio: float
    medium_access_model: Literal[
        "independent",
        "ap_serial",
        "shared_medium_serial",
    ] = "independent"
    guard_time_s: float = 1.0e-5


@dataclass(frozen=True, slots=True)
class AppTrafficConfig:
    """Synthetic app/action traffic repetition settings."""

    repeat_mode: Literal["none", "periodic"]
    period_s: float
    jitter_s: float
    start_offset_s: float
    repeat_until_end: bool


@dataclass(frozen=True, slots=True)
class SmallScaleFadingConfig:
    """Flat small-scale fading settings for the wireless channel."""

    enabled: bool
    model: Literal["none", "rayleigh", "rician"]
    k_factor_linear: float
    coherence_time_s: float
    doppler_hz: float | None
    normalize_mean: bool
    per_source_independent: bool
    random_phase: bool


def default_small_scale_fading_config() -> SmallScaleFadingConfig:
    """Return the default large-scale-only channel behavior."""
    return SmallScaleFadingConfig(
        enabled=False,
        model="none",
        k_factor_linear=0.0,
        coherence_time_s=0.2,
        doppler_hz=None,
        normalize_mean=True,
        per_source_independent=True,
        random_phase=True,
    )


@dataclass(frozen=True, slots=True)
class ChannelConfig:
    """Log-distance path loss channel settings."""

    path_loss_exponent: float
    reference_distance_m: float
    shadowing_db: float
    ambient_power_w: float
    small_scale: SmallScaleFadingConfig = field(
        default_factory=default_small_scale_fading_config
    )


@dataclass(frozen=True, slots=True)
class HarvesterConfig:
    """RF-to-DC harvester and storage capacitor settings."""

    capacitance_f: float
    initial_v_cap: float
    eta_model: str
    eta_constant: float
    leakage_w: float
    max_v_cap: float
    boost: BoostConfig


@dataclass(frozen=True, slots=True)
class BoostConfig:
    """Threshold-controlled boost/load discharge settings."""

    enabled: bool
    v_on: float
    v_off: float
    output_voltage_v: float
    load_power_w: float
    efficiency: float
    quiescent_power_on_w: float
    quiescent_power_off_w: float


@dataclass(frozen=True, slots=True)
class FullConfig:
    """Top-level simulator configuration."""

    simulation: SimulationConfig
    scenario: ScenarioConfig
    app_traffic: AppTrafficConfig
    transmitter: TransmitterConfig
    wifi: WifiConfig
    channel: ChannelConfig
    harvester: HarvesterConfig


@dataclass(frozen=True, slots=True)
class TrafficBurst:
    """A coarse app/action traffic burst used by the v0 simulator."""

    start_s: float
    duration_s: float
    power_scale: float
    direction: Literal["uplink", "downlink", "mixed"]
    label: str


@dataclass(frozen=True, slots=True)
class ActionInstance:
    """A concrete occurrence of an app/action within a simulation."""

    start_s: float
    app_id: str
    action_id: str
    instance_id: int
    label: str
    device_id: str = "mobile"


@dataclass(frozen=True, slots=True)
class NetworkTransaction:
    """A simplified app-level network transaction for transmitter v1."""

    start_s: float
    duration_s: float
    ul_bytes: int
    dl_bytes: int
    protocol: str
    label: str
    action_instance_id: int
    device_id: str = "mobile"


@dataclass(frozen=True, slots=True)
class ChunkEvent:
    """A simplified uplink or downlink chunk emitted by a transaction."""

    start_s: float
    payload_bytes: int
    direction: Literal["uplink", "downlink"]
    transaction_label: str
    action_instance_id: int
    device_id: str = "mobile"


@dataclass(frozen=True, slots=True)
class TxEvent:
    """A coarse RF transmission event emitted by the v0 transmitter model."""

    source_id: str
    start_s: float
    duration_s: float
    eirp_w: float
    center_freq_hz: float
    label: str
    source_type: Literal["mobile", "ap"] | None = None
    device_id: str | None = None
    target_device_id: str | None = None
    bandwidth_hz: float | None = None
    frame_type: str = "data"
    direction: Literal["uplink", "downlink", "control"] = "uplink"
    payload_bytes: int | None = None
    phy_rate_bps: float | None = None
    original_start_s: float | None = None

    def __post_init__(self) -> None:
        """Fill compatibility identity fields for legacy TxEvent construction."""
        source_type = self.source_type
        if source_type is None:
            source_type = "ap" if self.source_id.startswith("ap") else "mobile"
            object.__setattr__(self, "source_type", source_type)
        if source_type not in {"mobile", "ap"}:
            raise ValueError("TxEvent.source_type must be 'mobile' or 'ap'.")

        if self.device_id is None and source_type == "mobile":
            object.__setattr__(self, "device_id", self.source_id)
        if (
            self.target_device_id is None
            and source_type == "ap"
            and self.direction == "downlink"
            and self.device_id is not None
        ):
            object.__setattr__(self, "target_device_id", self.device_id)


@dataclass(frozen=True, slots=True)
class SimResult:
    """End-to-end v0 simulation result traces and intermediate objects."""

    time_s: np.ndarray
    received_power_w: np.ndarray
    received_power_by_source: dict[str, np.ndarray]
    harvested_power_w: np.ndarray
    v_cap: np.ndarray
    boost_state: np.ndarray
    capacitor_energy_j: np.ndarray
    net_capacitor_power_w: np.ndarray
    small_scale_gain_by_source: dict[str, np.ndarray]
    traffic_bursts: list[TrafficBurst]
    action_instances: list[ActionInstance]
    network_transactions: list[NetworkTransaction]
    chunk_events: list[ChunkEvent]
    tx_events: list[TxEvent]


@dataclass(frozen=True, slots=True)
class TransmitterResult:
    """Intermediate and final outputs from the transmitter pipeline."""

    traffic_bursts: list[TrafficBurst]
    action_instances: list[ActionInstance]
    network_transactions: list[NetworkTransaction]
    chunk_events: list[ChunkEvent]
    tx_events: list[TxEvent]
