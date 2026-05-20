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
from rfeh_sim.plotting import (
    save_boost_state_plot,
    save_received_power_plot,
    save_vcap_plot,
)


def run_example(
    config_path: str | Path,
    output_dir: str | Path,
) -> tuple[Path, Path, Path, Path]:
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

    return csv_path, vcap_path, received_power_path, boost_state_path


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

    csv_path, vcap_path, received_power_path, boost_state_path = run_example(
        args.config,
        args.output_dir,
    )
    print(f"Wrote trace CSV: {csv_path}")
    print(f"Wrote VCAP plot: {vcap_path}")
    print(f"Wrote received power plot: {received_power_path}")
    print(f"Wrote boost state plot: {boost_state_path}")


if __name__ == "__main__":
    main()
