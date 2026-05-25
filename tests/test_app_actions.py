"""Tests for canonical app/action normalization."""

from __future__ import annotations

import pytest

from rfeh_sim.app_actions import (
    CANONICAL_APP_ACTIONS,
    normalize_action_id,
    normalize_app_action,
    normalize_app_id,
)


def test_all_canonical_app_action_pairs_are_accepted() -> None:
    """Every canonical app/action pair validates unchanged."""
    for app_id, action_ids in CANONICAL_APP_ACTIONS.items():
        for action_id in action_ids:
            assert normalize_app_action(app_id, action_id) == (app_id, action_id)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Video", "video"),
        ("video_app", "video"),
        ("Music", "music"),
        ("Social Media", "social_media"),
        ("social-media", "social_media"),
        ("social_app", "social_media"),
        ("Communication", "communication"),
        ("chat_app", "communication"),
        ("Game", "game"),
    ],
)
def test_app_aliases_normalize_to_canonical_names(raw: str, expected: str) -> None:
    """Common app aliases normalize to canonical categories."""
    assert normalize_app_id(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Play", "play"),
        ("play_video", "play"),
        ("Thumb-up", "thumb_up"),
        ("Thumb Up", "thumb_up"),
        ("like", "thumb_up"),
        ("Send Text", "send_text"),
        ("send-message", "send_text"),
        ("Send Images", "send_images"),
        ("Send Videos", "send_videos"),
        ("Send Voice", "send_voice"),
        ("matchmaking", "matching"),
    ],
)
def test_action_aliases_normalize_to_canonical_names(raw: str, expected: str) -> None:
    """Common action aliases normalize to canonical action IDs."""
    assert normalize_action_id(raw) == expected


@pytest.mark.parametrize(
    ("app_id", "action_id", "expected"),
    [
        ("Video", "Play", ("video", "play")),
        ("Music", "Forward", ("music", "forward")),
        ("Social Media", "Thumb-up", ("social_media", "thumb_up")),
        ("social_app", "like", ("social_media", "thumb_up")),
        ("chat_app", "send_message", ("communication", "send_text")),
        ("Communication", "Send Images", ("communication", "send_images")),
        ("Game", "Gaming", ("game", "gaming")),
    ],
)
def test_app_action_alias_pairs_normalize(
    app_id: str,
    action_id: str,
    expected: tuple[str, str],
) -> None:
    """Free-form app/action pairs normalize and validate together."""
    assert normalize_app_action(app_id, action_id) == expected


def test_invalid_app_raises_clear_error() -> None:
    """Unknown app categories identify the bad input and supported categories."""
    with pytest.raises(ValueError, match="Unknown app category 'browser'"):
        normalize_app_id("browser")


def test_invalid_action_raises_clear_error() -> None:
    """Unknown actions identify the bad input."""
    with pytest.raises(ValueError, match="Unknown action 'refresh'"):
        normalize_action_id("refresh")


def test_invalid_action_for_known_app_raises_clear_error() -> None:
    """Known actions are still rejected for unsupported app categories."""
    with pytest.raises(ValueError, match="not valid for app category 'communication'"):
        normalize_app_action("communication", "play")


def test_blank_app_or_action_raises_clear_error() -> None:
    """Blank normalization inputs are rejected before alias lookup."""
    with pytest.raises(ValueError, match="app_id must be a non-empty string"):
        normalize_app_id(" ")
    with pytest.raises(ValueError, match="action_id must be a non-empty string"):
        normalize_action_id("")
