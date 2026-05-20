"""Output utilities for v0 simulation results."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from rfeh_sim.models import SimResult

TRACE_COLUMNS = [
    "time_s",
    "received_power_w",
    "harvested_power_w",
    "v_cap",
    "boost_state",
    "capacitor_energy_j",
    "net_capacitor_power_w",
]


def result_to_dataframe(result: SimResult) -> pd.DataFrame:
    """Convert a simulation result into a tabular trace dataframe."""
    return pd.DataFrame(
        {
            "time_s": result.time_s,
            "received_power_w": result.received_power_w,
            "harvested_power_w": result.harvested_power_w,
            "v_cap": result.v_cap,
            "boost_state": result.boost_state,
            "capacitor_energy_j": result.capacitor_energy_j,
            "net_capacitor_power_w": result.net_capacitor_power_w,
        },
        columns=TRACE_COLUMNS,
    )


def save_trace_csv(result: SimResult, path: str | Path) -> Path:
    """Save simulation traces to CSV and return the written path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_to_dataframe(result).to_csv(output_path, index=False)
    return output_path
