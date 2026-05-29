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

  // --- end-of-game overlay shared by youWin / youLose ---
  // Both Play-again and Continue are exposed. Play-again reloads the iframe
  // by default (works for every game without per-game wiring), or invokes a
  // custom onRestart callback if the game passes one.
  function showOverlay(opts) {
    if (document.getElementById("gg-win-overlay")) return;
    const ov = document.createElement("div");
    ov.id = "gg-win-overlay";
    ov.style.cssText = `
      position: fixed; inset: 0; z-index: 9999;
      background: rgba(8, 12, 32, 0.92);
      display: grid; place-items: center;
      font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
      animation: gg-fade 0.18s ease-out;
    `;
    const card = document.createElement("div");
    card.style.cssText = "text-align: center; padding: 40px 30px; max-width: 90%;";
    card.innerHTML = `
      <div style="font-size: clamp(48px, 11vw, 110px); font-weight: 900; line-height: 1;
                  background: ${opts.gradient};
                  -webkit-background-clip: text; background-clip: text; color: transparent;
                  letter-spacing: -0.02em;">${opts.title}</div>
      <div style="margin: 18px 0 22px; color: #9aa3c7; font-size: 16px;">${opts.subtitle || ""}</div>
    `;
    const row = document.createElement("div");
    row.style.cssText = "display: flex; gap: 12px; justify-content: center; flex-wrap: wrap;";

    const playAgain = document.createElement("button");
    playAgain.textContent = "Play again";
    playAgain.style.cssText = `
      background: linear-gradient(135deg, #7c5cff, #ff6b9d);
      border: 0; color: white; font-weight: 700;
      padding: 12px 28px; border-radius: 10px; cursor: pointer;
      font-size: 16px; font-family: inherit;
      box-shadow: 0 8px 24px rgba(124, 92, 255, 0.35);
    `;
    playAgain.addEventListener("click", () => {
      ov.remove();
      if (typeof opts.onRestart === "function") opts.onRestart();
      else location.reload();
    });

    const cont = document.createElement("button");
    cont.textContent = "Continue";
    cont.style.cssText = `
      background: transparent;
      border: 1px solid #475569;
      color: #cbd5e1; font-weight: 600;
      padding: 12px 28px; border-radius: 10px; cursor: pointer;
      font-size: 16px; font-family: inherit;
    `;
    cont.addEventListener("click", () => ov.remove());

    row.appendChild(playAgain);
    row.appendChild(cont);
    card.appendChild(row);
    ov.appendChild(card);
    if (!document.getElementById("gg-win-style")) {
      const st = document.createElement("style");
      st.id = "gg-win-style";
      st.textContent = "@keyframes gg-fade { from { opacity: 0 } to { opacity: 1 } }";
      document.head.appendChild(st);
    }
    document.body.appendChild(ov);
  }

  function youWin(title, subtitle, opts) {
    showOverlay({
      title: title || "You Win!",
      subtitle,
      gradient: "linear-gradient(135deg, #fcd34d, #f97316, #ec4899)",
      onRestart: opts && opts.onRestart,
    });
  }

  function youLose(title, subtitle, opts) {
    showOverlay({
      title: title || "You Lose",
      subtitle,
      gradient: "linear-gradient(135deg, #f87171, #dc2626, #7c2d12)",
      onRestart: opts && opts.onRestart,
    });
  }

  window.GG = { save, load, loadFromHost, youWin, youLose };
})();
