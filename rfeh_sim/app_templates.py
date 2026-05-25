"""Hard-coded v0 app/action traffic burst templates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np

from rfeh_sim.models import AppTrafficConfig, TrafficBurst

Direction = Literal["uplink", "downlink", "mixed"]


@dataclass(frozen=True, slots=True)
class _BurstTemplate:
    """Internal nominal burst template before seeded jitter is applied."""

    start_s: float
    duration_s: float
    power_scale: float
    direction: Direction
    label: str


_TEMPLATES: dict[tuple[str, str], tuple[_BurstTemplate, ...]] = {
    (
        "video_app",
        "play_video",
    ): (
        _BurstTemplate(0.10, 0.35, 1.20, "mixed", "playback_request"),
        _BurstTemplate(0.75, 1.20, 0.95, "downlink", "initial_buffer"),
        _BurstTemplate(2.50, 0.50, 0.70, "downlink", "buffer_refill"),
        _BurstTemplate(5.50, 0.45, 0.65, "downlink", "buffer_refill"),
    ),
    (
        "social_app",
        "like",
    ): (
        _BurstTemplate(0.05, 0.12, 0.75, "uplink", "like_request"),
        _BurstTemplate(0.25, 0.10, 0.45, "downlink", "like_ack"),
    ),
    (
        "social_app",
        "share",
    ): (
        _BurstTemplate(0.05, 0.20, 0.90, "uplink", "share_request"),
        _BurstTemplate(0.35, 0.35, 0.80, "mixed", "metadata_sync"),
        _BurstTemplate(0.90, 0.18, 0.50, "downlink", "share_ack"),
    ),
    (
        "chat_app",
        "send_message",
    ): (
        _BurstTemplate(0.03, 0.10, 0.70, "uplink", "message_upload"),
        _BurstTemplate(0.18, 0.08, 0.40, "downlink", "server_ack"),
        _BurstTemplate(0.45, 0.12, 0.35, "mixed", "receipt_sync"),
    ),
}


def generate_traffic_bursts(
    app_id: str,
    action_id: str,
    duration_s: float,
    seed: int,
    app_traffic_config: AppTrafficConfig | None = None,
) -> list[TrafficBurst]:
    """Generate deterministic coarse traffic bursts for a supported app/action.

    The v0 templates are synthetic and intentionally simple. They are not
    reverse-engineered traces; they provide plausible burst structure for the
    downstream RF and energy-harvesting models.

    Args:
        app_id: Synthetic application identifier.
        action_id: Synthetic user action identifier.
        duration_s: Total simulation duration in seconds.
        seed: Random seed controlling small timing jitter.

    Returns:
        Traffic bursts clipped to the simulation window.

    Raises:
        ValueError: If the app/action pair is unsupported or duration is invalid.
    """
    if duration_s <= 0.0:
        raise ValueError("Simulation duration must be positive.")
    if seed < 0:
        raise ValueError("Random seed must be non-negative.")

    key = (app_id, action_id)
    templates = _TEMPLATES.get(key)
    if templates is None:
        supported = ", ".join(f"{app}/{action}" for app, action in sorted(_TEMPLATES))
        raise ValueError(
            f"Unsupported app/action template: {app_id}/{action_id}. "
            f"Supported templates: {supported}."
        )

    if app_traffic_config is None or app_traffic_config.repeat_mode == "none":
        return _generate_single_template_pass(templates, duration_s, seed)

    return _generate_periodic_template_passes(templates, duration_s, seed, app_traffic_config)


def _generate_single_template_pass(
    templates: tuple[_BurstTemplate, ...],
    duration_s: float,
    seed: int,
) -> list[TrafficBurst]:
    """Generate the original finite v0 traffic burst sequence."""
    rng = np.random.default_rng(seed)
    bursts: list[TrafficBurst] = []
    for template in templates:
        start_s = template.start_s + float(rng.normal(0.0, 0.015))
        duration_jitter = 1.0 + float(rng.normal(0.0, 0.08))
        duration = template.duration_s * max(0.50, duration_jitter)

        start_s = min(max(0.0, start_s), duration_s)
        end_s = min(duration_s, start_s + duration)
        clipped_duration_s = end_s - start_s
        if clipped_duration_s <= 0.0:
            continue

        bursts.append(
            TrafficBurst(
                start_s=start_s,
                duration_s=clipped_duration_s,
                power_scale=template.power_scale,
                direction=template.direction,
                label=template.label,
            )
        )

    return bursts


def _generate_periodic_template_passes(
    templates: tuple[_BurstTemplate, ...],
    duration_s: float,
    seed: int,
    app_traffic_config: AppTrafficConfig,
) -> list[TrafficBurst]:
    """Tile the base traffic template periodically across the simulation."""
    if app_traffic_config.period_s <= 0.0:
        raise ValueError("Periodic traffic period_s must be positive.")
    if app_traffic_config.jitter_s < 0.0:
        raise ValueError("Periodic traffic jitter_s must be non-negative.")

    rng = np.random.default_rng(seed)
    bursts: list[TrafficBurst] = []
    period_index = 0
    while True:
        nominal_period_start_s = (
            app_traffic_config.start_offset_s
            + period_index * app_traffic_config.period_s
        )
        if nominal_period_start_s >= duration_s:
            break

        period_jitter_s = 0.0
        if app_traffic_config.jitter_s > 0.0:
            period_jitter_s = float(
                rng.uniform(-app_traffic_config.jitter_s, app_traffic_config.jitter_s)
            )

        period_start_s = max(0.0, nominal_period_start_s + period_jitter_s)
        for template in templates:
            start_s = period_start_s + template.start_s
            if start_s >= duration_s:
                continue
            end_s = min(duration_s, start_s + template.duration_s)
            clipped_duration_s = end_s - start_s
            if clipped_duration_s <= 0.0:
                continue
            bursts.append(
                TrafficBurst(
                    start_s=start_s,
                    duration_s=clipped_duration_s,
                    power_scale=template.power_scale,
                    direction=template.direction,
                    label=template.label,
                )
            )

        period_index += 1
        if not app_traffic_config.repeat_until_end:
            break

    return sorted(bursts, key=lambda burst: burst.start_s)
