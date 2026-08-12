import assert from 'node:assert/strict';
import test from 'node:test';
import { createAuthSessionEpochController } from './authSessionEpoch.js';

test('invalidated authentication generations never become current again', () => {
  const controller = createAuthSessionEpochController();
  const clinicianAGeneration = controller.current();

  controller.advance();

  assert.equal(controller.isCurrent(clinicianAGeneration), false);
  assert.equal(controller.isCurrent(controller.current()), true);
});

test('a stale refresh cannot clear or replace the next session refresh', () => {
  const controller = createAuthSessionEpochController();
  const clinicianAPromise = Promise.resolve('clinician-a');
  const clinicianAGeneration = controller.current();
  assert.equal(
    controller.setRefreshPromise(clinicianAGeneration, 'refresh-a', clinicianAPromise),
    true,
  );

  controller.advance();
  const clinicianBPromise = Promise.resolve('clinician-b');
  const clinicianBGeneration = controller.current();
  assert.equal(
    controller.setRefreshPromise(clinicianBGeneration, 'refresh-b', clinicianBPromise),
    true,
  );

  controller.clearRefreshPromise(clinicianAPromise);

  assert.equal(
    controller.getRefreshPromise(clinicianBGeneration, 'refresh-b'),
    clinicianBPromise,
  );
  assert.equal(controller.getRefreshPromise(clinicianAGeneration, 'refresh-a'), null);
});

test('a refresh operation cannot register after its session was invalidated', () => {
  const controller = createAuthSessionEpochController();
  const staleGeneration = controller.current();
  controller.advance();

  assert.equal(
    controller.setRefreshPromise(staleGeneration, 'refresh-a', Promise.resolve()),
    false,
  );
});
