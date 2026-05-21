"""Run the v0 RF energy harvesting simulator from a YAML config."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from rfeh_sim.config import load_config
from rfeh_sim.engine import run_simulation
from rfeh_sim.io import save_trace_csv
from rfeh_sim.models import FullConfig, SimResult
from rfeh_sim.plotting import (
    save_boost_state_plot,
    save_received_power_plot,
    save_small_scale_gain_plot,
    save_vcap_plot,
)


def run_example(
    config_path: str | Path,
    output_dir: str | Path,
) -> tuple[Path, Path, Path, Path, Path]:
    """Run the v0 simulation example and write CSV/plot outputs."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    config = load_config(config_path)
    result = run_simulation(config)

    csv_path = save_trace_csv(result, output_path / "trace.csv")
    vcap_path = save_vcap_plot(result, output_path / "vcap.png")
    received_power_path = save_received_power_plot(
        result,
        output_path / "received_power.png",
    )
    boost_state_path = save_boost_state_plot(result, output_path / "boost_state.png")
    small_scale_gain_path = save_small_scale_gain_plot(
        result,
        output_path / "small_scale_gain.png",
    )
    print_diagnostic_summary(config, result)

    return (
        csv_path,
        vcap_path,
        received_power_path,
        boost_state_path,
        small_scale_gain_path,
    )


def print_diagnostic_summary(config: FullConfig, result: SimResult) -> None:
    """Print concise channel and output diagnostics for an example run."""
    small_scale = config.channel.small_scale
    print(f"Small-scale model: {small_scale.model}")
    if small_scale.model == "rician":
        print(f"Rician K factor (linear): {small_scale.k_factor_linear:.6g}")
    print(f"Coherence time: {small_scale.coherence_time_s:.6g} s")
    if result.small_scale_gain_by_source:
        for source_id, gain in sorted(result.small_scale_gain_by_source.items()):
            print(f"Small-scale gain source: {source_id}")
            print(f"  mean: {gain.mean():.6g}")
            print(f"  std: {gain.std():.6g}")
            print(f"  min: {gain.min():.6g}")
            print(f"  max: {gain.max():.6g}")
    else:
        print("Small-scale gain: disabled")
    print(f"Mean received power: {result.received_power_w.mean():.6g} W")
    print(f"Max received power: {result.received_power_w.max():.6g} W")


def main() -> None:
    """Parse command-line arguments and run the v0 example."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="configs/default_v0.yaml",
        help="Path to a v0 YAML configuration file.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory where CSV and plot outputs will be written.",
    )
    args = parser.parse_args()

    (
        csv_path,
        vcap_path,
        received_power_path,
        boost_state_path,
        small_scale_gain_path,
    ) = run_example(
        args.config,
        args.output_dir,
    )
    print(f"Wrote trace CSV: {csv_path}")
    print(f"Wrote VCAP plot: {vcap_path}")
    print(f"Wrote received power plot: {received_power_path}")
    print(f"Wrote boost state plot: {boost_state_path}")
    print(f"Wrote small-scale gain plot: {small_scale_gain_path}")


if __name__ == "__main__":
    main()
