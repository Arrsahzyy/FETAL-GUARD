import assert from 'node:assert/strict';
import test from 'node:test';

import { createRealtimeEventPoller } from './realtimeEventPoller.js';


const flushMicrotasks = async () => {
  await Promise.resolve();
  await Promise.resolve();
};

function createScheduler() {
  let nextId = 1;
  const jobs = [];
  return {
    setTimer(callback, delay) {
      const job = { callback, delay, id: nextId, canceled: false };
      nextId += 1;
      jobs.push(job);
      return job.id;
    },
    clearTimer(id) {
      const job = jobs.find((candidate) => candidate.id === id);
      if (job) job.canceled = true;
    },
    next() {
      return jobs.find((job) => !job.canceled && !job.ran) || null;
    },
    async runNext() {
      const job = this.next();
      assert.ok(job, 'expected a scheduled job');
      job.ran = true;
      job.callback();
      await flushMicrotasks();
      return job;
    },
  };
}

function createDocument() {
  const listeners = new Set();
  return {
    visibilityState: 'visible',
    addEventListener(name, listener) {
      if (name === 'visibilitychange') listeners.add(listener);
    },
    removeEventListener(name, listener) {
      if (name === 'visibilitychange') listeners.delete(listener);
    },
    dispatchVisibility() {
      for (const listener of [...listeners]) listener();
    },
    listenerCount() {
      return listeners.size;
    },
  };
}

test('poller advances cursor and requests a single refetch per event batch', async () => {
  const scheduler = createScheduler();
  const seenCursors = [];
  const batches = [];
  const poller = createRealtimeEventPoller({
    initialCursor: 0,
    fetchEvents: async ({ cursor }) => {
      seenCursors.push(cursor);
      return cursor === 0
        ? { events: [{ event_id: 'event-1' }], next_cursor: 4, has_more: false, retry_after_ms: 5000 }
        : { events: [], next_cursor: 4, has_more: false, retry_after_ms: 5000 };
    },
    onEvents: async (events) => batches.push(events),
    setTimer: scheduler.setTimer,
    clearTimer: scheduler.clearTimer,
    random: () => 0.5,
  });

  poller.start();
  await scheduler.runNext();
  assert.deepEqual(seenCursors, [0]);
  assert.equal(batches.length, 1);
  assert.equal(poller.getState().cursor, 4);
  assert.equal(scheduler.next().delay, 5000);

  await scheduler.runNext();
  assert.deepEqual(seenCursors, [0, 4]);
  assert.equal(batches.length, 1);
  poller.stop();
});

test('poller retries the same cursor when the event consumer fails', async () => {
  const scheduler = createScheduler();
  const requestedCursors = [];
  let applyAttempt = 0;
  const poller = createRealtimeEventPoller({
    initialCursor: 0,
    fetchEvents: async ({ cursor }) => {
      requestedCursors.push(cursor);
      return {
        events: [{ event_id: 'event-retry' }],
        next_cursor: 7,
        has_more: false,
        retry_after_ms: 5000,
      };
    },
    onEvents: async () => {
      applyAttempt += 1;
      if (applyAttempt === 1) throw new Error('refetch failed');
    },
    baseDelayMs: 1000,
    random: () => 0.5,
    setTimer: scheduler.setTimer,
    clearTimer: scheduler.clearTimer,
  });

  poller.start();
  await scheduler.runNext();
  assert.equal(poller.getState().cursor, 0);
  assert.equal(scheduler.next().delay, 1000);

  await scheduler.runNext();
  assert.deepEqual(requestedCursors, [0, 0]);
  assert.equal(poller.getState().cursor, 7);
  poller.stop();
});

test('poller applies bounded exponential backoff and resets after success', async () => {
  const scheduler = createScheduler();
  let attempt = 0;
  const failures = [];
  const poller = createRealtimeEventPoller({
    initialCursor: 0,
    fetchEvents: async () => {
      attempt += 1;
      if (attempt <= 2) throw new Error('network unavailable');
      return { events: [], next_cursor: 0, has_more: false, retry_after_ms: 6000 };
    },
    onEvents: async () => undefined,
    onError: (_error, state) => failures.push(state.failureCount),
    baseDelayMs: 1000,
    maximumDelayMs: 8000,
    random: () => 0.5,
    setTimer: scheduler.setTimer,
    clearTimer: scheduler.clearTimer,
  });

  poller.start();
  await scheduler.runNext();
  assert.equal(scheduler.next().delay, 1000);
  await scheduler.runNext();
  assert.equal(scheduler.next().delay, 2000);
  await scheduler.runNext();
  assert.equal(scheduler.next().delay, 6000);
  assert.deepEqual(failures, [1, 2]);
  assert.equal(poller.getState().failureCount, 0);
  poller.stop();
});

test('poller aborts in-flight work and removes resources when stopped', async () => {
  const scheduler = createScheduler();
  const documentRef = createDocument();
  let capturedSignal;
  const poller = createRealtimeEventPoller({
    fetchEvents: ({ signal }) => {
      capturedSignal = signal;
      return new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => {
          const error = new Error('aborted');
          error.name = 'AbortError';
          reject(error);
        });
      });
    },
    onEvents: async () => undefined,
    setTimer: scheduler.setTimer,
    clearTimer: scheduler.clearTimer,
    documentRef,
  });

  poller.start();
  await scheduler.runNext();
  assert.equal(documentRef.listenerCount(), 1);
  assert.equal(capturedSignal.aborted, false);

  poller.stop();
  await flushMicrotasks();
  assert.equal(capturedSignal.aborted, true);
  assert.equal(documentRef.listenerCount(), 0);
  assert.equal(scheduler.next(), null);
});

test('hidden pages pause polling and resume immediately when visible', async () => {
  const scheduler = createScheduler();
  const documentRef = createDocument();
  const poller = createRealtimeEventPoller({
    fetchEvents: async () => ({ events: [], next_cursor: 0, retry_after_ms: 5000 }),
    onEvents: async () => undefined,
    setTimer: scheduler.setTimer,
    clearTimer: scheduler.clearTimer,
    documentRef,
  });

  poller.start();
  documentRef.visibilityState = 'hidden';
  documentRef.dispatchVisibility();
  assert.equal(scheduler.next(), null);

  documentRef.visibilityState = 'visible';
  documentRef.dispatchVisibility();
  assert.equal(scheduler.next().delay, 0);
  poller.stop();
});

test('poller bootstraps from the latest authorized watermark without replaying history', async () => {
  const scheduler = createScheduler();
  const requestedCursors = [];
  const batches = [];
  const poller = createRealtimeEventPoller({
    fetchEvents: async ({ cursor }) => {
      requestedCursors.push(cursor);
      return cursor === null
        ? { events: [], next_cursor: 12, has_more: false, retry_after_ms: 5000 }
        : {
            events: [{ event_id: 'event-new' }],
            next_cursor: 13,
            has_more: false,
            retry_after_ms: 5000,
          };
    },
    onEvents: async (events) => batches.push(events),
    setTimer: scheduler.setTimer,
    clearTimer: scheduler.clearTimer,
  });

  poller.start();
  await scheduler.runNext();
  assert.deepEqual(requestedCursors, [null]);
  assert.equal(poller.getState().cursor, 12);
  assert.equal(batches.length, 0);

  await scheduler.runNext();
  assert.deepEqual(requestedCursors, [null, 12]);
  assert.equal(batches.length, 1);
  poller.stop();
});
