/* components.js — section renderers. window.C.
   Each section builds its skeleton once, then updates in place so chart
   instances, scroll state and animations survive the 60 s data refresh. */
(function () {
  "use strict";
  const U = window.U, Ch = window.Charts;
  const $ = (id) => document.getElementById(id);

  const S = {                    // module state that must survive re-renders
    asset: null,                 // selected market tab
    equityTab: "equity",
    intelTab: "calendar",
    candleChart: null,
    equityChart: null,
    dailyChart: null,
    rChart: null,
    seenFeed: new Set(),
    firstFeedRender: true,
    openTrades: new Set(),
    lab: { sel: new Set(["GOLD", "NQ", "ES"]), session: "both", days: 29, polling: null, lastResult: null },
    btCharts: {},
  };

  /* ============================== topbar ================================ */
  function renderTopbar(D, M, health) {
    const el = $("topSession");
    const wins = U.sessionWindows(D && D.schedule);
    const now = new Date();
    const live = wins.find((w) => w.open <= now && now < w.close);
    const next = wins.find((w) => w.open > now);
    let html = "";
    if (live && window.HOLIDAY_TODAY) {
      html = `<span class="pill pill-idle">🏖 ${U.esc(live.label)} — holiday</span>`;
    } else if (live) {
      html = `<span class="pill pill-live"><span class="dot"></span>${U.esc(live.label)} live · ends ${U.fmtDur(live.close - now)}</span>`;
    } else {
      html = `<span class="pill pill-idle">Markets between sessions</span>`;
    }
    if (next) html += `<span class="pill pill-idle" style="border-style:dashed">Next · ${U.esc(next.label)} ${U.fmtDur(next.open - now)}</span>`;
    if (health && health.badge) html += health.badge;
    el.innerHTML = html;

    const fresh = $("dataFresh");
    if (D) {
      const age = (Date.now() - new Date(D.generated_utc)) / 1000;
      const liveData = age < 120;
      fresh.className = "topbar-fresh" + (liveData ? " is-live" : "");
      fresh.innerHTML = `<span class="dot"></span>DATA ${age < 90 ? Math.max(0, Math.round(age)) + "s" : U.fmtDurMin(age / 60)} AGO`;
    } else {
      fresh.innerHTML = "";
    }
    const wake = $("wakeSlot");
    wake.innerHTML = (health && health.asleep)
      ? `<button class="btn btn-wake" id="wakeBtn">⏰ Wake the agent</button>` : "";
    const wb = $("wakeBtn");
    if (wb) wb.onclick = () => wakeBot(wb);

    const halt = $("haltSlot");
    const provider = (D && D.broker && D.broker.provider) || "paper";
    const haltArmed = !!(D && D.halt_flag);
    const showHalt = provider !== "paper" || haltArmed;
    halt.innerHTML = !showHalt ? "" : haltArmed
      ? `<button class="btn btn-danger" id="haltBtn" data-mode="clear">✓ Clear halt</button>`
      : `<button class="btn btn-danger" id="haltBtn" data-mode="halt">⛔ Flatten &amp; halt</button>`;
    const hb = $("haltBtn");
    if (hb) hb.onclick = () => haltBot(hb, hb.dataset.mode);
  }

  function tickClock() {
    const el = $("clockTime");
    if (!el) return;
    const tz = (window.DATA && window.DATA.schedule && "Australia/Sydney") || "Australia/Sydney";
    const now = new Date();
    el.textContent = now.toLocaleTimeString("en-AU", { hour12: false, timeZone: tz });
    $("clockZone").textContent = now.toLocaleDateString("en-AU",
      { weekday: "short", day: "numeric", month: "short", timeZone: tz }) + " · Sydney";
  }

  /* ============================== banners =============================== */
  function renderBanners(D, health) {
    const el = $("banners");
    const rows = [];
    const broker = D.broker || {};
    if (broker.environment === "live")
      rows.push(`<div class="banner banner-live">🔴 LIVE ACCOUNT — real money is at risk (${U.esc(broker.provider || "")}${broker.account_id ? " · " + U.esc(String(broker.account_id)) : ""}). Use the kill switch above if anything looks wrong.</div>`);
    if ((D.bot_status || "").startsWith("REPLAY"))
      rows.push(`<div class="banner banner-replay">🔁 Showing replay data (test run on historical prices) — live data takes over at the next session.</div>`);
    if (D.halted_reason)
      rows.push(`<div class="banner banner-halt">⛔ ${U.esc(D.halted_reason)}</div>`);
    else if (D.halt_flag)
      rows.push(`<div class="banner banner-warn">⏳ Kill switch armed — waiting for the bot's next loop to flatten and halt (up to ~45s).</div>`);
    if (broker.provider && broker.provider !== "paper" && broker.connected === false)
      rows.push(`<div class="banner banner-warn">⚠ Lost connection to the broker (${U.esc(broker.provider)}) — the bot will keep retrying automatically.</div>`);
    if (broker.data_source === "fallback")
      rows.push(`<div class="banner banner-warn">⚠ The broker's price feed is unavailable — trading on a fallback data source for market timing (live positions still execute at the broker itself).</div>`);
    if (broker.last_order_error)
      rows.push(`<div class="banner banner-warn">⚠ Last order was refused: ${U.esc(broker.last_order_error)}</div>`);
    (broker.unmanaged_warnings || []).forEach((w) =>
      rows.push(`<div class="banner banner-warn">⚠ ${U.esc(w)}</div>`));
    if (health.asleep)
      rows.push(`<div class="banner banner-asleep"><span>💤 The agent stood down (data feed dropped) but <b>${U.esc(health.liveLabel || "the session")}</b> is still live — wake it to resume trading.</span></div>`);
    if (health.holiday)
      rows.push(`<div class="banner banner-holiday">🏖 ${U.esc(D.bot_status)} — standing down for a market holiday; trading resumes next session.</div>`);
    el.innerHTML = rows.join("");
  }

  function brandSubText(D) {
    if ((D.bot_status || "").startsWith("REPLAY")) return "replay data";
    const broker = D.broker || {};
    if (!broker.provider || broker.provider === "paper") return "paper account";
    const name = broker.provider === "ctrader" ? "cTrader" : broker.provider === "mt5" ? "MT5" : broker.provider;
    const acct = broker.account_id ? ` · ${broker.account_id}` : "";
    return broker.environment === "live" ? `${name} · LIVE${acct}` : `${name} · demo${acct}`;
  }

  /* ================================ hero ================================ */
  function renderHero(D, M, health) {
    const el = $("hero");
    if (!el.dataset.built) {
      el.dataset.built = "1";
      el.innerHTML = `
        <div class="hero-top">
          <div style="min-width:0">
            <div class="hero-eyebrow">Current capital <span class="pill pill-idle" style="height:22px;font-size:9.5px" id="heroTag">PAPER</span></div>
            <div class="hero-figure"><span class="currency">$</span><span id="heroInt">0</span><span class="cents" id="heroCents">.00</span></div>
            <div class="hero-deltas" id="heroDeltas"></div>
          </div>
          <div class="streak flat" id="streakBox">
            <div class="streak-ring">
              <div class="halo"></div>
              <svg viewBox="0 0 92 92">
                <circle class="track" cx="46" cy="46" r="40" fill="none" stroke-width="5"/>
                <circle class="arc" cx="46" cy="46" r="40" fill="none" stroke-width="5"
                        stroke-dasharray="251.3" stroke-dashoffset="251.3"/>
              </svg>
              <div class="streak-core">
                <span class="streak-ic" id="streakIc"></span>
                <span class="streak-n" id="streakN">—</span>
              </div>
            </div>
            <div class="streak-label" id="streakLbl">No streak</div>
          </div>
        </div>
        <div class="hero-spark" id="heroSpark"></div>
        <div class="hero-status" id="heroStatus"></div>`;
    }
    const bal = D.balance ?? 0;
    U.tweenNumber($("heroInt"), Math.floor(bal), (v) => Math.floor(v).toLocaleString("en-US"));
    $("heroCents").textContent = "." + (Math.round(bal * 100) % 100).toString().padStart(2, "0");

    const dayPct = D.balance ? 100 * M.dayPnl / (D.balance - M.dayPnl || 1) : 0;
    $("heroDeltas").innerHTML = `
      <span class="delta-chip">Today <b class="${U.cls(M.dayPnl)}">${U.money(M.dayPnl, true)}</b><span class="${U.cls(M.dayPnl)}">${U.pct(dayPct, 2, true)}</span></span>
      <span class="delta-chip">All-time <b class="${U.cls(M.allTime)}">${U.money(M.allTime, true)}</b><span class="${U.cls(M.allTime)}">${U.pct(M.allTimePct, 1, true)}</span></span>`;

    /* streak ring */
    const st = M.streak;
    const box = $("streakBox");
    box.className = "streak " + (st > 0 ? "up" : st < 0 ? "down" : "flat");
    const T = Ch.tokens();
    const col = st > 0 ? T.upInk : st < 0 ? T.downInk : T.ink3;
    const arc = box.querySelector(".arc");
    const frac = Math.min(Math.abs(st), 10) / 10;
    arc.style.stroke = col;
    arc.style.strokeDashoffset = String(251.3 * (1 - Math.max(frac, st !== 0 ? 0.06 : 0)));
    box.querySelector(".halo").style.setProperty("--halo",
      st > 0 ? "color-mix(in srgb, var(--up-ink), transparent 82%)"
      : st < 0 ? "color-mix(in srgb, var(--down-ink), transparent 82%)" : "transparent");
    $("streakIc").textContent = st > 0 ? "🔥" : st < 0 ? "↓" : "◦";
    $("streakN").textContent = st > 0 ? "+" + st : st < 0 ? String(st) : "0";
    $("streakLbl").textContent = st > 0 ? "Win streak" : st < 0 ? "Loss streak" : "No streak";

    Ch.sparkline($("heroSpark"), M.eq.slice(-90).map((p) => p.balance),
      M.allTime >= 0 ? T.up : T.down);

    $("heroStatus").innerHTML = `${health.pill}<span class="status-text" title="${U.esc(D.bot_status)}">${U.esc(D.bot_status || "")}</span>`;

    const tag = $("heroTag");
    const env = (D.broker && D.broker.environment) || "paper";
    tag.className = "pill " + (env === "live" ? "pill-halt" : env === "demo" ? "pill-warn" : "pill-idle");
    tag.textContent = env === "live" ? "LIVE" : env === "demo" ? "DEMO" : "PAPER";
  }

  /* ============================= positions ============================== */
  function renderPositions(D, M) {
    const el = $("positions");
    const open = Object.values(D.open_positions || {});
    const lastPx = (a) => {
      const cs = (D.candles || {})[a];
      return cs && cs.length ? cs[cs.length - 1].c : null;
    };
    let body;
    if (!open.length) {
      body = `<div class="empty-state"><span class="glyph">◇</span>Flat — no open positions.<br>
        Risking ${U.esc(String(D.risk_config?.risk_per_trade_pct ?? "—"))}% per trade when a setup fires.</div>`;
    } else {
      body = `<div class="pos-list">` + open.map((p) => {
        const px = lastPx(p.asset);
        const dir = p.direction === "LONG" ? 1 : -1;
        const upl = px !== null ? (px - p.entry_price) * p.units * dir : null;
        const lo = Math.min(p.stop, p.target), hiP = Math.max(p.stop, p.target);
        const posOf = (v) => Math.min(100, Math.max(0, 100 * (v - lo) / (hiP - lo || 1)));
        // orient so stop sits left, target right regardless of direction
        const flip = p.stop > p.target;
        const pf = (v) => flip ? 100 - posOf(v) : posOf(v);
        return `
        <div class="pos-row">
          <span class="pos-asset">${U.esc(p.asset)} <span class="side-tag ${p.direction === "LONG" ? "side-long" : "side-short"}">${p.direction}</span></span>
          <span></span>
          <span class="pos-upl ${upl === null ? "dim" : U.cls(upl)}">${upl === null ? "—" : U.money(upl, true)}</span>
          <span class="pos-meta">${p.units} units @ ${U.fmtPrice(p.entry_price)} · risk ${U.money(p.risk_usd)}</span>
          <div class="pos-range">
            <div class="range-bar">
              <span class="tick" style="left:${pf(p.entry_price)}%"></span>
              ${px !== null ? `<span class="cur" style="left:calc(${Math.min(99, Math.max(1, pf(px)))}% - 6px)"></span>` : ""}
            </div>
            <div class="range-labels"><span>SL ${U.fmtPrice(p.stop)}</span><span>TP ${U.fmtPrice(p.target)}</span></div>
          </div>
        </div>`;
      }).join("") + `</div>`;
    }
    el.innerHTML = `
      <div class="card-head"><span class="card-title"><span class="accent-tick"></span>Open positions</span>
        <span class="spacer"></span>
        <span class="card-note">${D.trades_this_session ?? 0}/${D.caps?.per_session ?? "—"} session · ${D.trades_today ?? 0}/${D.caps?.per_day ?? "—"} today</span>
      </div>${body}`;
  }

  /* =============================== market =============================== */
  function marketAssets(D) {
    const c = Object.keys(D.candles || {});
    if (c.length) return c;
    return Object.keys(D.assets_stage || {});
  }

  function renderMarket(D, M) {
    const el = $("market");
    const assets = marketAssets(D);
    if (!S.asset || !assets.includes(S.asset)) S.asset = assets[0] || null;

    if (!el.dataset.built) {
      el.dataset.built = "1";
      el.innerHTML = `
        <div class="market-head">
          <span class="card-title"><span class="accent-tick"></span>Live market</span>
          <div class="asset-tabs" id="assetTabs" role="tablist"></div>
          <span class="card-note">1-min · scroll to zoom · drag to pan</span>
          <span class="spacer"></span>
          <div class="ohlc-readout" id="ohlcReadout"></div>
          <div class="last-price" id="lastPrice"></div>
        </div>
        <div class="chart-shell market-canvas" id="marketShell"></div>
        <div class="stage-strip" id="stageStrip"></div>`;
      S.candleChart = new Ch.CandleChart($("marketShell"), {
        tz: "Australia/Sydney",
        onHover: (c) => {
          const r = $("ohlcReadout");
          if (!c) { r.innerHTML = ""; return; }
          r.innerHTML = `<span>O <b>${U.fmtPrice(c.o)}</b></span><span>H <b>${U.fmtPrice(c.h)}</b></span>
            <span>L <b>${U.fmtPrice(c.l)}</b></span><span>C <b>${U.fmtPrice(c.c)}</b></span>`;
        },
      });
    }

    /* tabs */
    $("assetTabs").innerHTML = assets.map((a) =>
      `<button class="asset-tab${a === S.asset ? " active" : ""}" role="tab" data-a="${U.esc(a)}">${U.esc(a)}</button>`).join("")
      || `<span class="card-note" style="padding:5px 10px">no session assets yet</span>`;
    $("assetTabs").querySelectorAll(".asset-tab").forEach((b) => {
      b.onclick = () => { S.asset = b.dataset.a; renderMarket(window.DATA, M); };
    });

    /* chart data */
    const candles = (D.candles || {})[S.asset] || [];
    const trades = M.trades.filter((t) => t.asset === S.asset);
    const position = (D.open_positions || {})[S.asset] || null;
    S.candleChart.setData(candles, trades, position ? { ...position } : null);

    /* last price + change */
    const lp = $("lastPrice");
    if (candles.length) {
      const last = candles[candles.length - 1];
      const first = candles[0];
      const chg = 100 * (last.c - first.o) / first.o;
      lp.innerHTML = `${U.fmtPrice(last.c)}<span class="chg ${U.cls(chg)}">${U.pct(chg, 2, true)}</span>`;
    } else lp.innerHTML = "";

    /* stage strip */
    const BIAS = { bullish: ["▲ Bullish", "bias-bull"], bearish: ["▼ Bearish", "bias-bear"], consolidation: ["◆ Ranging", "bias-flat"] };
    $("stageStrip").innerHTML = Object.entries(D.assets_stage || {}).map(([a, st]) => {
      const b = BIAS[st.bias];
      const stage = st.stage === "building_range" ? "building opening range"
        : st.stage === "hunting" ? `hunting breakout${st.range_low ? ` · ${st.range_low}–${st.range_high}` : ""}`
        : st.stage === "filtered" ? (st.filter_reason || "standing aside") : (st.stage || "");
      return `<span class="stage-chip"><span class="a">${U.esc(a)}</span>${b ? `<span class="${b[1]}">${b[0]}</span>` : ""}<span>${U.esc(stage)}</span></span>`;
    }).join("");
  }

  /* ============================== metrics =============================== */
  function mCell(label, value, opts = {}) {
    return `<div class="m-cell"><div class="m-label">${label}</div>
      <div class="m-value ${opts.cls || ""}">${value}</div>
      ${opts.sub ? `<div class="m-sub">${opts.sub}</div>` : ""}</div>`;
  }
  function renderMetrics(D, M) {
    const el = $("metrics");
    const s = (v, f = U.money) => v === null || v === undefined ? "—" : f(v);
    el.innerHTML = `
      <div class="card-head"><span class="card-title"><span class="accent-tick"></span>Performance metrics</span>
        <span class="spacer"></span><span class="card-note">computed from ${M.totalTrades} closed trades</span></div>
      <div class="metric-groups">
        <div class="metric-group"><h3>Profit &amp; loss</h3><div class="metric-cells">
          ${mCell("Today", U.money(M.dayPnl, true), { cls: U.cls(M.dayPnl) })}
          ${mCell("7 days", U.money(M.weekPnl, true), { cls: U.cls(M.weekPnl) })}
          ${mCell("30 days", U.money(M.monthPnl, true), { cls: U.cls(M.monthPnl) })}
          ${mCell("All-time", U.money(M.allTime, true), { cls: U.cls(M.allTime), sub: U.pct(M.allTimePct, 1, true) + " return" })}
        </div></div>
        <div class="metric-group"><h3>Edge</h3><div class="metric-cells">
          ${mCell("Win rate", M.winRate == null ? "—" : M.winRate + "%", { sub: `${M.wins}W · ${M.losses}L` })}
          ${mCell("Profit factor", s(M.profitFactor, (v) => U.num(v, 2)))}
          ${mCell("Expectancy", s(M.expectancy, (v) => U.money(v, true)), { cls: M.expectancy == null ? "" : U.cls(M.expectancy), sub: "per trade" })}
          ${mCell("Avg R", s(M.avgR, (v) => (v > 0 ? "+" : "") + U.num(v, 2)), { cls: M.avgR == null ? "" : U.cls(M.avgR) })}
        </div></div>
        <div class="metric-group"><h3>Averages</h3><div class="metric-cells">
          ${mCell("Avg win", s(M.avgWin), { cls: M.avgWin == null ? "" : "pos" })}
          ${mCell("Avg loss", s(M.avgLoss), { cls: M.avgLoss == null ? "" : "neg" })}
          ${mCell("Avg hold", M.avgDur == null ? "—" : U.fmtDurMin(M.avgDur))}
          ${mCell("Trades", String(M.totalTrades))}
        </div></div>
        <div class="metric-group"><h3>Risk</h3><div class="metric-cells">
          ${mCell("Max drawdown", s(M.maxDD), { cls: M.maxDD ? "neg" : "dim", sub: U.pct(Math.abs(M.maxDDpct), 1) + " of peak" })}
          ${mCell("Sharpe", M.sharpe == null ? "—" : U.num(M.sharpe, 2), { sub: "daily · annualised" })}
          ${mCell("Open risk", U.money(M.openRisk), { sub: M.activePositions + " active position" + (M.activePositions === 1 ? "" : "s") })}
          ${mCell("Exposure", U.moneyCompact(M.notional), { sub: U.num(M.leverage, 1) + "× leverage" })}
        </div></div>
      </div>`;
  }

  /* =============================== equity =============================== */
  function renderEquity(D, M) {
    const el = $("equity");
    if (!el.dataset.built) {
      el.dataset.built = "1";
      el.innerHTML = `
        <div class="card-head">
          <span class="card-title"><span class="accent-tick"></span>Equity</span>
          <div class="chart-tabs" id="equityTabs">
            <button class="chart-tab" data-t="equity">Equity curve</button>
            <button class="chart-tab" data-t="drawdown">Drawdown</button>
          </div>
          <span class="spacer"></span><span class="card-note" id="equityNote"></span>
        </div>
        <div class="chart-shell equity-canvas" id="equityShell"></div>`;
      S.equityChart = new Ch.LineChart($("equityShell"), { points: [] });
      $("equityTabs").querySelectorAll(".chart-tab").forEach((b) => {
        b.onclick = () => { S.equityTab = b.dataset.t; renderEquity(window.DATA, U.derive(window.DATA)); };
      });
    }
    $("equityTabs").querySelectorAll(".chart-tab").forEach((b) =>
      b.classList.toggle("active", b.dataset.t === S.equityTab));
    const T = Ch.tokens();

    // daily P&L lookup for the equity tooltip
    const dayOf = (d) => d.toLocaleDateString("en-CA", { timeZone: "Australia/Sydney" });
    const dailyMap = new Map(M.dailyPnl.map((r) => [r.day, r.pnl]));
    let peak = D.starting_balance || 0;

    if (S.equityTab === "equity") {
      const pts = M.eq.map((p) => {
        peak = Math.max(peak, p.balance);
        return { x: p.t, y: p.balance, dd: peak ? 100 * (peak - p.balance) / peak : 0 };
      });
      $("equityNote").textContent = "account balance after every closed trade · USD";
      S.equityChart.update({
        points: pts,
        color: (M.allTime >= 0 ? T.up : T.down),
        area: true, areaBase: undefined,
        baseline: D.starting_balance,
        emptyMsg: "No equity history yet",
        emptySub: "The curve starts with the first closed trade",
        yFmt: (v) => U.moneyCompact(v),
        tipTitle: (p) => p.x.toLocaleDateString("en-AU", { weekday: "short", day: "numeric", month: "short", timeZone: "Australia/Sydney" }),
        tipRows: (p) => [
          ["Equity", U.money(p.y)],
          ["Daily P&L", U.money(dailyMap.get(dayOf(p.x)) ?? 0, true), U.cls(dailyMap.get(dayOf(p.x)) ?? 0)],
          ["Drawdown", U.pct(p.dd, 1), p.dd > 0.05 ? "neg" : null],
        ],
      });
    } else {
      const pts = M.ddSeries.map((p) => ({ x: p.t, y: p.dd }));
      $("equityNote").textContent = "% below running equity peak";
      S.equityChart.update({
        points: pts,
        color: T.down, area: true, areaBase: 0,
        baseline: 0, includeZero: true,
        emptyMsg: "No drawdown history yet", emptySub: "",
        yFmt: (v) => U.num(v, 1) + "%",
        tipTitle: (p) => p.x.toLocaleDateString("en-AU", { weekday: "short", day: "numeric", month: "short", timeZone: "Australia/Sydney" }),
        tipRows: (p) => [["Drawdown", U.pct(p.y, 2), p.y < -0.05 ? "neg" : null]],
      });
    }
  }

  /* ============================ perf visuals ============================ */
  function renderPerf(D, M) {
    /* daily P&L bars */
    const dp = $("dailyPnl");
    if (!dp.dataset.built) {
      dp.dataset.built = "1";
      dp.innerHTML = `<div class="card-head"><span class="card-title"><span class="accent-tick"></span>Daily P&amp;L</span>
        <span class="spacer"></span><span class="card-note">USD per trading day</span></div>
        <div class="chart-shell mini-canvas" id="dailyShell"></div>`;
      S.dailyChart = new Ch.BarChart($("dailyShell"), { bars: [] });
    }
    S.dailyChart.update({
      bars: M.dailyPnl.slice(-22).map((r) => ({
        label: r.day.slice(5).replace("-", "/"), value: r.pnl, day: r.day,
      })),
      diverging: true,
      emptyMsg: "No closed trading days yet",
      emptySub: "Bars appear after the first day with trades",
      yFmt: (v) => U.moneyCompact(v),
      tipTitle: (b) => b.day,
      tipRows: (b) => [["P&L", U.money(b.value, true), U.cls(b.value)]],
    });

    /* R-multiple distribution */
    const rd = $("rDist");
    if (!rd.dataset.built) {
      rd.dataset.built = "1";
      rd.innerHTML = `<div class="card-head"><span class="card-title"><span class="accent-tick"></span>R-multiple distribution</span>
        <span class="spacer"></span><span class="card-note">trades per R bucket</span></div>
        <div class="chart-shell mini-canvas" id="rShell"></div>`;
      S.rChart = new Ch.BarChart($("rShell"), { bars: [] });
    }
    // diverging histogram: losing buckets hang below the baseline, winners rise above
    const labels = ["<−2R", "−2R", "−1.5R", "−1R", "−0.5R", "0R", "+0.5R", "+1R", "+1.5R", "+2R", ">2.5R"];
    const mids = [-2.25, -1.75, -1.25, -0.75, -0.25, 0.25, 0.75, 1.25, 1.75, 2.25, 2.75];
    S.rChart.update({
      bars: M.rCounts.map((v, i) => ({ label: labels[i], value: v * Math.sign(mids[i]), n: v })),
      diverging: true,
      emptyMsg: "No closed trades yet", emptySub: "",
      yFmt: (v) => String(Math.abs(Math.round(v))),
      tipTitle: (b) => b.label + " bucket",
      tipRows: (b) => [["Trades", String(b.n)]],
    });

    /* breakdown table */
    const bd = $("breakdown");
    const sess = Object.entries(M.bySession);
    const assets = Object.entries(M.perAsset);
    bd.innerHTML = `
      <div class="card-head"><span class="card-title"><span class="accent-tick"></span>Breakdown</span>
        <span class="spacer"></span><span class="card-note">by session &amp; asset</span></div>
      <div class="table-wrap"><table>
        <tr><th>Session</th><th class="num">Trades</th><th class="num">Win %</th><th class="num">P&amp;L</th></tr>
        ${sess.map(([k, v]) => `<tr><td>${U.esc(k)}</td><td class="num mono">${v.trades}</td>
          <td class="num mono">${v.trades ? Math.round(100 * v.wins / v.trades) : 0}%</td>
          <td class="num mono ${U.cls(v.pnl)}">${U.money(v.pnl, true)}</td></tr>`).join("")
        || `<tr><td colspan="4" class="dim">No closed trades yet.</td></tr>`}
      </table></div>
      <div class="table-wrap" style="margin-top:10px"><table>
        <tr><th>Asset</th><th class="num">Trades</th><th class="num">Win %</th><th class="num">P&amp;L</th></tr>
        ${assets.map(([a, v]) => `<tr><td><b>${U.esc(a)}</b></td><td class="num mono">${v.trades}</td>
          <td class="num mono">${v.trades ? Math.round(100 * v.wins / v.trades) : 0}%</td>
          <td class="num mono ${U.cls(v.pnl)}">${U.money(v.pnl, true)}</td></tr>`).join("")
        || `<tr><td colspan="4" class="dim">No closed trades yet.</td></tr>`}
      </table></div>`;
  }

  /* ================================ agent =============================== */
  const SEV = {
    entry: "sev-success", exit: "sev-success", manage: "sev-accent",
    halt: "sev-danger", bench: "sev-danger",
    adjustment: "sev-accent", suggestion: "sev-accent",
    filtered: "sev-warn", skipped: "sev-warn",
    range: "", assessment: "", info: "", session_start: "", session_end: "",
  };
  const CAT = {
    entry: "ENTRY", exit: "EXIT", manage: "MANAGE", halt: "HALT", bench: "BENCH",
    adjustment: "TUNE", suggestion: "IDEA", filtered: "FILTER", skipped: "SKIP",
    range: "RANGE", assessment: "BIAS", info: "INFO",
    session_start: "SESSION", session_end: "SESSION",
  };
  const FEED_MAX = 18;

  function renderAgent(D, M, health) {
    const el = $("agent");
    if (!el.dataset.built) {
      el.dataset.built = "1";
      el.innerHTML = `
        <div class="agent-head">
          <div class="radar" aria-hidden="true">
            <div class="ring r1"></div><div class="ring r2"></div><div class="ring r3"></div>
            <div class="sweep"></div><div class="core"></div>
            <div class="blip" style="left:70%;top:26%"></div>
            <div class="blip" style="left:28%;top:62%;animation-delay:1.6s"></div>
            <div class="blip" style="left:58%;top:74%;animation-delay:2.9s"></div>
          </div>
          <div class="agent-title-block">
            <div class="agent-state" id="agentState"></div>
            <div class="agent-substate" id="agentSub"></div>
          </div>
        </div>
        <div class="feed" id="feed"></div>`;
    }
    const assets = Object.keys(D.assets_stage || {});
    $("agentState").textContent = health.stateLabel;
    $("agentSub").textContent = assets.length
      ? `watching ${assets.join(" · ")} — ${D.session || "no session"}`
      : "standing by for the next session window";
    el.querySelector(".radar").style.opacity = health.working ? 1 : 0.35;
    el.querySelector(".sweep").style.animationPlayState = health.working ? "running" : "paused";

    /* feed — capped, newest first, slide-in on arrival */
    const feedEl = $("feed");
    const items = ((D.agent && D.agent.feed) || []).slice(0, FEED_MAX);
    feedEl.innerHTML = items.map((f) => {
      const key = (f.t || "") + "|" + (f.text || "").slice(0, 60);
      const fresh = !S.firstFeedRender && !S.seenFeed.has(key);
      const time = (f.t || "").replace("T", " ").slice(11, 19);
      return `<div class="feed-item ${SEV[f.kind] || ""}${fresh ? " fresh" : ""}">
        <span class="feed-time">${U.esc(time)}</span>
        <span class="feed-cat">${CAT[f.kind] || "INFO"}</span><span></span>
        <span class="feed-text">${U.esc(f.text)}</span>
      </div>`;
    }).join("") || `<div class="empty-state"><span class="glyph">◎</span>The agent narrates here from its next session — analysis, entries, trade management, lessons.</div>`;
    items.forEach((f) => S.seenFeed.add((f.t || "") + "|" + (f.text || "").slice(0, 60)));
    S.firstFeedRender = false;
  }

  /* ============================ suggestions ============================= */
  function renderSuggest(D) {
    const el = $("suggest");
    const A = D.agent || {};
    const SG = A.suggestions || { pending: [], history: [], used: 0, budget: 15 };
    if (window.LIVE_SUGG) {
      SG.pending = window.LIVE_SUGG.filter((x) => x.status === "pending");
      const decided = window.LIVE_SUGG.filter((x) => x.status !== "pending").reverse();
      SG.history = decided.concat(SG.history || []).slice(0, 10);
    }
    const pending = SG.pending.map((p) => `
      <div class="sugg" data-id="${U.esc(p.id)}">
        <div><span class="sugg-param">${U.esc(p.param)}</span>
          <span class="sugg-change">&nbsp;${U.esc(String(p.from))} → <b>${U.esc(String(p.to))}</b></span></div>
        <div class="sugg-why">${U.esc(p.why)}</div>
        <div class="sugg-evidence">Evidence: ${U.esc(p.evidence)} · proposed ${U.esc(p.created)}</div>
        <div class="sugg-actions">
          <button class="btn btn-approve" data-d="approved">✓ Approve</button>
          <button class="btn btn-reject" data-d="rejected">✕ Reject</button>
        </div>
      </div>`).join("")
      || `<div class="empty-state"><span class="glyph">◈</span>No pending suggestions. While auto-refinement budget remains, the agent applies small bounded improvements itself; once spent, proposals appear here for sign-off.</div>`;
    const hist = (SG.history || []).slice(0, 8).map((h) => `
      <div class="hist-item"><span class="mono">${U.esc(h.param)}: ${U.esc(String(h.from))} → ${U.esc(String(h.to))}</span>
        <span class="when">${U.esc(h.status || (h.auto ? "auto" : ""))} ${U.esc(h.day || h.created || "")}</span></div>`).join("");
    el.innerHTML = `
      <div class="card-head"><span class="card-title"><span class="accent-tick"></span>Suggestions &amp; refinements</span></div>
      <div class="budget-row"><span class="lbl">Auto-refinement budget</span>
        <div class="meter"><div style="width:${Math.min(100, 100 * (SG.used || 0) / (SG.budget || 1))}%"></div></div>
        <span class="val">${SG.used || 0}/${SG.budget || 15}</span></div>
      ${pending}
      ${hist ? `<div class="card-title" style="margin:16px 0 6px">Change history</div>${hist}` : ""}`;
    el.querySelectorAll(".sugg .btn").forEach((b) => {
      b.onclick = () => decide(b.closest(".sugg").dataset.id, b.dataset.d, b);
    });
  }

  async function decide(id, decision, btn) {
    btn.disabled = true;
    try {
      const r = await fetch("/api/decision", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, decision }),
      });
      const j = await r.json();
      btn.closest(".sugg").innerHTML = r.ok
        ? `<b class="${decision === "approved" ? "pos" : "dim"}">${decision === "approved" ? "✓ Approved." : "✕ Rejected."}</b> <span class="card-note">${U.esc(j.note || "")}</span>`
        : `<span class="neg">${U.esc(j.error || "failed")}</span>`;
    } catch (e) {
      btn.disabled = false;
      alert("Couldn't reach the dashboard server.\nOpen the dashboard via http://localhost:8765 (the TradingAgent-Dashboard task must be running).");
    }
  }

  async function wakeBot(btn) {
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = "Waking…";
    try {
      const r = await fetch("/api/wake", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      const j = await r.json();
      if (r.ok) {
        btn.textContent = "✓ " + (j.note || "Agent waking…");
        setTimeout(() => window.App && window.App.reload(), 5000);
      } else {
        btn.disabled = false; btn.textContent = original;
        alert(j.error || "Could not wake the agent.");
      }
    } catch (e) {
      btn.disabled = false; btn.textContent = original;
      alert("Couldn't reach the dashboard server.\nThe TradingAgent-Dashboard task must be running.");
    }
  }

  async function haltBot(btn, mode) {
    if (mode === "halt" && !confirm(
      "This flattens every open position and halts trading until you clear it from here. "
      + "Continue?")) return;
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = mode === "halt" ? "Halting…" : "Clearing…";
    try {
      const r = await fetch("/api/halt", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: mode }),
      });
      const j = await r.json();
      if (r.ok) {
        btn.textContent = "✓ " + (j.note || "Done");
        setTimeout(() => window.App && window.App.reload(), 3000);
      } else {
        btn.disabled = false; btn.textContent = original;
        alert(j.error || "Could not update the kill switch.");
      }
    } catch (e) {
      btn.disabled = false; btn.textContent = original;
      alert("Couldn't reach the dashboard server.\nThe TradingAgent-Dashboard task must be running.");
    }
  }

  /* ================================ intel =============================== */
  function renderIntel(D) {
    const el = $("intel");
    if (!el.dataset.built) {
      el.dataset.built = "1";
      el.innerHTML = `
        <div class="card-head"><span class="card-title"><span class="accent-tick"></span>Market intel</span>
          <div class="chart-tabs" id="intelTabs">
            <button class="chart-tab" data-t="calendar">Calendar</button>
            <button class="chart-tab" data-t="headlines">Headlines</button>
          </div><span class="spacer"></span>
          <span class="card-note" id="intelNote"></span></div>
        <div id="intelBody"></div>`;
      $("intelTabs").querySelectorAll(".chart-tab").forEach((b) => {
        b.onclick = () => { S.intelTab = b.dataset.t; renderIntel(window.DATA); };
      });
    }
    $("intelTabs").querySelectorAll(".chart-tab").forEach((b) =>
      b.classList.toggle("active", b.dataset.t === S.intelTab));
    const body = $("intelBody");
    if (S.intelTab === "calendar") {
      $("intelNote").textContent = "ForexFactory · next 48h";
      body.innerHTML = (D.events || []).slice(0, 9).map((e) => {
        const imp = String(e.impact || "low").toLowerCase();
        const lbl = e.impact === "Holiday" ? "HOLIDAY" : String(e.impact || "").toUpperCase();
        return `<div class="event-row">${e.top_tier ? "🚨 " : ""}<span class="impact-tag impact-${U.esc(imp)}">${U.esc(lbl)}</span>
          <span class="t">${U.esc(e.title)}</span><span class="when">${U.esc(U.countdown(e.when))}</span></div>`;
      }).join("") || `<div class="empty-state"><span class="glyph">◷</span>No notable events in the next 48 hours.</div>`;
    } else {
      $("intelNote").textContent = "CNBC market wire";
      body.innerHTML = (D.headlines || []).slice(0, 9).map((h) =>
        `<div class="headline-row">${U.esc(h.title)}</div>`).join("")
        || `<div class="empty-state"><span class="glyph">◌</span>No headlines cached yet.</div>`;
    }
  }

  /* ================================ lab ================================= */
  const BT_FALLBACK = {
    GOLD: { name: "Gold", sector: "Metals" }, SILVER: { name: "Silver", sector: "Metals" },
    COPPER: { name: "Copper", sector: "Metals" }, OIL: { name: "Crude Oil", sector: "Energy" },
    NQ: { name: "Nasdaq 100", sector: "Indices" }, ES: { name: "S&P 500", sector: "Indices" },
    YM: { name: "Dow Jones", sector: "Indices" }, EURUSD: { name: "EUR/USD", sector: "Forex" },
    USDJPY: { name: "USD/JPY", sector: "Forex" }, BTC: { name: "Bitcoin", sector: "Crypto" },
  };

  function renderLab(D) {
    const el = $("lab");
    if (el.dataset.built) { return; }
    el.dataset.built = "1";
    const cat = (D.backtest_assets && Object.keys(D.backtest_assets).length) ? D.backtest_assets : BT_FALLBACK;
    const bySector = {};
    Object.entries(cat).forEach(([k, v]) => (bySector[v.sector] = bySector[v.sector] || []).push([k, v]));
    el.innerHTML = `
      <div class="card-head"><span class="card-title"><span class="accent-tick"></span>Backtest lab</span>
        <span class="spacer"></span>
        <span class="card-note">tests the CURRENT strategy (incl. agent refinements) on real history · free 1-min data reaches ~29 days back</span></div>
      <div class="chip-groups">${Object.entries(bySector).map(([sec, list]) => `
        <div class="chip-group"><span class="sector">${U.esc(sec)}</span>
          ${list.map(([k, v]) => `<button class="chip${S.lab.sel.has(k) ? " sel" : ""}" data-k="${U.esc(k)}">${U.esc(v.name)}</button>`).join("")}
        </div>`).join("")}
      </div>
      <div class="lab-controls">
        <label>Session <select id="btSession">
          <option value="both">Both sessions</option><option value="asia">Asia only</option><option value="newyork">New York only</option>
        </select></label>
        <label>Period <select id="btDays">
          <option value="7">Last 7 days</option><option value="14">Last 14 days</option><option value="29" selected>Last 29 days (max)</option>
        </select></label>
        <button class="btn btn-primary" id="btRun">▶ Run backtest</button>
      </div>
      <div class="bt-status" id="btStatus"></div>
      <div id="btResults"></div>
      <div id="btHistory"></div>`;
    el.querySelectorAll(".chip").forEach((c) => {
      c.onclick = () => {
        const k = c.dataset.k;
        if (S.lab.sel.has(k)) S.lab.sel.delete(k); else S.lab.sel.add(k);
        c.classList.toggle("sel");
      };
    });
    $("btSession").value = S.lab.session;
    $("btSession").onchange = (e) => { S.lab.session = e.target.value; };
    $("btDays").onchange = (e) => { S.lab.days = Number(e.target.value); };
    $("btRun").onclick = () => runBacktest($("btRun"));
    loadBtHistory();
    // resume an in-flight backtest if the page was reloaded mid-run
    fetch("backtests/status.json?t=" + Date.now()).then((r) => r.json())
      .then((s) => { if (s.running) pollBacktest(); else if (s.result) loadResult(s.result); })
      .catch(() => {});
  }

  async function runBacktest(btn) {
    if (!S.lab.sel.size) { alert("Pick at least one asset."); return; }
    btn.disabled = true;
    try {
      const r = await fetch("/api/backtest", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assets: [...S.lab.sel], session: S.lab.session, days: S.lab.days }),
      });
      const j = await r.json();
      if (!r.ok) { alert(j.error || "could not start"); btn.disabled = false; return; }
      pollBacktest();
    } catch (e) {
      alert("Couldn't reach the dashboard server.\nOpen the dashboard via http://localhost:8765 (the TradingAgent-Dashboard task must be running).");
      btn.disabled = false;
    }
  }

  function pollBacktest() {
    clearInterval(S.lab.polling);
    S.lab.polling = setInterval(async () => {
      try {
        const r = await fetch("backtests/status.json?t=" + Date.now());
        const st = await r.json();
        const box = $("btStatus");
        if (box) box.innerHTML = `${U.esc(st.msg)}<div class="prog"><div style="width:${st.pct || 0}%"></div></div>`;
        if (!st.running) {
          clearInterval(S.lab.polling);
          const btn = $("btRun");
          if (btn) btn.disabled = false;
          if (st.result) loadResult(st.result);
          if (st.error && box) box.innerHTML = `<span class="neg">${U.esc(st.msg)}</span>`;
        }
      } catch (e) { /* server not up */ }
    }, 2000);
  }

  async function loadResult(id) {
    try {
      const r = await fetch(`backtests/${id}.json?t=` + Date.now());
      S.lab.lastResult = await r.json();
      renderBtResult();
      loadBtHistory();
    } catch (e) {}
  }

  const TRASH_SVG = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/></svg>`;

  async function loadBtHistory() {
    try {
      const r = await fetch("backtests/index.json?t=" + Date.now());
      const idx = await r.json();
      const el = $("btHistory");
      if (!el) return;
      if (!idx.length) { el.innerHTML = ""; return; }
      el.innerHTML = `<div class="bt-section-title">Previous runs</div>` + idx.map((x) => `
        <div class="hist-item bt-hist-item" data-id="${U.esc(x.id)}">
          <button class="hist-del" type="button" title="Delete this run" aria-label="Delete this backtest run">${TRASH_SVG}</button>
          <span><a class="bt-link" data-id="${U.esc(x.id)}">${U.esc(x.created.slice(0, 16).replace("T", " "))}</a>
          — ${U.esc(x.assets.join(", "))} · ${U.esc(x.session)} · ${x.days}d · ${x.trades} trades</span>
          <b class="mono ${U.cls(x.total_pnl)}">${U.money(x.total_pnl, true)}</b></div>`).join("");
      el.querySelectorAll(".bt-link").forEach((a) => { a.onclick = () => loadResult(a.dataset.id); });
      el.querySelectorAll(".hist-del").forEach((btn) => { btn.onclick = (e) => deleteBtRun(e, btn.closest(".bt-hist-item").dataset.id); });
    } catch (e) {}
  }

  async function deleteBtRun(e, id) {
    e.stopPropagation();
    const row = e.currentTarget.closest(".bt-hist-item");
    if (row) row.style.pointerEvents = "none";
    try {
      const r = await fetch("/api/backtest/delete", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
      });
      if (!r.ok) { if (row) row.style.pointerEvents = ""; return; }
      if (S.lab.lastResult && S.lab.lastResult.id === id) {
        S.lab.lastResult = null;
        const results = $("btResults");
        if (results) results.innerHTML = "";
      }
      loadBtHistory();
    } catch (err) {
      if (row) row.style.pointerEvents = "";
    }
  }

  function btKpi(label, value, cls) {
    return `<div class="bt-kpi"><div class="l">${label}</div><div class="v ${cls || ""}">${value}</div></div>`;
  }

  function renderBtResult() {
    const R = S.lab.lastResult, el = $("btResults");
    if (!R || !el) return;
    const s = R.stats;
    const retPct = (100 * (R.final_balance - R.starting_balance) / R.starting_balance).toFixed(2);
    el.innerHTML = `
      <div class="card-note" style="margin:12px 0 4px">Result <b class="mono">${U.esc(R.id)}</b> —
        ${U.esc((R.params.assets || []).join(", "))} · ${U.esc(R.params.session)} · ${R.sessions_tested} sessions ·
        filters: range ${R.params.strategy.range_atr_min}–${R.params.strategy.range_atr_max}× ATR, cutoff ${R.params.strategy.entry_cutoff_minutes}m</div>
      <div class="bt-kpis">
        ${btKpi("Total P&L", U.money(s.total_pnl, true) + ` <span style="font-size:12px">(${retPct}%)</span>`, U.cls(s.total_pnl))}
        ${btKpi("Trades", s.total_trades)}
        ${btKpi("Win rate", s.win_rate != null ? s.win_rate + "%" : "—")}
        ${btKpi("Profit factor", s.profit_factor ?? "—")}
        ${btKpi("Avg R", s.avg_r ?? "—")}
        ${btKpi("Max drawdown", U.money(s.max_drawdown), s.max_drawdown ? "neg" : "")}
        ${btKpi("Best day", U.money(R.best_day, true), "pos")}
        ${btKpi("Worst day", U.money(R.worst_day, true), "neg")}
      </div>
      <div class="bt-section-title">Backtest equity curve</div>
      <div class="chart-shell bt-canvas" id="btEquityShell"></div>
      <div class="bt-section-title">R-multiple distribution</div>
      <div class="chart-shell bt-canvas-sm" id="btRShell"></div>
      ${R.mc ? `
        <div class="bt-section-title">Monte Carlo — luck envelope <span class="card-note" style="text-transform:none;letter-spacing:0">1,000 re-orderings · dark band 25–75% · light 5–95% · gold median</span></div>
        <div class="chart-shell bt-canvas" id="btMcShell"></div>
        <div class="bt-kpis" style="margin-top:14px">
          ${btKpi("Median outcome", U.money(R.mc.stats.median_final))}
          ${btKpi("Unlucky (P5)", U.money(R.mc.stats.p5_final))}
          ${btKpi("Lucky (P95)", U.money(R.mc.stats.p95_final))}
          ${btKpi("Odds of profit", R.mc.stats.prob_profit_pct + "%")}
          ${btKpi("Typical max DD", R.mc.stats.median_max_dd_pct + "%")}
          ${btKpi("Bad-luck max DD", R.mc.stats.p95_max_dd_pct + "%")}
        </div>
        <div class="bt-section-title">Final balance distribution (1,000 runs)</div>
        <div class="chart-shell bt-canvas-sm" id="btFinalsShell"></div>`
      : `<div class="bt-note">Monte Carlo needs at least 5 trades.</div>`}`;

    const T = Ch.tokens();
    const eqPts = (R.equity_curve || []).map((p, i) => ({ x: i, y: p.balance }));
    new Ch.LineChart($("btEquityShell"), {
      points: eqPts, color: (R.final_balance >= R.starting_balance ? T.up : T.down),
      area: true, baseline: R.starting_balance,
      xFmt: (v) => "trade " + Math.round(v), yFmt: (v) => U.moneyCompact(v),
      tipTitle: (p) => "Trade " + p.x,
      tipRows: (p) => [["Balance", U.money(p.y)]],
    });
    const bins = [-1.5, -1, -0.5, 0, 0.5, 1, 1.5, 2, 2.5];
    const counts = new Array(bins.length).fill(0);
    (R.r_values || []).forEach((v) => {
      let i = bins.findIndex((b) => v < b); if (i === -1) i = bins.length - 1;
      counts[i]++;
    });
    const rLabels = ["≤−1.5R", "−1R", "−0.5R", "0R", "+0.5R", "+1R", "+1.5R", "+2R", "≥+2.5R"];
    new Ch.BarChart($("btRShell"), {
      bars: counts.map((v, i) => ({ label: rLabels[i], value: (i < 3 ? -v : v), n: v })),
      diverging: true, yFmt: (v) => String(Math.abs(Math.round(v))),
      tipTitle: (b) => b.label + " bucket", tipRows: (b) => [["Trades", String(b.n)]],
    });
    if (R.mc) {
      new Ch.BandChart($("btMcShell"), { bands: R.mc.bands, baseline: R.starting_balance });
      const fh = R.mc.finals_hist;
      new Ch.BarChart($("btFinalsShell"), {
        bars: fh.counts.map((v, i) => ({
          label: i === 0 ? U.moneyCompact(fh.lo) : (i === fh.counts.length - 1 ? U.moneyCompact(fh.hi) : ""),
          value: v,
        })),
        color: T.gold, yFmt: (v) => String(Math.round(v)),
        tipTitle: () => "Simulated final balances",
        tipRows: (b, i) => [["Runs", String(b.value)]],
      });
    }
  }

  /* =============================== archive ============================== */
  function renderArchive(D, M) {
    const el = $("archive");
    const trades = M.trades.slice().reverse();
    const rows = trades.map((t) => {
      const r = t.reflection || {};
      const open = S.openTrades.has(String(t.trade_id));
      return `
      <tr class="trade-row" data-id="${t.trade_id}">
        <td class="mono">#${t.trade_id}</td><td class="mono">${U.esc(t.day_key)}</td>
        <td>${U.esc(t.session)}</td><td><b>${U.esc(t.asset)}</b></td>
        <td><span class="side-tag ${t.direction === "LONG" ? "side-long" : "side-short"}">${t.direction}</span></td>
        <td class="mono">${U.fmtPrice(t.entry_price)} → ${U.fmtPrice(t.exit_price)}</td>
        <td>${U.esc(t.exit_reason)}</td>
        <td class="num"><span class="r-chip ${t.r_multiple > 0 ? "pos" : t.r_multiple < 0 ? "neg" : "flat"}">${(t.r_multiple > 0 ? "+" : "") + t.r_multiple}R</span></td>
        <td class="num mono ${U.cls(t.pnl)}"><b>${U.money(t.pnl, true)}</b></td>
        <td class="num mono">${U.fmtDurMin(t.duration_min)}</td>
      </tr>
      <tr class="detail-row" data-for="${t.trade_id}" ${open ? "" : "hidden"}><td colspan="10"><div class="detail-inner">
        <div class="sec"><b>Thinking</b> — ${U.esc(r.thinking)}</div>
        <div class="sec"><b class="pos">Went well</b> — ${U.esc((r.went_well || []).join(" "))}</div>
        <div class="sec"><b class="neg">Improve</b> — ${U.esc((r.improve || []).join(" "))}</div>
        ${(t.context && t.context.headlines && t.context.headlines.length)
          ? `<div class="sec"><b>At entry</b> — ${U.esc(t.context.headlines.join(" · "))}</div>` : ""}
      </div></td></tr>`;
    }).join("");
    el.innerHTML = `
      <div class="card-head"><span class="card-title"><span class="accent-tick"></span>Trade archive</span>
        <span class="spacer"></span><span class="card-note">click a trade for its full reflection</span></div>
      <div class="table-wrap"><table>
        <tr><th>#</th><th>Date</th><th>Session</th><th>Asset</th><th>Side</th>
            <th>Entry → Exit</th><th>Exit via</th><th class="num">R</th><th class="num">P&amp;L</th><th class="num">Held</th></tr>
        ${rows || `<tr><td colspan="10"><div class="empty-state"><span class="glyph">◇</span>No trades yet — the archive fills as the agent trades.</div></td></tr>`}
      </table></div>`;
    el.querySelectorAll(".trade-row").forEach((tr) => {
      tr.onclick = () => {
        const id = tr.dataset.id;
        const d = el.querySelector(`.detail-row[data-for="${id}"]`);
        const show = d.hidden;
        d.hidden = !show;
        if (show) S.openTrades.add(id); else S.openTrades.delete(id);
      };
    });
  }

  /* =============================== lessons ============================== */
  function renderLessons(D) {
    $("lessons").innerHTML = `
      <div class="card-head"><span class="card-title"><span class="accent-tick"></span>Latest lessons</span></div>
      ${(D.lessons || []).map((l) => `
        <div class="lesson-item"><div class="t">${U.esc((l.t || "").replace("T", " ").slice(0, 16))} UTC</div>
        <div class="x">${U.esc(l.text)}</div></div>`).join("")
        || `<div class="empty-state"><span class="glyph">✎</span>Lessons appear after the first trades.</div>`}`;
  }

  /* =============================== footer =============================== */
  function renderFooter(D) {
    const r = D.risk_config || {};
    $("footer").innerHTML = `
      RISK ${U.esc(String(r.risk_per_trade_pct ?? "—"))}% / TRADE<span class="sep">·</span>
      DAILY STOP −${U.esc(String(r.daily_loss_limit_pct ?? "—"))}%<span class="sep">·</span>
      MAX ${U.esc(String(r.max_trades_per_session ?? "—"))}/SESSION, ${U.esc(String(r.max_trades_per_day ?? "—"))}/DAY<span class="sep">·</span>
      DATA REFRESHES EVERY 60S<span class="sep">·</span>
      SNAPSHOT ${U.esc(D.generated_local || "")}`;
  }

  /* ============================ health model ============================ */
  function healthOf(D) {
    const replay = (D.bot_status || "").startsWith("REPLAY");
    const ageMin = (Date.now() - new Date(D.generated_utc)) / 60000;
    const wins = U.sessionWindows(D.schedule);
    const now = new Date();
    const liveWin = wins.find((w) => w.open <= now && now < w.close) || null;
    const holiday = D.bot_state === "HOLIDAY" && D.holiday_until && new Date(D.holiday_until) > new Date();
    window.HOLIDAY_TODAY = holiday;
    const asleep = !D.halted_reason && !replay && !holiday && !!liveWin
      && (D.bot_state === "ASLEEP" || ageMin > 3);
    let pill, stateLabel, working = false;
    if (D.halted_reason) {
      pill = `<span class="pill pill-halt"><span class="dot"></span>Halted</span>`;
      stateLabel = "Halted — risk guardrail hit";
    } else if (holiday) {
      pill = `<span class="pill pill-idle">🏖 Holiday</span>`;
      stateLabel = "Standing down — market holiday";
    } else if (asleep) {
      pill = `<span class="pill pill-warn"><span class="dot"></span>Asleep</span>`;
      stateLabel = "Asleep — data feed dropped";
    } else if (ageMin > 6) {
      pill = `<span class="pill pill-idle">Idle</span>`;
      stateLabel = "Idle — between sessions";
    } else {
      pill = `<span class="pill pill-live"><span class="dot"></span>Live</span>`;
      stateLabel = "Actively analysing the market";
      working = true;
    }
    return { replay, ageMin, liveWin, liveLabel: liveWin && liveWin.label, holiday, asleep, pill, stateLabel, working };
  }

  /* ============================== render all ============================ */
  function render(D) {
    if (!D) return;
    const M = U.derive(D);
    const health = healthOf(D);
    document.title = `${U.money(D.balance)} · Trading Agent`;
    $("brandSub").textContent = brandSubText(D);
    renderTopbar(D, M, health);
    renderBanners(D, health);
    renderHero(D, M, health);
    renderPositions(D, M);
    renderMarket(D, M);
    renderMetrics(D, M);
    renderEquity(D, M);
    renderPerf(D, M);
    renderAgent(D, M, health);
    renderSuggest(D);
    renderIntel(D);
    renderLab(D);
    renderArchive(D, M);
    renderLessons(D);
    renderFooter(D);
  }

  window.C = { render, tickClock, renderTopbar, healthOf };
})();
