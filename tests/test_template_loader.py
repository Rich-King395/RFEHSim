"""Tests for YAML-backed transaction template loading."""

from __future__ import annotations

import pytest

from rfeh_sim.app_actions import CANONICAL_APP_ACTIONS
from rfeh_sim.models import ActionInstance
from rfeh_sim.template_loader import (
    TransactionSpec,
    get_transaction_specs,
    load_transaction_template_registry,
)
from rfeh_sim.transmitter import generate_network_transactions


def _action(app_id: str, action_id: str) -> ActionInstance:
    """Create a representative action instance."""
    return ActionInstance(
        start_s=1.0,
        app_id=app_id,
        action_id=action_id,
        instance_id=0,
        label=f"{app_id}/{action_id}#0",
    )


def test_template_file_loads_successfully() -> None:
    """The packaged YAML template registry loads into TransactionSpecs."""
    registry = load_transaction_template_registry()

    assert registry
    assert all(isinstance(spec, TransactionSpec) for specs in registry.values() for spec in specs)


def test_all_required_app_action_combinations_exist() -> None:
    """Every canonical app/action has at least one transaction template."""
    registry = load_transaction_template_registry()

    for app_id, action_ids in CANONICAL_APP_ACTIONS.items():
        for action_id in action_ids:
            assert (app_id, action_id) in registry
            assert registry[(app_id, action_id)]


def test_transaction_template_ranges_are_valid() -> None:
    """Loaded template ranges satisfy physical and sampling constraints."""
    registry = load_transaction_template_registry()

    for specs in registry.values():
        for spec in specs:
            assert spec.start_delay_s[0] <= spec.start_delay_s[1]
            assert 0.0 <= spec.start_delay_s[0]
            assert 0.0 < spec.duration_s[0] <= spec.duration_s[1]
            assert 0 <= spec.ul_bytes[0] <= spec.ul_bytes[1]
            assert 0 <= spec.dl_bytes[0] <= spec.dl_bytes[1]
            assert 0.0 <= spec.probability <= 1.0
            if spec.repeat_count is not None:
                assert 0 <= spec.repeat_count[0] <= spec.repeat_count[1]
            if spec.repeat_interval_s is not None:
                assert 0.0 <= spec.repeat_interval_s[0] <= spec.repeat_interval_s[1]


@pytest.mark.parametrize(
    ("app_id", "action_id"),
    [
        ("video", "play"),
        ("music", "next"),
        ("social_media", "comment"),
        ("communication", "send_images"),
        ("game", "gaming"),
    ],
)
def test_get_transaction_specs_supports_canonical_names(
    app_id: str,
    action_id: str,
) -> None:
    """Canonical app/action names resolve through the template registry."""
    assert get_transaction_specs(app_id, action_id)


def test_get_transaction_specs_supports_legacy_aliases() -> None:
    """Old app/action names still resolve through normalization aliases."""
    assert get_transaction_specs("video_app", "play_video") == get_transaction_specs("video", "play")
    assert get_transaction_specs("social_app", "like") == get_transaction_specs(
        "social_media",
        "thumb_up",
    )
    assert get_transaction_specs("chat_app", "send_message") == get_transaction_specs(
        "communication",
        "send_text",
    )


def test_same_seed_gives_identical_yaml_generated_transactions() -> None:
    """YAML-backed transaction sampling remains deterministic."""
    action = _action("communication", "send_images")

    first = generate_network_transactions([action], seed=123)
    second = generate_network_transactions([action], seed=123)

    assert first == second


def test_different_seeds_change_yaml_sampled_values() -> None:
    """Different seeds affect sampled transaction timing or byte values."""
    action = _action("video", "play")

    first = generate_network_transactions([action], seed=123)
    second = generate_network_transactions([action], seed=124)

    assert first != second


def test_every_required_app_action_generates_transactions() -> None:
    """All canonical app/action pairs generate valid NetworkTransactions."""
    for app_id, action_ids in CANONICAL_APP_ACTIONS.items():
        for action_id in action_ids:
            transactions = generate_network_transactions([_action(app_id, action_id)], seed=42)
            assert transactions
            assert all(transaction.duration_s > 0.0 for transaction in transactions)
            assert all(transaction.ul_bytes >= 0 for transaction in transactions)
            assert all(transaction.dl_bytes >= 0 for transaction in transactions)


def test_communication_send_videos_has_largest_uplink_volume() -> None:
    """Video send is the heaviest communication uplink action for a fixed seed."""
    totals = {
        action_id: sum(
            transaction.ul_bytes
            for transaction in generate_network_transactions(
                [_action("communication", action_id)],
                seed=42,
            )
        )
        for action_id in CANONICAL_APP_ACTIONS["communication"]
    }

    assert totals["send_videos"] == max(totals.values())


def test_video_play_is_downlink_heavy() -> None:
    """Video playback templates produce much more downlink than uplink."""
    transactions = generate_network_transactions([_action("video", "play")], seed=42)

    assert sum(transaction.dl_bytes for transaction in transactions) > 20 * sum(
        transaction.ul_bytes for transaction in transactions
    )


def test_music_play_is_downlink_heavy_but_lighter_than_video_play() -> None:
    """Music play is downlink-oriented but lower-volume than video play."""
    video = generate_network_transactions([_action("video", "play")], seed=42)
    music = generate_network_transactions([_action("music", "play")], seed=42)

    assert sum(transaction.dl_bytes for transaction in music) > sum(
        transaction.ul_bytes for transaction in music
    )
    assert sum(transaction.dl_bytes for transaction in music) < sum(
        transaction.dl_bytes for transaction in video
    )


def test_game_gaming_generates_repeated_small_transactions() -> None:
    """Gaming expands repeated low-latency update specs deterministically."""
    transactions = generate_network_transactions([_action("game", "gaming")], seed=42)

    assert len(transactions) >= 22
    assert {transaction.label for transaction in transactions} == {
        "gameplay_update",
        "heartbeat",
    }
    assert max(transaction.ul_bytes for transaction in transactions) <= 1500
    assert max(transaction.dl_bytes for transaction in transactions) <= 3000


def test_game_matching_generates_repeated_polling_transactions() -> None:
    """Matchmaking expands repeated polling transactions."""
    transactions = generate_network_transactions([_action("game", "matching")], seed=42)

    polling = [transaction for transaction in transactions if transaction.label == "match_polling"]
    assert len(polling) >= 3
    assert all(transaction.ul_bytes <= 3000 for transaction in polling)
    assert all(transaction.dl_bytes <= 10000 for transaction in polling)


def test_social_thumb_up_is_lighter_than_comment_and_share() -> None:
    """Thumb-up is lighter than comment and share for fixed seed sampling."""
    totals = {
        action_id: sum(
            transaction.ul_bytes + transaction.dl_bytes
            for transaction in generate_network_transactions(
                [_action("social_media", action_id)],
                seed=42,
            )
        )
        for action_id in ("thumb_up", "comment", "share")
    }

    assert totals["thumb_up"] < totals["comment"]
    assert totals["thumb_up"] < totals["share"]


def test_old_supported_app_action_aliases_generate_transactions() -> None:
    """Legacy app/action names still resolve to their canonical templates."""
    assert generate_network_transactions([_action("video_app", "play_video")], seed=42)
    assert generate_network_transactions([_action("social_app", "like")], seed=42)
    assert generate_network_transactions([_action("social_app", "share")], seed=42)
    assert generate_network_transactions([_action("chat_app", "send_message")], seed=42)
