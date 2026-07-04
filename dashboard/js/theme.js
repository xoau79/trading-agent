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
    profit: "#3DD68C",
    loss: "#F2646C",
  };

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
    root.setProperty("--up", settings.profit);
    root.setProperty("--up-ink", settings.profit);
    root.setProperty("--down", settings.loss);
    root.setProperty("--down-ink", settings.loss);
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
