import assert from 'node:assert/strict';
import test from 'node:test';
import {
  csvEscape,
  formatAggregateCount,
  getHighestRiskForSessions,
  getRiskMeta,
  normalizeClinicianStatistics,
  normalizeRiskLevel,
} from './clinicianModels.js';

test('unknown risk values remain visible as data that needs verification', () => {
  assert.equal(normalizeRiskLevel('unexpected-contract-value'), 'unknown');
  assert.equal(getRiskMeta('unexpected-contract-value', 'id').className, 'unknown');

  const alertsBySession = new Map([
    ['session-1', [{ risk_level: 'unexpected-contract-value' }]],
  ]);
  assert.equal(getHighestRiskForSessions(['session-1'], alertsBySession), 'unknown');
});

test('known risk values retain their intended priority', () => {
  const alertsBySession = new Map([
    ['session-1', [{ risk_level: 'medium' }, { risk_level: 'high' }]],
  ]);
  assert.equal(getHighestRiskForSessions(['session-1'], alertsBySession), 'high');
});

test('CSV fields that spreadsheet applications can execute are neutralized', () => {
  assert.equal(csvEscape('=1+1'), "'=1+1");
  assert.equal(csvEscape('  +cmd'), "'  +cmd");
  assert.equal(csvEscape('@SUM(A1:A2)'), "'@SUM(A1:A2)");
  assert.equal(csvEscape("Ayu\rBudi"), '"Ayu\rBudi"');
  assert.equal(csvEscape('Nama Pasien'), 'Nama Pasien');
});

test('clinician aggregate statistics only accept complete non-negative integer counts', () => {
  assert.deepEqual(normalizeClinicianStatistics({
    total_patients: 150,
    active_monitoring: 12,
    high_priority_patients: 3,
    open_alerts: 8,
  }), {
    total: 150,
    monitoring: 12,
    highRisk: 3,
    alerts: 8,
  });

  assert.deepEqual(normalizeClinicianStatistics({
    total_patients: 0,
    active_monitoring: 0,
    high_priority_patients: 0,
    open_alerts: 0,
  }), {
    total: 0,
    monitoring: 0,
    highRisk: 0,
    alerts: 0,
  });

  assert.equal(normalizeClinicianStatistics(null), null);
  assert.equal(normalizeClinicianStatistics({ total_patients: 1 }), null);
  assert.equal(normalizeClinicianStatistics({
    total_patients: 1,
    active_monitoring: -1,
    high_priority_patients: 0,
    open_alerts: 0,
  }), null);
  assert.equal(normalizeClinicianStatistics({
    total_patients: 1,
    active_monitoring: 0,
    high_priority_patients: 0,
    open_alerts: '0',
  }), null);
  assert.equal(normalizeClinicianStatistics({
    total_patients: 1,
    active_monitoring: 2,
    high_priority_patients: 0,
    open_alerts: 0,
  }), null);
});

test('unavailable aggregate statistics render an honest placeholder instead of zero', () => {
  assert.equal(formatAggregateCount(0), '0');
  assert.equal(formatAggregateCount(42), '42');
  assert.equal(formatAggregateCount(null), '—');
  assert.equal(formatAggregateCount(undefined), '—');
});
