/* theme.js — appearance engine. window.Theme.
   Loaded synchronously right after the wallpaper/backdrop layers so saved
   settings apply before first paint (no flash of the default theme).
   Everything here is plain values (hex colours, px, numbers) written straight
   onto :root — app.css derives every tint/glow from them via color-mix(). */
(function () {
  "use strict";
  const STORAGE_KEY = "ta_theme_v1";

  const DEFAULTS = {
    bgMode: "color",      // "color" | "image"
    bg: "#07090F",
    wallpaper: null,       // data URL
    wallpaperBlur: 8,      // px
    wallpaperDim: 50,      // 0-90 (%)
    glassBlur: 0,          // px
    glassOpacity: 100,     // 40-100 (%)
    accent: "#5585E3",
    glow: 100,             // 0-200 (%)
    text: "#EAF0F9",       // base neutral text colour (--ink)
    profit: "#3DD68C",
    loss: "#F2646C",
    mcBand: "#5585E3",     // Monte Carlo simulation band fill, independent of accent
  };

  /* -------------------------- neutral text shading ------------------------
     --ink-2/--ink-3 (secondary / dimmed text) shade from the chosen text
     colour toward the background, same idea as the --surface-N ramp. They
     must land on :root as flat hex (not a color-mix() chain) because
     charts.js reads them back via getComputedStyle to hex-parse for canvas
     — a custom property holding an unresolved color-mix() string would
     break that parsing. */
  function hexToRgb(hex) {
    const h = (hex || "").replace("#", "").trim();
    const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
  }
  function rgbToHex(r, g, b) {
    return "#" + [r, g, b].map((v) => Math.max(0, Math.min(255, Math.round(v)))
      .toString(16).padStart(2, "0")).join("").toUpperCase();
  }
  function mix(hexA, hexB, weightA) {
    const a = hexToRgb(hexA), b = hexToRgb(hexB), wb = 1 - weightA;
    return rgbToHex(a.r * weightA + b.r * wb, a.g * weightA + b.g * wb, a.b * weightA + b.b * wb);
  }

  function load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return { ...DEFAULTS };
      const saved = JSON.parse(raw);
      return { ...DEFAULTS, ...saved };
    } catch (e) {
      return { ...DEFAULTS };
    }
  }

  function save(settings) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
      return true;
    } catch (e) {
      return false;
    }
  }

  function apply(settings) {
    const root = document.documentElement.style;
    root.setProperty("--bg", settings.bg);
    root.setProperty("--accent", settings.accent);
    root.setProperty("--ink", settings.text);
    root.setProperty("--ink-2", mix(settings.text, settings.bg, 0.70));
    root.setProperty("--ink-3", mix(settings.text, settings.bg, 0.43));
    root.setProperty("--up", settings.profit);
    root.setProperty("--up-ink", settings.profit);
    root.setProperty("--down", settings.loss);
    root.setProperty("--down-ink", settings.loss);
    root.setProperty("--mc-band", settings.mcBand);
    root.setProperty("--glow", String(settings.glow / 100));
    root.setProperty("--wallpaper-blur", settings.wallpaperBlur + "px");
    root.setProperty("--wallpaper-dim", String(settings.wallpaperDim / 100));
    root.setProperty("--glass-blur", settings.glassBlur + "px");
    root.setProperty("--glass-opacity", String(settings.glassOpacity / 100));

    const wallpaper = document.getElementById("wallpaper");
    const wallpaperImg = document.getElementById("wallpaperImg");
    const showImage = settings.bgMode === "image" && settings.wallpaper;
    if (wallpaper) wallpaper.hidden = !showImage;
    if (wallpaperImg) wallpaperImg.style.backgroundImage = showImage ? `url("${settings.wallpaper}")` : "";
    if (document.body) document.body.classList.toggle("has-wallpaper", !!showImage);

    if (window.Charts && window.Charts.refreshTokens) window.Charts.refreshTokens();
    if (window.DATA && window.C && window.C.render) window.C.render(window.DATA);
  }

  let current = load();
  apply(current);

  window.Theme = {
    DEFAULTS,
    get: () => ({ ...current }),
    set(partial) {
      current = { ...current, ...partial };
      apply(current);
      const saved = save(current);
      return { settings: { ...current }, saved };
    },
    reset() {
      current = { ...DEFAULTS };
      apply(current);
      save(current);
      return { ...current };
    },
  };
})();
