"""End-to-end v0 simulation engine."""

from __future__ import annotations

import numpy as np

from rfeh_sim.channel import (
    generate_small_scale_gain_by_source,
    received_power_by_source_trace,
)
from rfeh_sim.harvester import simulate_vcap
from rfeh_sim.models import FullConfig, SimResult
from rfeh_sim.transmitter import generate_tx_events_for_simulation


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

    transmitter_result = generate_tx_events_for_simulation(config)
    tx_events = transmitter_result.tx_events
    channel_seed = config.simulation.seed + 2
    received_power_by_source = received_power_by_source_trace(
        tx_events=tx_events,
        time_s=time_s,
        scenario_config=config.scenario,
        channel_config=config.channel,
        seed=channel_seed,
    )
    received_power_w = np.full(
        time_s.shape,
        config.channel.ambient_power_w,
        dtype=float,
    )
    for source_power_w in received_power_by_source.values():
        received_power_w += source_power_w
    small_scale_gain_by_source = generate_small_scale_gain_by_source(
        tx_events=tx_events,
        time_s=time_s,
        fading_config=config.channel.small_scale,
        seed=channel_seed,
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
        received_power_by_source=received_power_by_source,
        harvested_power_w=harvested_power_w,
        v_cap=v_cap,
        boost_state=boost_state,
        capacitor_energy_j=capacitor_energy_j,
        net_capacitor_power_w=net_capacitor_power_w,
        small_scale_gain_by_source=small_scale_gain_by_source,
        traffic_bursts=transmitter_result.traffic_bursts,
        action_instances=transmitter_result.action_instances,
        network_transactions=transmitter_result.network_transactions,
        chunk_events=transmitter_result.chunk_events,
        tx_events=tx_events,
    )
