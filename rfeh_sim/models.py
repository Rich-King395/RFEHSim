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
class ScenarioConfig:
    """Scenario inputs that identify the action and propagation geometry."""

    app_id: str
    action_id: str
    distance_m: float
    frequency_hz: float


@dataclass(frozen=True, slots=True)
class TransmitterConfig:
    """Transmitter settings after conversion to simulator-internal units."""

    default_eirp_w: float


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
class TxEvent:
    """A coarse RF transmission event emitted by the v0 transmitter model."""

    source_id: str
    start_s: float
    duration_s: float
    eirp_w: float
    center_freq_hz: float
    label: str


@dataclass(frozen=True, slots=True)
class SimResult:
    """End-to-end v0 simulation result traces and intermediate objects."""

    time_s: np.ndarray
    received_power_w: np.ndarray
    harvested_power_w: np.ndarray
    v_cap: np.ndarray
    boost_state: np.ndarray
    capacitor_energy_j: np.ndarray
    net_capacitor_power_w: np.ndarray
    small_scale_gain_by_source: dict[str, np.ndarray]
    traffic_bursts: list[TrafficBurst]
    tx_events: list[TxEvent]
