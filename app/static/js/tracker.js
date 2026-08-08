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
    return event;
  }

  function getBufferSize() {
    return eventBuffer.length;
  }

  function takeBatch(limit) {
    const batchSize = limit === undefined ? TRACKER_CONFIG.batchSize : limit;
    return eventBuffer.splice(0, Math.min(batchSize, eventBuffer.length));
  }

  window.SmartRecoTracker = Object.freeze({
    getSessionId: getSessionId,
    track: track,
    getBufferSize: getBufferSize,
    takeBatch: takeBatch,
  });
})(window);
