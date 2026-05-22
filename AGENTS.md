# RFEH Simulator Agent Instructions

This repository builds an end-to-end RF energy harvesting simulator:

```text
app/action -> transmitter -> channel -> receiver -> V_CAP
```

## General Rules

- Keep modules small, testable, and loosely coupled.
- Preserve backward compatibility with the existing burst-based transmitter when possible.
- Use Watts internally for power; convert dBm only at config/input boundaries.
- Use seconds for time.
- Use deterministic random seeds for any stochastic behavior.
- Add tests for every new feature or behavior change.
- Use Python 3.11+, dataclasses/type hints, clear docstrings, and focused pytest tests.

## Transmitter v1 Direction

Implement transmitter improvements as a simple five-layer model:

1. Action/session generator
2. `NetworkTransaction` generator
3. `ChunkEvent` generator
4. Simplified Wi-Fi `TxEvent` generator
5. RF `TxEvent` interface consumed by the channel

Support AP/mobile source IDs:

- Uplink chunks transmit as `source_id="mobile"`.
- Downlink chunks transmit as `source_id="ap"`.
- AP downlink events may trigger simplified mobile ACK events.

Do not implement full TCP/QUIC, full 802.11 MAC/PHY, Fresnel effects, or human movement for transmitter work.

## Before Finishing Coding Tasks

Run:

```bash
pytest
python examples/run_v0.py --config configs/default_v0.yaml --output-dir outputs
```

Also run any relevant example config for the feature being changed.
