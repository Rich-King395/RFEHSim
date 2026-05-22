"""Tests for YAML configuration loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from rfeh_sim.config import load_config
from rfeh_sim.models import FullConfig
from rfeh_sim.units import db_to_linear, dbm_to_watt


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
    assert config.transmitter.model == "burst"
    assert config.transmitter.mobile_eirp_w_mean == pytest.approx(dbm_to_watt(15.0))
    assert config.transmitter.mobile_eirp_dbm_std == pytest.approx(0.0)
    assert config.transmitter.ap_eirp_w_mean == pytest.approx(dbm_to_watt(15.0))
    assert config.transmitter.ap_eirp_dbm_std == pytest.approx(0.0)
    assert config.wifi.chunk_payload_bytes == 1500
    assert config.wifi.mobile_phy_rate_bps == pytest.approx(54.0e6)
    assert config.wifi.ap_phy_rate_bps == pytest.approx(54.0e6)
    assert config.channel.ambient_power_w == pytest.approx(dbm_to_watt(-30.0))
    assert config.channel.small_scale.enabled is False
    assert config.channel.small_scale.model == "none"
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


def test_load_small_scale_fading_config() -> None:
    """The small-scale fading example loads with dB values converted."""
    config = load_config(Path("configs/small_scale_fading_v0.yaml"))

    assert config.channel.small_scale.enabled is True
    assert config.channel.small_scale.model == "rician"
    assert config.channel.small_scale.k_factor_linear == pytest.approx(db_to_linear(6.0))
    assert config.channel.small_scale.coherence_time_s == pytest.approx(0.2)
    assert config.channel.small_scale.normalize_mean is True


def test_load_periodic_cyclic_receiver_config_uses_constant_eta() -> None:
    """The periodic/cyclic receiver example keeps constant RF-to-DC efficiency."""
    config = load_config(Path("configs/periodic_tx_cyclic_rx_v0.yaml"))

    assert config.harvester.eta_model == "constant"
    assert config.harvester.eta_constant == pytest.approx(0.45)


def test_load_source_specific_scenario_distances() -> None:
    """The transaction example can set different mobile and AP distances."""
    config = load_config(Path("configs/transaction_transmitter_v1.yaml"))

    assert config.scenario.distance_m == pytest.approx(0.5)
    assert config.scenario.mobile_distance_m == pytest.approx(0.5)
    assert config.scenario.ap_distance_m == pytest.approx(0.3)


def test_load_source_distances_mapping(tmp_path: Path) -> None:
    """The extensible source_distances_m mapping loads positive distances."""
    config_path = tmp_path / "source_distances.yaml"
    config_path.write_text(
        """
simulation:
  duration_s: 1.0
  dt_s: 0.001
  seed: 42
scenario:
  app_id: "video_app"
  action_id: "play_video"
  frequency_hz: 2.437e9
  source_distances_m:
    mobile: 0.5
    ap: 0.3
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

    config = load_config(config_path)

    assert config.scenario.distance_m is None
    assert config.scenario.source_distances_m == {"mobile": 0.5, "ap": 0.3}


def test_invalid_source_distance_mapping_raises(tmp_path: Path) -> None:
    """Source-specific distances must be finite and positive."""
    config_path = tmp_path / "invalid_source_distance.yaml"
    config_path.write_text(
        """
simulation:
  duration_s: 1.0
  dt_s: 0.001
  seed: 42
scenario:
  app_id: "video_app"
  action_id: "play_video"
  frequency_hz: 2.437e9
  source_distances_m:
    mobile: 0.0
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

    with pytest.raises(ValueError, match="source_distances_m.mobile"):
        load_config(config_path)


def test_load_transmitter_v1_config_fields(tmp_path: Path) -> None:
    """New transmitter and Wi-Fi schema fields load without changing behavior."""
    config_path = tmp_path / "transmitter_v1_fields.yaml"
    config_path.write_text(
        """
simulation:
  duration_s: 1.0
  dt_s: 0.001
  seed: 42
scenario:
  app_id: "video_app"
  action_id: "play_video"
  distance_m: 1.5
  frequency_hz: 2.437e9
transmitter:
  default_eirp_dbm: 15.0
  model: "transaction"
  mobile_eirp_dbm_mean: 14.0
  mobile_eirp_dbm_std: 1.0
  ap_eirp_dbm_mean: 20.0
  ap_eirp_dbm_std: 2.0
wifi:
  center_freq_hz: 2.437e9
  bandwidth_hz: 20e6
  chunk_payload_bytes: 1500
  mac_overhead_bytes: 64
  preamble_s: 4.0e-5
  mobile_phy_rate_mbps: 54.0
  ap_phy_rate_mbps: 48.0
  mac_ack_enabled: true
  sifs_s: 1.6e-5
  mac_ack_duration_s: 4.0e-5
  mac_ack_eirp_dbm: 10.0
  transport_ack_enabled: true
  transport_ack_ratio: 0.02
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

    config = load_config(config_path)

    assert config.transmitter.model == "transaction"
    assert config.transmitter.mobile_eirp_w_mean == pytest.approx(dbm_to_watt(14.0))
    assert config.transmitter.mobile_eirp_dbm_std == pytest.approx(1.0)
    assert config.transmitter.ap_eirp_w_mean == pytest.approx(dbm_to_watt(20.0))
    assert config.transmitter.ap_eirp_dbm_std == pytest.approx(2.0)
    assert config.wifi.center_freq_hz == pytest.approx(2.437e9)
    assert config.wifi.bandwidth_hz == pytest.approx(20e6)
    assert config.wifi.chunk_payload_bytes == 1500
    assert config.wifi.mac_overhead_bytes == 64
    assert config.wifi.mobile_phy_rate_bps == pytest.approx(54.0e6)
    assert config.wifi.ap_phy_rate_bps == pytest.approx(48.0e6)
    assert config.wifi.mac_ack_enabled is True
    assert config.wifi.mac_ack_eirp_w == pytest.approx(dbm_to_watt(10.0))
    assert config.wifi.transport_ack_enabled is True
    assert config.wifi.transport_ack_ratio == pytest.approx(0.02)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("mobile_eirp_dbm_std", -1.0, "mobile_eirp_dbm_std"),
        ("ap_eirp_dbm_std", -1.0, "ap_eirp_dbm_std"),
    ],
)
def test_invalid_transmitter_v1_eirp_std_raises(
    tmp_path: Path,
    field: str,
    value: float,
    match: str,
) -> None:
    """EIRP standard deviation fields must be non-negative."""
    config_path = tmp_path / "invalid_transmitter.yaml"
    config_path.write_text(
        f"""
simulation:
  duration_s: 1.0
  dt_s: 0.001
  seed: 42
scenario:
  app_id: "video_app"
  action_id: "play_video"
  distance_m: 1.5
  frequency_hz: 2.437e9
transmitter:
  default_eirp_dbm: 15.0
  {field}: {value}
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

    with pytest.raises(ValueError, match=match):
        load_config(config_path)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("chunk_payload_bytes", 0, "chunk_payload_bytes"),
        ("mobile_phy_rate_mbps", 0.0, "mobile_phy_rate_mbps"),
        ("ap_phy_rate_mbps", 0.0, "ap_phy_rate_mbps"),
        ("transport_ack_ratio", -0.01, "transport_ack_ratio"),
    ],
)
def test_invalid_wifi_config_raises(
    tmp_path: Path,
    field: str,
    value: float,
    match: str,
) -> None:
    """Wi-Fi config validates sizes, rates, and ACK ratio."""
    config_path = tmp_path / "invalid_wifi.yaml"
    config_path.write_text(
        f"""
simulation:
  duration_s: 1.0
  dt_s: 0.001
  seed: 42
scenario:
  app_id: "video_app"
  action_id: "play_video"
  distance_m: 1.5
  frequency_hz: 2.437e9
transmitter:
  default_eirp_dbm: 15.0
wifi:
  {field}: {value}
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

    with pytest.raises(ValueError, match=match):
        load_config(config_path)
