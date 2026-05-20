"""End-to-end v0 simulation engine."""

from __future__ import annotations

import numpy as np

from rfeh_sim.app_templates import generate_traffic_bursts
from rfeh_sim.channel import received_power_trace
from rfeh_sim.harvester import simulate_vcap
from rfeh_sim.models import FullConfig, SimResult
from rfeh_sim.transmitter import bursts_to_tx_events


def run_simulation(config: FullConfig) -> SimResult:
    """Run the v0 RF energy harvesting side-channel simulation pipeline.

    The pipeline is:
    app/action template -> traffic bursts -> TxEvents -> received RF power ->
    harvested power -> storage capacitor voltage.

    Args:
        config: Fully loaded simulator configuration.

    Returns:
        Simulation result containing final traces and intermediate objects.

    Raises:
        ValueError: If simulation duration or timestep is invalid.
    """
    if config.simulation.duration_s <= 0.0:
        raise ValueError("Simulation duration must be positive.")
    if config.simulation.dt_s <= 0.0:
        raise ValueError("Simulation time step dt_s must be positive.")
    if config.simulation.seed < 0:
        raise ValueError("Simulation random seed must be non-negative.")

    time_s = np.arange(
        0.0,
        config.simulation.duration_s + 0.5 * config.simulation.dt_s,
        config.simulation.dt_s,
        dtype=float,
    )

    traffic_bursts = generate_traffic_bursts(
        app_id=config.scenario.app_id,
        action_id=config.scenario.action_id,
        duration_s=config.simulation.duration_s,
        seed=config.simulation.seed,
        app_traffic_config=config.app_traffic,
    )
    tx_events = bursts_to_tx_events(
        bursts=traffic_bursts,
        transmitter_config=config.transmitter,
        scenario_config=config.scenario,
        seed=config.simulation.seed + 1,
    )
    received_power_w = received_power_trace(
        tx_events=tx_events,
        time_s=time_s,
        scenario_config=config.scenario,
        channel_config=config.channel,
    )
    (
        harvested_power_w,
        v_cap,
        boost_state,
        capacitor_energy_j,
        net_capacitor_power_w,
    ) = simulate_vcap(
        received_power_w=received_power_w,
        dt_s=config.simulation.dt_s,
        harvester_config=config.harvester,
    )

    return SimResult(
        time_s=time_s,
        received_power_w=received_power_w,
        harvested_power_w=harvested_power_w,
        v_cap=v_cap,
        boost_state=boost_state,
        capacitor_energy_j=capacitor_energy_j,
        net_capacitor_power_w=net_capacitor_power_w,
        traffic_bursts=traffic_bursts,
        tx_events=tx_events,
    )
