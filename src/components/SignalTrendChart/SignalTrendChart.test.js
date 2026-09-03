import test from 'node:test';
import assert from 'node:assert/strict';

import { normalizePoints, resolveDomain } from './signalTrendDomain.js';

/**
 * The domain is what decides whether the chart informs or misleads. An
 * auto-scaled sparkline draws a 139-141 bpm wobble and a 160-to-90 collapse
 * identically, because both fill the plot; keeping the reference band in frame
 * is what makes the height of the trace mean something.
 */

test('a nearly flat signal does not fill the plot', () => {
  const [minimum, maximum] = resolveDomain([139, 140, 141], [110, 160]);

  assert.ok(minimum <= 110, 'reference low must stay visible');
  assert.ok(maximum >= 160, 'reference high must stay visible');
  // The trace occupies a small slice of a domain dominated by the reference band.
  const traceShare = (141 - 139) / (maximum - minimum);
  assert.ok(traceShare < 0.15, `flat trace should stay flat, occupied ${traceShare}`);
});

test('a collapsing signal is visibly different from a flat one', () => {
  const flat = resolveDomain([139, 140, 141], [110, 160]);
  const collapsing = resolveDomain([160, 140, 120, 100, 90], [110, 160]);

  const flatShare = (141 - 139) / (flat[1] - flat[0]);
  const collapsingShare = (160 - 90) / (collapsing[1] - collapsing[0]);

  assert.ok(
    collapsingShare > flatShare * 4,
    'a large excursion must occupy far more of the plot than a small one',
  );
});

test('the reference band stays in frame even when data sits far outside it', () => {
  const [minimum, maximum] = resolveDomain([60, 62, 58], [110, 160]);

  assert.ok(minimum <= 58);
  assert.ok(maximum >= 160, 'the band must remain visible for comparison');
});

test('an explicit domain wins over the computed one', () => {
  assert.deepEqual(resolveDomain([100, 200], [110, 160], [0, 300]), [0, 300]);
});

test('an empty series still yields a usable domain', () => {
  const [minimum, maximum] = resolveDomain([], null, null);

  assert.ok(Number.isFinite(minimum) && Number.isFinite(maximum));
  assert.ok(maximum > minimum);
});

test('a series without a reference range is padded around its own extremes', () => {
  const [minimum, maximum] = resolveDomain([20, 80], null, null);

  assert.ok(minimum < 20);
  assert.ok(maximum > 80);
});

test('non-numeric samples are dropped rather than plotted as zero', () => {
  const points = normalizePoints([120, null, undefined, NaN, 130, 'abc']);

  assert.deepEqual(points.map((point) => point.value), [120, 130]);
});

test('bare numbers are spaced by the sample interval', () => {
  const points = normalizePoints([120, 121, 122], 500);

  assert.deepEqual(points.map((point) => point.elapsedMs), [0, 500, 1000]);
  assert.equal(points[0].isAbsolute, false);
});

test('timestamped points keep their own clock', () => {
  const points = normalizePoints([
    { value: 120, timestamp: '2026-08-31T10:00:00Z' },
    { value: 130, timestamp: '2026-08-31T10:00:30Z' },
  ]);

  assert.equal(points[1].elapsedMs - points[0].elapsedMs, 30_000);
  assert.equal(points[0].isAbsolute, true);
});
