/* util.js — formatting, parsing, derived metrics, session windows.
   Exposed as window.U. No dependencies; loaded first. */
(function () {
  "use strict";

  const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* ------------------------------- numbers ------------------------------ */
  function money(x, sign) {
    if (x === null || x === undefined || Number.isNaN(Number(x))) return "—";
    const v = Number(x);
    const s = Math.abs(v).toLocaleString("en-US",
      { style: "currency", currency: "USD" });
    return (v < 0 ? "−" : (sign && v > 0 ? "+" : "")) + s;
  }
  function moneyCompact(x) {
    if (x === null || x === undefined) return "—";
    const v = Number(x), a = Math.abs(v);
    if (a >= 1e6) return (v < 0 ? "−" : "") + "$" + (a / 1e6).toFixed(2) + "M";
    if (a >= 1e4) return (v < 0 ? "−" : "") + "$" + (a / 1e3).toFixed(1) + "K";
    if (a >= 10) return (v < 0 ? "−" : "") + "$" + Math.round(a).toLocaleString("en-US");
    if (a === 0) return "$0";
    return money(v);
  }
  function pct(x, dp = 1, sign) {
    if (x === null || x === undefined || Number.isNaN(Number(x))) return "—";
    const v = Number(x);
    return (sign && v > 0 ? "+" : "") + v.toFixed(dp) + "%";
  }
  function num(x, dp = 2) {
    if (x === null || x === undefined || Number.isNaN(Number(x))) return "—";
    return Number(x).toFixed(dp);
  }
  const cls = (v) => (v > 0 ? "pos" : v < 0 ? "neg" : "dim");

  function fmtPrice(v) {
    if (v === null || v === undefined) return "—";
    const a = Math.abs(v);
    const dp = a >= 1000 ? 1 : a >= 50 ? 2 : 4;
    return Number(v).toLocaleString("en-US",
      { minimumFractionDigits: dp, maximumFractionDigits: dp });
  }
  function fmtDurMin(min) {
    if (min === null || min === undefined) return "—";
    const m = Math.round(min);
    if (m < 60) return m + "m";
    return Math.floor(m / 60) + "h " + (m % 60) + "m";
  }
  function fmtDur(ms) {
    ms = Math.max(0, ms);
    const s = Math.floor(ms / 1000), h = Math.floor(s / 3600);
    return `${h}h ${Math.floor((s % 3600) / 60)}m ${s % 60}s`;
  }

  /* -------------------------------- time -------------------------------- */
  // Trade/equity timestamps come as "2026-07-01 01:23:45+00:00" — normalise
  // the space so Safari's Date parser accepts them too.
  function parseTS(t) {
    if (!t) return null;
    const s = String(t);
    if (s.endsWith(" start")) return new Date(s.slice(0, 10) + "T00:00:00Z");
    const d = new Date(s.includes("T") ? s : s.replace(" ", "T"));
    return Number.isNaN(+d) ? null : d;
  }
  function hhmm(d, tz) {
    return d.toLocaleTimeString("en-AU",
      { hour12: false, hour: "2-digit", minute: "2-digit", timeZone: tz });
  }
  function shortDate(d) {
    return d.toLocaleDateString("en-AU", { day: "numeric", month: "short" });
  }
  function countdown(iso) {
    const ms = new Date(iso) - Date.now();
    if (ms < -30 * 60000) return "passed";
    if (ms < 0) return "NOW";
    const m = Math.floor(ms / 60000);
    return m < 60 ? `in ${m}m` : `in ${Math.floor(m / 60)}h ${m % 60}m`;
  }

  /* --------------------------- session windows --------------------------- */
  const FALLBACK_SCHEDULE = {
    asia: { label: "Asian Session", open_tz: "Asia/Tokyo", open_time: "10:00", duration_minutes: 240 },
    newyork: { label: "New York Session", open_tz: "America/New_York", open_time: "09:30", duration_minutes: 390 },
  };
  function tzOffsetMs(tz, date) {
    const inTz = new Date(date.toLocaleString("en-US", { timeZone: tz }));
    const inUtc = new Date(date.toLocaleString("en-US", { timeZone: "UTC" }));
    return inTz - inUtc;
  }
  function sessionWindows(schedule) {
    const sched = schedule || (window.DATA && window.DATA.schedule) || FALLBACK_SCHEDULE;
    const out = [], now = new Date();
    for (let off = -1; off <= 7; off++) {
      for (const [name, s] of Object.entries(sched)) {
        const probe = new Date(now.getTime() + off * 86400e3);
        const p = new Intl.DateTimeFormat("en-CA", { timeZone: s.open_tz, year: "numeric", month: "2-digit", day: "2-digit" })
          .format(probe).split("-").map(Number);
        const [hh, mm] = s.open_time.split(":").map(Number);
        const guess = Date.UTC(p[0], p[1] - 1, p[2], hh, mm);
        const open = new Date(guess - tzOffsetMs(s.open_tz, new Date(guess)));
        const dow = new Intl.DateTimeFormat("en-US", { timeZone: s.open_tz, weekday: "short" }).format(open);
        if (dow === "Sat" || dow === "Sun") continue;
        out.push({ name, label: s.label.split("(")[0].trim(), open, close: new Date(open.getTime() + s.duration_minutes * 60000) });
      }
    }
    out.sort((a, b) => a.open - b.open);
    return out;
  }

  /* ---------------------------- derived metrics -------------------------- */
  function streakOf(trades) {
    let n = 0;
    for (let i = trades.length - 1; i >= 0; i--) {
      const p = trades[i].pnl;
      if (p === 0) break;
      const dir = p > 0 ? 1 : -1;
      if (n === 0) n = dir;
      else if (Math.sign(n) === dir) n += dir;
      else break;
    }
    return n;
  }

  function derive(D) {
    const trades = (D.trades || []).slice()
      .sort((a, b) => (parseTS(a.exit_time) || 0) - (parseTS(b.exit_time) || 0));
    const s = D.stats || {};
    const starting = D.starting_balance || 0;
    const balance = D.balance ?? starting;
    const now = Date.now();

    const pnlSince = (ms) => trades.reduce((acc, t) => {
      const et = parseTS(t.exit_time);
      return acc + (et && +et >= ms ? t.pnl : 0);
    }, 0);

    // daily P&L series from trades grouped by Sydney day_key
    const byDay = new Map();
    trades.forEach((t) => {
      byDay.set(t.day_key, (byDay.get(t.day_key) || 0) + t.pnl);
    });
    const dailyPnl = [...byDay.entries()]
      .map(([day, pnl]) => ({ day, pnl: Math.round(pnl * 100) / 100 }));

    // Sharpe from daily P&L as % of starting balance, annualised √252
    let sharpe = null;
    if (dailyPnl.length >= 5 && starting > 0) {
      const rets = dailyPnl.map((d) => d.pnl / starting);
      const mean = rets.reduce((a, b) => a + b, 0) / rets.length;
      const sd = Math.sqrt(rets.reduce((a, r) => a + (r - mean) ** 2, 0) / (rets.length - 1));
      sharpe = sd > 0 ? (mean / sd) * Math.sqrt(252) : null;
    }

    // equity curve → points + drawdown series (% from running peak)
    const eq = (D.equity_curve || []).map((p) => ({ t: parseTS(p.t), balance: p.balance }))
      .filter((p) => p.t);
    let peak = starting;
    const ddSeries = eq.map((p) => {
      peak = Math.max(peak, p.balance);
      return { t: p.t, dd: peak > 0 ? -100 * (peak - p.balance) / peak : 0 };
    });
    const maxDDpct = ddSeries.length ? Math.min(...ddSeries.map((d) => d.dd)) : 0;

    // open exposure
    const open = Object.values(D.open_positions || {});
    const notional = open.reduce((a, p) => a + p.units * p.entry_price, 0);
    const openRisk = open.reduce((a, p) => a + (p.risk_usd || 0), 0);

    // expectancy $ per trade
    const expectancy = trades.length
      ? trades.reduce((a, t) => a + t.pnl, 0) / trades.length : null;
    const avgDur = trades.length
      ? trades.reduce((a, t) => a + (t.duration_min || 0), 0) / trades.length : null;

    // per-session breakdown
    const bySession = {};
    trades.forEach((t) => {
      const k = t.session || "?";
      const o = bySession[k] || (bySession[k] = { trades: 0, wins: 0, pnl: 0 });
      o.trades++; if (t.pnl > 0) o.wins++; o.pnl += t.pnl;
    });

    // R-multiple distribution
    const rBins = [-2, -1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5];
    const rCounts = new Array(rBins.length + 1).fill(0);
    trades.forEach((t) => {
      let i = rBins.findIndex((b) => t.r_multiple < b);
      if (i === -1) i = rBins.length;
      rCounts[i]++;
    });

    return {
      trades, dailyPnl, eq, ddSeries, sharpe, bySession, rCounts, rBins,
      streak: streakOf(trades),
      dayPnl: D.day_pnl ?? 0,
      weekPnl: pnlSince(now - 7 * 86400e3),
      monthPnl: pnlSince(now - 30 * 86400e3),
      allTime: balance - starting,
      allTimePct: starting ? 100 * (balance - starting) / starting : 0,
      maxDDpct,
      notional, openRisk,
      leverage: balance > 0 ? notional / balance : 0,
      expectancy, avgDur,
      winRate: s.win_rate, profitFactor: s.profit_factor,
      avgWin: s.avg_win, avgLoss: s.avg_loss, avgR: s.avg_r,
      totalTrades: s.total_trades || 0, wins: s.wins || 0, losses: s.losses || 0,
      maxDD: s.max_drawdown, perAsset: s.per_asset || {},
      activePositions: open.length,
    };
  }

  /* ------------------------- animated number counter --------------------- */
  const REDUCED = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const counters = new WeakMap();
  function tweenNumber(el, to, fmt, dur = 650) {
    const from = counters.get(el) ?? to;
    counters.set(el, to);
    if (REDUCED || from === to || !Number.isFinite(from)) { el.textContent = fmt(to); return; }
    const t0 = performance.now();
    (function frame(t) {
      const k = Math.min(1, (t - t0) / dur);
      const e = 1 - Math.pow(1 - k, 3);
      el.textContent = fmt(from + (to - from) * e);
      if (k < 1 && counters.get(el) === to) requestAnimationFrame(frame);
    })(t0);
  }

  window.U = {
    esc, money, moneyCompact, pct, num, cls, fmtPrice, fmtDurMin, fmtDur,
    parseTS, hhmm, shortDate, countdown, sessionWindows, derive, tweenNumber,
    REDUCED,
  };
})();
