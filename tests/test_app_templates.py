"""Tests for synthetic app/action traffic templates."""

from __future__ import annotations

import pytest

from rfeh_sim.app_templates import generate_traffic_bursts
from rfeh_sim.models import AppTrafficConfig, TrafficBurst


def _periodic_config(
    *,
    period_s: float = 5.0,
    jitter_s: float = 0.2,
) -> AppTrafficConfig:
    """Create a periodic app traffic config for tests."""
    return AppTrafficConfig(
        repeat_mode="periodic",
        period_s=period_s,
        jitter_s=jitter_s,
        start_offset_s=0.0,
        repeat_until_end=True,
    )


def _none_config() -> AppTrafficConfig:
    """Create a non-repeating app traffic config for tests."""
    return AppTrafficConfig(
        repeat_mode="none",
        period_s=0.0,
        jitter_s=0.0,
        start_offset_s=0.0,
        repeat_until_end=True,
    )


@pytest.mark.parametrize(
    ("app_id", "action_id"),
    [
        ("video_app", "play_video"),
        ("social_app", "like"),
        ("social_app", "share"),
        ("chat_app", "send_message"),
    ],
)
def test_known_app_action_returns_non_empty_bursts(
    app_id: str,
    action_id: str,
) -> None:
    """Every supported app/action pair emits at least one traffic burst."""
    bursts = generate_traffic_bursts(app_id, action_id, duration_s=10.0, seed=42)

    assert bursts
    assert all(isinstance(burst, TrafficBurst) for burst in bursts)


def test_unknown_app_action_raises_value_error() -> None:
    """Unsupported app/action pairs fail with a clear ValueError."""
    with pytest.raises(ValueError, match="Unsupported app/action template"):
        generate_traffic_bursts(
            "unknown_app",
            "unknown_action",
            duration_s=10.0,
            seed=42,
        )


def test_same_seed_gives_identical_bursts() -> None:
    """Traffic generation is deterministic for the same seed."""
    first = generate_traffic_bursts("social_app", "share", duration_s=10.0, seed=7)
    second = generate_traffic_bursts("social_app", "share", duration_s=10.0, seed=7)

    assert first == second


def test_bursts_stay_inside_simulation_time() -> None:
    """Jittered and clipped bursts remain within the simulation window."""
    duration_s = 0.6
    bursts = generate_traffic_bursts(
        "video_app",
        "play_video",
        duration_s=duration_s,
        seed=123,
    )

    assert bursts
    for burst in bursts:
        assert 0.0 <= burst.start_s <= duration_s
        assert burst.duration_s > 0.0
        assert burst.start_s + burst.duration_s <= duration_s


def test_repeat_mode_none_preserves_finite_burst_behavior() -> None:
    """Non-periodic mode keeps the original finite early burst sequence."""
    implicit_none = generate_traffic_bursts(
        "video_app",
        "play_video",
        duration_s=60.0,
        seed=42,
    )
    explicit_none = generate_traffic_bursts(
        "video_app",
        "play_video",
        duration_s=60.0,
        seed=42,
        app_traffic_config=_none_config(),
    )

    assert explicit_none == implicit_none
    assert max(burst.start_s + burst.duration_s for burst in explicit_none) < 10.0


def test_periodic_mode_generates_bursts_across_full_duration() -> None:
    """Periodic mode tiles the app/action burst template through the run."""
    bursts = generate_traffic_bursts(
        "video_app",
        "play_video",
        duration_s=60.0,
        seed=42,
        app_traffic_config=_periodic_config(jitter_s=0.0),
    )

    assert any(burst.start_s < 2.0 for burst in bursts)
    assert any(25.0 <= burst.start_s <= 35.0 for burst in bursts)
    assert any(55.0 <= burst.start_s < 60.0 for burst in bursts)


def test_periodic_mode_same_seed_is_deterministic() -> None:
    """Periodic traffic jitter is deterministic for the same seed."""
    first = generate_traffic_bursts(
        "video_app",
        "play_video",
        duration_s=60.0,
        seed=7,
        app_traffic_config=_periodic_config(),
    )
    second = generate_traffic_bursts(
        "video_app",
        "play_video",
        duration_s=60.0,
        seed=7,
        app_traffic_config=_periodic_config(),
    )

    assert first == second


def test_periodic_mode_different_seeds_change_jittered_timings() -> None:
    """Different seeds produce different period jitter when jitter_s is positive."""
    first = generate_traffic_bursts(
        "video_app",
        "play_video",
        duration_s=60.0,
        seed=7,
        app_traffic_config=_periodic_config(jitter_s=0.2),
    )
    second = generate_traffic_bursts(
        "video_app",
        "play_video",
        duration_s=60.0,
        seed=8,
        app_traffic_config=_periodic_config(jitter_s=0.2),
    )

    assert [burst.start_s for burst in first] != [burst.start_s for burst in second]


def test_periodic_mode_keeps_bursts_inside_simulation_duration() -> None:
    """Periodic bursts are clipped or discarded at the simulation boundary."""
    duration_s = 60.0
    bursts = generate_traffic_bursts(
        "video_app",
        "play_video",
        duration_s=duration_s,
        seed=123,
        app_traffic_config=_periodic_config(),
    )

    assert bursts
    for burst in bursts:
        assert 0.0 <= burst.start_s < duration_s
        assert burst.duration_s > 0.0
        assert burst.start_s + burst.duration_s <= duration_s
