# RFEH End-to-End Simulator

## Project Overview

This repository implements a Python simulator for RF energy harvesting side-channel experiments. It takes a YAML configuration describing simulation timing, app/action traffic, transmitter settings, channel settings, and harvester settings, then produces receiver-side RF power and storage-capacitor voltage traces.

The implemented high-level pipeline is:

```text
YAML config
-> app/action traffic generation
-> transmitter TxEvents
-> wireless channel received RF power
-> RF-to-DC harvested power
-> storage capacitor energy update
-> V_CAP time series
```

The simulator outputs:

- `trace.csv`
- `Setting.txt`
- `tx_events.csv`
- `vcap.png`
- `received_power.png`
- `per_source_received_power.png`
- `tx_events_timeline.png`

`trace.csv` includes total receiver-collected RF power, harvested power, `V_CAP`, capacitor energy, net capacitor power, and per-source received-power columns when source diagnostics are available.

## Repository Structure

```text
RFEHSim/
  configs/
    default_v0.yaml
    multi_mobile_v1.yaml
    transaction_transmitter_v1.yaml
    app_action_sweep_base.yaml
    ...
  examples/
    run_v0.py
    run_app_action_sweep.py
  rfeh_sim/
    app_actions.py
    app_templates.py
    channel.py
    config.py
    engine.py
    harvester.py
    io.py
    models.py
    plotting.py
    template_loader.py
    transmitter.py
    units.py
    data/
      app_transaction_templates.yaml
  tests/
    test_channel.py
    test_config.py
    test_engine.py
    test_example_run.py
    test_harvester.py
    test_transmitter_multi_mobile.py
    ...
  pyproject.toml
  README.md
```

Key modules:

- `rfeh_sim/config.py`: loads YAML into typed dataclass configuration objects and converts dBm inputs to Watts.
- `rfeh_sim/models.py`: defines configuration, transmitter, channel, receiver, and result dataclasses.
- `rfeh_sim/engine.py`: runs the end-to-end simulation with `run_simulation`.
- `rfeh_sim/transmitter.py`: generates burst-mode or transaction-mode TxEvents.
- `rfeh_sim/channel.py`: computes path loss, optional flat small-scale fading, total received RF power, and per-source RF power.
- `rfeh_sim/harvester.py`: simulates constant-efficiency RF-to-DC harvesting and storage-capacitor voltage.
- `rfeh_sim/io.py`: writes `trace.csv`, `tx_events.csv`, and `Setting.txt`.
- `rfeh_sim/plotting.py`: writes matplotlib plots.
- `rfeh_sim/data/app_transaction_templates.yaml`: stores synthetic app/action transaction templates.

## End-to-End Simulation Pipeline

The main programmatic entry point is `rfeh_sim.engine.run_simulation(config)`. It accepts a loaded `FullConfig` and returns a `SimResult`.

```text
YAML file
  -> rfeh_sim.config.load_config(...)
  -> FullConfig
  -> rfeh_sim.engine.run_simulation(...)
       -> rfeh_sim.transmitter.generate_tx_events_for_simulation(...)
       -> rfeh_sim.channel.received_power_by_source_trace(...)
       -> total received_power_w = ambient_power_w + sum(per-source RF power)
       -> rfeh_sim.harvester.simulate_vcap(...)
  -> SimResult
  -> rfeh_sim.io / rfeh_sim.plotting outputs
```

```mermaid
flowchart LR
    A[YAML config] --> B[load_config]
    B --> C[FullConfig]
    C --> D[generate_tx_events_for_simulation]
    D --> E[TxEvents]
    E --> F[received_power_by_source_trace]
    F --> G[received_power_w]
    G --> H[simulate_vcap]
    H --> I[SimResult]
    I --> J[CSV, TXT, PNG outputs]
```

## Quick Start

Use Python 3.11 or newer.

Install the package and dependencies in your chosen Python environment:

```bash
python -m pip install -e .
```

Run the test suite:

```bash
pytest
```

Run the default example:

```bash
python examples/run_v0.py --config configs/default_v0.yaml --output-dir outputs
```

The plain `python` command may fail if it points to an environment without the dependencies from `pyproject.toml`.

## Basic Usage

### Run A Single Configuration

Use `examples/run_v0.py` with any YAML file in `configs/`:

```bash
python examples/run_v0.py --config configs/multi_mobile_v1.yaml --output-dir outputs_multi_mobile_v1
```

### Run The App/Action Sweep

The repository includes a batch runner for all supported canonical app/action pairs:

```bash
python examples/run_app_action_sweep.py --config configs/app_action_sweep_base.yaml --output-dir outputs_app_action_sweep
```

## Transmitter Model

The transmitter implementation is in `rfeh_sim/transmitter.py`. The public entry point is `generate_tx_events_for_simulation(config)`, which returns a `TransmitterResult`.

### Supported Modes

The transmitter mode is selected by `transmitter.model` in YAML.

- `burst`: legacy coarse burst model.
- `transaction`: app/action transaction model with `ActionInstance`, `NetworkTransaction`, `ChunkEvent`, and `TxEvent` stages.

### Burst Mode

Burst mode uses `rfeh_sim/app_templates.py::generate_traffic_bursts` and `rfeh_sim/transmitter.py::bursts_to_tx_events`.

Implemented legacy burst templates:

- `video_app/play_video`
- `social_app/like`
- `social_app/share`
- `chat_app/send_message`

Burst mode can use `app_traffic.repeat_mode: "none"` or `"periodic"`. In periodic mode, the base burst template is tiled through the simulation with seeded period jitter.

Each `TrafficBurst` becomes one mobile `TxEvent` with `source_id="mobile"`.

Implemented burst-mode power and duration rules in `bursts_to_tx_events`:

$$
T_{\mathrm{event}} = T_{\mathrm{burst}} \cdot s_T
$$

$$
P_{\mathrm{EIRP,event}} = P_{\mathrm{EIRP,default}} \cdot s_{\mathrm{burst}} \cdot s_P
$$

Where:

- `T_event` is `TxEvent.duration_s` in seconds.
- `T_burst` is `TrafficBurst.duration_s` in seconds.
- `s_T` is a seeded duration scale clamped by the implementation.
- `P_EIRP,event` is `TxEvent.eirp_w` in Watts.
- `P_EIRP,default` is `transmitter.default_eirp_dbm` converted to Watts.
- `s_burst` is `TrafficBurst.power_scale`.
- `s_P` is a seeded EIRP scale.

### Transaction Mode

Transaction mode is the main implemented transmitter pipeline:

```text
scenario app/action
-> generate_action_instances(...)
-> generate_network_transactions(...)
-> transactions_to_chunks(...)
-> chunks_to_tx_events(...)
-> generate_ack_tx_events(...)
-> schedule_tx_events(...)
-> list[TxEvent]
```

For a single-device legacy config, the loader synthesizes one mobile device. For a multi-mobile config, each item in `scenario.mobile_devices` generates its own actions and transactions.

#### App/Action Handling

Canonical app/action names and aliases are implemented in `rfeh_sim/app_actions.py`.

Canonical supported inputs:

- `video`: `play`, `next`, `pause`, `forward`
- `music`: `play`, `next`, `pause`, `forward`
- `social_media`: `thumb_up`, `comment`, `share`, `repost`
- `communication`: `send_text`, `send_images`, `send_videos`, `send_voice`
- `game`: `loading`, `entering`, `matching`, `gaming`

Aliases are normalized by `normalize_app_action(...)`. Examples implemented in code include:

- `video_app/play_video` -> `video/play`
- `social_app/like` -> `social_media/thumb_up`
- `chat_app/send_message` -> `communication/send_text`

Transaction templates are loaded from `rfeh_sim/data/app_transaction_templates.yaml` through `rfeh_sim/template_loader.py`. The templates are synthetic category-level defaults, not measured traces from specific apps.

#### ActionInstance Generation

Implemented in `generate_action_instances(...)`.

For `repeat_mode="none"`, the implementation creates one action near `app_traffic.start_offset_s`.

For `repeat_mode="periodic"`, nominal action starts use:

$$
t_i = t_{\mathrm{offset}} + iT
$$

Where:

- `t_i` is the nominal `ActionInstance.start_s` in seconds.
- `t_offset` is `app_traffic.start_offset_s` plus any device `start_offset_s`.
- `T` is `app_traffic.period_s` in seconds.
- A seeded uniform jitter in `[-jitter_s, jitter_s]` is added when `jitter_s > 0`.

The implementation clips/discards action starts outside the simulation duration.

#### NetworkTransaction Generation

Implemented in `generate_network_transactions(...)`.

For each `ActionInstance`, the code looks up one or more `TransactionSpec` entries and samples:

- `start_delay_s`
- `duration_s`
- `ul_bytes`
- `dl_bytes`
- optional `probability`
- optional `repeat_count`
- optional `repeat_interval_s`

The transaction start rule is:

$$
t_{\mathrm{transaction}} = t_{\mathrm{action}} + \Delta t_{\mathrm{start}}
$$

Where:

- `t_transaction` is `NetworkTransaction.start_s` in seconds.
- `t_action` is `ActionInstance.start_s` in seconds.
- `Delta t_start` is sampled from the template `start_delay_s` range, plus repeated-transaction offsets when configured.

The implementation uses procedural seeded sampling from YAML ranges rather than a closed-form traffic model.

#### ChunkEvent Generation

Implemented in `transactions_to_chunks(...)` and `_bytes_to_direction_chunks(...)`.

For each transaction:

- `ul_bytes` creates uplink chunks.
- `dl_bytes` creates downlink chunks.
- `wifi.chunk_payload_bytes` is the maximum payload per chunk.

Chunk count:

$$
N = \left\lceil \frac{B}{B_{\max}} \right\rceil
$$

Where:

- `N` is the number of chunks.
- `B` is `NetworkTransaction.ul_bytes` or `NetworkTransaction.dl_bytes`.
- `B_max` is `wifi.chunk_payload_bytes`.

Nominal chunk spacing:

$$
\Delta t = \frac{T_{\mathrm{transaction}}}{\max(N, 1)}
$$

Where:

- `Delta t` is spacing in seconds.
- `T_transaction` is `NetworkTransaction.duration_s`.

The implementation then adds a small seeded timing jitter, clamps chunk starts into the transaction window, and discards chunks outside the simulation duration.

#### TxEvent Generation

Implemented in `chunks_to_tx_events(...)`.

Uplink chunks become mobile data TxEvents:

```text
source_id = device_id
source_type = "mobile"
device_id = device_id
target_device_id = ap_id
direction = "uplink"
frame_type = "data"
```

Downlink chunks become AP data TxEvents:

```text
source_id = ap_id
source_type = "ap"
device_id = target phone device_id
target_device_id = target phone device_id
direction = "downlink"
frame_type = "data"
```

Simplified Wi-Fi airtime formula in `_wifi_airtime_s(...)`:

$$
T_{\mathrm{air}} =
T_{\mathrm{preamble}}
+ \frac{8(B_{\mathrm{payload}} + B_{\mathrm{mac}})}{R_{\mathrm{phy}}}
$$

Where:

- `T_air` is `TxEvent.duration_s` in seconds.
- `T_preamble` is `wifi.preamble_s` in seconds.
- `B_payload` is `ChunkEvent.payload_bytes` in bytes.
- `B_mac` is `wifi.mac_overhead_bytes` in bytes.
- `R_phy` is `wifi.mobile_phy_rate_mbps` or `wifi.ap_phy_rate_mbps`, converted to bits per second.

EIRP sampling in `_sample_eirp_w(...)`:

$$
P_{\mathrm{dBm}} \sim \mathcal{N}(\mu_{\mathrm{dBm}}, \sigma_{\mathrm{dB}})
$$

$$
P_{\mathrm{W}} = 10^{-3} \cdot 10^{P_{\mathrm{dBm}}/10}
$$

Where:

- `P_W` is `TxEvent.eirp_w` in Watts.
- `mu_dBm` is the configured mobile/AP mean EIRP converted from Watts back to dBm inside the sampler.
- `sigma_dB` is `mobile_eirp_dbm_std`, `ap_eirp_dbm_std`, or per-device/per-AP EIRP standard deviation.
- If `sigma_dB == 0`, the implementation returns the mean Watt value directly.

### ACK Generation

Implemented in `generate_ack_tx_events(...)`.

ACK generation is optional:

- `wifi.mac_ack_enabled`
- `wifi.transport_ack_enabled`

For each AP downlink data event, MAC ACK timing is:

$$
t_{\mathrm{ack}} =
t_{\mathrm{downlink}} + T_{\mathrm{downlink}} + T_{\mathrm{SIFS}}
$$

Where:

- `t_ack` is the ACK `TxEvent.start_s` in seconds.
- `t_downlink` is the AP downlink `TxEvent.start_s`.
- `T_downlink` is the AP downlink `TxEvent.duration_s`.
- `T_SIFS` is `wifi.sifs_s`.

MAC ACK duration is `wifi.mac_ack_duration_s`; EIRP is `wifi.mac_ack_eirp_dbm` converted to Watts.

Transport ACK payload bytes:

$$
B_{\mathrm{ack}} =
\left\lceil B_{\mathrm{downlink}} \cdot r_{\mathrm{ack}} \right\rceil
$$

Where:

- `B_ack` is transport ACK payload bytes.
- `B_downlink` is the downlink event payload bytes.
- `r_ack` is `wifi.transport_ack_ratio`.

In multi-mobile configs, ACKs are emitted by the target phone:

```text
source_id = target phone device_id
source_type = "mobile"
target_device_id = AP source_id
```

### Medium Access Scheduling

Implemented in `schedule_tx_events(...)`.

Supported `wifi.medium_access_model` values:

- `independent`: events are sorted, but not shifted; overlap is allowed.
- `ap_serial`: only AP events are serialized; mobile events are left unchanged.
- `shared_medium_serial`: all TxEvents are serialized by requested start time.

Serialization uses the procedural rule in `_serialize_tx_events(...)`:

$$
t'_{\mathrm{start}} =
\max(t_{\mathrm{requested}}, t_{\mathrm{free}} + T_{\mathrm{guard}})
$$

Where:

- `t'_start` is the scheduled `TxEvent.start_s`.
- `t_requested` is the original requested start.
- `t_free` is the current channel-free time cursor.
- `T_guard` is `wifi.guard_time_s`.

If an event is shifted, the original requested start is stored in `TxEvent.original_start_s`.

This scheduler is a deterministic simplification. It does not implement CSMA/CA backoff, collision recovery, OFDMA, MU-MIMO, aggregation, retries, or full 802.11 MAC behavior.

### TxEvent Fields

`TxEvent` is defined in `rfeh_sim/models.py` and is the RF event interface consumed by the channel.

Important fields:

- `source_id`: transmitter source identifier, such as `phone_1`, `ap_0`, `mobile`, or `ap`.
- `source_type`: `"mobile"` or `"ap"`.
- `device_id`: mobile device associated with the event.
- `target_device_id`: intended receiver/target device for AP downlink or ACK target.
- `start_s`: event start time in seconds.
- `duration_s`: event duration in seconds.
- `eirp_w`: EIRP in Watts.
- `center_freq_hz`: center frequency in Hz.
- `bandwidth_hz`: bandwidth in Hz, when set by transaction mode.
- `frame_type`: currently uses values such as `"data"`, `"mac_ack"`, and `"transport_ack"`.
- `direction`: `"uplink"`, `"downlink"`, or `"control"`.
- `payload_bytes`: payload bytes when applicable.
- `phy_rate_bps`: PHY rate in bits per second when applicable.
- `label`: human-readable event label from the template or ACK rule.
- `original_start_s`: requested start time before scheduler shifting, when shifted.

### Multi-Mobile Behavior

Multi-mobile scenarios are configured under `scenario.mobile_devices` and `scenario.ap`, as shown in `configs/multi_mobile_v1.yaml`.

For each configured mobile device:

- `device_id` is propagated through `ActionInstance`, `NetworkTransaction`, `ChunkEvent`, and `TxEvent`.
- The device has its own `app_id`, `action_id`, `distance_m`, EIRP mean/std, and `start_offset_s`.
- The transmitter uses deterministic per-device seed offsets.

AP downlink uses one AP source ID, not one AP per phone. Downlink events set `target_device_id` to the intended phone. ACK events for those downlink events are emitted by the target phone.

### Transmitter Limitations

Current transmitter limitations:

- App/action templates are synthetic category-level defaults, not measured app traces.
- No full TCP or QUIC packet model.
- No full Wi-Fi MAC/PHY model.
- No CSMA/CA backoff or collision recovery.
- No OFDMA or MU-MIMO.
- No frame aggregation or retransmission model.
- The scheduler is deterministic and simplified.
- Burst mode only supports the legacy app/action names listed above.

## Wireless Channel Model

The wireless channel implementation is in `rfeh_sim/channel.py`. The engine calls `received_power_by_source_trace(...)` to compute per-source RF power contributions and then adds ambient RF power to form `SimResult.received_power_w`.

### Received Power Computation

The channel consumes `list[TxEvent]`, the simulation time grid `time_s`, `ScenarioConfig`, `ChannelConfig`, and an optional seed.

For each `TxEvent`, the implementation checks whether each time sample is inside the event interval:

$$
\mathrm{active}_j[k] =
\begin{cases}
1, & t_k \ge t_{\mathrm{start},j} \ \mathrm{and}\ t_k < t_{\mathrm{start},j} + T_j \\
0, & \mathrm{otherwise}
\end{cases}
$$

Where:

- `t_k` is a sample in `time_s`, in seconds.
- `t_start,j` is `TxEvent.start_s`, in seconds.
- `T_j` is `TxEvent.duration_s`, in seconds.

For an event `j` from source `q`, received source contribution is:

$$
P_{r,j}[k] =
P_{\mathrm{EIRP},j}
\cdot G_{\mathrm{path},q}
\cdot G_{\mathrm{ss},q}[k]
\cdot \mathrm{active}_j[k]
$$

Where:

- `P_r,j[k]` is received RF power contribution in Watts.
- `P_EIRP,j` is `TxEvent.eirp_w` in Watts.
- `G_path,q` is large-scale path gain for `source_id=q`.
- `G_ss,q[k]` is small-scale fading power gain for `source_id=q`; it is `1` when fading is disabled.
- Implementing function: `received_power_by_source_trace(...)`.

Per-source traces exclude ambient power. Total received RF power is:

$$
P_r[k] =
P_{\mathrm{ambient}} + \sum_q P_{r,q}[k]
$$

Where:

- `P_r[k]` is `received_power_w[k]` in Watts.
- `P_ambient` is `channel.ambient_power_dbm` converted to Watts.
- `P_r,q[k]` is the sum of all active event contributions from source `q`.
- Implementing function: `received_power_trace(...)`; the engine performs the same summation in `run_simulation(...)`.

The summation is non-coherent power addition. Ambient power is added after source contributions and is not multiplied by path loss or small-scale fading.

### Large-Scale Path Loss

Large-scale path loss is implemented by `free_space_path_loss_db(...)`, `log_distance_path_loss_db(...)`, and `_path_gain_by_source(...)`.

Free-space reference loss:

$$
L_{\mathrm{FS}}(d, f) =
20 \log_{10}\left(\frac{4\pi d f}{c}\right)
$$

Where:

- `L_FS` is free-space path loss in dB.
- `d` is distance in meters.
- `f` is frequency in Hz.
- `c = 299792458` m/s.
- Implementing function: `free_space_path_loss_db(...)`.

Log-distance path loss:

$$
L(d) =
L_{\mathrm{FS}}(d_0, f)
+ 10 n \log_{10}\left(\frac{d}{d_0}\right)
+ X_{\mathrm{shadow}}
$$

Where:

- `L(d)` is path loss in dB.
- `d` is source-to-receiver distance in meters.
- `d_0` is `channel.reference_distance_m`, in meters.
- `f` is `scenario.frequency_hz`, in Hz.
- `n` is `channel.path_loss_exponent`.
- `X_shadow` is `channel.shadowing_db`, a deterministic configured dB offset.
- Implementing function: `log_distance_path_loss_db(...)`.

Linear path gain:

$$
G_{\mathrm{path}} = 10^{-L(d)/10}
$$

Where:

- `G_path` is a unitless linear gain.
- Implementing code: `_path_gain_by_source(...)`, using `rfeh_sim.units.db_to_linear(-path_loss_db)`.

#### Source Distance Lookup

Distance lookup is implemented in `get_distance_for_source(source_id, scenario_config)`.

Lookup order:

1. If `source_id` matches a configured `scenario.mobile_devices[].device_id`, use that mobile device distance.
2. If `source_id` matches `scenario.ap.ap_id`, use AP distance.
3. If `source_id` exists in `scenario.source_distances_m`, use that value.
4. If `source_id == "mobile"` and `scenario.mobile_distance_m` is set, use it.
5. If `source_id == "ap"` and `scenario.ap_distance_m` is set, use it.
6. If legacy `scenario.distance_m` is set, use it.
7. Otherwise, raise `ValueError`.

AP downlink path loss depends on the AP source distance, not on the target phone distance.

### Small-Scale Fading

Small-scale fading is configured under `channel.small_scale` and implemented by `generate_small_scale_gain(...)` and `generate_small_scale_gain_by_source(...)`.

Implemented modes:

- `none`: returns an all-ones gain trace.
- `rayleigh`: uses a time-correlated complex Gaussian process.
- `rician`: combines a deterministic LOS term and a time-correlated complex Gaussian process.

When `channel.small_scale.enabled` is false or `model == "none"`, the channel uses:

$$
G_{\mathrm{ss}}[k] = 1
$$

#### AR(1) Complex Gaussian Process

The complex Gaussian process is generated by `generate_complex_gaussian_ar1(...)`:

$$
g[k] =
\rho g[k-1] + \sqrt{1-\rho^2}\,w[k]
$$

$$
\rho = \exp\left(-\frac{\Delta t}{T_c}\right)
$$

Where:

- `g[k]` is the complex Gaussian fading process.
- `w[k] = (N(0,1) + jN(0,1)) / sqrt(2)`.
- `rho` is the AR(1) correlation coefficient.
- `Delta t` is inferred from `time_s`.
- `T_c` is `channel.small_scale.coherence_time_s`.
- Implementing functions: `generate_complex_gaussian_ar1(...)` and `_infer_time_step_s(...)`.

If `coherence_time_s` is not set but `doppler_hz` is set, config loading uses:

$$
T_c = \frac{0.423}{f_D}
$$

Where:

- `T_c` is coherence time in seconds.
- `f_D` is `channel.small_scale.doppler_hz` in Hz.
- Implementing function: `_load_small_scale_config(...)` in `rfeh_sim/config.py`.

If neither is set, config loading uses `coherence_time_s = 0.2`.

#### Rayleigh Mode

Rayleigh mode uses:

$$
h[k] = g[k]
$$

$$
G_{\mathrm{ss}}[k] = |h[k]|^2
$$

Where:

- `h[k]` is the complex channel sample.
- `G_ss[k]` is unitless fading power gain.
- Implementing function: `generate_small_scale_gain(...)`.

#### Rician Mode

Rician mode uses:

$$
h[k] =
\sqrt{\frac{K}{K+1}}e^{j\phi}
+ \sqrt{\frac{1}{K+1}}g[k]
$$

$$
G_{\mathrm{ss}}[k] = |h[k]|^2
$$

Where:

- `K` is `channel.small_scale.k_factor_db` converted to linear scale.
- `phi` is a random phase when `random_phase=true`, otherwise zero.
- `g[k]` is the AR(1) complex Gaussian process.
- Implementing functions: `_load_small_scale_config(...)` and `generate_small_scale_gain(...)`.

K-factor conversion uses:

$$
K_{\mathrm{linear}} = 10^{K_{\mathrm{dB}}/10}
$$

Where:

- `K_dB` is `channel.small_scale.k_factor_db`.
- Implementing function: `_load_small_scale_config(...)`, via `db_to_linear(...)`.

#### Mean Normalization

If `channel.small_scale.normalize_mean` is true, the gain is normalized by its sample mean:

$$
G'_{\mathrm{ss}}[k] =
\frac{G_{\mathrm{ss}}[k]}{\frac{1}{N}\sum_{i=0}^{N-1}G_{\mathrm{ss}}[i]}
$$

Where:

- `G'_ss[k]` is the normalized gain.
- `N` is the number of time samples.
- Implementing function: `generate_small_scale_gain(...)`.

#### Per-Source Fading

`generate_small_scale_gain_by_source(...)` creates fading traces by `source_id`.

- If `per_source_independent=true`, each source receives an independent deterministic trace using seed offsets.
- If `per_source_independent=false`, all sources share one trace.
- AP downlink events targeting different phones share AP fading because their `source_id` is the same AP ID.

### Channel Configuration Fields

Channel fields loaded by `rfeh_sim/config.py`:

- `channel.path_loss_exponent`
- `channel.reference_distance_m`
- `channel.shadowing_db`
- `channel.ambient_power_dbm`
- `channel.small_scale.enabled`
- `channel.small_scale.model`
- `channel.small_scale.k_factor_db`
- `channel.small_scale.coherence_time_s`
- `channel.small_scale.doppler_hz`
- `channel.small_scale.normalize_mean`
- `channel.small_scale.per_source_independent`
- `channel.small_scale.random_phase`

Scenario fields used by the channel:

- `scenario.frequency_hz`
- `scenario.distance_m`
- `scenario.mobile_distance_m`
- `scenario.ap_distance_m`
- `scenario.source_distances_m`
- `scenario.mobile_devices[].distance_m`
- `scenario.ap.distance_m`

### Channel Limitations

Current channel limitations:

- No Fresnel model.
- No human movement model.
- No explicit transmitter/receiver coordinate geometry beyond scalar source-to-receiver distances.
- No coherent phase-level summation across transmitters.
- No frequency-selective fading.
- No multipath geometry model.
- Shadowing is a deterministic configured dB offset, not a random spatial process.

## Receiver Model

The receiver and storage-capacitor model is implemented in `rfeh_sim/harvester.py`. The engine calls `simulate_vcap(received_power_w, dt_s, harvester_config)` with the total receiver-collected RF power trace from the channel.

### RF-to-DC Harvested Power

The implemented receiver converts total received RF power into harvested DC power with a constant RF-to-DC efficiency:

$$
\eta_{\mathrm{RF}}[k] = \eta_{\mathrm{constant}}
$$

$$
P_H[k] = \eta_{\mathrm{RF}}[k] P_r[k]
$$

Where:

- `P_r[k]` is `received_power_w[k]`, the total received RF power in Watts.
- `P_H[k]` is `harvested_power_w[k]` in Watts.
- `eta_constant` is `harvester.eta_constant`, unitless, and must be in `[0, 1]`.
- Implementing functions: `rf_to_dc_efficiency_constant(...)` and `simulate_vcap(...)`.

### eta_RF Models

Only one RF-to-DC efficiency model is implemented:

- `constant`: uses `eta_constant` for every sample.

If `harvester.eta_model` is not `"constant"`, `simulate_vcap(...)` raises `NotImplementedError`.

The following models are not implemented in the current repository:

- logistic efficiency
- voltage-derated efficiency
- LUT-based efficiency
- hardware-calibrated nonlinear rectifier model

### Capacitor Energy Update

The storage capacitor is updated in energy, not by direct linear voltage increments.

Initial energy:

$$
E_C[0] =
\frac{1}{2} C V_{\mathrm{init}}^2
$$

Where:

- `E_C[0]` is initial capacitor energy in Joules.
- `C` is `harvester.capacitance_f` in Farads.
- `V_init` is `harvester.initial_v_cap` in Volts.

Maximum configured energy:

$$
E_{\max} =
\frac{1}{2} C V_{\max}^2
$$

Where:

- `V_max` is `harvester.max_v_cap` in Volts.
- If `max_v_cap > 0`, capacitor energy is clamped to `E_max`.
- If `max_v_cap == 0`, the implementation clamps stored energy to zero.

For each time step except the final sample:

$$
P_{\mathrm{net}}[k] =
P_H[k] - P_{\mathrm{draw}}[k]
$$

$$
E_C[k+1] =
\min\left(E_{\max},
\max\left(0, E_C[k] + \Delta t \, P_{\mathrm{net}}[k]\right)\right)
$$

Where:

- `P_net[k]` is `net_capacitor_power_w[k]` in Watts.
- `P_draw[k]` is leakage, quiescent, and optional load draw in Watts.
- `Delta t` is `dt_s` in seconds.
- Implementing function: `simulate_vcap(...)`.

### V_CAP Computation

At each sample, capacitor voltage is computed from stored energy:

$$
V_{\mathrm{CAP}}[k] =
\sqrt{\frac{2E_C[k]}{C}}
$$

Where:

- `V_CAP[k]` is `v_cap[k]` in Volts.
- `E_C[k]` is `capacitor_energy_j[k]` in Joules.
- `C` is capacitance in Farads.

The implementation validates finite non-negative inputs and clamps energy to avoid negative voltage or NaN values.

### Leakage And Quiescent Power

Capacitor draw power is implemented in `_draw_power_w(...)`.

When boost/load is disabled:

$$
P_{\mathrm{draw}}[k] = P_{\mathrm{leak}}
$$

When boost/load is enabled but currently off:

$$
P_{\mathrm{draw}}[k] =
P_{\mathrm{leak}} + P_{q,\mathrm{off}}
$$

When boost/load is enabled and currently on:

$$
P_{\mathrm{draw}}[k] =
P_{\mathrm{leak}} + P_{q,\mathrm{on}}
+ \frac{P_{\mathrm{load}}}{\eta_{\mathrm{boost}}}
$$

Where:

- `P_leak` is `harvester.leakage_w` in Watts.
- `P_q,off` is `harvester.boost.quiescent_power_off_w` in Watts.
- `P_q,on` is `harvester.boost.quiescent_power_on_w` in Watts.
- `P_load` is `harvester.boost.load_power_w` in Watts.
- `eta_boost` is `harvester.boost.efficiency`, unitless, and must be in `(0, 1]`.

### Boost / Load Discharge

The optional boost/load model is controlled by `harvester.boost.enabled`.

When enabled, the implementation uses hysteresis:

$$
\sigma[k] =
\begin{cases}
1, & \sigma[k-1] = 0 \ \mathrm{and}\ V_{\mathrm{CAP}}[k] \ge V_{\mathrm{ON}} \\
0, & \sigma[k-1] = 1 \ \mathrm{and}\ V_{\mathrm{CAP}}[k] \le V_{\mathrm{OFF}} \\
\sigma[k-1], & \mathrm{otherwise}
\end{cases}
$$

Where:

- `sigma[k]` is `boost_state[k]`, stored as integer `0` or `1`.
- `V_ON` is `harvester.boost.v_on` in Volts.
- `V_OFF` is `harvester.boost.v_off` in Volts.
- The configuration requires `v_on > v_off`.

The boost state changes the draw power used in the energy update. The implementation does not directly reset `V_CAP` to `V_OFF` when the boost turns on; discharge occurs over finite time through `P_draw`.

`harvester.boost.output_voltage_v` is validated when boost is enabled, but the current model does not simulate a separate `V_OUT` trace.

### Measurement Model

No separate measurement model is implemented. The repository does not currently model:

- ADC quantization
- measurement noise
- moving-average smoothing
- a receiver sampling rate separate from `simulation.dt_s`

### Receiver Outputs

`simulate_vcap(...)` returns:

- `harvested_power_w`
- `v_cap`
- `boost_state`
- `capacitor_energy_j`
- `net_capacitor_power_w`

`SimResult` stores all of these traces. The default CSV export in `rfeh_sim/io.py` writes:

- `time_s`
- `received_power_w`
- `harvested_power_w`
- `v_cap`
- `capacitor_energy_j`
- `net_capacitor_power_w`
- per-source received-power columns when available

`boost_state` is available in `SimResult`, but it is not written to `trace.csv` by the current default output utility. The default example writes `vcap.png`; a `save_boost_state_plot(...)` helper exists in `rfeh_sim/plotting.py`, but `examples/run_v0.py` does not currently call it.

No `eta_rf` trace is stored in `SimResult` or written to CSV.

### Receiver Configuration Fields

Harvester fields loaded by `rfeh_sim/config.py`:

- `harvester.capacitance_f`
- `harvester.initial_v_cap`
- `harvester.eta_model`
- `harvester.eta_constant`
- `harvester.leakage_w`
- `harvester.max_v_cap`

Boost/load fields:

- `harvester.boost.enabled`
- `harvester.boost.v_on`
- `harvester.boost.v_off`
- `harvester.boost.output_voltage_v`
- `harvester.boost.load_power_w`
- `harvester.boost.efficiency`
- `harvester.boost.quiescent_power_on_w`
- `harvester.boost.quiescent_power_off_w`

### Receiver Limitations

Current receiver limitations:

- Only constant RF-to-DC efficiency is implemented.
- No nonlinear rectifier, voltage-derated efficiency, or LUT-based efficiency model.
- No measured hardware calibration data.
- No separate boost-converter output voltage dynamics.
- No ADC, quantization, measurement-noise, or smoothing model.
- The boost/load model is a simplified threshold-controlled load draw, not a detailed converter circuit model.
