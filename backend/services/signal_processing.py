"""Baseline derivation of technical vitals from stored raw sensor channels.

**These estimators are unvalidated.** They have never been compared against CTG,
Doppler, a tocotransducer, or any reference signal, and nothing here may be
described as clinically accurate. They exist so the backend stops depending on
numbers computed by the patient's own phone, and so that a value shown to a
clinician can be traced to raw samples the server actually holds.

Method, for both rate estimates: rectify the channel to an amplitude envelope,
smooth it, decimate it, then take the normalised autocorrelation peak inside the
plausible lag range. The peak height doubles as a signal quality index -- a clean
periodic signal correlates strongly with itself at one lag, noise does not.

Everything fails closed. When a window is too short, too flat, or too noisy the
functions return ``None`` rather than a guess, because an honest "belum tersedia"
is safe and an invented heart rate is not.

Pure Python on purpose: the backend runtime has no numpy. Cost matters because
derivation runs inside the ingestion request, so the correlation is written
against that constraint -- prefix-summed energies and ``math.sumprod`` for the
cross term. A 20 s window of 200 Hz four-channel piezo plus 100 Hz PPG measures
~80 ms end to end, against ~740 ms for the naive triple-accumulate form.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

# Technical plausibility bounds for accepting an estimate at all. Deliberately
# wider than the display reference ranges in AGENTS.md (FHR 110-160, maternal
# 60-100): those describe what is reassuring, these describe what the hardware
# could physically be measuring. A value outside these is treated as a failed
# measurement, never as a clinical finding.
FHR_SEARCH_RANGE_BPM = (50, 240)
MATERNAL_HR_SEARCH_RANGE_BPM = (30, 220)

# Below this autocorrelation peak the window is treated as unusable.
MIN_SIGNAL_QUALITY_INDEX = 0.35
# Shorter windows cannot resolve the lowest rate in the search range.
MIN_WINDOW_SECONDS = 8.0
# Envelope target rate after decimation.
ENVELOPE_RATE_HZ = 50.0
# Moving-average width used to turn a rectified signal into an amplitude
# envelope. Short enough to preserve a 240 bpm beat (0.25 s period), long enough
# to suppress the much faster oscillation the sensor itself carries.
ENVELOPE_SMOOTHING_SECONDS = 0.08

PIEZO_CHANNEL_COUNT = 4

# The correlation inner loop dominates derivation cost, and it runs inside the
# ingestion request. math.sumprod does it in C; the fallback keeps this importable
# on Python 3.11, where it does not exist yet.
try:
    from math import sumprod as _sum_of_products
except ImportError:  # pragma: no cover - exercised only on Python < 3.12
    def _sum_of_products(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right))


@dataclass(frozen=True)
class RateEstimate:
    """One rate estimate with the quality that justified accepting it."""

    bpm: int
    quality: float


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def deinterleave_piezo(samples: list[int], channel_count: int = PIEZO_CHANNEL_COUNT) -> list[list[int]]:
    """Split interleaved [ch0,ch1,ch2,ch3, ch0,...] samples into per-channel series."""
    if channel_count <= 0:
        return []
    return [samples[offset::channel_count] for offset in range(channel_count)]


def build_envelope(samples: list[int], sample_rate_hz: float) -> tuple[list[float], float]:
    """Rectify around the mean, smooth, and decimate to ``ENVELOPE_RATE_HZ``.

    Returns the envelope and its effective rate. The heartbeat shows up as
    periodic bursts of vibration amplitude, so the envelope -- not the raw
    oscillation -- is what carries the rate.

    The smoothing window is derived from ``ENVELOPE_SMOOTHING_SECONDS`` rather
    than from the decimation factor. Tying it to decimation makes the filter
    collapse to a couple of samples at low input rates, which leaves the sensor's
    own carrier frequency in the "envelope" and lets the rate search lock onto
    that instead of the beat. The window still passes every rate in the search
    ranges, whose shortest period is far longer.
    """
    if not samples or sample_rate_hz <= 0:
        return [], 0.0

    baseline = _mean([float(value) for value in samples])
    rectified = [abs(float(value) - baseline) for value in samples]

    smoothing = max(1, int(round(sample_rate_hz * ENVELOPE_SMOOTHING_SECONDS)))
    if smoothing > 1 and len(rectified) >= smoothing:
        smoothed: list[float] = []
        running = sum(rectified[:smoothing])
        smoothed.append(running / smoothing)
        for index in range(smoothing, len(rectified)):
            running += rectified[index] - rectified[index - smoothing]
            smoothed.append(running / smoothing)
    else:
        smoothed = rectified

    decimation = max(1, int(round(sample_rate_hz / ENVELOPE_RATE_HZ)))
    envelope = smoothed[::decimation]

    return envelope, sample_rate_hz / decimation


# A sub-harmonic peak in a clean signal is nearly as tall as the fundamental, so
# the fundamental is chosen as the earliest peak within this fraction of the best
# one rather than by height alone.
_SUBHARMONIC_TOLERANCE = 0.85


def autocorrelation_rate(
    envelope: list[float],
    envelope_rate_hz: float,
    search_range_bpm: tuple[int, int],
) -> RateEstimate | None:
    """Return the dominant rate in the search range, or None if none stands out.

    Uses the properly normalised correlation coefficient at each lag, so scores
    are comparable across lags and land in [-1, 1]; the accepted peak height
    doubles as the signal quality index.

    A periodic signal correlates with itself at *every* multiple of its period,
    and once the scores are correctly normalised those sub-harmonic peaks are
    nearly as tall as the fundamental. Picking the tallest peak therefore reports
    half or a third of the true rate -- an 84 bpm reading for a 168 bpm heart,
    which is both wrong and reassuring-looking. The fundamental is the *shortest*
    repeating period, so the earliest qualifying peak is selected instead.
    """
    minimum_bpm, maximum_bpm = search_range_bpm
    if not envelope or envelope_rate_hz <= 0 or minimum_bpm >= maximum_bpm:
        return None

    # A high rate means a short period, so the fastest rate gives the smallest lag.
    minimum_lag = max(1, int(envelope_rate_hz * 60.0 / maximum_bpm))
    maximum_lag = int(envelope_rate_hz * 60.0 / minimum_bpm)
    if maximum_lag <= minimum_lag or len(envelope) <= maximum_lag + 1:
        return None

    mean = _mean(envelope)
    centered = [value - mean for value in envelope]
    sample_count = len(centered)

    # Prefix sums of squares. Both energy terms at every lag are windows of this
    # same running total, so they cost one lookup each instead of another pass
    # over the overlap. Only the cross term still has to walk the data, which
    # takes this loop from three multiply-accumulates per sample to one.
    squared_prefix = [0.0] * (sample_count + 1)
    running = 0.0
    for index, value in enumerate(centered):
        running += value * value
        squared_prefix[index + 1] = running

    if squared_prefix[sample_count] <= 0:
        # A perfectly flat window carries no rate; a saturated or disconnected
        # sensor lands here rather than producing a fabricated number.
        return None

    scores: dict[int, float] = {}
    for lag in range(minimum_lag, maximum_lag + 1):
        overlap = sample_count - lag
        cross = _sum_of_products(centered[:overlap], centered[lag:])
        left_energy = squared_prefix[overlap]
        right_energy = squared_prefix[sample_count] - squared_prefix[lag]
        denominator = math.sqrt(left_energy * right_energy)
        scores[lag] = cross / denominator if denominator > 0 else 0.0

    best_score = max(scores.values())
    if best_score <= 0:
        return None

    threshold = best_score * _SUBHARMONIC_TOLERANCE
    chosen_lag: int | None = None
    for lag in range(minimum_lag, maximum_lag + 1):
        if scores[lag] < threshold:
            continue
        previous = scores.get(lag - 1, float("-inf"))
        following = scores.get(lag + 1, float("-inf"))
        if scores[lag] >= previous and scores[lag] >= following:
            chosen_lag = lag
            break

    if chosen_lag is None:
        chosen_lag = max(scores, key=lambda lag: scores[lag])

    bpm = int(round(envelope_rate_hz * 60.0 / chosen_lag))
    if not minimum_bpm <= bpm <= maximum_bpm:
        return None
    return RateEstimate(bpm=bpm, quality=min(1.0, scores[chosen_lag]))


def estimate_fetal_heart_rate(
    piezo_samples: list[int],
    sample_rate_hz: float,
    channel_count: int = PIEZO_CHANNEL_COUNT,
) -> RateEstimate | None:
    """Estimate FHR from the interleaved piezo array.

    ``sample_rate_hz`` is the per-channel rate the device reports in
    ``sample_rates_hz.p``, so an interleaved array holds
    ``sample_rate_hz * channel_count`` values per second and de-interleaving
    yields channels already at ``sample_rate_hz``.

    Each belt position sees the fetal heart differently, so every channel is
    evaluated independently and the most periodic one wins. Averaging the
    channels first would let three poorly-placed sensors bury a good one.
    """
    if not piezo_samples or sample_rate_hz <= 0 or channel_count <= 0:
        return None
    if len(piezo_samples) / (sample_rate_hz * channel_count) < MIN_WINDOW_SECONDS:
        return None

    best: RateEstimate | None = None
    for channel in deinterleave_piezo(piezo_samples, channel_count):
        if len(channel) / sample_rate_hz < MIN_WINDOW_SECONDS:
            continue
        envelope, envelope_rate_hz = build_envelope(channel, sample_rate_hz)
        estimate = autocorrelation_rate(envelope, envelope_rate_hz, FHR_SEARCH_RANGE_BPM)
        if estimate is not None and (best is None or estimate.quality > best.quality):
            best = estimate

    if best is None or best.quality < MIN_SIGNAL_QUALITY_INDEX:
        return None
    return best


def estimate_maternal_heart_rate(
    ppg_samples: list[int],
    sample_rate_hz: float,
) -> RateEstimate | None:
    """Estimate maternal HR from the MAX30102 IR channel."""
    if not ppg_samples or sample_rate_hz <= 0:
        return None
    if len(ppg_samples) / sample_rate_hz < MIN_WINDOW_SECONDS:
        return None

    envelope, envelope_rate_hz = build_envelope(ppg_samples, sample_rate_hz)
    estimate = autocorrelation_rate(envelope, envelope_rate_hz, MATERNAL_HR_SEARCH_RANGE_BPM)
    if estimate is None or estimate.quality < MIN_SIGNAL_QUALITY_INDEX:
        return None
    return estimate


def classify_contraction_indicator(fsr_samples: list[int]) -> str:
    """Map relative FSR deflection to the stored indicator vocabulary.

    This is mechanical pressure relative to the window's own resting baseline. It
    is not contraction strength and not a tocotransducer substitute, so the
    buckets stay deliberately coarse.
    """
    if len(fsr_samples) < 2:
        return "unknown"

    values = [float(value) for value in fsr_samples]
    resting = min(values)
    deflection = max(values) - resting
    if deflection <= 0:
        return "none"

    # Relative to the 12-bit ADC span the belt actually reports.
    ratio = deflection / 4095.0
    if ratio < 0.02:
        return "none"
    if ratio < 0.08:
        return "mild"
    if ratio < 0.20:
        return "regular"
    return "strong"
