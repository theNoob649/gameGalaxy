// Shared helper loaded by every game iframe.
// Provides GG.save(slug, value), GG.load(slug, fallback), and GG.onLoad().
// Saves go to localStorage immediately and bubble up to the parent page
// (which mirrors them to the cloud for signed-in users).
(function () {
  const pendingLoads = new Map();
  let counter = 0;

  function postToParent(msg) {
    try {
      window.parent.postMessage(Object.assign({ source: "gg" }, msg), "*");
    } catch (_) {}
  }

  function localKey(slug) {
    return "gg:save:" + slug;
  }

  function save(slug, value) {
    const payload = typeof value === "string" ? value : JSON.stringify(value);
    try {
      localStorage.setItem(localKey(slug), payload);
    } catch (_) {}
    postToParent({ type: "save", slug, payload });
  }

  function load(slug, fallback) {
    let raw = null;
    try {
      raw = localStorage.getItem(localKey(slug));
    } catch (_) {}
    if (raw == null) return fallback === undefined ? null : fallback;
    try {
      return JSON.parse(raw);
    } catch (_) {
      return raw;
    }
  }

  // Async fetch from host (used after a fresh sign-in cloud merge).
  function loadFromHost(slug) {
    return new Promise((resolve) => {
      const requestId = ++counter;
      pendingLoads.set(requestId, resolve);
      postToParent({ type: "load", slug, requestId });
      setTimeout(() => {
        if (pendingLoads.has(requestId)) {
          pendingLoads.delete(requestId);
          resolve(null);
        }
      }, 1500);
    });
  }

  window.addEventListener("message", (ev) => {
    const msg = ev.data;
    if (!msg || msg.source !== "gg-host") return;
    if (msg.type === "load-result" && pendingLoads.has(msg.requestId)) {
      const resolve = pendingLoads.get(msg.requestId);
      pendingLoads.delete(msg.requestId);
      resolve(msg.payload);
    }
  });

  window.GG = { save, load, loadFromHost };
})();
