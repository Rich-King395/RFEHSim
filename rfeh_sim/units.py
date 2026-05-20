"""Unit conversion helpers for RF power and path-gain calculations."""

from __future__ import annotations

import math


def dbm_to_watt(dbm: float) -> float:
    """Convert power from dBm to Watts."""
    return 1e-3 * 10.0 ** (dbm / 10.0)


def watt_to_dbm(watt: float) -> float:
    """Convert power from Watts to dBm.

    Raises:
        ValueError: If ``watt`` is not strictly positive.
    """
    if watt <= 0.0:
        raise ValueError("Power in Watts must be positive to convert to dBm.")
    return 10.0 * math.log10(watt / 1e-3)


def db_to_linear(db: float) -> float:
    """Convert a decibel ratio to a linear ratio."""
    return 10.0 ** (db / 10.0)


def linear_to_db(linear: float) -> float:
    """Convert a linear ratio to decibels.

    Raises:
        ValueError: If ``linear`` is not strictly positive.
    """
    if linear <= 0.0:
        raise ValueError("Linear ratio must be positive to convert to dB.")
    return 10.0 * math.log10(linear)
