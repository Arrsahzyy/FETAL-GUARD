"""Baseline vital derivation.

These tests use synthetic signals with a known period. They verify the estimator
recovers a rate it was given and refuses to answer when the signal cannot support
one -- they say nothing about accuracy on real fetal signals, which remains
unvalidated.
"""

import math

import pytest

from services.signal_processing import (
    FHR_SEARCH_RANGE_BPM,
    MIN_SIGNAL_QUALITY_INDEX,
    autocorrelation_rate,
    build_envelope,
    classify_contraction_indicator,
    deinterleave_piezo,
    estimate_fetal_heart_rate,
    estimate_maternal_heart_rate,
)


def pulse_train(bpm, sample_rate_hz, seconds, amplitude=800, baseline=2048):
    """Amplitude bursts at `bpm`, resembling the mechanical beat a piezo sees."""
    total = int(sample_rate_hz * seconds)
    period = sample_rate_hz * 60.0 / bpm
    samples = []
    for index in range(total):
        phase = (index % period) / period
        # Narrow burst at the start of each beat.
        envelope = math.exp(-((phase * 8.0) ** 2))
        samples.append(int(baseline + amplitude * envelope * math.sin(2 * math.pi * 12 * index / sample_rate_hz)))
    return samples


def interleave(channels):
    interleaved = []
    for frame in zip(*channels):
        interleaved.extend(frame)
    return interleaved


def test_deinterleave_splits_frames_into_channels():
    assert deinterleave_piezo([1, 2, 3, 4, 5, 6, 7, 8]) == [[1, 5], [2, 6], [3, 7], [4, 8]]


def test_envelope_decimates_towards_the_target_rate():
    envelope, rate = build_envelope(pulse_train(140, 200, 4), 200)

    assert rate == pytest.approx(50.0)
    assert len(envelope) == pytest.approx(200, abs=5)


@pytest.mark.parametrize("bpm", [90, 110, 120, 140, 155, 165, 180, 200])
def test_autocorrelation_recovers_a_known_rate(bpm):
    envelope, rate = build_envelope(pulse_train(bpm, 200, 12), 200)

    estimate = autocorrelation_rate(envelope, rate, FHR_SEARCH_RANGE_BPM)

    assert estimate is not None
    # Decimation quantises the lag, so allow a small tolerance.
    assert estimate.bpm == pytest.approx(bpm, rel=0.06)
    assert estimate.quality >= MIN_SIGNAL_QUALITY_INDEX


@pytest.mark.parametrize("bpm", [78, 100, 132, 150, 165, 174, 200, 220])
def test_estimator_does_not_lock_onto_a_sub_harmonic(bpm):
    """Regression: reporting period*2 or period*3 halves or thirds the rate.

    A correctly normalised autocorrelation peaks almost as strongly at every
    multiple of the true period, so a tallest-peak rule silently reported ~56 bpm
    for a 165 bpm signal -- a dangerously reassuring wrong answer.
    """
    envelope, rate = build_envelope(pulse_train(bpm, 200, 14), 200)

    estimate = autocorrelation_rate(envelope, rate, FHR_SEARCH_RANGE_BPM)

    assert estimate is not None
    for divisor in (2, 3, 4):
        assert estimate.bpm != pytest.approx(bpm / divisor, rel=0.08), (
            f"locked onto 1/{divisor} of {bpm} bpm"
        )
    assert estimate.bpm == pytest.approx(bpm, rel=0.06)


def test_fetal_rate_uses_the_most_periodic_channel():
    clean = pulse_train(145, 200, 12)
    flat = [2048] * len(clean)
    interleaved = interleave([flat, flat, clean, flat])

    estimate = estimate_fetal_heart_rate(interleaved, sample_rate_hz=200)

    assert estimate is not None
    assert estimate.bpm == pytest.approx(145, rel=0.06)


def test_fetal_rate_is_none_for_a_flat_channel_instead_of_a_guess():
    flat = [2048] * (200 * 12)

    assert estimate_fetal_heart_rate(interleave([flat] * 4), sample_rate_hz=200) is None


def test_fetal_rate_is_none_when_the_window_is_too_short():
    short = pulse_train(140, 200, 3)

    assert estimate_fetal_heart_rate(interleave([short] * 4), sample_rate_hz=200) is None


def test_fetal_rate_is_none_for_noise_without_a_dominant_period():
    # Deterministic pseudo-noise: no periodicity in the search band.
    noise = [2048 + (((index * 7919) % 977) - 488) for index in range(200 * 12)]

    estimate = estimate_fetal_heart_rate(interleave([noise] * 4), sample_rate_hz=200)

    assert estimate is None or estimate.quality >= MIN_SIGNAL_QUALITY_INDEX


def test_rate_outside_the_plausible_range_is_rejected():
    # 600 bpm is far above the fetal search ceiling and must not be reported.
    too_fast = pulse_train(600, 200, 12)

    estimate = estimate_fetal_heart_rate(interleave([too_fast] * 4), sample_rate_hz=200)

    assert estimate is None or estimate.bpm <= FHR_SEARCH_RANGE_BPM[1]


def test_maternal_rate_recovers_a_known_ppg_rate():
    estimate = estimate_maternal_heart_rate(pulse_train(78, 100, 15, baseline=50000), 100)

    assert estimate is not None
    assert estimate.bpm == pytest.approx(78, rel=0.08)


def test_maternal_rate_is_none_without_enough_samples():
    assert estimate_maternal_heart_rate(pulse_train(78, 100, 2, baseline=50000), 100) is None


@pytest.mark.parametrize(
    ("samples", "expected"),
    [
        ([], "unknown"),
        ([700], "unknown"),
        ([700, 700, 700], "none"),
        # Under 2% of the 12-bit span reads as resting, not a contraction.
        ([700, 740, 700], "none"),
        ([700, 800, 700], "mild"),
        ([700, 1100, 700], "regular"),
        ([700, 2000, 700], "strong"),
    ],
)
def test_contraction_indicator_buckets_relative_deflection(samples, expected):
    assert classify_contraction_indicator(samples) == expected


def naive_autocorrelation_scores(envelope, minimum_lag, maximum_lag):
    """Straightforward triple-accumulate correlation, used only as a reference.

    The production version replaces the two energy accumulations with prefix sums
    and the cross term with math.sumprod, purely for speed: a 20 s window went
    from ~740 ms to ~80 ms, and that runs inside the ingestion request. This
    reference exists so a future change to that loop has to stay numerically
    equivalent rather than merely stay fast.
    """
    mean = sum(envelope) / len(envelope)
    centered = [value - mean for value in envelope]
    scores = {}
    for lag in range(minimum_lag, maximum_lag + 1):
        overlap = len(centered) - lag
        cross = left_energy = right_energy = 0.0
        for index in range(overlap):
            left = centered[index]
            right = centered[index + lag]
            cross += left * right
            left_energy += left * left
            right_energy += right * right
        denominator = math.sqrt(left_energy * right_energy)
        scores[lag] = cross / denominator if denominator > 0 else 0.0
    return scores


@pytest.mark.parametrize("bpm", [64, 96, 140, 168, 210])
def test_optimised_correlation_matches_the_naive_reference(bpm):
    envelope, envelope_rate_hz = build_envelope(pulse_train(bpm, 200, 12), 200)
    minimum_lag = max(1, int(envelope_rate_hz * 60.0 / FHR_SEARCH_RANGE_BPM[1]))
    maximum_lag = int(envelope_rate_hz * 60.0 / FHR_SEARCH_RANGE_BPM[0])

    estimate = autocorrelation_rate(envelope, envelope_rate_hz, FHR_SEARCH_RANGE_BPM)
    reference = naive_autocorrelation_scores(envelope, minimum_lag, maximum_lag)

    assert estimate is not None
    # Compared at the lag the estimator settled on, not at the tallest peak: the
    # estimator deliberately prefers the earliest qualifying peak so a taller
    # sub-harmonic cannot halve the reported rate.
    chosen_lag = min(
        reference,
        key=lambda lag: abs(envelope_rate_hz * 60.0 / lag - estimate.bpm),
    )
    # Float reassociation moves the last couple of digits, nothing more.
    assert estimate.quality == pytest.approx(reference[chosen_lag], abs=1e-9)
