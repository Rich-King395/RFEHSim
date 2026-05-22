"""Tests for Transmitter v1 Layer 1 action instance generation."""

from __future__ import annotations

from rfeh_sim.models import AppTrafficConfig
from rfeh_sim.transmitter import generate_action_instances


def _traffic_config(
    *,
    repeat_mode: str = "periodic",
    period_s: float = 5.0,
    jitter_s: float = 0.2,
    start_offset_s: float = 0.0,
    repeat_until_end: bool = True,
) -> AppTrafficConfig:
    """Create app traffic config for Layer 1 tests."""
    return AppTrafficConfig(
        repeat_mode=repeat_mode,
        period_s=period_s,
        jitter_s=jitter_s,
        start_offset_s=start_offset_s,
        repeat_until_end=repeat_until_end,
    )


def test_repeat_mode_none_generates_one_instance() -> None:
    """Non-repeating action scheduling creates exactly one ActionInstance."""
    actions = generate_action_instances(
        app_id="video_app",
        action_id="play_video",
        duration_s=60.0,
        app_traffic_config=_traffic_config(repeat_mode="none", start_offset_s=1.5),
        seed=42,
    )

    assert len(actions) == 1
    assert actions[0].start_s == 1.5
    assert actions[0].instance_id == 0
    assert actions[0].app_id == "video_app"
    assert actions[0].action_id == "play_video"


def test_periodic_mode_generates_multiple_instances_across_duration() -> None:
    """Periodic action scheduling spans beginning, middle, and end."""
    actions = generate_action_instances(
        app_id="video_app",
        action_id="play_video",
        duration_s=60.0,
        app_traffic_config=_traffic_config(jitter_s=0.0),
        seed=42,
    )
    starts = [action.start_s for action in actions]

    assert len(actions) > 1
    assert any(start < 2.0 for start in starts)
    assert any(start > 30.0 for start in starts)
    assert any(55.0 <= start <= 60.0 for start in starts)
    assert [action.instance_id for action in actions] == list(range(len(actions)))


def test_same_seed_gives_identical_action_instances() -> None:
    """Layer 1 action jitter is deterministic for the same seed."""
    config = _traffic_config(jitter_s=0.2)
    first = generate_action_instances("video_app", "play_video", 60.0, config, seed=7)
    second = generate_action_instances("video_app", "play_video", 60.0, config, seed=7)

    assert first == second


def test_different_seed_changes_jittered_start_times() -> None:
    """Different seeds change periodic start times when jitter is enabled."""
    config = _traffic_config(jitter_s=0.2)
    first = generate_action_instances("video_app", "play_video", 60.0, config, seed=7)
    second = generate_action_instances("video_app", "play_video", 60.0, config, seed=8)

    assert [action.start_s for action in first] != [
        action.start_s for action in second
    ]


def test_action_instances_stay_inside_simulation_duration() -> None:
    """All generated ActionInstances stay inside the simulation window."""
    duration_s = 60.0
    actions = generate_action_instances(
        app_id="video_app",
        action_id="play_video",
        duration_s=duration_s,
        app_traffic_config=_traffic_config(jitter_s=0.2),
        seed=123,
    )

    assert actions
    for action in actions:
        assert 0.0 <= action.start_s <= duration_s


def test_periodic_instances_exist_after_30s_and_near_end() -> None:
    """For a 60 s, 5 s period run, Layer 1 covers late simulation time."""
    actions = generate_action_instances(
        app_id="video_app",
        action_id="play_video",
        duration_s=60.0,
        app_traffic_config=_traffic_config(period_s=5.0, jitter_s=0.0),
        seed=42,
    )
    starts = [action.start_s for action in actions]

    assert any(start >= 30.0 for start in starts)
    assert any(55.0 <= start <= 60.0 for start in starts)
