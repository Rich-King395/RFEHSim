"""Output utilities for v0 simulation results."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import pandas as pd
import yaml

from rfeh_sim.models import FullConfig, SimResult

TRACE_COLUMNS = [
    "time_s",
    "received_power_w",
    "harvested_power_w",
    "v_cap",
    "capacitor_energy_j",
    "net_capacitor_power_w",
]

TX_EVENT_COLUMNS = [
    "source_id",
    "source_type",
    "device_id",
    "target_device_id",
    "start_s",
    "duration_s",
    "eirp_w",
    "direction",
    "frame_type",
    "payload_bytes",
    "phy_rate_bps",
    "label",
]


def result_to_dataframe(result: SimResult) -> pd.DataFrame:
    """Convert a simulation result into a tabular trace dataframe."""
    data = {
        "time_s": result.time_s,
        "received_power_w": result.received_power_w,
        "harvested_power_w": result.harvested_power_w,
        "v_cap": result.v_cap,
        "capacitor_energy_j": result.capacitor_energy_j,
        "net_capacitor_power_w": result.net_capacitor_power_w,
    }
    columns = list(TRACE_COLUMNS)
    for source_id, received_power_w in sorted(result.received_power_by_source.items()):
        column = f"received_power_{_safe_column_suffix(source_id)}_w"
        data[column] = received_power_w
        columns.append(column)
    return pd.DataFrame(data, columns=columns)


def save_trace_csv(result: SimResult, path: str | Path) -> Path:
    """Save simulation traces to CSV and return the written path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result_to_dataframe(result).to_csv(output_path, index=False)
    return output_path


def tx_events_to_dataframe(result: SimResult) -> pd.DataFrame:
    """Convert TxEvents into a tabular dataframe for diagnostics."""
    rows = [
        {
            "source_id": event.source_id,
            "source_type": event.source_type,
            "device_id": event.device_id,
            "target_device_id": event.target_device_id,
            "start_s": event.start_s,
            "duration_s": event.duration_s,
            "eirp_w": event.eirp_w,
            "direction": event.direction,
            "frame_type": event.frame_type,
            "payload_bytes": event.payload_bytes,
            "phy_rate_bps": event.phy_rate_bps,
            "label": event.label,
        }
        for event in result.tx_events
    ]
    return pd.DataFrame(rows, columns=TX_EVENT_COLUMNS)


def save_tx_events_csv(result: SimResult, path: str | Path) -> Path:
    """Save TxEvent diagnostics to CSV and return the written path."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tx_events_to_dataframe(result).to_csv(output_path, index=False)
    return output_path


def save_settings_txt(
    config: FullConfig,
    config_path: str | Path,
    path: str | Path,
) -> Path:
    """Save the experiment settings used for a run in ``parameter: value`` form."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_path = Path(config_path)
    raw_config = _load_raw_yaml_settings(source_path)

    lines = [
        f"Number of mobile devices: {len(config.scenario.mobile_devices)}",
    ]
    if config.scenario.ap is not None:
        lines.append(f"AP ID: {config.scenario.ap.ap_id} distance_m: {config.scenario.ap.distance_m}")
    for device in config.scenario.mobile_devices:
        lines.append(f"Mobile device {device.device_id} app/action: {device.app_id}/{device.action_id}")
        lines.append(f"Mobile device {device.device_id} distance_m: {device.distance_m}")

    lines.append("")
    lines.append("YAML settings: start")
    for key, value in _flatten_settings("", raw_config):
        lines.append(f"{key}: {_format_setting_value(value)}")
    lines.append("YAML settings: end")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def _safe_column_suffix(source_id: str) -> str:
    """Convert a source identifier into a stable CSV column suffix."""
    suffix = re.sub(r"[^0-9A-Za-z_]+", "_", source_id.strip())
    return suffix or "source"


def _load_raw_yaml_settings(config_path: Path) -> dict[str, Any]:
    """Load raw YAML settings for human-readable output."""
    with config_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)
    if not isinstance(raw, dict):
        return {}
    return raw


def _flatten_settings(prefix: str, value: Any) -> list[tuple[str, Any]]:
    """Flatten nested YAML settings into stable dotted parameter names."""
    if isinstance(value, dict):
        if not value:
            return [(prefix, {})] if prefix else []
        items: list[tuple[str, Any]] = []
        for key, child_value in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            items.extend(_flatten_settings(child_prefix, child_value))
        return items
    if isinstance(value, list):
        if not value:
            return [(prefix, [])]
        items = []
        for index, child_value in enumerate(value):
            child_prefix = f"{prefix}[{index}]"
            items.extend(_flatten_settings(child_prefix, child_value))
        return items
    return [(prefix, value)]


def _format_setting_value(value: Any) -> str:
    """Format a YAML scalar for ``Setting.txt``."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)
