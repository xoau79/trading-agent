/* demo.js — deterministic sample data so the dashboard can be previewed
   (?demo=1) without a running bot. Never loaded in normal operation. */
(function () {
  "use strict";
  // deterministic PRNG so the demo looks the same on every load
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  window.makeDemoData = function () {
    const rnd = mulberry32(1337);
    const now = new Date();
    const iso = (d) => d.toISOString().replace(".000Z", "+00:00").replace("T", " ").replace("Z", "+00:00");

    /* candles: 240 one-minute bars per asset — mean-reverting drift with
       occasional impulse bursts so the tape has realistic texture */
    function walk(px, vol, n) {
      const out = [];
      let drift = 0;
      for (let i = 0; i < n; i++) {
        const t = Math.floor(now.getTime() / 60000) * 60 - (n - i) * 60;
        if (rnd() < 0.04) drift += (rnd() - 0.5) * vol * 2.2;      // impulse
        drift = drift * 0.82 + (rnd() - 0.5) * vol * 0.3;
        const o = px;
        px = px + drift + (rnd() - 0.5) * vol * 1.5;
        const c = px;
        const h = Math.max(o, c) + rnd() * vol * 0.6;
        const l = Math.min(o, c) - rnd() * vol * 0.6;
        out.push({ t, o: +o.toFixed(2), h: +h.toFixed(2), l: +l.toFixed(2), c: +c.toFixed(2) });
      }
      return out;
    }
    const candles = {
      GOLD: walk(3341, 1.0, 240),
      NQ: walk(22740, 8.5, 240),
      ES: walk(6270, 2.1, 240),
    };

    /* trades: ~26 across the last 3 weeks; last two land inside today's candles */
    const assets = ["GOLD", "NQ", "ES"];
    const starting = 10000;
    let balance = starting;
    const trades = [];
    const equity = [{ t: iso(new Date(now - 21 * 86400e3)), balance }];
    let id = 1;
    // fixed outcome weave (~57% winners) so the demo reads the same every load:
    // a believable, modestly profitable book rather than a lucky random draw
    const PATTERN = "WLWWLWLWWLWWLLWWLWWLWLWWLLWWLW";
    let seq = 0;
    for (let d = 20; d >= 1; d--) {
      const day = new Date(now - d * 86400e3);
      if ([0, 6].includes(day.getUTCDay())) continue;
      const nT = rnd() < 0.16 ? 0 : 1 + Math.floor(rnd() * 2.6);
      for (let k = 0; k < nT; k++) {
        const a = assets[Math.floor(rnd() * 3)];
        const win = PATTERN[seq++ % PATTERN.length] === "W";
        const r = win ? (rnd() < 0.72 ? 2 : +(0.5 + rnd()).toFixed(2))
                      : -(rnd() < 0.88 ? 1 : +(1 + rnd() * 0.3).toFixed(2));
        const risk = Math.round(balance * 0.007);
        const pnl = +(r * risk + (rnd() - 0.5) * 6).toFixed(2);
        balance = +(balance + pnl).toFixed(2);
        const base = a === "GOLD" ? 3300 : a === "NQ" ? 22500 : 6200;
        const entry = +(base * (0.99 + rnd() * 0.02)).toFixed(2);
        const dirLong = rnd() < 0.55;
        const move = entry * 0.004 * (r / 2);
        const exit = +(entry + (dirLong ? move : -move)).toFixed(2);
        const et = new Date(day); et.setUTCHours(1 + Math.floor(rnd() * 4), Math.floor(rnd() * 60));
        const dur = 12 + Math.floor(rnd() * 130);
        const xt = new Date(et.getTime() + dur * 60000);
        trades.push({
          trade_id: id++, asset: a, direction: dirLong ? "LONG" : "SHORT",
          entry_time: iso(et), entry_price: entry, units: +(risk / (entry * 0.005)).toFixed(3),
          risk_usd: risk, stop: +(entry * (dirLong ? 0.995 : 1.005)).toFixed(2),
          target: +(entry * (dirLong ? 1.01 : 0.99)).toFixed(2),
          exit_time: iso(xt), exit_price: exit,
          exit_reason: win ? "target" : (rnd() < 0.8 ? "stop" : "time"),
          pnl, r_multiple: +r.toFixed(2), balance_after: balance,
          session: rnd() < 0.45 ? "asia" : "newyork",
          day_key: day.toISOString().slice(0, 10), duration_min: dur,
          mfe: +(Math.max(0, r) + rnd() * 0.4).toFixed(2), mae: +(rnd() * 0.9).toFixed(2),
          context: { range_low: +(entry * 0.997).toFixed(2), range_high: +(entry * 1.003).toFixed(2), range_atr_ratio: +(0.5 + rnd()).toFixed(2), tv_rating: "BUY" },
          reflection: {
            thinking: "Mechanical ORB entry: a 1-minute candle closed beyond the opening range, which by the rules signals an entry with the stop at the far side of the range and a 2R target.",
            went_well: ["Followed the system exactly — entry, stop, size and target were all rule-based."],
            improve: [win ? "Little to fault — a textbook trade for this system." : "A normal, controlled 1R loss — the cost of doing business."],
          },
        });
        equity.push({ t: iso(xt), balance });
      }
    }
    // two of today's trades sit inside the candle window so markers show;
    // direction is chosen from the actual tape so price, P&L and streak agree
    const gc = candles.GOLD;
    [[38, 84], [128, 176]].forEach(([i0, i1]) => {
      const e = gc[i0], x = gc[i1];
      const dirLong = x.c >= e.o;
      const risk = Math.round(balance * 0.007);
      const units = +(risk / (e.o * 0.0016)).toFixed(3);
      const pnl = +(Math.abs(x.c - e.o) * units).toFixed(2);
      const r = +(pnl / risk).toFixed(2);
      balance = +(balance + pnl).toFixed(2);
      trades.push({
        trade_id: id++, asset: "GOLD", direction: dirLong ? "LONG" : "SHORT",
        entry_time: iso(new Date(e.t * 1000)), entry_price: e.o,
        units, risk_usd: risk,
        stop: +(e.o * (dirLong ? 0.9984 : 1.0016)).toFixed(2),
        target: +(e.o * (dirLong ? 1.0032 : 0.9968)).toFixed(2),
        exit_time: iso(new Date(x.t * 1000)), exit_price: x.c,
        exit_reason: r >= 1.9 ? "target" : "time", pnl, r_multiple: r,
        balance_after: balance, session: "newyork",
        day_key: now.toISOString().slice(0, 10), duration_min: Math.round((x.t - e.t) / 60),
        mfe: +(r + 0.3).toFixed(2), mae: 0.4,
        context: { range_low: +(e.o * 0.997).toFixed(2), range_high: +(e.o * 1.003).toFixed(2), range_atr_ratio: 1.2, tv_rating: "BUY" },
        reflection: { thinking: "Breakout beyond the opening range with 1.2× ATR width — rules said go.", went_well: ["Clean fill, no chase."], improve: ["Textbook trade for this system."] },
      });
      equity.push({ t: iso(new Date(x.t * 1000)), balance });
    });

    const wins = trades.filter((t) => t.pnl > 0), losses = trades.filter((t) => t.pnl < 0);
    const gw = wins.reduce((a, t) => a + t.pnl, 0), gl = -losses.reduce((a, t) => a + t.pnl, 0);
    let peak = starting, maxdd = 0;
    equity.forEach((p) => { peak = Math.max(peak, p.balance); maxdd = Math.max(maxdd, peak - p.balance); });
    const perAsset = {};
    trades.forEach((t) => {
      const a = perAsset[t.asset] = perAsset[t.asset] || { trades: 0, wins: 0, pnl: 0 };
      a.trades++; if (t.pnl > 0) a.wins++; a.pnl = +(a.pnl + t.pnl).toFixed(2);
    });

    const dayTrades = trades.filter((t) => t.day_key === now.toISOString().slice(0, 10));
    const feedKinds = [
      ["info", "Session risk check passed — balance above daily stop, all caps clear."],
      ["assessment", "GOLD 20-EMA slope positive on 15m — bias shifting bullish."],
      ["range", "GOLD opening range set: 3,338.4 – 3,343.1 (1.18× ATR) — inside my tradeable band."],
      ["skipped", "NQ breakout printed but spread widened past my limit — standing aside."],
      ["entry", "LONG GOLD @ 3,343.6 — 1-min close above the range. Stop 3,338.2, target 3,354.4, risking 1.0%."],
      ["manage", "GOLD +1.1R and holding above VWAP — leaving the stop untouched, letting the target work."],
      ["filtered", "ES opening range 3.4× ATR — too wide to trust, filtered for the session."],
      ["exit", "GOLD target filled @ 3,354.4 — +2.0R banked. That's the system working as designed."],
      ["assessment", "NQ consolidating in a 0.3% band — no edge either side, patience."],
      ["suggestion", "Proposing entry_cutoff_minutes 0 → 30: late-session entries are underperforming (-0.4R avg over 12 trades)."],
      ["info", "News desk: FOMC minutes in 3h 40m — will flatten 5 min before if anything is open."],
      ["manage", "SHORT GOLD probe -0.6R — stop is doing its job, no intervention."],
      ["exit", "Stopped on the GOLD short @ 3,349.9 — -1.0R, contained exactly to plan."],
      ["range", "NQ range set: 22,712 – 22,758 (0.9× ATR) — hunting a breakout either side."],
      ["info", "Tokyo volume tapering — tightening my expectations for follow-through."],
      ["assessment", "GOLD bid resilience at the range low suggests absorption — watching for a sweep."],
      ["entry", "LONG GOLD @ 3,346.1 — second confirming close beyond range. Stop 3,341.0, 2R target."],
      ["manage", "GOLD +0.8R — moving nothing; the math needs full winners."],
      ["info", "Data feed healthy · 3 assets streaming · latency nominal."],
      ["exit", "Session-end flatten: GOLD +1.3R banked ahead of the close."],
    ];
    const feed = feedKinds.map((f, i) => ({
      t: new Date(now - (feedKinds.length - i) * 7 * 60000).toISOString().slice(0, 19),
      kind: f[0], icon: "", text: f[1],
    })).reverse();

    return {
      generated_utc: new Date(now - 28000).toISOString().slice(0, 19) + "+00:00",
      generated_local: now.toLocaleString("en-AU", { timeZone: "Australia/Sydney", hour12: false }) + " Sydney",
      bot_status: "GOLD: managing LONG (+1.1R); NQ: hunting breakout; ES: standing aside (filter)",
      bot_state: "LIVE", holiday_until: null,
      balance, starting_balance: starting,
      day_pnl: +dayTrades.reduce((a, t) => a + t.pnl, 0).toFixed(2),
      session: "newyork", trades_this_session: 2, trades_today: dayTrades.length,
      caps: { per_session: 4, per_day: 8 },
      halted_reason: null, benched: {},
      open_positions: {
        GOLD: {
          asset: "GOLD", direction: "LONG", entry_time: iso(new Date((gc[205].t) * 1000)),
          entry_price: gc[205].o, units: 14.2, risk_usd: 105,
          stop: +(gc[205].o - 5.2).toFixed(2), target: +(gc[205].o + 10.4).toFixed(2),
          trade_id: id,
        },
      },
      assets_stage: {
        GOLD: { stage: "hunting", bias: "bullish", range_low: 3338.4, range_high: 3343.1, range_atr_ratio: 1.18 },
        NQ: { stage: "hunting", bias: "consolidation", range_low: 22712, range_high: 22758, range_atr_ratio: 0.9 },
        ES: { stage: "filtered", bias: "bearish", filter_reason: "range 3.4× ATR — too wide to trust" },
      },
      candles,
      equity_curve: equity,
      stats: {
        total_trades: trades.length, wins: wins.length, losses: losses.length,
        win_rate: +(100 * wins.length / trades.length).toFixed(1),
        profit_factor: +(gw / gl).toFixed(2),
        avg_win: +(gw / wins.length).toFixed(2), avg_loss: +(-gl / losses.length).toFixed(2),
        avg_r: +(trades.reduce((a, t) => a + t.r_multiple, 0) / trades.length).toFixed(2),
        total_pnl: +(balance - starting).toFixed(2), max_drawdown: +maxdd.toFixed(2),
        per_asset: perAsset,
      },
      trades,
      events: [
        { title: "FOMC Meeting Minutes", impact: "High", top_tier: true, when: new Date(now.getTime() + 3.7 * 3600e3).toISOString() },
        { title: "Unemployment Claims", impact: "Medium", top_tier: false, when: new Date(now.getTime() + 9 * 3600e3).toISOString() },
        { title: "Non-Farm Employment Change", impact: "High", top_tier: true, when: new Date(now.getTime() + 26 * 3600e3).toISOString() },
        { title: "ISM Services PMI", impact: "Medium", top_tier: false, when: new Date(now.getTime() + 28 * 3600e3).toISOString() },
        { title: "Bank Holiday — Independence Day", impact: "Holiday", top_tier: false, when: new Date(now.getTime() + 40 * 3600e3).toISOString() },
      ],
      headlines: [
        { title: "S&P 500 notches a fresh record close as megacap tech extends its run" },
        { title: "Gold steadies near $3,340 with FOMC minutes on deck" },
        { title: "Treasury yields slip as traders price two cuts by December" },
        { title: "Oil edges higher after larger-than-expected inventory draw" },
        { title: "Dollar index softens for a third session ahead of payrolls" },
        { title: "Nasdaq futures flat as chipmakers digest export-rule headlines" },
      ],
      lessons: [
        { t: new Date(now - 1 * 86400e3).toISOString().slice(0, 19), text: "[newyork review] 2 trades, +212.40 USD, avg +0.50R. Winners paid for the probe losses — the math only works with full 2R targets." },
        { t: new Date(now - 2 * 86400e3).toISOString().slice(0, 19), text: "[GOLD LOSS -1.00R] Stopped in 9 min — a fast fakeout. If these cluster, consider requiring a second confirming close beyond the range." },
        { t: new Date(now - 3 * 86400e3).toISOString().slice(0, 19), text: "[asia review] No trades — filters kept the system flat. Patience is a position." },
        { t: new Date(now - 4 * 86400e3).toISOString().slice(0, 19), text: "[NQ WIN +2.00R] Price reached 2.2R before the fill — a textbook breakout with follow-through." },
      ],
      risk_config: { risk_per_trade_pct: 1.0, daily_loss_limit_pct: 3.0, max_trades_per_session: 4, max_trades_per_day: 8 },
      tv_widgets: {},
      agent: {
        feed,
        assessments: { GOLD: "bullish", NQ: "consolidation", ES: "bearish" },
        suggestions: {
          pending: [{
            id: "sugg-demo-1", param: "strategy.entry_cutoff_minutes", from: 0, to: 30,
            why: "Late-session entries have too little time to reach 2R: the last 12 trades opened under 30 minutes before close averaged −0.4R.",
            evidence: "12 trades · window 2026-06-05 → 2026-07-01", created: "2026-07-01", status: "pending",
          }],
          history: [
            { param: "strategy.range_atr_min", from: 0.3, to: 0.4, status: "auto-applied", day: "2026-06-24" },
            { param: "strategy.tv_confluence_enabled", from: false, to: true, status: "approved", day: "2026-06-18" },
          ],
          used: 6, budget: 15,
        },
        overrides: {},
      },
      schedule: {
        asia: { label: "Asian Session", open_tz: "Asia/Tokyo", open_time: "10:00", duration_minutes: 240 },
        newyork: { label: "New York Session", open_tz: "America/New_York", open_time: "09:30", duration_minutes: 390 },
      },
      effective_strategy: { opening_range_minutes: 15, target_r_multiple: 2.0 },
      backtest_assets: {},
    };
  };
})();
