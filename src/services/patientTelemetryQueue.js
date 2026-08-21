const DATABASE_NAME = 'fetal_guard_patient_telemetry_v1';
const DATABASE_VERSION = 2;
const STORE_NAME = 'packets';
const SCOPE_INDEX = 'scopeKey';
const SCOPE_STATUS_INDEX = 'scopeStatus';
const SCOPE_STATUS_ORDER_INDEX = 'scopeStatusOrder';

const memoryQueue = new Map();
let databasePromise = null;
let indexedDbUnavailable = typeof globalThis.indexedDB === 'undefined';

const cloneValue = (value) => {
  if (typeof globalThis.structuredClone === 'function') {
    return globalThis.structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value));
};

const openDatabase = async () => {
  if (indexedDbUnavailable) return null;
  if (databasePromise) return databasePromise;

  databasePromise = new Promise((resolve, reject) => {
    const request = globalThis.indexedDB.open(DATABASE_NAME, DATABASE_VERSION);
    request.onupgradeneeded = (event) => {
      const database = request.result;
      const store = database.objectStoreNames.contains(STORE_NAME)
        ? request.transaction.objectStore(STORE_NAME)
        : database.createObjectStore(STORE_NAME, { keyPath: 'id' });
      if (!store.indexNames.contains(SCOPE_INDEX)) {
        store.createIndex(SCOPE_INDEX, SCOPE_INDEX, { unique: false });
      }
      if (!store.indexNames.contains(SCOPE_STATUS_INDEX)) {
        store.createIndex(SCOPE_STATUS_INDEX, ['scopeKey', 'status'], { unique: false });
      }
      if (!store.indexNames.contains(SCOPE_STATUS_ORDER_INDEX)) {
        store.createIndex(
          SCOPE_STATUS_ORDER_INDEX,
          ['scopeKey', 'status', 'enqueueOrder'],
          { unique: false },
        );
      }
      if (event.oldVersion > 0 && event.oldVersion < 2) {
        let fallbackOrder = Date.now() * 1000;
        const cursorRequest = store.openCursor();
        cursorRequest.onsuccess = () => {
          const cursor = cursorRequest.result;
          if (!cursor) return;
          const record = cursor.value;
          if (!Number.isFinite(record.enqueueOrder)) {
            fallbackOrder += 1;
            record.enqueueOrder = Math.max(
              fallbackOrder,
              Number(record.createdAt || 0) * 1000,
            );
            cursor.update(record);
          }
          cursor.continue();
        };
      }
    };
    request.onsuccess = () => {
      const database = request.result;
      database.onversionchange = () => database.close();
      resolve(database);
    };
    request.onerror = () => reject(request.error || new Error('telemetry_queue_open_failed'));
    request.onblocked = () => reject(new Error('telemetry_queue_open_blocked'));
  }).catch(() => {
    indexedDbUnavailable = true;
    databasePromise = null;
    return null;
  });

  return databasePromise;
};

const runRequest = (database, mode, createRequest) => new Promise((resolve, reject) => {
  const transaction = database.transaction(STORE_NAME, mode);
  const store = transaction.objectStore(STORE_NAME);
  let result;
  let request;
  try {
    request = createRequest(store);
  } catch (error) {
    transaction.abort();
    reject(error);
    return;
  }

  request.onsuccess = () => {
    result = request.result;
  };
  request.onerror = () => reject(request.error || new Error('telemetry_queue_request_failed'));
  transaction.oncomplete = () => resolve(result);
  transaction.onabort = () => reject(transaction.error || new Error('telemetry_queue_transaction_aborted'));
  transaction.onerror = () => reject(transaction.error || new Error('telemetry_queue_transaction_failed'));
});

const sortRecords = (records) => records.sort((left, right) => {
  const timeDifference = Number(left.createdAt || 0) - Number(right.createdAt || 0);
  if (timeDifference !== 0) return timeDifference;
  const orderDifference = Number(left.enqueueOrder || 0) - Number(right.enqueueOrder || 0);
  if (orderDifference !== 0) return orderDifference;
  return Number(left.sequenceNumber || 0) - Number(right.sequenceNumber || 0);
});

export const createTelemetryQueueScope = ({ userId, sessionId, deviceId }) => {
  const parts = [userId, sessionId, deviceId].map((value) => String(value || '').trim());
  if (parts.some((part) => !part)) throw new Error('telemetry_queue_scope_incomplete');
  return parts.map((part) => encodeURIComponent(part)).join('|');
};

export const putTelemetryRecord = async (record) => {
  if (!record?.id || !record?.scopeKey) throw new Error('telemetry_queue_record_invalid');
  const database = await openDatabase();
  if (!database) {
    const storedRecord = cloneValue(record);
    memoryQueue.set(storedRecord.id, storedRecord);
    return { record: cloneValue(storedRecord), durable: false };
  }

  await runRequest(database, 'readwrite', (store) => store.put(record));
  return { record, durable: true };
};

export const listTelemetryRecords = async (scopeKey) => {
  if (!scopeKey) return { records: [], durable: !indexedDbUnavailable };
  const database = await openDatabase();
  if (!database) {
    const records = Array.from(memoryQueue.values())
      .filter((record) => record.scopeKey === scopeKey)
      .map(cloneValue);
    return { records: sortRecords(records), durable: false };
  }

  const records = await runRequest(
    database,
    'readonly',
    (store) => store.index(SCOPE_INDEX).getAll(scopeKey),
  );
  return { records: sortRecords(records || []), durable: true };
};

export const hasTelemetryRecord = async (recordId) => {
  if (!recordId) return { exists: false, durable: !indexedDbUnavailable };
  const database = await openDatabase();
  if (!database) {
    return { exists: memoryQueue.has(recordId), durable: false };
  }
  const count = await runRequest(database, 'readonly', (store) => store.count(recordId));
  return { exists: Number(count || 0) > 0, durable: true };
};

export const getTelemetryQueueStats = async (scopeKey) => {
  if (!scopeKey) return {
    total: 0,
    pending: 0,
    failed: 0,
    durable: !indexedDbUnavailable,
  };
  const database = await openDatabase();
  if (!database) {
    const records = Array.from(memoryQueue.values())
      .filter((record) => record.scopeKey === scopeKey);
    return {
      total: records.length,
      pending: records.filter((record) => record.status === 'pending').length,
      failed: records.filter((record) => record.status === 'failed').length,
      durable: false,
    };
  }

  const [total, pending, failed] = await Promise.all([
    runRequest(database, 'readonly', (store) => store.index(SCOPE_INDEX).count(scopeKey)),
    runRequest(
      database,
      'readonly',
      (store) => store.index(SCOPE_STATUS_INDEX).count([scopeKey, 'pending']),
    ),
    runRequest(
      database,
      'readonly',
      (store) => store.index(SCOPE_STATUS_INDEX).count([scopeKey, 'failed']),
    ),
  ]);
  return {
    total: Number(total || 0),
    pending: Number(pending || 0),
    failed: Number(failed || 0),
    durable: true,
  };
};

export const getNextPendingTelemetryRecord = async (scopeKey) => {
  if (!scopeKey) return { record: null, durable: !indexedDbUnavailable };
  const database = await openDatabase();
  if (!database) {
    const record = sortRecords(
      Array.from(memoryQueue.values())
        .filter((item) => item.scopeKey === scopeKey && item.status === 'pending'),
    )[0] || null;
    return { record: record ? cloneValue(record) : null, durable: false };
  }

  const keyRange = globalThis.IDBKeyRange.bound(
    [scopeKey, 'pending', 0],
    [scopeKey, 'pending', Number.MAX_SAFE_INTEGER],
  );
  const records = await runRequest(
    database,
    'readonly',
    (store) => store.index(SCOPE_STATUS_ORDER_INDEX).getAll(keyRange, 1),
  );
  return { record: records?.[0] || null, durable: true };
};

export const updateTelemetryRecord = async (recordId, updates) => {
  const database = await openDatabase();
  if (!database) {
    const current = memoryQueue.get(recordId);
    if (!current) return { record: null, durable: false };
    const updated = { ...current, ...cloneValue(updates) };
    memoryQueue.set(recordId, updated);
    return { record: cloneValue(updated), durable: false };
  }

  const updatedRecord = await new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    const getRequest = store.get(recordId);
    let result = null;

    getRequest.onsuccess = () => {
      if (!getRequest.result) return;
      result = { ...getRequest.result, ...cloneValue(updates) };
      store.put(result);
    };
    getRequest.onerror = () => reject(getRequest.error || new Error('telemetry_queue_read_failed'));
    transaction.oncomplete = () => resolve(result);
    transaction.onabort = () => reject(transaction.error || new Error('telemetry_queue_transaction_aborted'));
    transaction.onerror = () => reject(transaction.error || new Error('telemetry_queue_transaction_failed'));
  });
  return { record: updatedRecord, durable: true };
};

export const deleteTelemetryRecord = async (recordId) => {
  const database = await openDatabase();
  if (!database) {
    memoryQueue.delete(recordId);
    return { durable: false };
  }
  await runRequest(database, 'readwrite', (store) => store.delete(recordId));
  return { durable: true };
};

export const clearTelemetryRecordsForUser = async (userId) => {
  const userScopePrefix = `${encodeURIComponent(String(userId || '').trim())}|`;
  if (userScopePrefix === '|') throw new Error('telemetry_queue_user_required');
  const database = await openDatabase();
  if (!database) {
    let count = 0;
    for (const [recordId, record] of memoryQueue.entries()) {
      if (String(record.scopeKey || '').startsWith(userScopePrefix)) {
        memoryQueue.delete(recordId);
        count += 1;
      }
    }
    return { count, durable: false };
  }

  const count = await new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, 'readwrite');
    const store = transaction.objectStore(STORE_NAME);
    const request = store.openCursor();
    let deleted = 0;
    request.onsuccess = () => {
      const cursor = request.result;
      if (!cursor) return;
      if (String(cursor.value?.scopeKey || '').startsWith(userScopePrefix)) {
        cursor.delete();
        deleted += 1;
      }
      cursor.continue();
    };
    request.onerror = () => reject(request.error || new Error('telemetry_queue_read_failed'));
    transaction.oncomplete = () => resolve(deleted);
    transaction.onabort = () => reject(transaction.error || new Error('telemetry_queue_transaction_aborted'));
    transaction.onerror = () => reject(transaction.error || new Error('telemetry_queue_transaction_failed'));
  });
  return { count, durable: true };
};

export const requeueFailedTelemetryRecords = async (scopeKey) => {
  const { records, durable } = await listTelemetryRecords(scopeKey);
  const failedRecords = records.filter((record) => record.status === 'failed');
  await Promise.all(failedRecords.map((record) => updateTelemetryRecord(record.id, {
    status: 'pending',
    attempts: 0,
    nextAttemptAt: 0,
    lastError: null,
  })));
  return { count: failedRecords.length, durable };
};
