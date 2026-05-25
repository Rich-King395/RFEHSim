"""Matplotlib plotting helpers for v0 simulation traces."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

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
    """Save the total RF power collected at the receiver."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure, axis = plt.subplots(figsize=(8, 4.5))
    axis.plot(result.time_s, result.received_power_w, linewidth=1.4)
    axis.set_xlabel("Time (s)")
    axis.set_ylabel("Receiver Total RF Power (W)")
    axis.set_title("Receiver-Collected Total RF Power")
    axis.grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    return output_path


def save_per_source_received_power_plot(result: SimResult, path: str | Path) -> Path:
    """Save one subplot per source for receiver-collected RF power."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if result.received_power_by_source:
        source_items = sorted(result.received_power_by_source.items())
        figure_height = max(3.2, 2.2 * len(source_items))
        figure, axes = plt.subplots(
            len(source_items),
            1,
            figsize=(9, figure_height),
            sharex=True,
        )
        axes_list = [axes] if len(source_items) == 1 else list(axes)
        for axis, (source_id, received_power_w) in zip(axes_list, source_items):
            axis.plot(result.time_s, received_power_w, linewidth=1.2, label=source_id)
            axis.set_ylabel("RF Power (W)")
            axis.set_title(f"Source {source_id}")
            axis.grid(True, alpha=0.3)
        axes_list[-1].set_xlabel("Time (s)")
        figure.suptitle("Per-Source Receiver-Collected RF Power", y=0.995)
    else:
        figure, axis = plt.subplots(figsize=(8, 4.5))
        axis.plot(result.time_s, [0.0] * len(result.time_s), linewidth=1.1)
        axis.text(
            0.5,
            0.5,
            "no transmitter sources",
            transform=axis.transAxes,
            ha="center",
            va="center",
        )
        axis.set_xlabel("Time (s)")
        axis.set_ylabel("RF Power (W)")
        axis.set_title("Per-Source Receiver-Collected RF Power")
        axis.grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    return output_path


def save_small_scale_gain_plot(result: SimResult, path: str | Path) -> Path:
    """Save a small-scale fading power-gain plot for each source."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure, axis = plt.subplots(figsize=(8, 4.0))
    if result.small_scale_gain_by_source:
        for source_id, gain in sorted(result.small_scale_gain_by_source.items()):
            axis.plot(result.time_s, gain, linewidth=1.1, label=source_id)
        axis.legend(loc="best")
    else:
        axis.plot(result.time_s, [1.0] * len(result.time_s), linewidth=1.1)
        axis.text(
            0.5,
            0.5,
            "small-scale fading disabled",
            transform=axis.transAxes,
            ha="center",
            va="center",
        )
    axis.set_xlabel("Time (s)")
    axis.set_ylabel("G_SS")
    axis.set_title("Small-Scale Fading Gain")
    axis.grid(True, alpha=0.3)
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    return output_path


def save_tx_events_timeline_plot(result: SimResult, path: str | Path) -> Path:
    """Save a compact TxEvent timeline grouped by source ID."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    source_ids = sorted({event.source_id for event in result.tx_events})
    figure_height = max(3.2, 0.45 * max(1, len(source_ids)) + 1.8)
    figure, axis = plt.subplots(figsize=(10, figure_height))
    if source_ids:
        y_by_source = {source_id: index for index, source_id in enumerate(source_ids)}
        color_by_frame = {
            "data": "tab:blue",
            "mac_ack": "tab:orange",
            "transport_ack": "tab:green",
        }
        segments = []
        colors = []
        frame_types = set()
        for event in result.tx_events:
            y_value = y_by_source[event.source_id]
            segments.append(
                [
                    (event.start_s, y_value),
                    (event.start_s + event.duration_s, y_value),
                ]
            )
            colors.append(color_by_frame.get(event.frame_type, "tab:gray"))
            frame_types.add(event.frame_type)
        axis.add_collection(
            LineCollection(segments, colors=colors, linewidths=5.0, alpha=0.85)
        )
        axis.set_yticks(list(y_by_source.values()))
        axis.set_yticklabels(source_ids)
        if result.tx_events:
            axis.set_xlim(
                min(event.start_s for event in result.tx_events),
                max(event.start_s + event.duration_s for event in result.tx_events),
            )
        axis.set_ylim(-0.75, len(source_ids) - 0.25)
        handles = [
            Line2D(
                [0],
                [0],
                color=color_by_frame.get(frame_type, "tab:gray"),
                lw=5,
                label=frame_type,
            )
            for frame_type in sorted(frame_types)
        ]
        axis.legend(handles=handles, loc="best")
    else:
        axis.text(
            0.5,
            0.5,
            "no TxEvents",
            transform=axis.transAxes,
            ha="center",
            va="center",
        )
    axis.set_xlabel("Time (s)")
    axis.set_ylabel("Source ID")
    axis.set_title("TxEvent Timeline")
    axis.grid(True, axis="x", alpha=0.3)
    figure.tight_layout()
    figure.savefig(output_path, dpi=150)
    plt.close(figure)
    return output_path
