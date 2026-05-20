"""RF energy harvesting side-channel simulator package."""

from rfeh_sim.app_templates import generate_traffic_bursts
from rfeh_sim.channel import (
    free_space_path_loss_db,
    log_distance_path_loss_db,
    received_power_trace,
)
from rfeh_sim.config import load_config
from rfeh_sim.engine import run_simulation
from rfeh_sim.harvester import rf_to_dc_efficiency_constant, simulate_vcap
from rfeh_sim.io import result_to_dataframe, save_trace_csv
from rfeh_sim.models import (
    AppTrafficConfig,
    BoostConfig,
    ChannelConfig,
    FullConfig,
    HarvesterConfig,
    ScenarioConfig,
    SimResult,
    SimulationConfig,
    TrafficBurst,
    TransmitterConfig,
    TxEvent,
)
from rfeh_sim.transmitter import bursts_to_tx_events

__all__ = [
    "ChannelConfig",
    "AppTrafficConfig",
    "BoostConfig",
    "FullConfig",
    "HarvesterConfig",
    "ScenarioConfig",
    "SimResult",
    "SimulationConfig",
    "TrafficBurst",
    "TransmitterConfig",
    "TxEvent",
    "bursts_to_tx_events",
    "free_space_path_loss_db",
    "generate_traffic_bursts",
    "load_config",
    "log_distance_path_loss_db",
    "received_power_trace",
    "rf_to_dc_efficiency_constant",
    "result_to_dataframe",
    "run_simulation",
    "save_trace_csv",
    "simulate_vcap",
]
