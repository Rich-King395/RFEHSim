"""Run the RFEH simulator for every supported canonical app/action pair."""

from __future__ import annotations

import argparse
from dataclasses import replace
import sys
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from rfeh_sim.app_actions import CANONICAL_APP_ACTIONS
from rfeh_sim.config import load_config
from rfeh_sim.engine import run_simulation
from rfeh_sim.io import save_trace_csv
from rfeh_sim.models import FullConfig, SimResult
from rfeh_sim.plotting import (
    save_boost_state_plot,
    save_per_source_received_power_plot,
    save_received_power_plot,
    save_vcap_plot,
)

SUMMARY_COLUMNS = [
    "app_id",
    "action_id",
    "num_action_instances",
    "num_transactions",
    "num_chunks",
    "num_tx_events",
    "num_mobile_tx_events",
    "num_ap_tx_events",
    "total_mobile_airtime_s",
    "total_ap_airtime_s",
    "total_ul_bytes",
    "total_dl_bytes",
    "mean_received_power_w",
    "max_received_power_w",
    "final_v_cap",
    "num_boost_transitions",
]


def supported_app_actions() -> list[tuple[str, str]]:
    """Return all supported canonical app/action pairs in stable order."""
    return [
        (app_id, action_id)
        for app_id, action_ids in CANONICAL_APP_ACTIONS.items()
        for action_id in action_ids
    ]


def run_sweep(
    config_path: str | Path,
    output_dir: str | Path,
    app_actions: Iterable[tuple[str, str]] | None = None,
    save_individual_plots: bool = True,
    save_comparison_plots: bool = True,
) -> pd.DataFrame:
    """Run all requested app/action simulations and save outputs."""
    base_config = load_config(config_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, float | int | str]] = []
    pairs = list(supported_app_actions() if app_actions is None else app_actions)
    for app_id, action_id in pairs:
        config = _config_for_app_action(base_config, app_id, action_id)
        result = run_simulation(config)
        run_dir = output_path / app_id / action_id
        run_dir.mkdir(parents=True, exist_ok=True)

        save_trace_csv(result, run_dir / "trace.csv")
        if save_individual_plots:
            save_vcap_plot(result, run_dir / "vcap.png")
            save_received_power_plot(result, run_dir / "received_power.png")
            save_per_source_received_power_plot(
                result,
                run_dir / "per_source_received_power.png",
            )
            save_boost_state_plot(result, run_dir / "boost_state.png")

        rows.append(_summary_row(app_id, action_id, result))

    summary = pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
    summary_path = output_path / "summary.csv"
    summary.to_csv(summary_path, index=False)
    if save_comparison_plots:
        _save_comparison_plots(summary, output_path)
    return summary


def _config_for_app_action(
    base_config: FullConfig,
    app_id: str,
    action_id: str,
) -> FullConfig:
    """Return a copy of the base config with scenario app/action overridden."""
    return replace(
        base_config,
        scenario=replace(base_config.scenario, app_id=app_id, action_id=action_id),
    )


def _summary_row(
    app_id: str,
    action_id: str,
    result: SimResult,
) -> dict[str, float | int | str]:
    """Build one sweep summary row from a simulation result."""
    mobile_events = [event for event in result.tx_events if event.source_id == "mobile"]
    ap_events = [event for event in result.tx_events if event.source_id == "ap"]
    return {
        "app_id": app_id,
        "action_id": action_id,
        "num_action_instances": len(result.action_instances),
        "num_transactions": len(result.network_transactions),
        "num_chunks": len(result.chunk_events),
        "num_tx_events": len(result.tx_events),
        "num_mobile_tx_events": len(mobile_events),
        "num_ap_tx_events": len(ap_events),
        "total_mobile_airtime_s": sum(event.duration_s for event in mobile_events),
        "total_ap_airtime_s": sum(event.duration_s for event in ap_events),
        "total_ul_bytes": sum(
            chunk.payload_bytes for chunk in result.chunk_events if chunk.direction == "uplink"
        ),
        "total_dl_bytes": sum(
            chunk.payload_bytes for chunk in result.chunk_events if chunk.direction == "downlink"
        ),
        "mean_received_power_w": float(np.mean(result.received_power_w)),
        "max_received_power_w": float(np.max(result.received_power_w)),
        "final_v_cap": float(result.v_cap[-1]),
        "num_boost_transitions": int(np.count_nonzero(np.diff(result.boost_state))),
    }


def _save_comparison_plots(summary: pd.DataFrame, output_dir: Path) -> None:
    """Save bar charts comparing key sweep metrics."""
    metrics = [
        ("total_ul_bytes", "Total Uplink Bytes"),
        ("total_dl_bytes", "Total Downlink Bytes"),
        ("total_mobile_airtime_s", "Total Mobile Airtime (s)"),
        ("total_ap_airtime_s", "Total AP Airtime (s)"),
        ("final_v_cap", "Final V_CAP (V)"),
    ]
    labels = [f"{row.app_id}/{row.action_id}" for row in summary.itertuples()]
    for column, title in metrics:
        figure, axis = plt.subplots(figsize=(11, 4.8))
        axis.bar(labels, summary[column])
        axis.set_title(title)
        axis.set_ylabel(column)
        axis.tick_params(axis="x", labelrotation=75)
        axis.grid(True, axis="y", alpha=0.25)
        figure.tight_layout()
        figure.savefig(output_dir / f"{column}.png", dpi=150)
        plt.close(figure)


def main() -> None:
    """Parse command-line arguments and run the app/action sweep."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="configs/app_action_sweep_base.yaml",
        help="Base YAML config used for each app/action run.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs_app_action_sweep",
        help="Directory where sweep outputs will be written.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of app/action pairs to run.",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip individual and comparison plots.",
    )
    args = parser.parse_args()

    pairs = supported_app_actions()
    if args.limit is not None:
        pairs = pairs[: args.limit]
    summary = run_sweep(
        config_path=args.config,
        output_dir=args.output_dir,
        app_actions=pairs,
        save_individual_plots=not args.no_plots,
        save_comparison_plots=not args.no_plots,
    )
    print(f"Ran {len(summary)} app/action simulations.")
    print(f"Wrote summary CSV: {Path(args.output_dir) / 'summary.csv'}")


if __name__ == "__main__":
    main()
