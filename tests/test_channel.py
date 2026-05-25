"""Tests for the v0 fixed-distance wireless channel model."""

from __future__ import annotations

import numpy as np
import pytest

from rfeh_sim.channel import (
    free_space_path_loss_db,
    generate_small_scale_gain,
    generate_small_scale_gain_by_source,
    get_distance_for_source,
    log_distance_path_loss_db,
    received_power_by_source_trace,
    received_power_trace,
)
from rfeh_sim.models import (
    APConfig,
    ChannelConfig,
    MobileDeviceConfig,
    ScenarioConfig,
    SmallScaleFadingConfig,
    TxEvent,
)
from rfeh_sim.units import db_to_linear, dbm_to_watt


def _scenario_config(distance_m: float = 1.5) -> ScenarioConfig:
    """Create a representative fixed-distance scenario."""
    return ScenarioConfig(
        app_id="video_app",
        action_id="play_video",
        distance_m=distance_m,
        frequency_hz=2.437e9,
    )


def _channel_config() -> ChannelConfig:
    """Create a representative log-distance channel config."""
    return ChannelConfig(
        path_loss_exponent=2.2,
        reference_distance_m=1.0,
        shadowing_db=0.0,
        ambient_power_w=dbm_to_watt(-30.0),
    )


def _multi_mobile_scenario() -> ScenarioConfig:
    """Create a multi-mobile scenario with distinct source distances."""
    return ScenarioConfig(
        app_id="video",
        action_id="play",
        distance_m=None,
        frequency_hz=2.437e9,
        ap=APConfig(
            ap_id="ap_0",
            distance_m=3.0,
            eirp_w_mean=dbm_to_watt(20.0),
            eirp_dbm_std=1.0,
        ),
        mobile_devices=(
            MobileDeviceConfig(
                device_id="phone_1",
                app_id="video",
                action_id="play",
                distance_m=0.5,
                eirp_w_mean=dbm_to_watt(15.0),
                eirp_dbm_std=1.0,
            ),
            MobileDeviceConfig(
                device_id="phone_2",
                app_id="social_media",
                action_id="comment",
                distance_m=2.0,
                eirp_w_mean=dbm_to_watt(15.0),
                eirp_dbm_std=1.0,
                start_offset_s=1.0,
            ),
        ),
        source_distances_m={
            "phone_1": 9.0,
            "phone_2": 9.0,
            "ap_0": 9.0,
        },
    )


def _small_scale_config(
    *,
    enabled: bool = True,
    model: str = "rayleigh",
    k_factor_linear: float = 0.0,
    coherence_time_s: float = 0.05,
    normalize_mean: bool = True,
) -> SmallScaleFadingConfig:
    """Create small-scale fading settings for channel tests."""
    return SmallScaleFadingConfig(
        enabled=enabled,
        model=model,
        k_factor_linear=k_factor_linear,
        coherence_time_s=coherence_time_s,
        doppler_hz=None,
        normalize_mean=normalize_mean,
        per_source_independent=True,
        random_phase=True,
    )


def _tx_event() -> TxEvent:
    """Create a representative active TxEvent."""
    return TxEvent(
        source_id="mobile",
        start_s=0.20,
        duration_s=0.30,
        eirp_w=dbm_to_watt(15.0),
        center_freq_hz=2.437e9,
        label="request",
    )


def _source_tx_event(source_id: str) -> TxEvent:
    """Create an active TxEvent for a specific transmitter source."""
    return TxEvent(
        source_id=source_id,
        start_s=0.0,
        duration_s=1.0,
        eirp_w=dbm_to_watt(15.0),
        center_freq_hz=2.437e9,
        label=f"{source_id}_event",
    )


def _source_tx_event_at(
    source_id: str,
    start_s: float = 0.0,
    duration_s: float = 1.0,
    target_device_id: str | None = None,
) -> TxEvent:
    """Create an active TxEvent for a source and optional target device."""
    return TxEvent(
        source_id=source_id,
        source_type="ap" if source_id.startswith("ap") else "mobile",
        device_id=target_device_id if source_id.startswith("ap") else source_id,
        target_device_id=target_device_id,
        start_s=start_s,
        duration_s=duration_s,
        eirp_w=dbm_to_watt(15.0),
        center_freq_hz=2.437e9,
        label=f"{source_id}_event",
        direction="downlink" if source_id.startswith("ap") else "uplink",
    )


def test_path_loss_increases_with_distance() -> None:
    """Log-distance path loss should grow as transmitter distance increases."""
    near_loss_db = log_distance_path_loss_db(
        distance_m=1.0,
        frequency_hz=2.437e9,
        reference_distance_m=1.0,
        path_loss_exponent=2.2,
    )
    far_loss_db = log_distance_path_loss_db(
        distance_m=3.0,
        frequency_hz=2.437e9,
        reference_distance_m=1.0,
        path_loss_exponent=2.2,
    )

    assert far_loss_db > near_loss_db


def test_free_space_path_loss_doubles_distance_by_six_db() -> None:
    """Free-space path loss follows the expected 20 log10(d) law."""
    loss_1m_db = free_space_path_loss_db(distance_m=1.0, frequency_hz=2.437e9)
    loss_2m_db = free_space_path_loss_db(distance_m=2.0, frequency_hz=2.437e9)

    assert loss_2m_db - loss_1m_db == pytest.approx(20.0 * np.log10(2.0))


def test_path_gain_decreases_with_distance() -> None:
    """The linear path gain implied by path loss decreases with distance."""
    near_loss_db = log_distance_path_loss_db(
        distance_m=1.0,
        frequency_hz=2.437e9,
        reference_distance_m=1.0,
        path_loss_exponent=2.2,
    )
    far_loss_db = log_distance_path_loss_db(
        distance_m=3.0,
        frequency_hz=2.437e9,
        reference_distance_m=1.0,
        path_loss_exponent=2.2,
    )

    assert db_to_linear(-far_loss_db) < db_to_linear(-near_loss_db)


def test_get_distance_for_source_uses_legacy_fallback() -> None:
    """Legacy scenario.distance_m remains the fallback for all sources."""
    scenario = _scenario_config(distance_m=2.0)

    assert get_distance_for_source("mobile", scenario) == pytest.approx(2.0)
    assert get_distance_for_source("ap", scenario) == pytest.approx(2.0)
    assert get_distance_for_source("sensor", scenario) == pytest.approx(2.0)


def test_get_distance_for_source_uses_mobile_and_ap_distances() -> None:
    """Named source distances override the legacy fallback for mobile and AP."""
    scenario = ScenarioConfig(
        app_id="video_app",
        action_id="play_video",
        distance_m=9.0,
        frequency_hz=2.437e9,
        mobile_distance_m=1.0,
        ap_distance_m=5.0,
    )

    assert get_distance_for_source("mobile", scenario) == pytest.approx(1.0)
    assert get_distance_for_source("ap", scenario) == pytest.approx(5.0)
    assert get_distance_for_source("sensor", scenario) == pytest.approx(9.0)


def test_source_distance_mapping_takes_precedence() -> None:
    """Explicit source_distances_m entries override legacy named fields."""
    scenario = ScenarioConfig(
        app_id="video_app",
        action_id="play_video",
        distance_m=9.0,
        frequency_hz=2.437e9,
        mobile_distance_m=1.0,
        ap_distance_m=5.0,
        source_distances_m={"mobile": 2.0, "sensor": 4.0},
    )

    assert get_distance_for_source("mobile", scenario) == pytest.approx(2.0)
    assert get_distance_for_source("sensor", scenario) == pytest.approx(4.0)
    assert get_distance_for_source("ap", scenario) == pytest.approx(5.0)


def test_get_distance_for_source_uses_multi_mobile_geometry_first() -> None:
    """Mobile device IDs and AP IDs take precedence over source_distances_m."""
    scenario = _multi_mobile_scenario()

    assert get_distance_for_source("phone_1", scenario) == pytest.approx(0.5)
    assert get_distance_for_source("phone_2", scenario) == pytest.approx(2.0)
    assert get_distance_for_source("ap_0", scenario) == pytest.approx(3.0)


def test_equal_eirp_closer_phone_has_higher_received_power() -> None:
    """For equal EIRP, the closer mobile contributes more received power."""
    scenario = _multi_mobile_scenario()
    channel_config = _channel_config()
    time_s = np.array([0.0])
    by_source = received_power_by_source_trace(
        [
            _source_tx_event_at("phone_1"),
            _source_tx_event_at("phone_2"),
        ],
        time_s,
        scenario,
        channel_config,
    )

    assert by_source["phone_1"][0] > by_source["phone_2"][0]


def test_ap_event_uses_ap_distance_not_target_phone_distance() -> None:
    """AP downlink path loss depends on AP source distance, not target phone distance."""
    scenario = _multi_mobile_scenario()
    channel_config = _channel_config()
    time_s = np.array([0.0])
    by_source = received_power_by_source_trace(
        [
            _source_tx_event_at("ap_0", target_device_id="phone_1"),
            _source_tx_event_at("phone_2"),
        ],
        time_s,
        scenario,
        channel_config,
    )

    assert get_distance_for_source("ap_0", scenario) == pytest.approx(3.0)
    assert get_distance_for_source("phone_1", scenario) == pytest.approx(0.5)
    assert by_source["ap_0"][0] < by_source["phone_2"][0]


def test_multi_source_total_equals_ambient_plus_per_source_contributions() -> None:
    """Total received power is non-coherent sum of source powers plus ambient."""
    scenario = _multi_mobile_scenario()
    channel_config = _channel_config()
    time_s = np.linspace(0.0, 1.0, 101)
    tx_events = [
        _source_tx_event_at("phone_1"),
        _source_tx_event_at("phone_2"),
        _source_tx_event_at("ap_0", target_device_id="phone_1"),
    ]

    total = received_power_trace(tx_events, time_s, scenario, channel_config)
    by_source = received_power_by_source_trace(tx_events, time_s, scenario, channel_config)
    reconstructed = np.full(time_s.shape, channel_config.ambient_power_w, dtype=float)
    for source_trace in by_source.values():
        reconstructed += source_trace

    assert set(by_source) == {"phone_1", "phone_2", "ap_0"}
    np.testing.assert_allclose(total, reconstructed)
    assert np.all(np.isfinite(total))
    assert np.all(total >= 0.0)


def test_unknown_source_without_fallback_distance_raises() -> None:
    """Unknown sources require either source_distances_m or legacy distance_m."""
    scenario = ScenarioConfig(
        app_id="video_app",
        action_id="play_video",
        distance_m=None,
        frequency_hz=2.437e9,
        mobile_distance_m=1.0,
        ap_distance_m=5.0,
    )

    with pytest.raises(ValueError, match="source_id='sensor'"):
        received_power_trace(
            [_source_tx_event("sensor")],
            np.array([0.0, 0.5]),
            scenario,
            _channel_config(),
        )


def test_unknown_source_with_source_distance_mapping_works() -> None:
    """Non-mobile/AP sources work when they have an explicit distance entry."""
    scenario = ScenarioConfig(
        app_id="video_app",
        action_id="play_video",
        distance_m=None,
        frequency_hz=2.437e9,
        source_distances_m={"sensor": 2.0},
    )
    time_s = np.array([0.0, 0.5])
    trace = received_power_trace(
        [_source_tx_event("sensor")],
        time_s,
        scenario,
        _channel_config(),
    )

    assert trace.shape == time_s.shape
    assert np.all(trace > _channel_config().ambient_power_w)


def test_source_specific_distance_changes_received_power() -> None:
    """For equal EIRP, the closer source contributes more received power."""
    scenario = ScenarioConfig(
        app_id="video_app",
        action_id="play_video",
        distance_m=None,
        frequency_hz=2.437e9,
        mobile_distance_m=1.0,
        ap_distance_m=5.0,
    )
    channel_config = _channel_config()
    time_s = np.array([0.0])

    mobile_trace = received_power_trace(
        [_source_tx_event("mobile")],
        time_s,
        scenario,
        channel_config,
    )
    ap_trace = received_power_trace(
        [_source_tx_event("ap")],
        time_s,
        scenario,
        channel_config,
    )

    mobile_contribution = mobile_trace[0] - channel_config.ambient_power_w
    ap_contribution = ap_trace[0] - channel_config.ambient_power_w
    assert mobile_contribution > ap_contribution


def test_received_power_without_tx_events_equals_ambient() -> None:
    """With no active transmitter, the channel returns ambient RF power only."""
    channel_config = _channel_config()
    time_s = np.linspace(0.0, 1.0, 11)
    trace = received_power_trace(
        [],
        time_s,
        _scenario_config(),
        channel_config,
    )

    np.testing.assert_allclose(trace, channel_config.ambient_power_w)


def test_received_power_is_at_least_ambient_power() -> None:
    """The received trace includes ambient RF power as a lower bound."""
    channel_config = _channel_config()
    time_s = np.linspace(0.0, 1.0, 11)
    trace = received_power_trace(
        [_tx_event()],
        time_s,
        _scenario_config(),
        channel_config,
    )

    assert np.all(trace >= channel_config.ambient_power_w)


def test_received_power_increases_during_active_tx_event() -> None:
    """Active TxEvents add received RF power above the ambient level."""
    channel_config = _channel_config()
    time_s = np.array([0.1, 0.25, 0.35, 0.6])
    trace = received_power_trace(
        [_tx_event()],
        time_s,
        _scenario_config(),
        channel_config,
    )

    assert trace[0] == pytest.approx(channel_config.ambient_power_w)
    assert trace[1] > channel_config.ambient_power_w
    assert trace[2] > channel_config.ambient_power_w
    assert trace[3] == pytest.approx(channel_config.ambient_power_w)


def test_received_power_trace_shape_matches_time_shape() -> None:
    """The output trace shape follows the input time grid shape."""
    time_s = np.linspace(0.0, 1.0, 101)
    trace = received_power_trace(
        [_tx_event()],
        time_s,
        _scenario_config(),
        _channel_config(),
    )

    assert trace.shape == time_s.shape


def test_received_power_total_equals_sources_plus_ambient() -> None:
    """Total received power is ambient plus all source contributions."""
    time_s = np.linspace(0.0, 1.0, 101)
    scenario = ScenarioConfig(
        app_id="video_app",
        action_id="play_video",
        distance_m=None,
        frequency_hz=2.437e9,
        mobile_distance_m=0.5,
        ap_distance_m=1.5,
    )
    tx_events = [_source_tx_event("mobile"), _source_tx_event("ap")]
    channel_config = _channel_config()

    total = received_power_trace(tx_events, time_s, scenario, channel_config)
    by_source = received_power_by_source_trace(tx_events, time_s, scenario, channel_config)
    reconstructed = np.full(time_s.shape, channel_config.ambient_power_w, dtype=float)
    for source_trace in by_source.values():
        reconstructed += source_trace

    assert set(by_source) == {"mobile", "ap"}
    np.testing.assert_allclose(total, reconstructed)


def test_received_power_rejects_non_finite_time_values() -> None:
    """Non-finite time samples are rejected before trace calculations."""
    with pytest.raises(ValueError, match="time_s"):
        received_power_trace(
            [_tx_event()],
            np.array([0.0, np.nan]),
            _scenario_config(),
            _channel_config(),
        )


def test_small_scale_disabled_preserves_large_scale_received_power() -> None:
    """Disabled fading exactly preserves the old large-scale-only channel."""
    time_s = np.linspace(0.0, 1.0, 1001)
    baseline_config = _channel_config()
    disabled_config = ChannelConfig(
        path_loss_exponent=baseline_config.path_loss_exponent,
        reference_distance_m=baseline_config.reference_distance_m,
        shadowing_db=baseline_config.shadowing_db,
        ambient_power_w=baseline_config.ambient_power_w,
        small_scale=_small_scale_config(enabled=False, model="rician"),
    )

    baseline = received_power_trace([_tx_event()], time_s, _scenario_config(), baseline_config)
    disabled = received_power_trace(
        [_tx_event()],
        time_s,
        _scenario_config(),
        disabled_config,
        seed=123,
    )

    np.testing.assert_allclose(disabled, baseline, rtol=0.0, atol=0.0)


def test_small_scale_model_none_returns_all_ones_gain() -> None:
    """The none model is an all-ones fading power gain."""
    time_s = np.linspace(0.0, 1.0, 1001)
    gain = generate_small_scale_gain(
        time_s,
        _small_scale_config(enabled=True, model="none"),
        seed=42,
    )

    np.testing.assert_array_equal(gain, np.ones_like(time_s))


def test_rayleigh_gain_is_non_negative_and_mean_normalized() -> None:
    """Rayleigh fading gain is finite, non-negative, and mean-normalized."""
    time_s = np.arange(0.0, 20.0, 0.001)
    gain = generate_small_scale_gain(
        time_s,
        _small_scale_config(model="rayleigh", coherence_time_s=0.05),
        seed=42,
    )

    assert np.all(np.isfinite(gain))
    assert np.all(gain >= 0.0)
    assert np.mean(gain) == pytest.approx(1.0)


def test_rician_gain_is_non_negative_and_mean_normalized() -> None:
    """Rician fading gain is finite, non-negative, and mean-normalized."""
    time_s = np.arange(0.0, 20.0, 0.001)
    gain = generate_small_scale_gain(
        time_s,
        _small_scale_config(
            model="rician",
            k_factor_linear=db_to_linear(6.0),
            coherence_time_s=0.05,
        ),
        seed=42,
    )

    assert np.all(np.isfinite(gain))
    assert np.all(gain >= 0.0)
    assert np.mean(gain) == pytest.approx(1.0)


def test_rayleigh_gain_has_larger_variance_than_high_k_rician_gain() -> None:
    """High-K Rician fading fluctuates less than Rayleigh fading."""
    time_s = np.arange(0.0, 30.0, 0.001)
    rayleigh = generate_small_scale_gain(
        time_s,
        _small_scale_config(model="rayleigh", coherence_time_s=0.05),
        seed=7,
    )
    rician = generate_small_scale_gain(
        time_s,
        _small_scale_config(
            model="rician",
            k_factor_linear=db_to_linear(12.0),
            coherence_time_s=0.05,
        ),
        seed=7,
    )

    assert np.var(rayleigh) > np.var(rician)


def test_same_seed_gives_identical_small_scale_gain() -> None:
    """Small-scale fading generation is deterministic for the same seed."""
    time_s = np.arange(0.0, 5.0, 0.001)
    config = _small_scale_config(model="rayleigh", coherence_time_s=0.05)

    first = generate_small_scale_gain(time_s, config, seed=99)
    second = generate_small_scale_gain(time_s, config, seed=99)

    np.testing.assert_allclose(first, second)


def test_different_seeds_give_different_small_scale_gain() -> None:
    """Different seeds produce different fading traces."""
    time_s = np.arange(0.0, 5.0, 0.001)
    config = _small_scale_config(model="rayleigh", coherence_time_s=0.05)

    first = generate_small_scale_gain(time_s, config, seed=99)
    second = generate_small_scale_gain(time_s, config, seed=100)

    assert not np.allclose(first, second)


def test_larger_coherence_time_produces_smoother_fading() -> None:
    """Longer coherence time produces smaller sample-to-sample gain changes."""
    time_s = np.arange(0.0, 10.0, 0.001)
    fast = generate_small_scale_gain(
        time_s,
        _small_scale_config(model="rayleigh", coherence_time_s=0.01),
        seed=42,
    )
    slow = generate_small_scale_gain(
        time_s,
        _small_scale_config(model="rayleigh", coherence_time_s=0.5),
        seed=42,
    )

    assert np.mean(np.abs(np.diff(slow))) < np.mean(np.abs(np.diff(fast)))


def test_received_power_shape_and_non_negative_with_fading() -> None:
    """Fading keeps the received power trace shape and non-negative values."""
    time_s = np.linspace(0.0, 1.0, 1001)
    base = _channel_config()
    fading_config = ChannelConfig(
        path_loss_exponent=base.path_loss_exponent,
        reference_distance_m=base.reference_distance_m,
        shadowing_db=base.shadowing_db,
        ambient_power_w=base.ambient_power_w,
        small_scale=_small_scale_config(model="rayleigh", coherence_time_s=0.05),
    )
    trace = received_power_trace(
        [_tx_event()],
        time_s,
        _scenario_config(),
        fading_config,
        seed=42,
    )

    assert trace.shape == time_s.shape
    assert np.all(trace >= 0.0)
    active = (time_s >= _tx_event().start_s) & (time_s < _tx_event().start_s + _tx_event().duration_s)
    assert np.std(trace[active]) > 0.0


def test_small_scale_fading_is_generated_per_multi_mobile_source() -> None:
    """Each transmitter source ID gets its own fading trace."""
    time_s = np.linspace(0.0, 2.0, 2001)
    fading = _small_scale_config(model="rician", k_factor_linear=db_to_linear(6.0))
    tx_events = [
        _source_tx_event_at("phone_1"),
        _source_tx_event_at("phone_2"),
        _source_tx_event_at("ap_0", target_device_id="phone_1"),
    ]

    gains = generate_small_scale_gain_by_source(tx_events, time_s, fading, seed=42)

    assert set(gains) == {"phone_1", "phone_2", "ap_0"}
    assert all(gain.shape == time_s.shape for gain in gains.values())
    assert not np.allclose(gains["phone_1"], gains["phone_2"])
    assert not np.allclose(gains["phone_1"], gains["ap_0"])


def test_ap_events_targeting_different_phones_share_ap_fading_trace() -> None:
    """AP downlinks to different phones use one AP-to-receiver fading path."""
    time_s = np.linspace(0.0, 2.0, 2001)
    scenario = _multi_mobile_scenario()
    base = _channel_config()
    channel_config = ChannelConfig(
        path_loss_exponent=base.path_loss_exponent,
        reference_distance_m=base.reference_distance_m,
        shadowing_db=base.shadowing_db,
        ambient_power_w=base.ambient_power_w,
        small_scale=_small_scale_config(model="rayleigh", coherence_time_s=0.05),
    )
    ap_events = [
        _source_tx_event_at("ap_0", start_s=0.0, duration_s=0.5, target_device_id="phone_1"),
        _source_tx_event_at("ap_0", start_s=1.0, duration_s=0.5, target_device_id="phone_2"),
    ]

    gains = generate_small_scale_gain_by_source(
        ap_events,
        time_s,
        channel_config.small_scale,
        seed=42,
    )
    by_source = received_power_by_source_trace(
        ap_events,
        time_s,
        scenario,
        channel_config,
        seed=42,
    )

    assert set(gains) == {"ap_0"}
    assert set(by_source) == {"ap_0"}
    assert np.any(by_source["ap_0"] > 0.0)
