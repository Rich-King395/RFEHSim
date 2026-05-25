"""Tests for unit conversion helpers."""

from __future__ import annotations

import math

import pytest

from rfeh_sim.units import db_to_linear, dbm_to_watt, linear_to_db, watt_to_dbm


def test_dbm_to_watt_known_values() -> None:
    """Known dBm power levels convert to expected Watt values."""
    assert dbm_to_watt(0.0) == pytest.approx(1e-3)
    assert dbm_to_watt(30.0) == pytest.approx(1.0)
    assert dbm_to_watt(-30.0) == pytest.approx(1e-6)


def test_watt_to_dbm_known_values() -> None:
    """Known Watt power levels convert to expected dBm values."""
    assert watt_to_dbm(1e-3) == pytest.approx(0.0)
    assert watt_to_dbm(1.0) == pytest.approx(30.0)
    assert watt_to_dbm(1e-6) == pytest.approx(-30.0)


def test_dbm_watt_round_trip() -> None:
    """dBm to Watt conversion is reversible for positive powers."""
    for dbm in [-60.0, -30.0, 0.0, 15.0, 30.0]:
        assert watt_to_dbm(dbm_to_watt(dbm)) == pytest.approx(dbm)


def test_db_linear_round_trip() -> None:
    """dB to linear ratio conversion is reversible for positive ratios."""
    for db in [-20.0, -3.0, 0.0, 10.0, 40.0]:
        assert linear_to_db(db_to_linear(db)) == pytest.approx(db)


def test_log_conversions_reject_non_positive_inputs() -> None:
    """Logarithmic conversions reject zero and negative inputs."""
    for value in [0.0, -1.0, -math.inf]:
        with pytest.raises(ValueError):
            watt_to_dbm(value)
        with pytest.raises(ValueError):
            linear_to_db(value)
