(function (window) {
  "use strict";

  const SESSION_STORAGE_KEY = "smartreco.tracking.session_id";
  const TRACKER_CONFIG = Object.freeze({
    batchSize: 20,
    flushIntervalMs: 10000,
    maxRetries: 3,
    retryDelayMs: 1000,
  });
  const eventBuffer = [];
  let runtimeConfig = null;
  let flushTimer = null;
  let flushScheduled = false;
  let isFlushing = false;

  function generateSessionId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }

    return "session-" + Date.now() + "-" + Math.random().toString(36).slice(2);
  }

  function getSessionId() {
    let sessionId = window.sessionStorage.getItem(SESSION_STORAGE_KEY);

    if (!sessionId) {
      sessionId = generateSessionId();
      window.sessionStorage.setItem(SESSION_STORAGE_KEY, sessionId);
    }

    return sessionId;
  }

  function createEvent(eventType, details) {
    const eventDetails = details || {};

    return {
      event_type: eventType,
      resource_type: eventDetails.resourceType || null,
      resource_id: eventDetails.resourceId || null,
      page_url: eventDetails.pageUrl || window.location.href,
      event_timestamp: new Date().toISOString(),
      metadata: eventDetails.metadata || {},
    };
  }

  function track(eventType, details) {
    const event = createEvent(eventType, details);
    eventBuffer.push(event);
    ensureFlushTimer();

    if (eventBuffer.length >= TRACKER_CONFIG.batchSize) {
      scheduleFlush();
    }

    return event;
  }

  function getBufferSize() {
    return eventBuffer.length;
  }

  function takeBatch(limit) {
    const batchSize = limit === undefined ? TRACKER_CONFIG.batchSize : limit;
    return eventBuffer.splice(0, Math.min(batchSize, eventBuffer.length));
  }

  function configure(config) {
    runtimeConfig = {
      userId: config && config.userId,
      getAccessToken: config && config.getAccessToken,
    };

    if (eventBuffer.length > 0) {
      ensureFlushTimer();
    }
  }

  function buildBatchPayload(events) {
    return {
      session: {
        user_id: runtimeConfig.userId,
        session_id: getSessionId(),
      },
      client: {},
      events: events,
    };
  }

  async function getAccessToken() {
    if (!runtimeConfig || typeof runtimeConfig.getAccessToken !== "function") {
      return null;
    }

    try {
      const token = await runtimeConfig.getAccessToken();
      return typeof token === "string" && token.trim() ? token : null;
    } catch (error) {
      return null;
    }
  }

  function waitForRetry() {
    return new Promise(function (resolve) {
      window.setTimeout(resolve, TRACKER_CONFIG.retryDelayMs);
    });
  }

  async function sendBatch(events, token, keepalive) {
    for (let attempt = 0; attempt <= TRACKER_CONFIG.maxRetries; attempt += 1) {
      try {
        const response = await window.fetch("/api/v1/events", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: "Bearer " + token,
          },
          body: JSON.stringify(buildBatchPayload(events)),
          keepalive: keepalive,
        });

        if (response.ok) {
          return { delivered: true, transient: false };
        }

        if (response.status < 500) {
          return { delivered: false, transient: false };
        }
      } catch (error) {
        // Network failures use the same bounded retry path as HTTP 5xx responses.
      }

      if (attempt < TRACKER_CONFIG.maxRetries) {
        await waitForRetry();
      }
    }

    return { delivered: false, transient: true };
  }

  function ensureFlushTimer() {
    if (flushTimer !== null || eventBuffer.length === 0) {
      return;
    }

    flushTimer = window.setTimeout(function () {
      flushTimer = null;
      flush();
    }, TRACKER_CONFIG.flushIntervalMs);
  }

  function clearFlushTimer() {
    if (flushTimer !== null) {
      window.clearTimeout(flushTimer);
      flushTimer = null;
    }
  }

  function scheduleFlush() {
    if (flushScheduled || isFlushing) {
      return;
    }

    flushScheduled = true;
    window.setTimeout(function () {
      flushScheduled = false;
      flush();
    }, 0);
  }

  async function flush(options) {
    const flushOptions = options || {};

    if (isFlushing || eventBuffer.length === 0) {
      return false;
    }

    isFlushing = true;
    clearFlushTimer();
    let batch = takeBatch();
    let canScheduleNextBatch = false;

    try {
      const token = await getAccessToken();
      if (!token || !runtimeConfig.userId) {
        eventBuffer.unshift.apply(eventBuffer, batch);
        batch = [];
        return false;
      }

      const result = await sendBatch(batch, token, flushOptions.keepalive === true);
      canScheduleNextBatch = !result.transient;

      if (!result.delivered && result.transient) {
        eventBuffer.unshift.apply(eventBuffer, batch);
        batch = [];
      }

      return result.delivered;
    } catch (error) {
      if (batch.length > 0) {
        eventBuffer.unshift.apply(eventBuffer, batch);
      }
      return false;
    } finally {
      isFlushing = false;

      if (eventBuffer.length > 0) {
        ensureFlushTimer();
        if (canScheduleNextBatch && eventBuffer.length >= TRACKER_CONFIG.batchSize) {
          scheduleFlush();
        }
      }
    }
  }

  window.document.addEventListener("visibilitychange", function () {
    if (window.document.visibilityState === "hidden") {
      flush({ keepalive: true });
    }
  });

  window.SmartRecoTracker = Object.freeze({
    configure: configure,
    getSessionId: getSessionId,
    track: track,
    getBufferSize: getBufferSize,
    takeBatch: takeBatch,
    flush: flush,
  });
})(window);
