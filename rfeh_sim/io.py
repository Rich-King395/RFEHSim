"""Output utilities for v0 simulation results."""

from __future__ import annotations

from pathlib import Path
import re

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
    data = {
        "time_s": result.time_s,
        "received_power_w": result.received_power_w,
        "harvested_power_w": result.harvested_power_w,
        "v_cap": result.v_cap,
        "boost_state": result.boost_state,
        "capacitor_energy_j": result.capacitor_energy_j,
        "net_capacitor_power_w": result.net_capacitor_power_w,
    }
    columns = list(TRACE_COLUMNS)
    for source_id, received_power_w in sorted(result.received_power_by_source.items()):
        column = f"received_power_{_safe_column_suffix(source_id)}_w"
        data[column] = received_power_w
        columns.append(column)
    for source_id, gain in sorted(result.small_scale_gain_by_source.items()):
        column = f"small_scale_gain_{_safe_column_suffix(source_id)}"
        data[column] = gain
        columns.append(column)
    return pd.DataFrame(data, columns=columns)


def save_trace_csv(result: SimResult, path: str | Path) -> Path:
    """Save simulation traces to CSV and return the written path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_to_dataframe(result).to_csv(output_path, index=False)
    return output_path


def _safe_column_suffix(source_id: str) -> str:
    """Convert a source identifier into a stable CSV column suffix."""
    suffix = re.sub(r"[^0-9A-Za-z_]+", "_", source_id.strip())
    return suffix or "source"
