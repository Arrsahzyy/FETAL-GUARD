import assert from 'node:assert/strict';
import test from 'node:test';

import {
  createTelemetryQueueScope,
  deleteTelemetryRecord,
  getNextPendingTelemetryRecord,
  getTelemetryQueueStats,
  hasTelemetryRecord,
  putTelemetryRecord,
  requeueFailedTelemetryRecords,
  updateTelemetryRecord,
} from './patientTelemetryQueue.js';

const createRecord = (id, scopeKey, enqueueOrder) => ({
  id,
  scopeKey,
  status: 'pending',
  enqueueOrder,
  createdAt: enqueueOrder,
  sequenceNumber: enqueueOrder,
  payload: { p: [1000 + enqueueOrder] },
  metadata: { ingestion_id: id },
});

test('telemetry queue isolates owners and returns only the oldest pending record', async () => {
  const firstScope = createTelemetryQueueScope({
    userId: 'user-a',
    sessionId: 'session-a',
    deviceId: 'device-a',
  });
  const secondScope = createTelemetryQueueScope({
    userId: 'user-b',
    sessionId: 'session-b',
    deviceId: 'device-b',
  });
  const recordIds = ['queue-a-2', 'queue-a-1', 'queue-b-1'];

  await putTelemetryRecord(createRecord(recordIds[0], firstScope, 2));
  await putTelemetryRecord(createRecord(recordIds[1], firstScope, 1));
  await putTelemetryRecord(createRecord(recordIds[2], secondScope, 1));

  const firstStats = await getTelemetryQueueStats(firstScope);
  const secondStats = await getTelemetryQueueStats(secondScope);
  const next = await getNextPendingTelemetryRecord(firstScope);

  assert.equal(firstStats.pending, 2);
  assert.equal(secondStats.pending, 1);
  assert.equal(next.record.id, recordIds[1]);
  assert.equal((await hasTelemetryRecord(recordIds[2])).exists, true);

  await Promise.all(recordIds.map((recordId) => deleteTelemetryRecord(recordId)));
});

test('failed telemetry remains quarantined until an explicit retry', async () => {
  const scopeKey = createTelemetryQueueScope({
    userId: 'user-retry',
    sessionId: 'session-retry',
    deviceId: 'device-retry',
  });
  const recordId = 'queue-retry-1';
  await putTelemetryRecord(createRecord(recordId, scopeKey, 1));
  await updateTelemetryRecord(recordId, {
    status: 'failed',
    attempts: 5,
    lastHttpStatus: 409,
  });

  const quarantined = await getTelemetryQueueStats(scopeKey);
  assert.equal(quarantined.pending, 0);
  assert.equal(quarantined.failed, 1);
  assert.equal((await getNextPendingTelemetryRecord(scopeKey)).record, null);

  const retried = await requeueFailedTelemetryRecords(scopeKey);
  assert.equal(retried.count, 1);
  assert.equal((await getNextPendingTelemetryRecord(scopeKey)).record.id, recordId);

  await deleteTelemetryRecord(recordId);
});
