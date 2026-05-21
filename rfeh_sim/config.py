"""YAML configuration loading for the v0 simulator."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import yaml

from rfeh_sim.models import (
    AppTrafficConfig,
    BoostConfig,
    ChannelConfig,
    FullConfig,
    HarvesterConfig,
    ScenarioConfig,
    SmallScaleFadingConfig,
    SimulationConfig,
    TransmitterConfig,
)
from rfeh_sim.units import db_to_linear, dbm_to_watt


def load_config(path: str | Path) -> FullConfig:
    """Load a YAML simulator configuration file.

    Power values expressed in dBm at the YAML boundary are converted to Watts
    before the returned dataclasses are created.

    Args:
        path: Path to a YAML configuration file.

    Returns:
        A validated ``FullConfig`` instance.

    Raises:
        ValueError: If the YAML document is invalid or required values are missing.
    """
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)

    if not isinstance(raw, dict):
        raise ValueError(f"Configuration file is empty or invalid: {config_path}")

    _require_sections(
        raw,
        ["simulation", "scenario", "transmitter", "channel", "harvester"],
    )

    simulation_raw = _require_mapping(raw, "simulation")
    scenario_raw = _require_mapping(raw, "scenario")
    app_traffic_raw = _optional_mapping(raw, "app_traffic")
    transmitter_raw = _require_mapping(raw, "transmitter")
    channel_raw = _require_mapping(raw, "channel")
    small_scale_raw = _optional_mapping(channel_raw, "small_scale")
    harvester_raw = _require_mapping(raw, "harvester")
    boost_raw = _optional_mapping(harvester_raw, "boost")

    return FullConfig(
        simulation=SimulationConfig(
            duration_s=_required_float(simulation_raw, "simulation", "duration_s"),
            dt_s=_required_float(simulation_raw, "simulation", "dt_s"),
            seed=_required_int(simulation_raw, "simulation", "seed"),
        ),
        scenario=ScenarioConfig(
            app_id=_required_str(scenario_raw, "scenario", "app_id"),
            action_id=_required_str(scenario_raw, "scenario", "action_id"),
            distance_m=_required_float(scenario_raw, "scenario", "distance_m"),
            frequency_hz=_required_float(scenario_raw, "scenario", "frequency_hz"),
        ),
        app_traffic=_load_app_traffic_config(app_traffic_raw),
        transmitter=TransmitterConfig(
            default_eirp_w=dbm_to_watt(
                _required_float(transmitter_raw, "transmitter", "default_eirp_dbm")
            ),
        ),
        channel=ChannelConfig(
            path_loss_exponent=_required_float(
                channel_raw,
                "channel",
                "path_loss_exponent",
            ),
            reference_distance_m=_required_float(
                channel_raw,
                "channel",
                "reference_distance_m",
            ),
            shadowing_db=_required_float(channel_raw, "channel", "shadowing_db"),
            ambient_power_w=dbm_to_watt(
                _required_float(channel_raw, "channel", "ambient_power_dbm")
            ),
            small_scale=_load_small_scale_config(small_scale_raw),
        ),
        harvester=HarvesterConfig(
            capacitance_f=_required_float(
                harvester_raw,
                "harvester",
                "capacitance_f",
            ),
            initial_v_cap=_required_float(
                harvester_raw,
                "harvester",
                "initial_v_cap",
            ),
            eta_model=_required_str(harvester_raw, "harvester", "eta_model"),
            eta_constant=_required_float(harvester_raw, "harvester", "eta_constant"),
            leakage_w=_required_float(harvester_raw, "harvester", "leakage_w"),
            max_v_cap=_required_float(harvester_raw, "harvester", "max_v_cap"),
            boost=_load_boost_config(boost_raw),
        ),
    )


def _require_sections(raw: dict[str, Any], section_names: list[str]) -> None:
    """Ensure all top-level configuration sections are present."""
    missing = [name for name in section_names if name not in raw]
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"Configuration is missing required section(s): {missing_text}")


def _require_mapping(raw: dict[str, Any], section: str) -> dict[str, Any]:
    """Return a required YAML section as a mapping."""
    value = raw[section]
    if not isinstance(value, dict):
        raise ValueError(f"Configuration section '{section}' must be a mapping.")
    return value


def _optional_mapping(raw: dict[str, Any], section: str) -> dict[str, Any]:
    """Return an optional YAML section as a mapping, or an empty mapping."""
    if section not in raw:
        return {}
    value = raw[section]
    if not isinstance(value, dict):
        raise ValueError(f"Configuration section '{section}' must be a mapping.")
    return value


def _load_app_traffic_config(raw: dict[str, Any]) -> AppTrafficConfig:
    """Load optional app/action traffic repetition settings."""
    repeat_mode = str(raw.get("repeat_mode", "none"))
    if repeat_mode not in {"none", "periodic"}:
        raise ValueError(
            "Configuration field 'app_traffic.repeat_mode' must be 'none' "
            "or 'periodic'."
        )

    period_s = _optional_float(raw, "app_traffic", "period_s", 0.0)
    jitter_s = _optional_float(raw, "app_traffic", "jitter_s", 0.0)
    start_offset_s = _optional_float(raw, "app_traffic", "start_offset_s", 0.0)
    repeat_until_end = _optional_bool(
        raw,
        "app_traffic",
        "repeat_until_end",
        True,
    )

    if repeat_mode == "periodic" and period_s <= 0.0:
        raise ValueError(
            "Configuration field 'app_traffic.period_s' must be positive "
            "when repeat_mode='periodic'."
        )
    if jitter_s < 0.0:
        raise ValueError("Configuration field 'app_traffic.jitter_s' must be >= 0.")
    if start_offset_s < 0.0:
        raise ValueError(
            "Configuration field 'app_traffic.start_offset_s' must be >= 0."
        )

    return AppTrafficConfig(
        repeat_mode=repeat_mode,
        period_s=period_s,
        jitter_s=jitter_s,
        start_offset_s=start_offset_s,
        repeat_until_end=repeat_until_end,
    )


def _load_boost_config(raw: dict[str, Any]) -> BoostConfig:
    """Load optional threshold-controlled boost/load settings."""
    enabled = _optional_bool(raw, "harvester.boost", "enabled", False)
    boost = BoostConfig(
        enabled=enabled,
        v_on=_optional_float(raw, "harvester.boost", "v_on", 0.0),
        v_off=_optional_float(raw, "harvester.boost", "v_off", 0.0),
        output_voltage_v=_optional_float(
            raw,
            "harvester.boost",
            "output_voltage_v",
            0.0,
        ),
        load_power_w=_optional_float(raw, "harvester.boost", "load_power_w", 0.0),
        efficiency=_optional_float(raw, "harvester.boost", "efficiency", 1.0),
        quiescent_power_on_w=_optional_float(
            raw,
            "harvester.boost",
            "quiescent_power_on_w",
            0.0,
        ),
        quiescent_power_off_w=_optional_float(
            raw,
            "harvester.boost",
            "quiescent_power_off_w",
            0.0,
        ),
    )
    if not enabled:
        return boost
    if boost.v_on <= boost.v_off:
        raise ValueError("Configuration requires harvester.boost.v_on > v_off.")
    if boost.output_voltage_v <= 0.0:
        raise ValueError(
            "Configuration field 'harvester.boost.output_voltage_v' must be positive."
        )
    if boost.load_power_w < 0.0:
        raise ValueError(
            "Configuration field 'harvester.boost.load_power_w' must be >= 0."
        )
    if not 0.0 < boost.efficiency <= 1.0:
        raise ValueError(
            "Configuration field 'harvester.boost.efficiency' must be in (0, 1]."
        )
    if boost.quiescent_power_on_w < 0.0:
        raise ValueError(
            "Configuration field 'harvester.boost.quiescent_power_on_w' must be >= 0."
        )
    if boost.quiescent_power_off_w < 0.0:
        raise ValueError(
            "Configuration field 'harvester.boost.quiescent_power_off_w' must be >= 0."
        )
    return boost


def _load_small_scale_config(raw: dict[str, Any]) -> SmallScaleFadingConfig:
    """Load optional flat small-scale fading channel settings."""
    enabled = _optional_bool(raw, "channel.small_scale", "enabled", False)
    model = str(raw.get("model", "none"))
    if model not in {"none", "rayleigh", "rician"}:
        raise ValueError(
            "Configuration field 'channel.small_scale.model' must be 'none', "
            "'rayleigh', or 'rician'."
        )

    doppler_hz = _optional_nullable_float(
        raw,
        "channel.small_scale",
        "doppler_hz",
        None,
    )
    coherence_time_s = _optional_nullable_float(
        raw,
        "channel.small_scale",
        "coherence_time_s",
        None,
    )
    if coherence_time_s is None:
        if doppler_hz is not None:
            if doppler_hz <= 0.0:
                raise ValueError(
                    "Configuration field 'channel.small_scale.doppler_hz' "
                    "must be positive when provided."
                )
            coherence_time_s = 0.423 / doppler_hz
        else:
            coherence_time_s = 0.2
    if coherence_time_s <= 0.0:
        raise ValueError(
            "Configuration field 'channel.small_scale.coherence_time_s' "
            "must be positive."
        )

    k_factor_db = _optional_float(raw, "channel.small_scale", "k_factor_db", 0.0)
    k_factor_linear = db_to_linear(k_factor_db)
    if k_factor_linear < 0.0:
        raise ValueError(
            "Configuration field 'channel.small_scale.k_factor_db' must convert "
            "to a non-negative linear K factor."
        )

    return SmallScaleFadingConfig(
        enabled=enabled,
        model=model,
        k_factor_linear=k_factor_linear,
        coherence_time_s=coherence_time_s,
        doppler_hz=doppler_hz,
        normalize_mean=_optional_bool(
            raw,
            "channel.small_scale",
            "normalize_mean",
            True,
        ),
        per_source_independent=_optional_bool(
            raw,
            "channel.small_scale",
            "per_source_independent",
            True,
        ),
        random_phase=_optional_bool(
            raw,
            "channel.small_scale",
            "random_phase",
            True,
        ),
    )


def _required_float(raw: dict[str, Any], section: str, field: str) -> float:
    """Read a required finite floating-point field with a clear error."""
    if field not in raw:
        raise ValueError(f"Configuration is missing required field '{section}.{field}'.")
    try:
        value = float(raw[field])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Configuration field '{section}.{field}' must be a finite number."
        ) from exc
    if not math.isfinite(value):
        raise ValueError(
            f"Configuration field '{section}.{field}' must be a finite number."
        )
    return value


def _optional_float(
    raw: dict[str, Any],
    section: str,
    field: str,
    default: float,
) -> float:
    """Read an optional finite floating-point field with a clear error."""
    if field not in raw:
        return default
    return _required_float(raw, section, field)


def _optional_nullable_float(
    raw: dict[str, Any],
    section: str,
    field: str,
    default: float | None,
) -> float | None:
    """Read an optional finite float, allowing explicit YAML null."""
    if field not in raw or raw[field] is None:
        return default
    return _required_float(raw, section, field)


def _optional_bool(
    raw: dict[str, Any],
    section: str,
    field: str,
    default: bool,
) -> bool:
    """Read an optional boolean field with a clear error."""
    if field not in raw:
        return default
    value = raw[field]
    if not isinstance(value, bool):
        raise ValueError(f"Configuration field '{section}.{field}' must be boolean.")
    return value


def _required_int(raw: dict[str, Any], section: str, field: str) -> int:
    """Read a required integer field with a clear error."""
    if field not in raw:
        raise ValueError(f"Configuration is missing required field '{section}.{field}'.")
    try:
        return int(raw[field])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Configuration field '{section}.{field}' must be an integer."
        ) from exc


def _required_str(raw: dict[str, Any], section: str, field: str) -> str:
    """Read a required string field with a clear error."""
    if field not in raw:
        raise ValueError(f"Configuration is missing required field '{section}.{field}'.")
    value = raw[field]
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"Configuration field '{section}.{field}' must be a non-empty string."
        )
    return value
