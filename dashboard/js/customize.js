/* customize.js — wires the Customize drawer (button, panel, controls) to
   window.Theme. Loaded last; safe to assume Theme/Charts/C are all ready. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const MAX_DIM = 1920;

  const els = {
    btn: $("customizeBtn"),
    overlay: $("customizeOverlay"),
    panel: $("customizePanel"),
    close: $("customizeClose"),
    reset: $("czReset"),
    bgModes: $("czBgModes"),
    bgColorGroup: $("czBgColorGroup"),
    bgImageGroup: $("czBgImageGroup"),
    bg: $("czBg"),
    bgHex: $("czBgHex"),
    wallpaperThumb: $("czWallpaperThumb"),
    wallpaperFile: $("czWallpaperFile"),
    wallpaperClear: $("czWallpaperClear"),
    wallpaperBlur: $("czWallpaperBlur"),
    wallpaperBlurVal: $("czWallpaperBlurVal"),
    wallpaperDim: $("czWallpaperDim"),
    wallpaperDimVal: $("czWallpaperDimVal"),
    wallpaperError: $("czWallpaperError"),
    glassBlur: $("czGlassBlur"),
    glassBlurVal: $("czGlassBlurVal"),
    glassOpacity: $("czGlassOpacity"),
    glassOpacityVal: $("czGlassOpacityVal"),
    accent: $("czAccent"),
    accentHex: $("czAccentHex"),
    glow: $("czGlow"),
    glowVal: $("czGlowVal"),
    profit: $("czProfit"),
    profitHex: $("czProfitHex"),
    loss: $("czLoss"),
    lossHex: $("czLossHex"),
    mcBand: $("czMcBand"),
    mcBandHex: $("czMcBandHex"),
  };

  if (!els.btn || !window.Theme) return;

  /* -------------------------------- hex code entry ------------------------ */
  // Lets you find a colour by typing its 6-character hex code (e.g. "e5bddf" for
  // orchid) into the field next to a swatch — no "#" required. Applies as soon as
  // 6 valid hex digits are present; reverts to the current colour otherwise.
  function hexOf(color) { return (color || "").replace("#", "").toUpperCase(); }
  function bindHex(hexInput, colorInput, apply) {
    if (!hexInput || !colorInput) return;
    hexInput.addEventListener("input", () => {
      const clean = hexInput.value.replace(/[^0-9a-fA-F]/g, "").slice(0, 6).toUpperCase();
      if (hexInput.value !== clean) hexInput.value = clean;
      hexInput.classList.remove("invalid");
      if (clean.length === 6) {
        const hex = "#" + clean;
        colorInput.value = hex;
        apply(hex);
      }
    });
    hexInput.addEventListener("blur", () => {
      const incomplete = hexInput.value.length > 0 && hexInput.value.length !== 6;
      hexInput.value = hexOf(colorInput.value);
      if (incomplete) {
        hexInput.classList.add("invalid");
        setTimeout(() => hexInput.classList.remove("invalid"), 900);
      }
    });
    hexInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") hexInput.blur();
    });
  }
  bindHex(els.bgHex, els.bg, (hex) => window.Theme.set({ bg: hex }));
  bindHex(els.accentHex, els.accent, (hex) => window.Theme.set({ accent: hex }));
  bindHex(els.profitHex, els.profit, (hex) => window.Theme.set({ profit: hex }));
  bindHex(els.lossHex, els.loss, (hex) => window.Theme.set({ loss: hex }));
  bindHex(els.mcBandHex, els.mcBand, (hex) => window.Theme.set({ mcBand: hex }));

  function syncUI() {
    const s = window.Theme.get();
    els.bg.value = s.bg;
    els.bgHex.value = hexOf(s.bg);
    els.accent.value = s.accent;
    els.accentHex.value = hexOf(s.accent);
    els.profit.value = s.profit;
    els.profitHex.value = hexOf(s.profit);
    els.loss.value = s.loss;
    els.lossHex.value = hexOf(s.loss);
    els.mcBand.value = s.mcBand;
    els.mcBandHex.value = hexOf(s.mcBand);

    els.wallpaperBlur.value = s.wallpaperBlur;
    els.wallpaperBlurVal.textContent = s.wallpaperBlur + "px";
    els.wallpaperDim.value = s.wallpaperDim;
    els.wallpaperDimVal.textContent = s.wallpaperDim + "%";
    els.glassBlur.value = s.glassBlur;
    els.glassBlurVal.textContent = s.glassBlur + "px";
    els.glassOpacity.value = s.glassOpacity;
    els.glassOpacityVal.textContent = s.glassOpacity + "%";
    els.glow.value = s.glow;
    els.glowVal.textContent = s.glow + "%";

    els.bgColorGroup.hidden = s.bgMode !== "color";
    els.bgImageGroup.hidden = s.bgMode !== "image";
    [...els.bgModes.children].forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.bgMode === s.bgMode);
    });
    els.wallpaperThumb.style.backgroundImage = s.wallpaper ? `url("${s.wallpaper}")` : "none";
  }

  function showError(msg) {
    els.wallpaperError.textContent = msg;
    els.wallpaperError.hidden = false;
  }
  function hideError() { els.wallpaperError.hidden = true; }

  /* -------------------------------- panel open/close -------------------- */
  let hideTimer = null;
  function openPanel() {
    if (hideTimer) { clearTimeout(hideTimer); hideTimer = null; }
    els.overlay.hidden = false;
    els.panel.hidden = false;
    requestAnimationFrame(() => {
      els.overlay.classList.add("open");
      els.panel.classList.add("open");
    });
    document.addEventListener("keydown", onKeydown);
  }
  function closePanel() {
    els.overlay.classList.remove("open");
    els.panel.classList.remove("open");
    document.removeEventListener("keydown", onKeydown);
    if (hideTimer) clearTimeout(hideTimer);
    hideTimer = setTimeout(() => {
      els.overlay.hidden = true;
      els.panel.hidden = true;
      hideTimer = null;
    }, 280);
  }
  function onKeydown(e) { if (e.key === "Escape") closePanel(); }

  els.btn.addEventListener("click", () => { syncUI(); openPanel(); });
  els.close.addEventListener("click", closePanel);
  els.overlay.addEventListener("click", closePanel);

  /* -------------------------------- background mode ---------------------- */
  els.bgModes.addEventListener("click", (e) => {
    const btn = e.target.closest(".cz-mode");
    if (!btn) return;
    const mode = btn.dataset.bgMode;
    const s = window.Theme.get();
    const patch = { bgMode: mode };
    if (mode === "image" && s.glassBlur === 0) {
      patch.glassBlur = 16;
      patch.glassOpacity = 72;
    }
    window.Theme.set(patch);
    syncUI();
  });

  els.bg.addEventListener("input", () => {
    window.Theme.set({ bg: els.bg.value });
    els.bgHex.value = hexOf(els.bg.value);
  });

  /* -------------------------------- wallpaper upload ---------------------- */
  function downscaleImage(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onerror = () => reject(new Error("read failed"));
      reader.onload = () => {
        const img = new Image();
        img.onerror = () => reject(new Error("decode failed"));
        img.onload = () => {
          let { width, height } = img;
          if (width > MAX_DIM || height > MAX_DIM) {
            const scale = MAX_DIM / Math.max(width, height);
            width = Math.round(width * scale);
            height = Math.round(height * scale);
          }
          const canvas = document.createElement("canvas");
          canvas.width = width; canvas.height = height;
          canvas.getContext("2d").drawImage(img, 0, 0, width, height);
          resolve(canvas.toDataURL("image/jpeg", 0.82));
        };
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  els.wallpaperFile.addEventListener("change", async () => {
    const file = els.wallpaperFile.files && els.wallpaperFile.files[0];
    els.wallpaperFile.value = "";
    if (!file) return;
    hideError();
    try {
      const dataUrl = await downscaleImage(file);
      const s = window.Theme.get();
      const patch = { wallpaper: dataUrl, bgMode: "image" };
      if (s.glassBlur === 0) { patch.glassBlur = 16; patch.glassOpacity = 72; }
      const { saved } = window.Theme.set(patch);
      if (!saved) showError("Image applied, but it's too large to save — it will reset on reload.");
      syncUI();
    } catch (err) {
      showError("Couldn't load that image — try a different file.");
    }
  });

  els.wallpaperClear.addEventListener("click", () => {
    hideError();
    window.Theme.set({ wallpaper: null, bgMode: "color" });
    syncUI();
  });

  /* -------------------------------- sliders / colors ---------------------- */
  els.wallpaperBlur.addEventListener("input", () => {
    els.wallpaperBlurVal.textContent = els.wallpaperBlur.value + "px";
    window.Theme.set({ wallpaperBlur: Number(els.wallpaperBlur.value) });
  });
  els.wallpaperDim.addEventListener("input", () => {
    els.wallpaperDimVal.textContent = els.wallpaperDim.value + "%";
    window.Theme.set({ wallpaperDim: Number(els.wallpaperDim.value) });
  });
  els.glassBlur.addEventListener("input", () => {
    els.glassBlurVal.textContent = els.glassBlur.value + "px";
    window.Theme.set({ glassBlur: Number(els.glassBlur.value) });
  });
  els.glassOpacity.addEventListener("input", () => {
    els.glassOpacityVal.textContent = els.glassOpacity.value + "%";
    window.Theme.set({ glassOpacity: Number(els.glassOpacity.value) });
  });
  els.glow.addEventListener("input", () => {
    els.glowVal.textContent = els.glow.value + "%";
    window.Theme.set({ glow: Number(els.glow.value) });
  });
  els.accent.addEventListener("input", () => {
    window.Theme.set({ accent: els.accent.value });
    els.accentHex.value = hexOf(els.accent.value);
  });
  els.profit.addEventListener("input", () => {
    window.Theme.set({ profit: els.profit.value });
    els.profitHex.value = hexOf(els.profit.value);
  });
  els.loss.addEventListener("input", () => {
    window.Theme.set({ loss: els.loss.value });
    els.lossHex.value = hexOf(els.loss.value);
  });
  els.mcBand.addEventListener("input", () => {
    window.Theme.set({ mcBand: els.mcBand.value });
    els.mcBandHex.value = hexOf(els.mcBand.value);
  });

  els.reset.addEventListener("click", () => {
    hideError();
    window.Theme.reset();
    syncUI();
  });

  syncUI();
})();
