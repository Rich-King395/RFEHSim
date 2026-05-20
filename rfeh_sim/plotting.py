"""Matplotlib plotting helpers for v0 simulation traces."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from rfeh_sim.models import SimResult


def save_vcap_plot(result: SimResult, path: str | Path) -> Path:
    """Save a storage capacitor voltage plot."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.plot(result.time_s, result.v_cap, linewidth=1.8)
    axis.set_xlabel("Time (s)")
    axis.set_ylabel("V_CAP (V)")
    axis.set_title("Storage Capacitor Voltage")
    axis.grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    return output_path


def save_boost_state_plot(result: SimResult, path: str | Path) -> Path:
    """Save a threshold boost/load state plot."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure, axis = plt.subplots(figsize=(8, 3.2))
    axis.step(result.time_s, result.boost_state, where="post", linewidth=1.4)
    axis.set_xlabel("Time (s)")
    axis.set_ylabel("Boost State")
    axis.set_yticks([0, 1])
    axis.set_title("Boost/Load State")
    axis.grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    return output_path


def save_received_power_plot(result: SimResult, path: str | Path) -> Path:
    """Save a received RF power plot."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.plot(result.time_s, result.received_power_w, linewidth=1.4)
    axis.set_xlabel("Time (s)")
    axis.set_ylabel("Received RF Power (W)")
    axis.set_title("Received RF Power")
    axis.grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    return output_path
