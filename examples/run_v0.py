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
from rfeh_sim.io import save_settings_txt, save_trace_csv, save_tx_events_csv
from rfeh_sim.models import FullConfig, SimResult
from rfeh_sim.channel import get_distance_for_source
from rfeh_sim.plotting import (
    save_per_source_received_power_plot,
    save_received_power_plot,
    save_tx_events_timeline_plot,
    save_vcap_plot,
)


def run_example(
    config_path: str | Path,
    output_dir: str | Path,
) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    """Run the v0 simulation example and write CSV/plot outputs."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    for stale_name in ("boost_state.png", "small_scale_gain.png"):
        stale_path = output_path / stale_name
        if stale_path.exists():
            stale_path.unlink()

    config = load_config(config_path)
    result = run_simulation(config)

    settings_path = save_settings_txt(config, config_path, output_path / "Setting.txt")
    csv_path = save_trace_csv(result, output_path / "trace.csv")
    tx_events_csv_path = save_tx_events_csv(result, output_path / "tx_events.csv")
    vcap_path = save_vcap_plot(result, output_path / "vcap.png")
    received_power_path = save_received_power_plot(
        result,
        output_path / "received_power.png",
    )
    per_source_received_power_path = save_per_source_received_power_plot(
        result,
        output_path / "per_source_received_power.png",
    )
    tx_events_timeline_path = save_tx_events_timeline_plot(
        result,
        output_path / "tx_events_timeline.png",
    )
    print_diagnostic_summary(config, result)

    return (
        settings_path,
        csv_path,
        tx_events_csv_path,
        vcap_path,
        received_power_path,
        per_source_received_power_path,
        tx_events_timeline_path,
    )


def print_diagnostic_summary(config: FullConfig, result: SimResult) -> None:
    """Print concise channel and output diagnostics for an example run."""
    devices = config.scenario.mobile_devices
    print(f"Mobile devices: {len(devices)}")
    if devices:
        print(f"Device IDs: {', '.join(device.device_id for device in devices)}")
        for device in devices:
            print(
                f"Device: {device.device_id} "
                f"app/action={device.app_id}/{device.action_id}"
            )
    else:
        print("Device IDs: none")

    small_scale = config.channel.small_scale
    print(f"Small-scale model: {small_scale.model}")
    if small_scale.model == "rician":
        print(f"Rician K factor (linear): {small_scale.k_factor_linear:.6g}")
    print(f"Coherence time: {small_scale.coherence_time_s:.6g} s")
    source_ids = sorted({event.source_id for event in result.tx_events})
    print(f"TxEvent sources: {', '.join(source_ids) if source_ids else 'none'}")
    for source_id in source_ids:
        distance_m = get_distance_for_source(source_id, config.scenario)
        received_power_w = result.received_power_by_source.get(source_id)
        source_events = [event for event in result.tx_events if event.source_id == source_id]
        total_airtime_s = sum(event.duration_s for event in source_events)
        print(f"Source: {source_id}")
        print(f"  distance: {distance_m:.6g} m")
        print(f"  TxEvents: {len(source_events)}")
        print(f"  total airtime: {total_airtime_s:.6g} s")
        if received_power_w is not None:
            print(f"  mean received contribution: {received_power_w.mean():.6g} W")
            print(f"  max received contribution: {received_power_w.max():.6g} W")
    device_ids = sorted({event.device_id for event in result.tx_events if event.device_id})
    for device_id in device_ids:
        payload_bytes = sum(
            event.payload_bytes or 0
            for event in result.tx_events
            if event.device_id == device_id and event.frame_type == "data"
        )
        print(f"Device payload bytes: {device_id} {payload_bytes}")
    if result.tx_events:
        first_start_s = min(event.start_s for event in result.tx_events)
        last_end_s = max(event.start_s + event.duration_s for event in result.tx_events)
        print(f"First TxEvent time: {first_start_s:.6g} s")
        print(f"Last TxEvent time: {last_end_s:.6g} s")
    else:
        print("First TxEvent time: none")
        print("Last TxEvent time: none")
    print(f"Mean receiver total RF power: {result.received_power_w.mean():.6g} W")
    print(f"Max receiver total RF power: {result.received_power_w.max():.6g} W")
    print(f"Final V_CAP: {result.v_cap[-1]:.6g} V")


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
        settings_path,
        csv_path,
        tx_events_csv_path,
        vcap_path,
        received_power_path,
        per_source_received_power_path,
        tx_events_timeline_path,
    ) = run_example(
        args.config,
        args.output_dir,
    )
    print(f"Wrote trace CSV: {csv_path}")
    print(f"Wrote settings TXT: {settings_path}")
    print(f"Wrote TxEvents CSV: {tx_events_csv_path}")
    print(f"Wrote VCAP plot: {vcap_path}")
    print(f"Wrote receiver total RF power plot: {received_power_path}")
    print(f"Wrote per-source received power plot: {per_source_received_power_path}")
    print(f"Wrote TxEvents timeline plot: {tx_events_timeline_path}")


if __name__ == "__main__":
    main()
