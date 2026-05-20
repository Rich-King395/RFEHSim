"""V0 fixed-distance wireless channel model."""

from __future__ import annotations

import math

import numpy as np

from rfeh_sim.models import ChannelConfig, ScenarioConfig, TxEvent
from rfeh_sim.units import db_to_linear

_SPEED_OF_LIGHT_M_PER_S = 299_792_458.0


def free_space_path_loss_db(distance_m: float, frequency_hz: float) -> float:
    """Compute free-space path loss in dB.

    Args:
        distance_m: Transmitter-to-receiver distance in meters.
        frequency_hz: RF center frequency in Hertz.

    Returns:
        Free-space path loss in dB.

    Raises:
        ValueError: If distance or frequency is not strictly positive.
    """
    _require_positive_finite(distance_m, "distance_m")
    _require_positive_finite(frequency_hz, "frequency_hz")

    return 20.0 * math.log10(
        4.0 * math.pi * distance_m * frequency_hz / _SPEED_OF_LIGHT_M_PER_S
    )


def log_distance_path_loss_db(
    distance_m: float,
    frequency_hz: float,
    reference_distance_m: float,
    path_loss_exponent: float,
    shadowing_db: float = 0.0,
) -> float:
    """Compute log-distance path loss in dB.

    The reference loss is the free-space path loss at ``reference_distance_m``.
    V0 uses a deterministic fixed shadowing term from configuration.
    """
    _require_positive_finite(distance_m, "distance_m")
    _require_positive_finite(frequency_hz, "frequency_hz")
    _require_positive_finite(reference_distance_m, "reference_distance_m")
    _require_positive_finite(path_loss_exponent, "path_loss_exponent")
    _require_finite(shadowing_db, "shadowing_db")

    reference_loss_db = free_space_path_loss_db(reference_distance_m, frequency_hz)
    distance_ratio = distance_m / reference_distance_m
    return (
        reference_loss_db
        + 10.0 * path_loss_exponent * math.log10(distance_ratio)
        + shadowing_db
    )


def received_power_trace(
    tx_events: list[TxEvent],
    time_s: np.ndarray,
    scenario_config: ScenarioConfig,
    channel_config: ChannelConfig,
) -> np.ndarray:
    """Compute received RF power over time for v0 TxEvents.

    Args:
        tx_events: Coarse transmission events using EIRP in Watts.
        time_s: One-dimensional simulation time grid in seconds.
        scenario_config: Scenario settings with fixed distance and frequency.
        channel_config: Log-distance channel settings with ambient power in Watts.

    Returns:
        Array of received RF power in Watts with the same shape as ``time_s``.
    """
    _require_non_negative_finite(
        channel_config.ambient_power_w,
        "channel_config.ambient_power_w",
    )

    time_array = np.asarray(time_s, dtype=float)
    if time_array.ndim != 1:
        raise ValueError("time_s must be a one-dimensional array.")
    if not np.all(np.isfinite(time_array)):
        raise ValueError("time_s must contain only finite seconds values.")
    received_power_w = np.full(
        time_array.shape,
        channel_config.ambient_power_w,
        dtype=float,
    )

    path_loss_db = log_distance_path_loss_db(
        distance_m=scenario_config.distance_m,
        frequency_hz=scenario_config.frequency_hz,
        reference_distance_m=channel_config.reference_distance_m,
        path_loss_exponent=channel_config.path_loss_exponent,
        shadowing_db=channel_config.shadowing_db,
    )
    path_gain_linear = db_to_linear(-path_loss_db)

    for event in tx_events:
        _require_finite(event.start_s, "TxEvent.start_s")
        if not math.isfinite(event.duration_s):
            raise ValueError("TxEvent.duration_s must be finite.")
        if event.duration_s <= 0.0:
            continue
        _require_non_negative_finite(event.eirp_w, "TxEvent.eirp_w")

        event_end_s = event.start_s + event.duration_s
        active = (time_array >= event.start_s) & (time_array < event_end_s)
        received_power_w[active] += event.eirp_w * path_gain_linear

    return received_power_w


def _require_positive_finite(value: float, name: str) -> None:
    """Require a finite, strictly positive scalar."""
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive.")


def _require_non_negative_finite(value: float, name: str) -> None:
    """Require a finite, non-negative scalar."""
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")


def _require_finite(value: float, name: str) -> None:
    """Require a finite scalar."""
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite.")
