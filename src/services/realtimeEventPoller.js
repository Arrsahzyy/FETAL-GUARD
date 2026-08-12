const clampDelay = (value, minimum, maximum) => (
  Math.min(maximum, Math.max(minimum, Number(value) || minimum))
);

const isCanceledRequest = (error) => (
  error?.name === 'AbortError'
  || error?.code === 'ERR_CANCELED'
  || error?.code === 'ABORT_ERR'
);

export function createRealtimeEventPoller({
  fetchEvents,
  onEvents,
  onError = () => undefined,
  onHeartbeat = () => undefined,
  initialCursor = null,
  initialDelayMs = 0,
  baseDelayMs = 5_000,
  maximumDelayMs = 45_000,
  heartbeatIntervalMs = 45_000,
  jitterRatio = 0.15,
  random = Math.random,
  now = Date.now,
  setTimer = (callback, delay) => window.setTimeout(callback, delay),
  clearTimer = (timerId) => window.clearTimeout(timerId),
  documentRef = typeof document === 'undefined' ? null : document,
  AbortControllerClass = AbortController,
} = {}) {
  if (typeof fetchEvents !== 'function' || typeof onEvents !== 'function') {
    throw new TypeError('fetchEvents and onEvents are required');
  }

  let cursor = initialCursor === null
    ? null
    : Number.isSafeInteger(initialCursor) && initialCursor >= 0
      ? initialCursor
      : null;
  let failureCount = 0;
  let timerId = null;
  let requestController = null;
  let started = false;
  let lastHeartbeatAt = now();

  const isVisible = () => !documentRef || documentRef.visibilityState !== 'hidden';

  const cancelTimer = () => {
    if (timerId === null) return;
    clearTimer(timerId);
    timerId = null;
  };

  const cancelRequest = () => {
    requestController?.abort();
    requestController = null;
  };

  const withJitter = (delay) => {
    const boundedJitter = Math.min(0.5, Math.max(0, jitterRatio));
    const factor = 1 + ((random() * 2) - 1) * boundedJitter;
    return Math.round(delay * factor);
  };

  const schedule = (callback, delay) => {
    cancelTimer();
    if (!started || !isVisible()) return;
    timerId = setTimer(() => {
      timerId = null;
      void callback();
    }, Math.max(0, delay));
  };

  const poll = async () => {
    if (!started || !isVisible() || requestController) return;
    const controller = new AbortControllerClass();
    requestController = controller;

    try {
      const page = await fetchEvents({ cursor, signal: controller.signal });
      if (!started || controller.signal.aborted) return;

      const nextCursor = Number(page?.next_cursor);
      if (
        !Number.isSafeInteger(nextCursor)
        || nextCursor < 0
        || (cursor !== null && nextCursor < cursor)
      ) {
        throw new Error('Realtime event endpoint returned an invalid cursor');
      }
      const events = Array.isArray(page?.events) ? page.events : [];
      if (events.length > 0) {
        // A cursor is acknowledged only after the consumer successfully
        // applies the batch. If refetch/state application fails, retry the
        // same events instead of creating a permanent client-side gap.
        await onEvents(events, { cursor: nextCursor });
        cursor = nextCursor;
        lastHeartbeatAt = now();
      } else {
        cursor = nextCursor;
        if (now() - lastHeartbeatAt >= heartbeatIntervalMs) {
          await onHeartbeat({ cursor });
          lastHeartbeatAt = now();
        }
      }
      failureCount = 0;
      if (!started || controller.signal.aborted) return;

      const retryDelay = page?.has_more
        ? 10
        : clampDelay(page?.retry_after_ms, baseDelayMs, maximumDelayMs);
      schedule(poll, retryDelay);
    } catch (error) {
      if (!started || controller.signal.aborted || isCanceledRequest(error)) return;
      failureCount += 1;
      onError(error, { failureCount });
      const exponentialDelay = Math.min(
        maximumDelayMs,
        baseDelayMs * (2 ** Math.min(failureCount - 1, 10)),
      );
      schedule(poll, withJitter(exponentialDelay));
    } finally {
      if (requestController === controller) requestController = null;
    }
  };

  const handleVisibilityChange = () => {
    if (!started) return;
    if (!isVisible()) {
      cancelTimer();
      cancelRequest();
      return;
    }
    schedule(poll, 0);
  };

  return {
    start() {
      if (started) return;
      started = true;
      documentRef?.addEventListener('visibilitychange', handleVisibilityChange);
      schedule(poll, initialDelayMs);
    },
    stop() {
      if (!started) return;
      started = false;
      cancelTimer();
      cancelRequest();
      documentRef?.removeEventListener('visibilitychange', handleVisibilityChange);
    },
    getState() {
      return { cursor, failureCount, isRunning: started };
    },
  };
}

export default createRealtimeEventPoller;
