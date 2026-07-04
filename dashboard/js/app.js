/* app.js — boot, data loading, refresh loops.
   data.js is loaded via <script> injection (not fetch) so the dashboard also
   works opened straight from disk; the /api endpoints need the local server.
   Append ?demo=1 to preview the full UI with generated sample data. */
(function () {
  "use strict";
  const params = new URLSearchParams(location.search);
  const DEMO = params.has("demo");

  function loadScript(src) {
    return new Promise((res, rej) => {
      const sc = document.createElement("script");
      sc.src = src;
      sc.onload = () => { sc.remove(); res(); };
      sc.onerror = () => { sc.remove(); rej(new Error("load failed: " + src)); };
      document.body.appendChild(sc);
    });
  }

  let lastGenerated = null;
  function loadData(first) {
    if (DEMO) {
      if (window.makeDemoData) { window.DATA = window.makeDemoData(); C.render(window.DATA); }
      return;
    }
    loadScript("data.js?t=" + Date.now()).then(() => {
      if (!window.DATA) return;
      if (first || window.DATA.generated_utc !== lastGenerated) {
        lastGenerated = window.DATA.generated_utc;
        C.render(window.DATA);
      }
    }).catch(() => {
      if (first && !window.DATA) {
        document.getElementById("hero").innerHTML =
          `<div class="empty-state" style="padding:40px 10px"><span class="glyph">◎</span>
           <b>Waiting for first data…</b><br>data.js does not exist yet — the agent creates it on its first run.<br>
           <span style="opacity:.7">Preview the interface any time with <span class="mono">?demo=1</span></span></div>`;
      }
    });
  }

  async function loadSuggestions() {
    if (DEMO) return;
    try {
      const r = await fetch("/api/suggestions?t=" + Date.now());
      const j = await r.json();
      const changed = JSON.stringify(j) !== JSON.stringify(window.LIVE_SUGG);
      window.LIVE_SUGG = j;
      if (changed && window.DATA) C.render(window.DATA);
    } catch (e) { /* static-file mode — fall back to the data.js export */ }
  }

  function boot() {
    C.tickClock();
    setInterval(C.tickClock, 1000);
    if (DEMO) {
      loadScript("js/demo.js").then(() => {
        loadData(true);
        setInterval(() => loadData(false), 4000);   // demo ticks faster
      });
      return;
    }
    loadData(true);
    loadSuggestions();
    setInterval(() => loadData(false), 60000);
    setInterval(loadSuggestions, 30000);
    // surface the ASLEEP state as data goes stale inside a live window, even
    // though generated_utc stopped changing because the bot exited
    setInterval(() => {
      if (!window.DATA) return;
      const ageMin = (Date.now() - new Date(window.DATA.generated_utc)) / 60000;
      const wins = U.sessionWindows(window.DATA.schedule);
      const now = new Date();
      if (ageMin > 3 && wins.some((w) => w.open <= now && now < w.close))
        C.render(window.DATA);
    }, 20000);
  }

  window.App = { reload: () => loadData(true) };
  boot();
})();
