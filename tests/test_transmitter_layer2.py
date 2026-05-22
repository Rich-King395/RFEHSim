"""Tests for Transmitter v1 Layer 2 network transaction generation."""

from __future__ import annotations

import pytest

from rfeh_sim.models import ActionInstance, NetworkTransaction
from rfeh_sim.transmitter import generate_network_transactions


def _action(app_id: str, action_id: str, instance_id: int = 0) -> ActionInstance:
    """Create an ActionInstance for Layer 2 tests."""
    return ActionInstance(
        start_s=1.0,
        app_id=app_id,
        action_id=action_id,
        instance_id=instance_id,
        label=f"{app_id}/{action_id}#{instance_id}",
    )


@pytest.mark.parametrize(
    ("app_id", "action_id"),
    [
        ("social_app", "like"),
        ("social_app", "share"),
        ("chat_app", "send_message"),
        ("video_app", "play_video"),
    ],
)
def test_known_app_action_returns_non_empty_transactions(
    app_id: str,
    action_id: str,
) -> None:
    """Every supported action template emits at least one transaction."""
    transactions = generate_network_transactions([_action(app_id, action_id)], seed=42)

    assert transactions
    assert all(isinstance(transaction, NetworkTransaction) for transaction in transactions)


def test_unknown_app_action_raises_value_error() -> None:
    """Unsupported app/action pairs fail with a clear ValueError."""
    with pytest.raises(ValueError, match="Unsupported app/action transaction template"):
        generate_network_transactions([_action("unknown_app", "unknown_action")], seed=42)


def test_same_seed_gives_identical_transactions() -> None:
    """Layer 2 transaction sampling is deterministic for the same seed."""
    action = _action("video_app", "play_video")
    first = generate_network_transactions([action], seed=7)
    second = generate_network_transactions([action], seed=7)

    assert first == second


def test_social_share_has_more_uplink_than_like_for_fixed_seed() -> None:
    """The share template is uplink-heavier than the like template."""
    like = generate_network_transactions([_action("social_app", "like")], seed=42)
    share = generate_network_transactions([_action("social_app", "share")], seed=42)

    assert sum(transaction.ul_bytes for transaction in share) > sum(
        transaction.ul_bytes for transaction in like
    )


def test_video_play_has_more_downlink_than_like_for_fixed_seed() -> None:
    """The video playback template is downlink-heavier than a social like."""
    like = generate_network_transactions([_action("social_app", "like")], seed=42)
    video = generate_network_transactions([_action("video_app", "play_video")], seed=42)

    assert sum(transaction.dl_bytes for transaction in video) > sum(
        transaction.dl_bytes for transaction in like
    )


def test_transactions_have_positive_duration_and_non_negative_bytes() -> None:
    """Generated transaction durations and byte counts are physically valid."""
    transactions = generate_network_transactions(
        [
            _action("social_app", "like", instance_id=0),
            _action("social_app", "share", instance_id=1),
            _action("chat_app", "send_message", instance_id=2),
            _action("video_app", "play_video", instance_id=3),
        ],
        seed=123,
    )

    assert transactions
    for transaction in transactions:
        assert transaction.duration_s > 0.0
        assert transaction.ul_bytes >= 0
        assert transaction.dl_bytes >= 0
        assert isinstance(transaction.ul_bytes, int)
        assert isinstance(transaction.dl_bytes, int)


def test_transaction_labels_are_set_correctly() -> None:
    """Templates set stable, expected transaction labels."""
    share = generate_network_transactions([_action("social_app", "share")], seed=42)
    video = generate_network_transactions([_action("video_app", "play_video")], seed=42)

    assert {transaction.label for transaction in share} == {
        "share_api",
        "preview_fetch",
        "telemetry",
    }
    assert {transaction.label for transaction in video} == {
        "metadata",
        "media_segment",
        "heartbeat",
    }


def test_transaction_start_includes_action_start_and_delay() -> None:
    """Transaction start times are offset from the parent ActionInstance."""
    action = _action("chat_app", "send_message")
    transactions = generate_network_transactions([action], seed=42)

    assert all(transaction.start_s >= action.start_s for transaction in transactions)
    assert all(transaction.action_instance_id == action.instance_id for transaction in transactions)
