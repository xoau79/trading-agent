/* charts.js — canvas chart engine (no dependencies). window.Charts.
   One visual language: hairline grid, thin marks, crosshair + tooltip on
   every plot, right-hand price axis, Sydney-time x-axis.
   Charts: CandleChart (zoom/pan/markers), LineChart, BarChart, BandChart. */
(function () {
  "use strict";
  const U = window.U;

  /* ------------------------------ tokens -------------------------------- */
  let TOK = null;
  function refreshTokens() { TOK = null; }
  function tokens() {
    if (TOK) return TOK;
    const cs = getComputedStyle(document.documentElement);
    const v = (n, fb) => (cs.getPropertyValue(n) || fb).trim();
    TOK = {
      grid: "rgba(151,168,199,0.07)",
      axis: "rgba(151,168,199,0.16)",
      ink: v("--ink", "#EAF0F9"),
      ink2: v("--ink-2", "#9DA9BC"),
      ink3: v("--ink-3", "#5E6B80"),
      accent: v("--accent", "#5585E3"),
      gold: v("--gold", "#BC8A32"),
      violet: v("--violet", "#8377E0"),
      up: v("--up", "#27A874"),
      down: v("--down", "#DE4E56"),
      upInk: v("--up-ink", "#3DD68C"),
      downInk: v("--down-ink", "#F2646C"),
      surface: v("--surface", "#0E1219"),
      surface2: v("--surface-2", "#131A26"),
      mono: "500 10px " + (v("--font-mono", "monospace") || "monospace"),
      mono11: "500 11px " + (v("--font-mono", "monospace") || "monospace"),
    };
    return TOK;
  }

  function withAlpha(hex, a) {
    const h = hex.replace("#", "");
    const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
    return `rgba(${r},${g},${b},${a})`;
  }

  /* ------------------------------ tooltip -------------------------------- */
  const Tip = {
    el: null,
    ensure() { if (!this.el) this.el = document.getElementById("chartTip"); return this.el; },
    show(px, py, build) {
      const el = this.ensure();
      if (!el) return;
      el.innerHTML = "";
      build(el);
      el.hidden = false;
      const r = el.getBoundingClientRect();
      let x = px + 16, y = py + 14;
      if (x + r.width > innerWidth - 12) x = px - r.width - 16;
      if (y + r.height > innerHeight - 12) y = py - r.height - 14;
      el.style.left = Math.max(8, x) + "px";
      el.style.top = Math.max(8, y) + "px";
    },
    hide() { const el = this.ensure(); if (el) el.hidden = true; },
  };
  // tooltip rows: values lead, labels follow; keys are short color strokes
  function tipTitle(el, text) {
    const d = document.createElement("div");
    d.className = "tip-title"; d.textContent = text; el.appendChild(d);
  }
  function tipRow(el, label, value, valCls, keyColor) {
    const row = document.createElement("div");
    row.className = "tip-row";
    const l = document.createElement("span");
    if (keyColor) {
      const k = document.createElement("span");
      k.className = "key"; k.style.background = keyColor; l.appendChild(k);
    }
    l.appendChild(document.createTextNode(label));
    const v = document.createElement("b");
    if (valCls) v.className = valCls;
    v.textContent = value;
    row.appendChild(l); row.appendChild(v);
    el.appendChild(row);
  }

  /* --------------------------- canvas plumbing --------------------------- */
  class Surface {
    constructor(shell, onSize) {
      this.shell = shell;
      this.onSize = onSize;
      this.canvas = document.createElement("canvas");
      shell.appendChild(this.canvas);
      this.ctx = this.canvas.getContext("2d");
      this.w = 0; this.h = 0;
      // measure now, but only fire the redraw callback from the (async)
      // ResizeObserver — the owning chart hasn't finished constructing yet
      this.ro = new ResizeObserver(() => this.resize(true));
      this.ro.observe(shell);
      this.resize(false);
    }
    resize(fire) {
      const r = this.shell.getBoundingClientRect();
      if (r.width < 4 || r.height < 4) return;
      const dpr = window.devicePixelRatio || 1;
      this.w = r.width; this.h = r.height;
      this.canvas.width = Math.round(r.width * dpr);
      this.canvas.height = Math.round(r.height * dpr);
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (fire && this.onSize) this.onSize();
    }
    clear() { this.ctx.clearRect(0, 0, this.w, this.h); }
    destroy() { this.ro.disconnect(); this.canvas.remove(); }
  }

  function niceStep(span, target) {
    const raw = span / Math.max(1, target);
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    for (const m of [1, 2, 2.5, 5, 10]) if (raw <= m * mag) return m * mag;
    return 10 * mag;
  }
  function niceTicks(lo, hi, target = 5) {
    if (!(hi > lo)) { hi = lo + 1; }
    const step = niceStep(hi - lo, target);
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step)
      out.push(Math.round(v / step) * step);
    return out;
  }

  function drawYGrid(ctx, T, plot, yScale, ticks, fmt) {
    ctx.strokeStyle = T.grid; ctx.lineWidth = 1;
    ctx.fillStyle = T.ink3; ctx.font = T.mono; ctx.textAlign = "left"; ctx.textBaseline = "middle";
    ticks.forEach((v) => {
      const y = Math.round(yScale(v)) + 0.5;
      if (y < plot.top - 1 || y > plot.bottom + 1) return;
      ctx.beginPath(); ctx.moveTo(plot.left, y); ctx.lineTo(plot.right, y); ctx.stroke();
      ctx.fillText(fmt(v), plot.right + 8, y);
    });
  }

  function axisTag(ctx, T, x, y, text, opts = {}) {
    ctx.font = T.mono;
    const w = ctx.measureText(text).width + 12, h = 17;
    let bx = x, by = y - h / 2;
    if (opts.alignRight) bx = x - w;
    ctx.fillStyle = opts.bg || T.surface2;
    ctx.beginPath(); ctx.roundRect(bx, by, w, h, 4); ctx.fill();
    if (opts.stroke) { ctx.strokeStyle = opts.stroke; ctx.lineWidth = 1; ctx.stroke(); }
    ctx.fillStyle = opts.ink || T.ink2;
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillText(text, bx + w / 2, y + 0.5);
  }

  function emptyState(ctx, T, w, h, msg, sub) {
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    ctx.fillStyle = T.ink2; ctx.font = "600 13px Inter, system-ui, sans-serif";
    ctx.fillText(msg, w / 2, h / 2 - 10);
    if (sub) {
      ctx.fillStyle = T.ink3; ctx.font = "400 11.5px Inter, system-ui, sans-serif";
      ctx.fillText(sub, w / 2, h / 2 + 12);
    }
  }

  /* ============================ CandleChart ============================== */
  const AXIS_W = 64, AXIS_H = 24;

  class CandleChart {
    constructor(shell, opts = {}) {
      this.shell = shell;
      this.tz = opts.tz;
      this.onHover = opts.onHover || null;   // (candle|null) -> header OHLC readout
      this.candles = [];
      this.trades = [];
      this.position = null;
      this.view = null;                       // {i0, i1} float
      this.follow = true;
      this.cursor = null;                     // {x, y} css px
      this.hoverTrade = null;
      this.surf = new Surface(shell, () => this.draw());
      shell.classList.add("can-grab");
      this._bind();
    }

    setData(candles, trades, position) {
      const prevN = this.candles.length;
      this.candles = candles || [];
      this.trades = trades || [];
      this.position = position || null;
      const n = this.candles.length;
      if (!this.view || prevN === 0) this.resetView();
      else if (this.follow && n > prevN) {
        const shift = n - prevN;
        this.view.i0 += shift; this.view.i1 += shift;
        this.clampView();
      }
      this.draw();
    }

    resetView() {
      const n = this.candles.length;
      const span = Math.min(n, 120);
      this.view = { i0: n - span, i1: n + Math.max(4, span * 0.06) };
      this.follow = true;
    }

    clampView() {
      const n = this.candles.length;
      const span = this.view.i1 - this.view.i0;
      const minSpan = 15, maxSpan = n * 1.2 + 40;
      if (span < minSpan) this.view.i1 = this.view.i0 + minSpan;
      if (span > maxSpan) this.view.i0 = this.view.i1 - maxSpan;
      if (this.view.i1 > n + span * 0.6) { const d = this.view.i1 - (n + span * 0.6); this.view.i0 -= d; this.view.i1 -= d; }
      if (this.view.i0 < -span * 0.6) { const d = -span * 0.6 - this.view.i0; this.view.i0 += d; this.view.i1 += d; }
      this.follow = this.view.i1 >= n - 0.5;
    }

    _bind() {
      const el = this.shell;
      let drag = null;
      el.addEventListener("wheel", (e) => {
        if (!this.candles.length) return;
        e.preventDefault();
        const rect = el.getBoundingClientRect();
        const px = e.clientX - rect.left;
        const plot = this.plot();
        const frac = Math.min(1, Math.max(0, (px - plot.left) / (plot.right - plot.left)));
        const { i0, i1 } = this.view;
        const anchor = i0 + frac * (i1 - i0);
        const k = Math.exp(e.deltaY * 0.0016);
        this.view.i0 = anchor - (anchor - i0) * k;
        this.view.i1 = anchor + (i1 - anchor) * k;
        this.clampView(); this.draw();
      }, { passive: false });

      el.addEventListener("pointerdown", (e) => {
        if (!this.candles.length) return;
        drag = { x: e.clientX, v0: this.view.i0, v1: this.view.i1 };
        el.setPointerCapture(e.pointerId);
        el.classList.add("is-grabbing");
      });
      el.addEventListener("pointermove", (e) => {
        const rect = el.getBoundingClientRect();
        this.cursor = { x: e.clientX - rect.left, y: e.clientY - rect.top, cx: e.clientX, cy: e.clientY };
        if (drag) {
          const plot = this.plot();
          const perPx = (drag.v1 - drag.v0) / (plot.right - plot.left);
          const di = (drag.x - e.clientX) * perPx;
          this.view.i0 = drag.v0 + di; this.view.i1 = drag.v1 + di;
          this.clampView();
        }
        this.draw();
      });
      const end = () => { drag = null; el.classList.remove("is-grabbing"); };
      el.addEventListener("pointerup", end);
      el.addEventListener("pointercancel", end);
      el.addEventListener("pointerleave", () => {
        this.cursor = null; this.hoverTrade = null;
        Tip.hide(); if (this.onHover) this.onHover(null);
        this.draw();
      });
      el.addEventListener("dblclick", () => { this.resetView(); this.draw(); });
    }

    plot() {
      return { left: 8, top: 10, right: this.surf.w - AXIS_W, bottom: this.surf.h - AXIS_H };
    }

    draw() {
      const { ctx } = this.surf, T = tokens();
      const W = this.surf.w, H = this.surf.h;
      if (!W) return;
      this.surf.clear();
      const n = this.candles.length;
      if (!n) {
        emptyState(ctx, T, W, H, "Awaiting market data",
          "Candles stream in once the agent's session is live");
        return;
      }
      const plot = this.plot();
      const { i0, i1 } = this.view;
      const span = i1 - i0;
      const xOf = (i) => plot.left + ((i + 0.5 - i0) / span) * (plot.right - plot.left);
      const iOf = (x) => i0 + ((x - plot.left) / (plot.right - plot.left)) * span - 0.5;

      const lo0 = Math.max(0, Math.floor(i0)), hi0 = Math.min(n - 1, Math.ceil(i1));
      let lo = Infinity, hi = -Infinity;
      for (let i = lo0; i <= hi0; i++) {
        const c = this.candles[i];
        if (c.l < lo) lo = c.l;
        if (c.h > hi) hi = c.h;
      }
      // include visible trade/position levels so markers never clip
      const inView = (t) => t._i1 >= i0 - 1 && t._i0 <= i1 + 1;
      this.indexTrades();
      this.trades.forEach((t) => {
        if (!inView(t)) return;
        lo = Math.min(lo, t.entry_price, t.exit_price);
        hi = Math.max(hi, t.entry_price, t.exit_price);
      });
      if (this.position) {
        lo = Math.min(lo, this.position.stop);
        hi = Math.max(hi, this.position.target);
      }
      if (!Number.isFinite(lo)) { lo = 0; hi = 1; }
      const pad = (hi - lo) * 0.08 || 1;
      lo -= pad; hi += pad;
      const yOf = (v) => plot.top + (hi - v) / (hi - lo) * (plot.bottom - plot.top);

      /* grid + axes */
      drawYGrid(ctx, T, plot, yOf, niceTicks(lo, hi, 6), (v) => U.fmtPrice(v));
      // time ticks every ~110px
      const per = (plot.right - plot.left) / span;
      const tickEvery = Math.max(1, Math.round(110 / per));
      ctx.font = T.mono; ctx.fillStyle = T.ink3; ctx.textAlign = "center"; ctx.textBaseline = "top";
      ctx.strokeStyle = T.grid;
      for (let i = Math.ceil(i0 / tickEvery) * tickEvery; i <= Math.min(n - 1, i1); i += tickEvery) {
        if (i < 0) continue;
        const x = Math.round(xOf(i)) + 0.5;
        ctx.beginPath(); ctx.moveTo(x, plot.top); ctx.lineTo(x, plot.bottom); ctx.stroke();
        ctx.fillText(U.hhmm(new Date(this.candles[i].t * 1000), this.tz), x, plot.bottom + 8);
      }
      // frame baseline
      ctx.strokeStyle = T.axis;
      ctx.beginPath(); ctx.moveTo(plot.left, plot.bottom + 0.5); ctx.lineTo(plot.right, plot.bottom + 0.5); ctx.stroke();

      /* position levels (behind candles) */
      if (this.position) this.drawLevel(ctx, T, plot, yOf, this.position);

      /* candles */
      const bw = Math.max(1, Math.min(21, per * 0.72));
      ctx.save();
      ctx.beginPath(); ctx.rect(plot.left, plot.top - 6, plot.right - plot.left, plot.bottom - plot.top + 6); ctx.clip();
      for (let i = lo0; i <= hi0; i++) {
        const c = this.candles[i];
        const x = xOf(i);
        const up = c.c >= c.o;
        const col = up ? T.up : T.down;
        ctx.strokeStyle = col; ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(Math.round(x) + 0.5, yOf(c.h));
        ctx.lineTo(Math.round(x) + 0.5, yOf(c.l));
        ctx.stroke();
        const yO = yOf(c.o), yC = yOf(c.c);
        const top = Math.min(yO, yC), hgt = Math.max(1, Math.abs(yC - yO));
        ctx.fillStyle = col;
        if (bw <= 2) {
          ctx.fillRect(Math.round(x) - 0.5, top, 1.5, hgt);
        } else {
          ctx.beginPath();
          ctx.roundRect(x - bw / 2, top, bw, hgt, Math.min(2, bw / 3));
          ctx.fill();
        }
      }

      /* trade markers */
      this.hoverTrade = null;
      const hits = [];
      this.trades.forEach((t) => {
        if (!inView(t)) return;
        const x1 = xOf(t._i0), y1 = yOf(t.entry_price);
        const x2 = xOf(t._i1), y2 = yOf(t.exit_price);
        const col = t.pnl >= 0 ? T.up : T.down;
        ctx.strokeStyle = withAlpha(col, 0.6); ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
        this.marker(ctx, T, x1, y1, t.direction === "LONG" ? "up" : "down", col);
        this.marker(ctx, T, x2, y2, "exit", col);
        hits.push({ t, x1, y1, x2, y2 });
      });
      // open position entry marker
      if (this.position && this.position._i0 !== undefined && this.position._i0 >= i0 - 1) {
        const col = this.position.direction === "LONG" ? T.up : T.down;
        this.marker(ctx, T, xOf(this.position._i0), yOf(this.position.entry_price),
          this.position.direction === "LONG" ? "up" : "down", col);
      }
      ctx.restore();

      /* last price line + tag */
      const last = this.candles[n - 1];
      if (last.c >= lo && last.c <= hi) {
        const y = Math.round(yOf(last.c)) + 0.5;
        ctx.strokeStyle = withAlpha(T.accent, 0.5); ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(plot.left, y); ctx.lineTo(plot.right, y); ctx.stroke();
        axisTag(ctx, T, plot.right + 3, y, U.fmtPrice(last.c),
          { bg: T.accent, ink: "#fff" });
      }

      /* crosshair */
      const cur = this.cursor;
      if (cur && cur.x >= plot.left && cur.x <= plot.right && cur.y >= plot.top && cur.y <= plot.bottom) {
        const ci = Math.round(Math.min(n - 1, Math.max(0, iOf(cur.x))));
        const cx = Math.round(xOf(ci)) + 0.5;
        ctx.strokeStyle = withAlpha(T.ink2, 0.35); ctx.lineWidth = 1;
        ctx.setLineDash([1, 3]);
        ctx.beginPath(); ctx.moveTo(cx, plot.top); ctx.lineTo(cx, plot.bottom); ctx.stroke();
        const cy = Math.round(cur.y) + 0.5;
        ctx.beginPath(); ctx.moveTo(plot.left, cy); ctx.lineTo(plot.right, cy); ctx.stroke();
        ctx.setLineDash([]);
        const price = hi - (cur.y - plot.top) / (plot.bottom - plot.top) * (hi - lo);
        axisTag(ctx, T, plot.right + 3, cy, U.fmtPrice(price), { bg: T.surface2, ink: T.ink, stroke: T.axis });
        const cnd = this.candles[ci];
        if (cnd) {
          axisTag(ctx, T, Math.min(Math.max(cx, plot.left + 30), plot.right - 30), plot.bottom + 11,
            U.hhmm(new Date(cnd.t * 1000), this.tz), { bg: T.surface2, ink: T.ink, stroke: T.axis, alignRight: false });
          if (this.onHover) this.onHover(cnd);
        }

        /* trade hover: nearest marker within 16px, else near connector */
        let best = null, bestD = 16;
        hits.forEach((h) => {
          [[h.x1, h.y1], [h.x2, h.y2]].forEach(([hx, hy]) => {
            const d = Math.hypot(hx - cur.x, hy - cur.y);
            if (d < bestD) { bestD = d; best = h; }
          });
        });
        if (!best) {
          hits.forEach((h) => {
            const d = distToSeg(cur.x, cur.y, h.x1, h.y1, h.x2, h.y2);
            if (d < 7 && (best === null || d < bestD)) { bestD = d; best = h; }
          });
        }
        if (best) {
          this.hoverTrade = best.t;
          // re-ring the hovered markers so the chart responds
          const col = best.t.pnl >= 0 ? T.up : T.down;
          [[best.x1, best.y1], [best.x2, best.y2]].forEach(([hx, hy]) => {
            ctx.strokeStyle = withAlpha(col, 0.85); ctx.lineWidth = 1.5;
            ctx.beginPath(); ctx.arc(hx, hy, 9, 0, Math.PI * 2); ctx.stroke();
          });
          const t = best.t;
          Tip.show(cur.cx, cur.cy, (el) => {
            tipTitle(el, `Trade #${t.trade_id} · ${t.asset} ${t.direction}`);
            tipRow(el, "Entry", U.fmtPrice(t.entry_price) + "  " + shortTime(t.entry_time, this.tz));
            tipRow(el, "Exit", U.fmtPrice(t.exit_price) + "  " + shortTime(t.exit_time, this.tz));
            tipRow(el, "P&L", U.money(t.pnl, true) + " (" + (t.r_multiple > 0 ? "+" : "") + t.r_multiple + "R)", U.cls(t.pnl));
            tipRow(el, "Size", t.units + " units");
            tipRow(el, "Duration", U.fmtDurMin(t.duration_min));
            tipRow(el, "Exit via", String(t.exit_reason || "—"));
          });
        } else if (this.position && nearLevel(cur, this.position, yOf, plot)) {
          const p = this.position;
          Tip.show(cur.cx, cur.cy, (el) => {
            tipTitle(el, `Open · ${p.asset} ${p.direction}`);
            tipRow(el, "Entry", U.fmtPrice(p.entry_price));
            tipRow(el, "Stop", U.fmtPrice(p.stop), "neg");
            tipRow(el, "Target", U.fmtPrice(p.target), "pos");
            tipRow(el, "Size", p.units + " units");
            tipRow(el, "Risk", U.money(p.risk_usd));
          });
        } else {
          Tip.hide();
        }
      } else if (this.onHover) {
        this.onHover(null);
        Tip.hide();
      }
    }

    indexTrades() {
      // map trade entry/exit times to candle indexes once per draw window
      const ts = this.candles.map((c) => c.t);
      const at = (iso) => {
        const d = U.parseTS(iso); if (!d) return 0;
        const t = d.getTime() / 1000;
        let lo = 0, hi = ts.length - 1;
        while (lo < hi) { const m = (lo + hi) >> 1; if (ts[m] < t) lo = m + 1; else hi = m; }
        return lo;
      };
      this.trades.forEach((t) => {
        if (t._i0 === undefined || t._n !== ts.length) {
          t._i0 = at(t.entry_time); t._i1 = at(t.exit_time); t._n = ts.length;
        }
      });
      if (this.position && (this.position._i0 === undefined || this.position._n !== ts.length)) {
        this.position._i0 = at(this.position.entry_time); this.position._n = ts.length;
      }
    }

    marker(ctx, T, x, y, kind, col) {
      ctx.save();
      ctx.fillStyle = col;
      ctx.strokeStyle = T.surface; ctx.lineWidth = 2;   // 2px surface ring
      if (kind === "up") {
        ctx.beginPath();
        ctx.moveTo(x, y - 5.5); ctx.lineTo(x + 5.5, y + 4.5); ctx.lineTo(x - 5.5, y + 4.5);
        ctx.closePath(); ctx.stroke(); ctx.fill();
      } else if (kind === "down") {
        ctx.beginPath();
        ctx.moveTo(x, y + 5.5); ctx.lineTo(x + 5.5, y - 4.5); ctx.lineTo(x - 5.5, y - 4.5);
        ctx.closePath(); ctx.stroke(); ctx.fill();
      } else {
        ctx.beginPath(); ctx.arc(x, y, 4.5, 0, Math.PI * 2); ctx.stroke(); ctx.fill();
        ctx.fillStyle = T.surface;
        ctx.beginPath(); ctx.arc(x, y, 1.6, 0, Math.PI * 2); ctx.fill();
      }
      ctx.restore();
    }

    drawLevel(ctx, T, plot, yOf, p) {
      const lines = [
        [p.target, T.up, "TP"], [p.entry_price, T.ink3, "IN"], [p.stop, T.down, "SL"],
      ];
      lines.forEach(([v, col, lbl]) => {
        const y = Math.round(yOf(v)) + 0.5;
        if (y < plot.top || y > plot.bottom) return;
        ctx.strokeStyle = withAlpha(col === T.ink3 ? "#9DA9BC" : col, 0.45);
        ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(plot.left, y); ctx.lineTo(plot.right, y); ctx.stroke();
        ctx.font = tokens().mono; ctx.fillStyle = withAlpha(col === T.ink3 ? "#9DA9BC" : col, 0.9);
        ctx.textAlign = "left"; ctx.textBaseline = "bottom";
        ctx.fillText(lbl + " " + U.fmtPrice(v), plot.left + 6, y - 3);
      });
    }
  }

  function shortTime(iso, tz) {
    const d = U.parseTS(iso);
    return d ? U.hhmm(d, tz) : "—";
  }
  function distToSeg(px, py, x1, y1, x2, y2) {
    const dx = x2 - x1, dy = y2 - y1;
    const l2 = dx * dx + dy * dy;
    let t = l2 ? ((px - x1) * dx + (py - y1) * dy) / l2 : 0;
    t = Math.max(0, Math.min(1, t));
    return Math.hypot(px - (x1 + t * dx), py - (y1 + t * dy));
  }
  function nearLevel(cur, p, yOf, plot) {
    return [p.entry_price, p.stop, p.target].some((v) => {
      const y = yOf(v);
      return y >= plot.top && y <= plot.bottom && Math.abs(cur.y - y) < 7;
    });
  }

  /* ============================= LineChart =============================== */
  /* cfg: { points: [{x:Date|num, y}], color, area, baseline, yFmt, xFmt,
            tipTitle(pt), tipRows(pt,i)->[[label,value,cls,key]], belowZeroFill } */
  class LineChart {
    constructor(shell, cfg) {
      this.shell = shell;
      this.cfg = cfg;
      this.cursor = null;
      this.surf = new Surface(shell, () => this.draw());
      shell.classList.add("can-grab");
      shell.addEventListener("pointermove", (e) => {
        const r = shell.getBoundingClientRect();
        this.cursor = { x: e.clientX - r.left, y: e.clientY - r.top, cx: e.clientX, cy: e.clientY };
        this.draw();
      });
      shell.addEventListener("pointerleave", () => { this.cursor = null; Tip.hide(); this.draw(); });
    }
    update(cfg) { Object.assign(this.cfg, cfg); this.draw(); }

    draw() {
      const { ctx } = this.surf, T = tokens();
      const W = this.surf.w, H = this.surf.h;
      if (!W) return;
      this.surf.clear();
      const c = this.cfg;
      const pts = c.points || [];
      if (pts.length < 2) {
        emptyState(ctx, T, W, H, c.emptyMsg || "Not enough data yet",
          c.emptySub || "This chart draws as soon as there is history to show");
        return;
      }
      const plot = { left: 8, top: 12, right: W - AXIS_W, bottom: H - AXIS_H };
      const xs = pts.map((p) => +p.x);
      const x0 = Math.min(...xs), x1 = Math.max(...xs);
      let lo = Math.min(...pts.map((p) => p.y)), hi = Math.max(...pts.map((p) => p.y));
      if (c.baseline !== undefined && c.baseline !== null) {
        lo = Math.min(lo, c.baseline); hi = Math.max(hi, c.baseline);
      }
      if (c.includeZero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
      const pad = (hi - lo) * 0.1 || 1;
      lo -= pad; hi += pad;
      const xOf = (x) => plot.left + (x - x0) / Math.max(1, x1 - x0) * (plot.right - plot.left);
      const yOf = (v) => plot.top + (hi - v) / (hi - lo) * (plot.bottom - plot.top);

      drawYGrid(ctx, T, plot, yOf, niceTicks(lo, hi, 5), c.yFmt || ((v) => U.moneyCompact(v)));
      // x labels: ~5 ticks
      ctx.font = T.mono; ctx.fillStyle = T.ink3; ctx.textAlign = "center"; ctx.textBaseline = "top";
      const nT = Math.max(2, Math.min(6, Math.floor((plot.right - plot.left) / 130)));
      for (let k = 0; k <= nT; k++) {
        const x = x0 + (k / nT) * (x1 - x0);
        ctx.fillText((c.xFmt || ((v) => U.shortDate(new Date(v))))(x), xOf(x), plot.bottom + 8);
      }
      ctx.strokeStyle = T.axis;
      ctx.beginPath(); ctx.moveTo(plot.left, plot.bottom + 0.5); ctx.lineTo(plot.right, plot.bottom + 0.5); ctx.stroke();

      if (c.baseline !== undefined && c.baseline !== null) {
        const y = Math.round(yOf(c.baseline)) + 0.5;
        ctx.strokeStyle = T.axis; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(plot.left, y); ctx.lineTo(plot.right, y); ctx.stroke();
      }

      const color = c.color || T.accent;
      /* area wash */
      if (c.area) {
        const zeroY = yOf(c.areaBase !== undefined ? c.areaBase : lo);
        ctx.beginPath();
        pts.forEach((p, i) => { const X = xOf(+p.x), Y = yOf(p.y); i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); });
        ctx.lineTo(xOf(+pts[pts.length - 1].x), zeroY);
        ctx.lineTo(xOf(+pts[0].x), zeroY);
        ctx.closePath();
        ctx.fillStyle = withAlpha(color, 0.1);
        ctx.fill();
      }
      /* line */
      ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.lineJoin = "round"; ctx.lineCap = "round";
      ctx.beginPath();
      pts.forEach((p, i) => { const X = xOf(+p.x), Y = yOf(p.y); i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); });
      ctx.stroke();
      /* end dot with surface ring */
      const lastP = pts[pts.length - 1];
      ctx.fillStyle = color; ctx.strokeStyle = T.surface; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(xOf(+lastP.x), yOf(lastP.y), 4, 0, Math.PI * 2); ctx.stroke(); ctx.fill();

      /* crosshair + tooltip */
      const cur = this.cursor;
      if (cur && cur.x >= plot.left && cur.x <= plot.right && cur.y >= plot.top - 4 && cur.y <= plot.bottom + 4) {
        let best = 0, bd = Infinity;
        pts.forEach((p, i) => { const d = Math.abs(xOf(+p.x) - cur.x); if (d < bd) { bd = d; best = i; } });
        const p = pts[best];
        const X = Math.round(xOf(+p.x)) + 0.5;
        ctx.strokeStyle = withAlpha(T.ink2, 0.35); ctx.setLineDash([1, 3]);
        ctx.beginPath(); ctx.moveTo(X, plot.top); ctx.lineTo(X, plot.bottom); ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = color; ctx.strokeStyle = T.surface; ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(xOf(+p.x), yOf(p.y), 4.5, 0, Math.PI * 2); ctx.stroke(); ctx.fill();
        Tip.show(cur.cx, cur.cy, (el) => {
          if (c.tipTitle) tipTitle(el, c.tipTitle(p, best));
          (c.tipRows ? c.tipRows(p, best) : []).forEach((r) => tipRow(el, r[0], r[1], r[2], r[3]));
        });
      } else {
        Tip.hide();
      }
    }
  }

  /* ============================== BarChart =============================== */
  /* cfg: { bars: [{label, value, tip?}], color | diverging, yFmt, tipTitle,
            tipRows(bar,i), maxBarW } */
  class BarChart {
    constructor(shell, cfg) {
      this.shell = shell; this.cfg = cfg;
      this.cursor = null; this.hover = -1;
      this.surf = new Surface(shell, () => this.draw());
      shell.addEventListener("pointermove", (e) => {
        const r = shell.getBoundingClientRect();
        this.cursor = { x: e.clientX - r.left, y: e.clientY - r.top, cx: e.clientX, cy: e.clientY };
        this.draw();
      });
      shell.addEventListener("pointerleave", () => { this.cursor = null; this.hover = -1; Tip.hide(); this.draw(); });
    }
    update(cfg) { Object.assign(this.cfg, cfg); this.draw(); }

    draw() {
      const { ctx } = this.surf, T = tokens();
      const W = this.surf.w, H = this.surf.h;
      if (!W) return;
      this.surf.clear();
      const c = this.cfg, bars = c.bars || [];
      if (!bars.length) {
        emptyState(ctx, T, W, H, c.emptyMsg || "No data yet", c.emptySub || "");
        return;
      }
      const plot = { left: 8, top: 12, right: W - AXIS_W, bottom: H - AXIS_H };
      let lo = Math.min(0, ...bars.map((b) => b.value));
      let hi = Math.max(0, ...bars.map((b) => b.value));
      if (lo === hi) hi = lo + 1;
      const pad = (hi - lo) * 0.12;
      hi += pad; if (lo < 0) lo -= pad;
      const yOf = (v) => plot.top + (hi - v) / (hi - lo) * (plot.bottom - plot.top);
      drawYGrid(ctx, T, plot, yOf, niceTicks(lo, hi, 4), c.yFmt || ((v) => String(v)));

      const slot = (plot.right - plot.left) / bars.length;
      const bw = Math.min(c.maxBarW || 24, Math.max(2, slot - Math.max(2, slot * 0.25)));
      const zero = yOf(0);
      /* baseline */
      ctx.strokeStyle = T.axis;
      ctx.beginPath(); ctx.moveTo(plot.left, Math.round(zero) + 0.5); ctx.lineTo(plot.right, Math.round(zero) + 0.5); ctx.stroke();

      /* hit test first so hovered bar can lift */
      let hover = -1;
      if (this.cursor && this.cursor.x >= plot.left && this.cursor.x <= plot.right
          && this.cursor.y >= plot.top && this.cursor.y <= plot.bottom + AXIS_H) {
        hover = Math.min(bars.length - 1, Math.max(0, Math.floor((this.cursor.x - plot.left) / slot)));
      }
      this.hover = hover;

      bars.forEach((b, i) => {
        const x = plot.left + slot * i + (slot - bw) / 2;
        const v = b.value;
        const col = c.diverging ? (v >= 0 ? T.up : T.down) : (c.color || T.accent);
        const y0 = Math.min(zero, yOf(v)), h = Math.max(1.5, Math.abs(zero - yOf(v)));
        ctx.fillStyle = i === hover ? withAlpha(col, 1) : withAlpha(col, 0.82);
        ctx.beginPath();
        const r = Math.min(4, bw / 2);
        // rounded at the data end, square at the baseline
        if (v >= 0) ctx.roundRect(x, y0, bw, h, [r, r, 0, 0]);
        else ctx.roundRect(x, y0, bw, h, [0, 0, r, r]);
        ctx.fill();
        if (i === hover) {
          ctx.strokeStyle = withAlpha(col, 0.5); ctx.lineWidth = 1;
          ctx.stroke();
        }
      });

      /* x labels: first / last / a few between */
      ctx.font = T.mono; ctx.fillStyle = T.ink3; ctx.textAlign = "center"; ctx.textBaseline = "top";
      const every = Math.max(1, Math.ceil(bars.length / Math.floor((plot.right - plot.left) / 84)));
      bars.forEach((b, i) => {
        if (i % every !== 0 && i !== bars.length - 1) return;
        ctx.fillText(String(b.label), plot.left + slot * i + slot / 2, plot.bottom + 8);
      });

      if (hover >= 0) {
        const b = bars[hover];
        Tip.show(this.cursor.cx, this.cursor.cy, (el) => {
          if (c.tipTitle) tipTitle(el, c.tipTitle(b, hover));
          (c.tipRows ? c.tipRows(b, hover) : [["Value", String(b.value)]])
            .forEach((r) => tipRow(el, r[0], r[1], r[2], r[3]));
        });
      } else {
        Tip.hide();
      }
    }
  }

  /* ============================== BandChart ============================== */
  /* Monte-Carlo luck envelope: bands {p5,p25,p50,p75,p95}, baseline */
  class BandChart {
    constructor(shell, cfg) {
      this.shell = shell; this.cfg = cfg;
      this.cursor = null;
      this.surf = new Surface(shell, () => this.draw());
      shell.addEventListener("pointermove", (e) => {
        const r = shell.getBoundingClientRect();
        this.cursor = { x: e.clientX - r.left, y: e.clientY - r.top, cx: e.clientX, cy: e.clientY };
        this.draw();
      });
      shell.addEventListener("pointerleave", () => { this.cursor = null; Tip.hide(); this.draw(); });
    }
    update(cfg) { Object.assign(this.cfg, cfg); this.draw(); }
    draw() {
      const { ctx } = this.surf, T = tokens();
      const W = this.surf.w, H = this.surf.h;
      if (!W) return;
      this.surf.clear();
      const b = this.cfg.bands;
      if (!b || !b.p50 || b.p50.length < 2) { emptyState(ctx, T, W, H, "No simulation yet", ""); return; }
      const n = b.p50.length;
      const plot = { left: 8, top: 12, right: W - AXIS_W, bottom: H - AXIS_H };
      const all = [...b.p5, ...b.p95, this.cfg.baseline ?? b.p50[0]];
      let lo = Math.min(...all), hi = Math.max(...all);
      const pad = (hi - lo) * 0.08 || 1; lo -= pad; hi += pad;
      const xOf = (i) => plot.left + (i / (n - 1)) * (plot.right - plot.left);
      const yOf = (v) => plot.top + (hi - v) / (hi - lo) * (plot.bottom - plot.top);
      drawYGrid(ctx, T, plot, yOf, niceTicks(lo, hi, 5), (v) => U.moneyCompact(v));
      ctx.font = T.mono; ctx.fillStyle = T.ink3; ctx.textAlign = "center"; ctx.textBaseline = "top";
      [0, 0.25, 0.5, 0.75, 1].forEach((k) => {
        ctx.fillText("trade " + Math.round(k * (n - 1)), xOf(k * (n - 1)), plot.bottom + 8);
      });

      const band = (top, bot, alpha) => {
        ctx.beginPath();
        top.forEach((v, i) => { i ? ctx.lineTo(xOf(i), yOf(v)) : ctx.moveTo(xOf(i), yOf(v)); });
        for (let i = n - 1; i >= 0; i--) ctx.lineTo(xOf(i), yOf(bot[i]));
        ctx.closePath();
        ctx.fillStyle = withAlpha(T.accent, alpha); ctx.fill();
      };
      band(b.p95, b.p5, 0.08);
      band(b.p75, b.p25, 0.16);
      if (this.cfg.baseline !== undefined) {
        const y = Math.round(yOf(this.cfg.baseline)) + 0.5;
        ctx.strokeStyle = T.axis;
        ctx.beginPath(); ctx.moveTo(plot.left, y); ctx.lineTo(plot.right, y); ctx.stroke();
      }
      ctx.strokeStyle = T.gold; ctx.lineWidth = 2; ctx.lineJoin = "round";
      ctx.beginPath();
      b.p50.forEach((v, i) => { i ? ctx.lineTo(xOf(i), yOf(v)) : ctx.moveTo(xOf(i), yOf(v)); });
      ctx.stroke();

      const cur = this.cursor;
      if (cur && cur.x >= plot.left && cur.x <= plot.right) {
        const i = Math.round(((cur.x - plot.left) / (plot.right - plot.left)) * (n - 1));
        const X = Math.round(xOf(i)) + 0.5;
        ctx.strokeStyle = withAlpha(T.ink2, 0.35); ctx.setLineDash([1, 3]);
        ctx.beginPath(); ctx.moveTo(X, plot.top); ctx.lineTo(X, plot.bottom); ctx.stroke();
        ctx.setLineDash([]);
        Tip.show(cur.cx, cur.cy, (el) => {
          tipTitle(el, "After trade " + i);
          tipRow(el, "Median", U.money(b.p50[i]), null, T.gold);
          tipRow(el, "Lucky (P95)", U.money(b.p95[i]), "pos");
          tipRow(el, "Unlucky (P5)", U.money(b.p5[i]), "neg");
        });
      } else {
        Tip.hide();
      }
    }
  }

  /* ------------------------------ sparkline ------------------------------ */
  function sparkline(el, values, color) {
    if (!el) return;
    el.innerHTML = "";
    if (!values || values.length < 2) return;
    const w = el.clientWidth || 300, h = el.clientHeight || 46;
    const lo = Math.min(...values), hi = Math.max(...values);
    const span = hi - lo || 1;
    const X = (i) => (i / (values.length - 1)) * (w - 8) + 4;
    const Y = (v) => h - 5 - ((v - lo) / span) * (h - 10);
    const pts = values.map((v, i) => `${X(i).toFixed(1)},${Y(v).toFixed(1)}`).join(" ");
    const last = values[values.length - 1];
    const svg = `<svg viewBox="0 0 ${w} ${h}" width="100%" height="100%" preserveAspectRatio="none" aria-hidden="true">
      <polyline points="${pts} ${X(values.length - 1).toFixed(1)},${h - 1} ${X(0).toFixed(1)},${h - 1}"
        fill="${withAlpha(color, 0.09)}" stroke="none"/>
      <polyline points="${pts}" fill="none" stroke="${color}" stroke-width="2"
        stroke-linejoin="round" stroke-linecap="round"/>
      <circle cx="${X(values.length - 1)}" cy="${Y(last)}" r="3.5" fill="${color}" stroke="${tokens().surface}" stroke-width="2"/>
    </svg>`;
    el.innerHTML = svg;
  }

  window.Charts = { CandleChart, LineChart, BarChart, BandChart, sparkline, Tip, tokens, refreshTokens };
})();
