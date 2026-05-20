"""Tests for YAML configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from rfeh_sim.config import load_config
from rfeh_sim.models import FullConfig
from rfeh_sim.units import dbm_to_watt


def test_load_default_config() -> None:
    """The default v0 YAML file loads into typed configuration models."""
    config = load_config(Path("configs/default_v0.yaml"))

    assert isinstance(config, FullConfig)
    assert config.simulation.duration_s == pytest.approx(60.0)
    assert config.simulation.dt_s == pytest.approx(0.001)
    assert config.simulation.seed == 42
    assert config.scenario.app_id == "video_app"
    assert config.scenario.action_id == "play_video"
    assert config.scenario.distance_m == pytest.approx(0.5)
    assert config.scenario.frequency_hz == pytest.approx(2.437e9)
    assert config.app_traffic.repeat_mode == "periodic"
    assert config.app_traffic.period_s == pytest.approx(5.0)
    assert config.app_traffic.jitter_s == pytest.approx(0.2)
    assert config.transmitter.default_eirp_w == pytest.approx(dbm_to_watt(15.0))
    assert config.channel.ambient_power_w == pytest.approx(dbm_to_watt(-30.0))
    assert not hasattr(config.transmitter, "default_eirp_dbm")
    assert not hasattr(config.channel, "ambient_power_dbm")
    assert config.harvester.capacitance_f == pytest.approx(0.0022)
    assert config.harvester.eta_model == "constant"


def test_missing_required_section_raises(tmp_path: Path) -> None:
    """Missing top-level sections produce a clear configuration error."""
    config_path = tmp_path / "missing.yaml"
    config_path.write_text(
        """
simulation:
  duration_s: 1.0
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required section"):
        load_config(config_path)


def test_missing_required_field_raises_clear_error(tmp_path: Path) -> None:
    """Missing fields identify the exact section and field name."""
    config_path = tmp_path / "missing_field.yaml"
    config_path.write_text(
        """
simulation:
  duration_s: 1.0
  seed: 42
scenario:
  app_id: "video_app"
  action_id: "play_video"
  distance_m: 1.5
  frequency_hz: 2.437e9
transmitter:
  default_eirp_dbm: 15.0
channel:
  path_loss_exponent: 2.2
  reference_distance_m: 1.0
  shadowing_db: 0.0
  ambient_power_dbm: -30.0
harvester:
  capacitance_f: 0.001
  initial_v_cap: 0.1
  eta_model: "constant"
  eta_constant: 0.35
  leakage_w: 1.0e-7
  max_v_cap: 5.0
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="simulation.dt_s"):
        load_config(config_path)
