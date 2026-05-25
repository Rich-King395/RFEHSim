"""Canonical app/action naming and alias normalization."""

from __future__ import annotations

import re

CANONICAL_APP_ACTIONS: dict[str, tuple[str, ...]] = {
    "video": ("play", "next", "pause", "forward"),
    "music": ("play", "next", "pause", "forward"),
    "social_media": ("thumb_up", "comment", "share", "repost"),
    "communication": ("send_text", "send_images", "send_videos", "send_voice"),
    "game": ("loading", "entering", "matching", "gaming"),
}

_APP_ALIASES: dict[str, str] = {
    "video": "video",
    "video_app": "video",
    "music": "music",
    "music_app": "music",
    "social": "social_media",
    "social_app": "social_media",
    "social_media": "social_media",
    "communication": "communication",
    "communication_app": "communication",
    "chat": "communication",
    "chat_app": "communication",
    "messaging": "communication",
    "message": "communication",
    "game": "game",
    "game_app": "game",
}

_ACTION_ALIASES: dict[str, str] = {
    "play": "play",
    "play_video": "play",
    "next": "next",
    "pause": "pause",
    "forward": "forward",
    "fast_forward": "forward",
    "seek_forward": "forward",
    "thumb_up": "thumb_up",
    "thumbs_up": "thumb_up",
    "like": "thumb_up",
    "comment": "comment",
    "share": "share",
    "repost": "repost",
    "send_text": "send_text",
    "send_message": "send_text",
    "message_send": "send_text",
    "text": "send_text",
    "send_images": "send_images",
    "send_image": "send_images",
    "send_photo": "send_images",
    "send_photos": "send_images",
    "send_videos": "send_videos",
    "send_video": "send_videos",
    "send_voice": "send_voice",
    "send_audio": "send_voice",
    "voice": "send_voice",
    "loading": "loading",
    "load": "loading",
    "entering": "entering",
    "enter": "entering",
    "matching": "matching",
    "matchmaking": "matching",
    "gaming": "gaming",
    "gameplay": "gaming",
}


def normalize_app_id(app_id: str) -> str:
    """Normalize an app category to its canonical lowercase snake_case name."""
    normalized = _normalize_token(app_id, "app_id")
    canonical = _APP_ALIASES.get(normalized)
    if canonical is None:
        supported = ", ".join(sorted(CANONICAL_APP_ACTIONS))
        raise ValueError(
            f"Unknown app category '{app_id}'. Supported categories: {supported}."
        )
    return canonical


def normalize_action_id(action_id: str) -> str:
    """Normalize an action ID to its canonical lowercase snake_case name."""
    normalized = _normalize_token(action_id, "action_id")
    canonical = _ACTION_ALIASES.get(normalized)
    if canonical is None:
        supported = ", ".join(sorted({action for actions in CANONICAL_APP_ACTIONS.values() for action in actions}))
        raise ValueError(
            f"Unknown action '{action_id}'. Supported canonical actions: {supported}."
        )
    return canonical


def normalize_app_action(app_id: str, action_id: str) -> tuple[str, str]:
    """Normalize and validate an app/action pair.

    The app category is validated first, then the normalized action is checked
    against the actions supported by that category.
    """
    canonical_app = normalize_app_id(app_id)
    canonical_action = normalize_action_id(action_id)
    valid_actions = CANONICAL_APP_ACTIONS[canonical_app]
    if canonical_action not in valid_actions:
        supported = ", ".join(valid_actions)
        raise ValueError(
            f"Action '{action_id}' normalizes to '{canonical_action}', which is "
            f"not valid for app category '{canonical_app}'. Supported actions: "
            f"{supported}."
        )
    return canonical_app, canonical_action


def _normalize_token(value: str, field_name: str) -> str:
    """Normalize free-form user text to lowercase snake_case."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    token = value.strip().lower()
    token = re.sub(r"[^0-9a-z]+", "_", token)
    token = re.sub(r"_+", "_", token).strip("_")
    if not token:
        raise ValueError(f"{field_name} must contain at least one letter or digit.")
    return token
