"""V0 RF-to-DC energy harvester and storage capacitor model."""

from __future__ import annotations

import math

import numpy as np

from rfeh_sim.models import HarvesterConfig


def rf_to_dc_efficiency_constant(p_r_w: np.ndarray, eta: float) -> np.ndarray:
    """Return constant RF-to-DC efficiency values for received RF powers.

    Args:
        p_r_w: Received RF power trace in Watts.
        eta: Constant conversion efficiency, normally between 0 and 1.

    Returns:
        An array of efficiency values with the same shape as ``p_r_w``.

    Raises:
        ValueError: If ``eta`` is outside the inclusive range [0, 1].
    """
    if not math.isfinite(eta) or not 0.0 <= eta <= 1.0:
        raise ValueError("RF-to-DC efficiency eta must be finite and between 0 and 1.")

    return np.full_like(np.asarray(p_r_w, dtype=float), eta, dtype=float)


def simulate_vcap(
    received_power_w: np.ndarray,
    dt_s: float,
    harvester_config: HarvesterConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Simulate harvested power and storage capacitor voltage over time.

    V0 uses constant RF-to-DC efficiency and an energy-based capacitor update.
    When ``harvester_config.boost.enabled`` is false, the model preserves the
    original charging/leakage-only behavior. When boost is enabled, a hysteretic
    threshold switch applies load draw between ``v_on`` and ``v_off``.

    Args:
        received_power_w: Received RF power trace in Watts.
        dt_s: Simulation time step in seconds.
        harvester_config: Harvester and capacitor settings.

    Returns:
        A tuple ``(harvested_power_w, v_cap, boost_state, capacitor_energy_j,
        net_capacitor_power_w)``. ``boost_state`` contains integer 0/1 values.

    Raises:
        ValueError: If physical parameters are invalid.
        NotImplementedError: If a non-constant efficiency model is requested.
    """
    _require_positive_finite(dt_s, "dt_s")
    _require_positive_finite(harvester_config.capacitance_f, "capacitance_f")
    _require_non_negative_finite(harvester_config.initial_v_cap, "initial_v_cap")
    _require_non_negative_finite(harvester_config.leakage_w, "leakage_w")
    _require_non_negative_finite(harvester_config.max_v_cap, "max_v_cap")
    _validate_boost_config(harvester_config)
    if harvester_config.eta_model != "constant":
        raise NotImplementedError("V0 only supports eta_model='constant'.")

    received_power = np.asarray(received_power_w, dtype=float)
    if received_power.ndim != 1:
        raise ValueError("received_power_w must be a one-dimensional array.")
    if not np.all(np.isfinite(received_power)):
        raise ValueError("received_power_w must contain only finite Watt values.")
    if np.any(received_power < 0.0):
        raise ValueError("received_power_w must be non-negative.")

    eta = rf_to_dc_efficiency_constant(
        received_power,
        harvester_config.eta_constant,
    )
    harvested_power_w = eta * received_power
    v_cap = np.empty_like(received_power, dtype=float)
    boost_state = np.zeros(received_power.shape, dtype=int)
    capacitor_energy_j = np.empty_like(received_power, dtype=float)
    net_capacitor_power_w = np.empty_like(received_power, dtype=float)
    if received_power.size == 0:
        return (
            harvested_power_w,
            v_cap,
            boost_state,
            capacitor_energy_j,
            net_capacitor_power_w,
        )

    capacitance_f = harvester_config.capacitance_f
    energy_j = 0.5 * capacitance_f * harvester_config.initial_v_cap**2
    if harvester_config.max_v_cap > 0.0:
        max_energy_j = 0.5 * capacitance_f * harvester_config.max_v_cap**2
        energy_j = min(energy_j, max_energy_j)
    else:
        max_energy_j = 0.0
        energy_j = 0.0

    boost_on = False
    for idx in range(received_power.size):
        v_cap[idx] = math.sqrt(2.0 * energy_j / capacitance_f)
        capacitor_energy_j[idx] = energy_j

        if harvester_config.boost.enabled:
            if not boost_on and v_cap[idx] >= harvester_config.boost.v_on:
                boost_on = True
            elif boost_on and v_cap[idx] <= harvester_config.boost.v_off:
                boost_on = False

        boost_state[idx] = int(boost_on)
        draw_power_w = _draw_power_w(harvester_config, boost_on)
        net_capacitor_power_w[idx] = harvested_power_w[idx] - draw_power_w

        if idx == received_power.size - 1:
            continue

        energy_j = max(0.0, energy_j + dt_s * net_capacitor_power_w[idx])
        energy_j = min(energy_j, max_energy_j)

    return (
        harvested_power_w,
        v_cap,
        boost_state,
        capacitor_energy_j,
        net_capacitor_power_w,
    )


def _draw_power_w(harvester_config: HarvesterConfig, boost_on: bool) -> float:
    """Return capacitor draw power for the current boost/load state."""
    if not harvester_config.boost.enabled:
        return harvester_config.leakage_w
    if not boost_on:
        return (
            harvester_config.leakage_w
            + harvester_config.boost.quiescent_power_off_w
        )
    return (
        harvester_config.leakage_w
        + harvester_config.boost.quiescent_power_on_w
        + harvester_config.boost.load_power_w / harvester_config.boost.efficiency
    )


def _validate_boost_config(harvester_config: HarvesterConfig) -> None:
    """Validate boost/load settings when the threshold model is enabled."""
    boost = harvester_config.boost
    if not boost.enabled:
        return
    _require_non_negative_finite(boost.v_on, "boost.v_on")
    _require_non_negative_finite(boost.v_off, "boost.v_off")
    if boost.v_on <= boost.v_off:
        raise ValueError("Boost threshold requires boost.v_on > boost.v_off.")
    _require_positive_finite(boost.output_voltage_v, "boost.output_voltage_v")
    _require_non_negative_finite(boost.load_power_w, "boost.load_power_w")
    _require_positive_finite(boost.efficiency, "boost.efficiency")
    if boost.efficiency > 1.0:
        raise ValueError("boost.efficiency must be <= 1.")
    _require_non_negative_finite(
        boost.quiescent_power_on_w,
        "boost.quiescent_power_on_w",
    )
    _require_non_negative_finite(
        boost.quiescent_power_off_w,
        "boost.quiescent_power_off_w",
    )


def _require_positive_finite(value: float, name: str) -> None:
    """Require a finite, strictly positive scalar."""
    if not math.isfinite(value) or value <= 0.0:
        raise ValueError(f"{name} must be finite and positive.")


def _require_non_negative_finite(value: float, name: str) -> None:
    """Require a finite, non-negative scalar."""
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative.")
