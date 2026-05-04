// Parent-page save broker.
// Listens for postMessages from game iframes and pushes saves to the cloud
// when the user is signed in. Also responds to load requests by reading
// either localStorage (always) or the server (when signed in).

(function () {
  const KEY_PREFIX = "gg:save:";
  let signedIn = false;
  let cloudSaves = {};

  async function refreshAuth() {
    try {
      const res = await fetch("/api/me", { credentials: "same-origin" });
      const data = await res.json();
      signedIn = !!data.signed_in;
      if (signedIn) {
        const r = await fetch("/api/saves", { credentials: "same-origin" });
        const j = await r.json();
        cloudSaves = j.saves || {};
        // Merge server saves into localStorage so games see them on load.
        Object.entries(cloudSaves).forEach(([slug, entry]) => {
          if (entry && typeof entry.payload === "string") {
            const local = localStorage.getItem(KEY_PREFIX + slug);
            const localTime = localStorage.getItem(KEY_PREFIX + slug + ":t") || "";
            if (!local || (entry.updated_at && entry.updated_at > localTime)) {
              localStorage.setItem(KEY_PREFIX + slug, entry.payload);
              localStorage.setItem(KEY_PREFIX + slug + ":t", entry.updated_at || "");
            }
          }
        });
      }
    } catch (_) {
      signedIn = false;
    }
  }

  refreshAuth();

  async function pushCloud(slug, payload) {
    if (!signedIn) return;
    try {
      await fetch(`/api/saves/${encodeURIComponent(slug)}`, {
        method: "PUT",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload }),
      });
    } catch (_) {
      // Network blip — local save still wins.
    }
  }

  window.addEventListener("message", (ev) => {
    const msg = ev.data;
    if (!msg || typeof msg !== "object" || msg.source !== "gg") return;
    const { type, slug, payload, requestId } = msg;
    if (typeof slug !== "string") return;
    const localKey = KEY_PREFIX + slug;
    const tsKey = localKey + ":t";

    if (type === "save" && typeof payload === "string") {
      localStorage.setItem(localKey, payload);
      localStorage.setItem(tsKey, new Date().toISOString());
      pushCloud(slug, payload);
    } else if (type === "load") {
      const data = localStorage.getItem(localKey);
      if (ev.source && ev.source.postMessage) {
        ev.source.postMessage(
          { source: "gg-host", type: "load-result", slug, requestId, payload: data },
          "*"
        );
      }
    }
  });
})();
