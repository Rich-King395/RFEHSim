"""V0 transmitter model converting traffic bursts into RF TxEvents."""

from __future__ import annotations

import numpy as np

from rfeh_sim.models import ScenarioConfig, TrafficBurst, TransmitterConfig, TxEvent


def bursts_to_tx_events(
    bursts: list[TrafficBurst],
    transmitter_config: TransmitterConfig,
    scenario_config: ScenarioConfig,
    seed: int,
) -> list[TxEvent]:
    """Convert coarse traffic bursts into coarse RF transmission events.

    V0 intentionally avoids packet-level and Wi-Fi MAC/PHY details. Each burst
    becomes one mobile-originated RF event whose EIRP is based on the configured
    default EIRP in Watts multiplied by the burst power scale, with a small
    deterministic seeded jitter.

    Args:
        bursts: Traffic bursts generated from an app/action template.
        transmitter_config: Transmitter settings using internal Watt units.
        scenario_config: Scenario settings providing center frequency.
        seed: Random seed controlling small event jitter.

    Returns:
        A list of coarse transmission events.

    Raises:
        ValueError: If the configured EIRP or center frequency is invalid.
    """
    if transmitter_config.default_eirp_w <= 0.0:
        raise ValueError("Transmitter default EIRP must be positive.")
    if scenario_config.frequency_hz <= 0.0:
        raise ValueError("Scenario center frequency must be positive.")
    if seed < 0:
        raise ValueError("Random seed must be non-negative.")

    rng = np.random.default_rng(seed)
    tx_events: list[TxEvent] = []
    for burst in bursts:
        if burst.duration_s <= 0.0:
            continue

        duration_scale = min(1.0, max(0.70, 1.0 + float(rng.normal(0.0, 0.04))))
        eirp_scale = max(0.10, 1.0 + float(rng.normal(0.0, 0.03)))
        duration_s = burst.duration_s * duration_scale
        eirp_w = transmitter_config.default_eirp_w * burst.power_scale * eirp_scale

        tx_events.append(
            TxEvent(
                source_id="mobile",
                start_s=burst.start_s,
                duration_s=duration_s,
                eirp_w=eirp_w,
                center_freq_hz=scenario_config.frequency_hz,
                label=burst.label,
            )
        )

    return tx_events
