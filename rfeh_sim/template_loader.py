"""Load and validate app/action transaction templates."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from rfeh_sim.app_actions import CANONICAL_APP_ACTIONS, normalize_app_action

DEFAULT_TEMPLATE_PATH = Path(__file__).resolve().parent / "data" / "app_transaction_templates.yaml"


@dataclass(frozen=True, slots=True)
class TransactionSpec:
    """Template specification for one sampled NetworkTransaction family."""

    label: str
    protocol: str
    start_delay_s: tuple[float, float]
    duration_s: tuple[float, float]
    ul_bytes: tuple[int, int]
    dl_bytes: tuple[int, int]
    probability: float = 1.0
    repeat_count: tuple[int, int] | None = None
    repeat_interval_s: tuple[float, float] | None = None


TemplateRegistry = dict[tuple[str, str], tuple[TransactionSpec, ...]]


def load_transaction_template_registry(
    path: str | Path | None = None,
) -> TemplateRegistry:
    """Load app/action transaction templates from YAML."""
    template_path = DEFAULT_TEMPLATE_PATH if path is None else Path(path)
    return _load_transaction_template_registry_cached(str(template_path))


def get_transaction_specs(
    app_id: str,
    action_id: str,
    path: str | Path | None = None,
) -> tuple[TransactionSpec, ...]:
    """Return transaction specs for a normalized app/action pair."""
    try:
        canonical_app, canonical_action = normalize_app_action(app_id, action_id)
    except ValueError as exc:
        raise ValueError(
            f"Unsupported app/action transaction template: {app_id}/{action_id}."
        ) from exc
    registry = load_transaction_template_registry(path)
    specs = registry.get((canonical_app, canonical_action))
    if specs is None:
        supported = ", ".join(f"{app}/{action}" for app, action in sorted(registry))
        raise ValueError(
            f"Unsupported app/action transaction template: "
            f"{app_id}/{action_id} normalizes to {canonical_app}/{canonical_action}. "
            f"Supported templates: {supported}."
        )
    return specs


@lru_cache(maxsize=8)
def _load_transaction_template_registry_cached(path: str) -> TemplateRegistry:
    """Cached implementation for loading a YAML template registry."""
    template_path = Path(path)
    with template_path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)

    if not isinstance(raw, dict):
        raise ValueError(f"Transaction template file is empty or invalid: {template_path}")
    templates_raw = raw.get("templates")
    if not isinstance(templates_raw, dict):
        raise ValueError("Transaction template file requires a top-level 'templates' mapping.")

    registry: TemplateRegistry = {}
    for app_id, actions_raw in templates_raw.items():
        if not isinstance(actions_raw, dict):
            raise ValueError(f"Template app '{app_id}' must map to actions.")
        for action_id, action_raw in actions_raw.items():
            canonical_app, canonical_action = normalize_app_action(str(app_id), str(action_id))
            transactions_raw = _required_list(
                action_raw,
                f"templates.{canonical_app}.{canonical_action}.transactions",
            )
            specs = tuple(
                _load_transaction_spec(
                    spec_raw,
                    f"templates.{canonical_app}.{canonical_action}.transactions[{index}]",
                )
                for index, spec_raw in enumerate(transactions_raw)
            )
            if not specs:
                raise ValueError(
                    f"Template {canonical_app}/{canonical_action} must contain at least one transaction."
                )
            registry[(canonical_app, canonical_action)] = specs

    missing = [
        f"{app}/{action}"
        for app, actions in CANONICAL_APP_ACTIONS.items()
        for action in actions
        if (app, action) not in registry
    ]
    if missing:
        raise ValueError(
            "Transaction template file is missing required app/action template(s): "
            + ", ".join(missing)
        )

    return registry


def _load_transaction_spec(raw: Any, path: str) -> TransactionSpec:
    """Load and validate one transaction spec mapping."""
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must be a mapping.")

    probability = float(raw.get("probability", 1.0))
    if not 0.0 <= probability <= 1.0:
        raise ValueError(f"{path}.probability must be in [0, 1].")

    repeat_count = None
    if "repeat_count" in raw:
        repeat_count = _int_range(raw["repeat_count"], f"{path}.repeat_count", minimum=0)
    repeat_interval_s = None
    if "repeat_interval_s" in raw:
        repeat_interval_s = _float_range(
            raw["repeat_interval_s"],
            f"{path}.repeat_interval_s",
            minimum=0.0,
            strictly_positive=False,
        )

    return TransactionSpec(
        label=_required_str(raw, "label", path),
        protocol=_required_str(raw, "protocol", path),
        start_delay_s=_float_range(
            raw.get("start_delay_s"),
            f"{path}.start_delay_s",
            minimum=0.0,
            strictly_positive=False,
        ),
        duration_s=_float_range(
            raw.get("duration_s"),
            f"{path}.duration_s",
            minimum=0.0,
            strictly_positive=True,
        ),
        ul_bytes=_int_range(raw.get("ul_bytes"), f"{path}.ul_bytes", minimum=0),
        dl_bytes=_int_range(raw.get("dl_bytes"), f"{path}.dl_bytes", minimum=0),
        probability=probability,
        repeat_count=repeat_count,
        repeat_interval_s=repeat_interval_s,
    )


def _required_list(raw: Any, path: str) -> list[Any]:
    """Return a required non-empty list."""
    if not isinstance(raw, dict):
        raise ValueError(f"{path.rsplit('.', 1)[0]} must be a mapping.")
    value = raw.get("transactions")
    if not isinstance(value, list):
        raise ValueError(f"{path} must be a list.")
    return value


def _required_str(raw: dict[str, Any], field: str, path: str) -> str:
    """Read a required non-empty string field."""
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{path}.{field} must be a non-empty string.")
    return value


def _float_range(
    value: Any,
    path: str,
    *,
    minimum: float,
    strictly_positive: bool,
) -> tuple[float, float]:
    """Read a two-element float range."""
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise ValueError(f"{path} must be a two-element range.")
    lower = float(value[0])
    upper = float(value[1])
    if lower > upper:
        raise ValueError(f"{path} requires min <= max.")
    if strictly_positive and lower <= minimum:
        raise ValueError(f"{path} minimum must be > {minimum}.")
    if not strictly_positive and lower < minimum:
        raise ValueError(f"{path} minimum must be >= {minimum}.")
    return lower, upper


def _int_range(value: Any, path: str, *, minimum: int) -> tuple[int, int]:
    """Read a two-element integer range."""
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise ValueError(f"{path} must be a two-element range.")
    lower = int(value[0])
    upper = int(value[1])
    if lower > upper:
        raise ValueError(f"{path} requires min <= max.")
    if lower < minimum:
        raise ValueError(f"{path} minimum must be >= {minimum}.")
    return lower, upper
