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
  const productViewContexts = new Set();
  let collectorsInitialized = false;
  let timeTracking = null;

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

  function hasResourceContext(details) {
    return Boolean(details && details.resourceType && details.resourceId);
  }

  function trackProductView(details) {
    if (!hasResourceContext(details)) {
      return null;
    }

    const pageUrl = details.pageUrl || window.location.href;
    const contextKey = details.resourceType + ":" + details.resourceId + ":" + pageUrl;
    if (productViewContexts.has(contextKey)) {
      return null;
    }

    productViewContexts.add(contextKey);
    return track("PRODUCT_VIEW", {
      resourceType: details.resourceType,
      resourceId: details.resourceId,
      pageUrl: pageUrl,
      metadata: details.metadata || {},
    });
  }

  function trackSearch(query, options) {
    if (typeof query !== "string" || !query.trim()) {
      return null;
    }

    const searchOptions = options || {};
    return track("SEARCH", {
      pageUrl: searchOptions.pageUrl,
      metadata: { query: query.trim() },
    });
  }

  function trackClick(details) {
    if (!hasResourceContext(details)) {
      return null;
    }

    return track("CLICK", {
      resourceType: details.resourceType,
      resourceId: details.resourceId,
      pageUrl: details.pageUrl,
      metadata: details.metadata || {},
    });
  }

  function now() {
    return window.performance.now();
  }

  function pauseTimeTracking() {
    if (!timeTracking || timeTracking.activeStart === null) {
      return;
    }

    timeTracking.elapsedMilliseconds += Math.max(0, now() - timeTracking.activeStart);
    timeTracking.activeStart = null;
  }

  function resumeTimeTracking() {
    if (timeTracking && timeTracking.activeStart === null) {
      timeTracking.activeStart = now();
    }
  }

  function startTimeTracking(details) {
    if (timeTracking) {
      return false;
    }

    const timeDetails = details || {};
    timeTracking = {
      resourceType: timeDetails.resourceType || null,
      resourceId: timeDetails.resourceId || null,
      pageUrl: timeDetails.pageUrl || window.location.href,
      elapsedMilliseconds: 0,
      activeStart: window.document.visibilityState === "hidden" ? null : now(),
    };
    return true;
  }

  function stopTimeTracking() {
    if (!timeTracking) {
      return null;
    }

    pauseTimeTracking();
    const completedTracking = timeTracking;
    timeTracking = null;

    return track("TIME_SPENT", {
      resourceType: completedTracking.resourceType,
      resourceId: completedTracking.resourceId,
      pageUrl: completedTracking.pageUrl,
      metadata: { duration: completedTracking.elapsedMilliseconds / 1000 },
    });
  }

  function getSearchQuery(form) {
    const fieldName = form.getAttribute("data-track-search-field");
    const field = fieldName
      ? form.elements.namedItem(fieldName)
      : form.querySelector("[data-track-search-query]");

    return field && typeof field.value === "string" ? field.value : "";
  }

  function handleSearchSubmit(event) {
    const form = event.target;
    if (!form || !form.matches || !form.matches("[data-track-search]")) {
      return;
    }

    try {
      trackSearch(getSearchQuery(form));
    } catch (error) {
      // Tracking must never interrupt a normal search submission.
    }
  }

  function handleTrackedClick(event) {
    const target = event.target;
    if (!target || typeof target.closest !== "function") {
      return;
    }

    const trackedElement = target.closest("[data-track-click]");
    if (!trackedElement) {
      return;
    }

    try {
      const action = trackedElement.getAttribute("data-track-click");
      trackClick({
        resourceType: trackedElement.getAttribute("data-resource-type"),
        resourceId: trackedElement.getAttribute("data-resource-id"),
        metadata: action ? { action: action } : {},
      });
    } catch (error) {
      // Tracking must never interrupt click navigation or UI handling.
    }
  }

  function initializeCollectors(options) {
    const collectorOptions = options || {};

    if (!collectorsInitialized) {
      window.document.addEventListener("submit", handleSearchSubmit);
      window.document.addEventListener("click", handleTrackedClick);
      collectorsInitialized = true;
    }

    if (collectorOptions.productView) {
      trackProductView(collectorOptions.productView);
    }

    if (collectorOptions.timeTracking) {
      startTimeTracking(collectorOptions.timeTracking);
    }
  }

  function destroyCollectors() {
    if (collectorsInitialized) {
      window.document.removeEventListener("submit", handleSearchSubmit);
      window.document.removeEventListener("click", handleTrackedClick);
      collectorsInitialized = false;
    }

    return stopTimeTracking();
  }

  function handleVisibilityChange() {
    if (window.document.visibilityState === "hidden") {
      pauseTimeTracking();
      flush({ keepalive: true });
    } else {
      resumeTimeTracking();
    }
  }

  window.document.addEventListener("visibilitychange", handleVisibilityChange);

  window.SmartRecoTracker = Object.freeze({
    configure: configure,
    getSessionId: getSessionId,
    track: track,
    getBufferSize: getBufferSize,
    takeBatch: takeBatch,
    flush: flush,
    trackProductView: trackProductView,
    trackSearch: trackSearch,
    trackClick: trackClick,
    startTimeTracking: startTimeTracking,
    stopTimeTracking: stopTimeTracking,
    initializeCollectors: initializeCollectors,
    destroyCollectors: destroyCollectors,
  });
})(window);
