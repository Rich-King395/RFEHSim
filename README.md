# RFEH End-to-End Simulator

This project implements a v0 RF energy harvesting side-channel simulator.

The simulator maps:

```text
app_id + action_id
-> traffic burst templates
-> RF transmission events
-> received RF power
-> harvested power
-> storage capacitor voltage V_CAP
```

Version 0 intentionally uses simplified models: hard-coded app/action traffic
templates, a coarse transmitter model, log-distance path loss, constant
RF-to-DC efficiency, a storage capacitor voltage trace, and an optional
threshold-controlled boost/load discharge model. It does not include Fresnel
effects, detailed Wi-Fi MAC/PHY behavior, packet-level TCP/QUIC, or detailed
boost converter electronics.

## Installation

Use Python 3.11 or newer.

```bash
python -m pip install -e .
```

## Run Tests

```bash
pytest
```

## Run The V0 Example

```bash
python examples/run_v0.py --config configs/default_v0.yaml --output-dir outputs
```

`configs/default_v0.yaml` enables periodic synthetic traffic so the received RF
power trace contains repeated burst trains across a longer simulation. Use
`app_traffic.repeat_mode: "none"` to preserve the original finite action burst.

To run a receiver configuration with visible charge/discharge cycles:

```bash
python examples/run_v0.py --config configs/receiver_cyclic_v0.yaml --output-dir outputs_receiver_cyclic
```

## Expected Outputs

The example writes these files:

- `outputs/trace.csv`
- `outputs/vcap.png`
- `outputs/received_power.png`
- `outputs/boost_state.png`

The CSV contains:

```text
time_s, received_power_w, harvested_power_w, v_cap, boost_state, capacitor_energy_j, net_capacitor_power_w
```
