"""V0 fixed-distance wireless channel model."""

from __future__ import annotations

import math

import numpy as np

from rfeh_sim.models import ChannelConfig, ScenarioConfig, SmallScaleFadingConfig, TxEvent
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
    seed: int | None = None,
) -> np.ndarray:
    """Compute received RF power over time for v0 TxEvents.

    Args:
        tx_events: Coarse transmission events using EIRP in Watts.
        time_s: One-dimensional simulation time grid in seconds.
        scenario_config: Scenario settings with fixed distance and frequency.
        channel_config: Log-distance channel settings with ambient power in Watts.
        seed: Optional random seed for deterministic small-scale fading.

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
    small_scale_by_source = generate_small_scale_gain_by_source(
        tx_events,
        time_array,
        channel_config.small_scale,
        seed,
    )

    for event in tx_events:
        _require_finite(event.start_s, "TxEvent.start_s")
        if not math.isfinite(event.duration_s):
            raise ValueError("TxEvent.duration_s must be finite.")
        if event.duration_s <= 0.0:
            continue
        _require_non_negative_finite(event.eirp_w, "TxEvent.eirp_w")

        event_end_s = event.start_s + event.duration_s
        active = (time_array >= event.start_s) & (time_array < event_end_s)
        small_scale_gain = small_scale_by_source.get(event.source_id)
        if small_scale_gain is None:
            small_scale_gain = np.ones_like(time_array, dtype=float)
        received_power_w[active] += (
            event.eirp_w * path_gain_linear * small_scale_gain[active]
        )

    return received_power_w


def generate_complex_gaussian_ar1(
    num_samples: int,
    dt_s: float,
    coherence_time_s: float,
    seed: int | None = None,
) -> np.ndarray:
    """Generate a unit-power time-correlated complex Gaussian AR(1) process."""
    if num_samples < 0:
        raise ValueError("num_samples must be non-negative.")
    _require_non_negative_finite(dt_s, "dt_s")
    _require_positive_finite(coherence_time_s, "coherence_time_s")
    if num_samples == 0:
        return np.array([], dtype=np.complex128)

    rng = np.random.default_rng(seed)
    rho = math.exp(-dt_s / coherence_time_s)
    innovation_scale = math.sqrt(max(0.0, 1.0 - rho**2))
    samples = np.empty(num_samples, dtype=np.complex128)
    samples[0] = _complex_unit_gaussian(rng)
    for idx in range(1, num_samples):
        samples[idx] = (
            rho * samples[idx - 1]
            + innovation_scale * _complex_unit_gaussian(rng)
        )
    return samples


def generate_small_scale_gain(
    time_s: np.ndarray,
    fading_config: SmallScaleFadingConfig,
    seed: int | None = None,
) -> np.ndarray:
    """Generate flat small-scale fading power gain over a time grid."""
    time_array = np.asarray(time_s, dtype=float)
    if time_array.ndim != 1:
        raise ValueError("time_s must be a one-dimensional array.")
    if not np.all(np.isfinite(time_array)):
        raise ValueError("time_s must contain only finite seconds values.")
    if not fading_config.enabled or fading_config.model == "none":
        return np.ones(time_array.shape, dtype=float)
    if fading_config.model not in {"rayleigh", "rician"}:
        raise ValueError(
            "Small-scale fading model must be 'none', 'rayleigh', or 'rician'."
        )

    dt_s = _infer_time_step_s(time_array)
    base_seed = 0 if seed is None else seed
    gaussian = generate_complex_gaussian_ar1(
        num_samples=time_array.size,
        dt_s=dt_s,
        coherence_time_s=fading_config.coherence_time_s,
        seed=base_seed,
    )
    if fading_config.model == "rayleigh":
        channel = gaussian
    else:
        k_factor = fading_config.k_factor_linear
        _require_non_negative_finite(k_factor, "k_factor_linear")
        rng = np.random.default_rng(base_seed + 1)
        phase = float(rng.uniform(0.0, 2.0 * math.pi)) if fading_config.random_phase else 0.0
        los = math.sqrt(k_factor / (k_factor + 1.0)) * np.exp(1j * phase)
        scattered = math.sqrt(1.0 / (k_factor + 1.0)) * gaussian
        channel = los + scattered

    gain = np.abs(channel) ** 2
    if fading_config.normalize_mean and gain.size > 0:
        mean_gain = float(np.mean(gain))
        if mean_gain > 0.0:
            gain = gain / mean_gain
    return gain.astype(float, copy=False)


def generate_small_scale_gain_by_source(
    tx_events: list[TxEvent],
    time_s: np.ndarray,
    fading_config: SmallScaleFadingConfig,
    seed: int | None,
) -> dict[str, np.ndarray]:
    """Generate deterministic small-scale fading gain traces by TxEvent source."""
    if not fading_config.enabled or fading_config.model == "none":
        return {}

    source_ids = sorted({event.source_id for event in tx_events})
    if not source_ids:
        return {}

    base_seed = 0 if seed is None else seed
    if not fading_config.per_source_independent:
        shared = generate_small_scale_gain(time_s, fading_config, seed=base_seed)
        return {source_id: shared for source_id in source_ids}

    return {
        source_id: generate_small_scale_gain(
            time_s,
            fading_config,
            seed=base_seed + source_index,
        )
        for source_index, source_id in enumerate(source_ids)
    }


def _infer_time_step_s(time_s: np.ndarray) -> float:
    """Infer a representative positive timestep from a one-dimensional grid."""
    if time_s.size < 2:
        return 0.0
    deltas = np.diff(time_s)
    if not np.all(deltas >= 0.0):
        raise ValueError("time_s must be monotonically non-decreasing.")
    positive_deltas = deltas[deltas > 0.0]
    if positive_deltas.size == 0:
        return 0.0
    return float(np.median(positive_deltas))


def _complex_unit_gaussian(rng: np.random.Generator) -> complex:
    """Draw one zero-mean complex Gaussian sample with unit average power."""
    return complex(rng.normal(0.0, 1.0), rng.normal(0.0, 1.0)) / math.sqrt(2.0)


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
