"""Tests for the v0 RF energy harvester model."""

from __future__ import annotations

import numpy as np
import pytest

from rfeh_sim.harvester import simulate_vcap
from rfeh_sim.models import BoostConfig, HarvesterConfig


def _boost_config(
    *,
    enabled: bool = False,
    v_on: float = 0.66,
    v_off: float = 0.64,
    load_power_w: float = 5e-5,
    efficiency: float = 0.75,
    quiescent_power_on_w: float = 1e-6,
    quiescent_power_off_w: float = 1e-7,
) -> BoostConfig:
    """Create boost/load settings for harvester tests."""
    return BoostConfig(
        enabled=enabled,
        v_on=v_on,
        v_off=v_off,
        output_voltage_v=3.3,
        load_power_w=load_power_w,
        efficiency=efficiency,
        quiescent_power_on_w=quiescent_power_on_w,
        quiescent_power_off_w=quiescent_power_off_w,
    )


def _harvester_config(
    *,
    initial_v_cap: float = 0.1,
    eta_constant: float = 0.5,
    leakage_w: float = 0.0,
    max_v_cap: float = 5.0,
    boost: BoostConfig | None = None,
) -> HarvesterConfig:
    """Create a representative harvester configuration."""
    return HarvesterConfig(
        capacitance_f=0.001,
        initial_v_cap=initial_v_cap,
        eta_model="constant",
        eta_constant=eta_constant,
        leakage_w=leakage_w,
        max_v_cap=max_v_cap,
        boost=boost or _boost_config(enabled=False),
    )


def test_zero_received_power_and_zero_leakage_keeps_vcap_constant() -> None:
    """With no input power or leakage, capacitor voltage remains unchanged."""
    received_power_w = np.zeros(20)
    _, v_cap, *_ = simulate_vcap(
        received_power_w,
        dt_s=0.01,
        harvester_config=_harvester_config(initial_v_cap=0.25, leakage_w=0.0),
    )

    assert np.all(v_cap == pytest.approx(0.25))


def test_positive_received_power_increases_vcap() -> None:
    """Positive harvested power charges the storage capacitor."""
    received_power_w = np.full(20, 1e-4)
    _, v_cap, *_ = simulate_vcap(
        received_power_w,
        dt_s=0.01,
        harvester_config=_harvester_config(initial_v_cap=0.1),
    )

    assert v_cap[-1] > v_cap[0]


def test_vcap_update_uses_capacitor_energy_equation() -> None:
    """The first VCAP step follows E[k+1] = E[k] + dt * harvested power."""
    config = _harvester_config(
        initial_v_cap=0.2,
        eta_constant=0.5,
        leakage_w=1e-6,
        max_v_cap=5.0,
    )
    received_power_w = np.array([1e-4, 1e-4])
    _, v_cap, *_ = simulate_vcap(received_power_w, dt_s=0.1, harvester_config=config)

    initial_energy_j = 0.5 * config.capacitance_f * config.initial_v_cap**2
    expected_energy_j = initial_energy_j + 0.1 * (0.5 * 1e-4 - config.leakage_w)
    expected_v_cap = np.sqrt(2.0 * expected_energy_j / config.capacitance_f)

    assert v_cap[1] == pytest.approx(expected_v_cap)


def test_higher_received_power_leads_to_higher_final_vcap() -> None:
    """More received RF power produces a higher final capacitor voltage."""
    config = _harvester_config(initial_v_cap=0.1)
    _, low_v_cap, *_ = simulate_vcap(
        np.full(20, 1e-5),
        dt_s=0.01,
        harvester_config=config,
    )
    _, high_v_cap, *_ = simulate_vcap(
        np.full(20, 1e-4),
        dt_s=0.01,
        harvester_config=config,
    )

    assert high_v_cap[-1] > low_v_cap[-1]


def test_vcap_never_becomes_negative() -> None:
    """Leakage can discharge the capacitor, but voltage never goes below zero."""
    received_power_w = np.zeros(50)
    _, v_cap, *_ = simulate_vcap(
        received_power_w,
        dt_s=0.1,
        harvester_config=_harvester_config(initial_v_cap=0.1, leakage_w=1e-3),
    )

    assert np.all(v_cap >= 0.0)
    assert np.all(np.isfinite(v_cap))
    assert v_cap[-1] == pytest.approx(0.0)


def test_vcap_respects_max_vcap() -> None:
    """The capacitor voltage is clamped at max_v_cap."""
    received_power_w = np.full(100, 1.0)
    _, v_cap, *_ = simulate_vcap(
        received_power_w,
        dt_s=0.1,
        harvester_config=_harvester_config(initial_v_cap=0.1, max_v_cap=0.2),
    )

    assert np.max(v_cap) <= 0.2 + 1e-12
    assert v_cap[-1] == pytest.approx(0.2)


def test_simulate_vcap_rejects_nan_received_power() -> None:
    """NaN received power is rejected rather than propagating into VCAP."""
    with pytest.raises(ValueError, match="finite Watt"):
        simulate_vcap(
            np.array([0.0, np.nan]),
            dt_s=0.01,
            harvester_config=_harvester_config(),
        )


def test_boost_disabled_preserves_monotonic_charging_behavior() -> None:
    """With boost disabled, positive RF input keeps the old monotonic charging path."""
    _, v_cap, boost_state, _, net_power = simulate_vcap(
        np.full(100, 1e-4),
        dt_s=0.01,
        harvester_config=_harvester_config(
            initial_v_cap=0.1,
            leakage_w=0.0,
            boost=_boost_config(enabled=False),
        ),
    )

    assert np.all(boost_state == 0)
    assert np.all(net_power >= 0.0)
    assert np.all(np.diff(v_cap) >= -1e-15)


def test_boost_turns_on_when_vcap_reaches_v_on() -> None:
    """Sufficient RF input charges VCAP to V_ON and enables the boost state."""
    _, v_cap, boost_state, *_ = simulate_vcap(
        np.full(2000, 1e-3),
        dt_s=0.001,
        harvester_config=_harvester_config(
            initial_v_cap=0.63,
            eta_constant=0.5,
            boost=_boost_config(enabled=True, v_on=0.66, v_off=0.64),
        ),
    )

    assert np.any(v_cap >= 0.66)
    assert np.any(boost_state == 1)


def test_boost_high_load_discharges_to_v_off_and_turns_off() -> None:
    """A high load discharges VCAP to V_OFF and disables the boost state."""
    _, v_cap, boost_state, *_ = simulate_vcap(
        np.full(3000, 1e-6),
        dt_s=0.001,
        harvester_config=_harvester_config(
            initial_v_cap=0.67,
            eta_constant=0.5,
            boost=_boost_config(
                enabled=True,
                v_on=0.66,
                v_off=0.64,
                load_power_w=5e-4,
            ),
        ),
    )

    assert boost_state[0] == 1
    assert np.any(v_cap <= 0.64)
    assert np.any(boost_state == 0)


def test_boost_state_toggles_repeatedly_under_suitable_input() -> None:
    """Alternating charge/discharge creates repeated boost state transitions."""
    received_power_w = np.tile(
        np.concatenate([np.full(1000, 1e-3), np.full(1000, 1e-6)]),
        5,
    )
    _, _, boost_state, *_ = simulate_vcap(
        received_power_w,
        dt_s=0.001,
        harvester_config=_harvester_config(
            initial_v_cap=0.64,
            eta_constant=0.5,
            boost=_boost_config(
                enabled=True,
                v_on=0.66,
                v_off=0.64,
                load_power_w=3e-4,
            ),
        ),
    )
    transitions = np.count_nonzero(np.diff(boost_state) != 0)

    assert transitions >= 2


def test_boost_v_on_must_exceed_v_off() -> None:
    """Invalid hysteresis thresholds raise a clear ValueError."""
    with pytest.raises(ValueError, match="v_on > boost.v_off"):
        simulate_vcap(
            np.full(10, 1e-4),
            dt_s=0.001,
            harvester_config=_harvester_config(
                boost=_boost_config(enabled=True, v_on=0.64, v_off=0.64),
            ),
        )


def test_higher_rf_power_reaches_v_on_faster() -> None:
    """Stronger received RF power shortens charge time from V_OFF to V_ON."""
    config = _harvester_config(
        initial_v_cap=0.64,
        eta_constant=0.5,
        boost=_boost_config(enabled=True, v_on=0.66, v_off=0.64, load_power_w=0.0),
    )
    _, _, low_state, *_ = simulate_vcap(np.full(5000, 2e-4), 0.001, config)
    _, _, high_state, *_ = simulate_vcap(np.full(5000, 8e-4), 0.001, config)

    assert _first_on_index(high_state) < _first_on_index(low_state)


def test_higher_load_power_reaches_v_off_faster() -> None:
    """Stronger load draw shortens discharge time from V_ON to V_OFF."""
    low_load = _harvester_config(
        initial_v_cap=0.67,
        eta_constant=0.0,
        boost=_boost_config(enabled=True, v_on=0.66, v_off=0.64, load_power_w=1e-4),
    )
    high_load = _harvester_config(
        initial_v_cap=0.67,
        eta_constant=0.0,
        boost=_boost_config(enabled=True, v_on=0.66, v_off=0.64, load_power_w=5e-4),
    )
    _, _, low_state, *_ = simulate_vcap(np.zeros(5000), 0.001, low_load)
    _, _, high_state, *_ = simulate_vcap(np.zeros(5000), 0.001, high_load)

    assert _first_off_after_on_index(high_state) < _first_off_after_on_index(low_state)


def _first_on_index(boost_state: np.ndarray) -> int:
    """Return the first boost-on sample index."""
    on_indices = np.flatnonzero(boost_state == 1)
    assert on_indices.size > 0
    return int(on_indices[0])


def _first_off_after_on_index(boost_state: np.ndarray) -> int:
    """Return the first boost-off sample index after initially being on."""
    on_index = _first_on_index(boost_state)
    off_indices = np.flatnonzero(boost_state[on_index:] == 0)
    assert off_indices.size > 0
    return int(on_index + off_indices[0])
