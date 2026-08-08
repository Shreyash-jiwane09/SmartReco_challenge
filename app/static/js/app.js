(function (window) {
  "use strict";

  const tracker = window.SmartRecoTracker;
  const context = window.SmartRecoContext;

  if (
    !tracker ||
    !context ||
    !context.userId ||
    typeof context.getAccessToken !== "function"
  ) {
    return;
  }

  try {
    tracker.configure({
      userId: context.userId,
      getAccessToken: context.getAccessToken,
    });
    tracker.initializeCollectors({
      productView: context.productView,
      timeTracking: context.timeTracking,
    });
  } catch (error) {
    // Missing or malformed runtime context must not affect page behavior.
  }
})(window);
