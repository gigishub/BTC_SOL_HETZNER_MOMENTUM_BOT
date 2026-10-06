"""Read-only browser dashboard: candles, trailing stop, entries/exits and the latest bot log lines.

Uses only public KuCoin candles, the strategy code and balance.csv; it never touches the API keys or places orders.
Usage: python -m bot.dashboard [--port 8080]   (listens on localhost only; reach it with an SSH tunnel)
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, render_template_string

from .balance import read as read_balance
from .config import SYMBOLS, SymbolConfig
from .data import bar_length, fetch_candles
from .signals import compute_state, decide_today

CHART_BARS = 200
WARMUP_BARS = 1500  # same history as the bot so the EMA240 matches
DRY_LOG = Path(__file__).resolve().parent.parent / "dry_run.log"
LIVE_LOG = Path(__file__).resolve().parent.parent / "trading_midnight_utc.log"

app = Flask(__name__)


def _ts(t: pd.Timestamp) -> int:
    return int(t.timestamp())


def symbol_view(cfg: SymbolConfig) -> dict:
    now = pd.Timestamp.now(tz="UTC")
    bar = bar_length(cfg.timeframe)
    raw = fetch_candles(cfg.symbol, cfg.timeframe, WARMUP_BARS, now)
    closed = raw[raw.index + bar <= now]
    d = decide_today(closed, cfg.params, bar)
    s = compute_state(closed, cfg.params)

    flips = s["in_trade"].diff().fillna(0)
    trades, open_trade = [], None
    for t, row in s.iterrows():
        if flips[t] == 1:
            open_trade = {"entry_time": t, "entry": float(row["open"])}
        elif flips[t] == -1 and open_trade:
            trades.append({**open_trade, "exit_time": t, "exit": float(row["open"])})
            open_trade = None
    if open_trade:
        trades.append(open_trade)

    tail = s.iloc[-CHART_BARS:]
    first = tail.index[0]
    markers = []
    for tr in trades:
        if tr["entry_time"] >= first:
            markers.append({"time": _ts(tr["entry_time"]), "position": "belowBar", "color": "#2ea043",
                            "shape": "arrowUp", "text": f"entry {tr['entry']:.2f}"})
        if "exit_time" in tr and tr["exit_time"] >= first:
            markers.append({"time": _ts(tr["exit_time"]), "position": "aboveBar", "color": "#f85149",
                            "shape": "arrowDown", "text": f"exit {tr['exit']:.2f}"})

    rows = []
    for tr in reversed(trades[-8:]):
        end = tr.get("exit") or float(closed["close"].iloc[-1])
        rows.append({"entry_time": str(tr["entry_time"].date()), "entry": tr["entry"],
                     "exit_time": str(tr["exit_time"].date()) if "exit_time" in tr else "open",
                     "exit": tr.get("exit"), "pnl_pct": (end / tr["entry"] - 1) * 100})

    stop = None if pd.isna(d.stop) else d.stop
    cur = trades[-1] if trades and "exit_time" not in trades[-1] else None
    return {
        "symbol": cfg.symbol,
        "status": "IN TRADE" if d.target else "FLAT",
        "event": d.event,
        "last_close": d.last_close,
        "last_close_date": str(d.last_close_time.date()),
        "stop": stop,
        "stop_dist_pct": None if stop is None else (stop / d.last_close - 1) * 100,
        "entry": cur["entry"] if cur else None,
        "entry_date": str(cur["entry_time"].date()) if cur else None,
        "signal": d.signal,
        "candles": [{"time": _ts(t), "open": r.open, "high": r.high, "low": r.low, "close": r.close}
                    for t, r in tail.iterrows()],
        "stop_line": [{"time": _ts(t), "value": float(v)} for t, v in tail["trail_sl"].items()
                      if tail["in_trade"][t] and not pd.isna(v)],
        "ema": [{"time": _ts(t), "value": float(v)} for t, v in tail["ema_trend"].items()],
        "markers": sorted(markers, key=lambda m: m["time"]),
        "trades": rows,
    }


def log_tail(path: Path, lines: int = 12, pattern: str | None = None) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(errors="replace").splitlines()
    if pattern:
        text = [ln for ln in text if re.search(pattern, ln)]
    return [ln[:220] for ln in text[-lines:]]


@app.route("/api/data")
def api_data():
    views = []
    for cfg in SYMBOLS:
        try:
            views.append(symbol_view(cfg))
        except Exception as exc:
            views.append({"symbol": cfg.symbol, "error": str(exc)})
    bal = read_balance()
    series = bal.drop_duplicates("time", keep="last") if len(bal) else bal
    return jsonify({
        "balance": bal.iloc[-1].to_dict() if len(bal) else None,
        "balance_series": [{"time": int(pd.Timestamp(t, tz="UTC").timestamp()), "value": float(v)}
                           for t, v in zip(series.get("time", []), series.get("total_usdt", []))],
        "symbols": views,
        "dry_log": log_tail(DRY_LOG),
        "live_log": log_tail(LIVE_LOG, 12, r"WARNING|ERROR|Trade|BUY|SELL|order|balance|No action|->|account value"),
        "updated": pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%d %H:%M UTC"),
    })


PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bot dashboard</title>
<script src="https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.js"></script>
<style>
 body{margin:0;padding:16px;background:#0d1117;color:#e6edf3;font:14px system-ui,sans-serif}
 h1{font-size:18px;margin:0 0 12px} h2{font-size:15px;margin:0}
 .card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin-bottom:16px}
 .head{display:flex;flex-wrap:wrap;gap:8px 24px;align-items:baseline;margin-bottom:8px}
 .k{color:#8b949e;font-size:12px} .v{font-size:15px}
 .in{color:#2ea043} .flat{color:#8b949e} .neg{color:#f85149} .pos{color:#2ea043}
 .chart{height:340px} table{border-collapse:collapse;width:100%;margin-top:8px}
 td,th{text-align:left;padding:4px 8px;border-bottom:1px solid #21262d;font-size:13px}
 pre{margin:0;white-space:pre-wrap;font-size:12px;color:#c9d1d9;overflow-x:auto}
 .legend{font-size:12px;color:#8b949e;margin-top:4px}
</style></head><body>
<h1>Bot dashboard <span class="k" id="upd"></span></h1>
<div class="card"><div class="head"><h2>Account</h2><span id="bal" class="k">no balance snapshot yet</span></div>
 <div class="chart" id="balch" style="height:200px"></div>
 <div class="legend">Total account value in USDT (free USDT + coins at last price), recorded hourly.</div></div>
<div id="root">Loading...</div>
<div class="card"><h2>Dry run log (stopped at switch day)</h2><pre id="dry"></pre></div>
<div class="card"><h2>Live run log (new bot, 00:00 UTC, filtered)</h2><pre id="live"></pre></div>
<script>
const f=(x,d=2)=>x==null?'-':Number(x).toLocaleString(undefined,{minimumFractionDigits:d,maximumFractionDigits:d});
const pc=x=>x==null?'-':`<span class="${x>=0?'pos':'neg'}">${x>=0?'+':''}${x.toFixed(1)}%</span>`;
fetch('/api/data').then(r=>r.json()).then(data=>{
 document.getElementById('upd').textContent='updated '+data.updated;
 const b=data.balance;
 if(b){document.getElementById('bal').innerHTML=`<span><span class="k">total</span><br><span class="v"><b>${f(b.total_usdt)} USDT</b></span></span>
  &nbsp; <span><span class="k">free USDT</span><br><span class="v">${f(b.free_usdt)}</span></span>
  ${Object.keys(b).filter(k=>k.endsWith('_usdt')&&!['total_usdt','free_usdt'].includes(k)).map(k=>`&nbsp; <span><span class="k">${k.replace('_usdt','').toUpperCase()}</span><br><span class="v">${f(b[k])}</span></span>`).join('')}
  &nbsp; <span class="k">as of ${b.time} UTC</span>`;
  const bc=LightweightCharts.createChart(document.getElementById('balch'),{autoSize:true,
   layout:{background:{color:'#161b22'},textColor:'#8b949e'},grid:{vertLines:{color:'#21262d'},horzLines:{color:'#21262d'}}});
  bc.addLineSeries({color:'#2ea043',lineWidth:2}).setData(data.balance_series); bc.timeScale().fitContent();}
 const root=document.getElementById('root'); root.innerHTML='';
 data.symbols.forEach((s,i)=>{
  const c=document.createElement('div'); c.className='card';
  if(s.error){c.innerHTML=`<h2>${s.symbol}</h2><div class="neg">${s.error}</div>`;root.appendChild(c);return;}
  c.innerHTML=`<div class="head"><h2>${s.symbol}</h2>
   <span class="${s.status=='FLAT'?'flat':'in'}"><b>${s.status}</b> (${s.event})</span>
   <span><span class="k">last close ${s.last_close_date}</span><br><span class="v">${f(s.last_close)}</span></span>
   <span><span class="k">entry</span><br><span class="v">${f(s.entry)} <span class="k">${s.entry_date||''}</span></span></span>
   <span><span class="k">stop-loss</span><br><span class="v">${f(s.stop)} ${s.stop_dist_pct!=null?'('+s.stop_dist_pct.toFixed(1)+'% from close)':''}</span></span>
   <span><span class="k">signal</span><br><span class="v">${s.signal}</span></span></div>
   <div class="chart" id="ch${i}"></div>
   <div class="legend">Orange = trailing stop, blue = EMA240. Entry/exit are the strategy's simulated fills at the bar open, not actual exchange fills.</div>
   <table><tr><th>Entry</th><th>Entry price</th><th>Exit</th><th>Exit price</th><th>P/L</th></tr>
   ${s.trades.map(t=>`<tr><td>${t.entry_time}</td><td>${f(t.entry)}</td><td>${t.exit_time}</td><td>${f(t.exit)}</td><td>${pc(t.pnl_pct)}</td></tr>`).join('')}</table>`;
  root.appendChild(c);
  const chart=LightweightCharts.createChart(document.getElementById('ch'+i),{autoSize:true,
   layout:{background:{color:'#161b22'},textColor:'#8b949e'},grid:{vertLines:{color:'#21262d'},horzLines:{color:'#21262d'}}});
  const cs=chart.addCandlestickSeries(); cs.setData(s.candles); cs.setMarkers(s.markers);
  chart.addLineSeries({color:'#58a6ff',lineWidth:1,priceLineVisible:false}).setData(s.ema);
  chart.addLineSeries({color:'#f0883e',lineWidth:2,lineStyle:2,priceLineVisible:false}).setData(s.stop_line);
  chart.timeScale().fitContent();
 });
 document.getElementById('dry').textContent=data.dry_log.join('\\n');
 document.getElementById('live').textContent=data.live_log.join('\\n');
}).catch(e=>{document.getElementById('root').textContent='Error: '+e});
</script></body></html>"""


@app.route("/")
def index():
    return render_template_string(PAGE)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    app.run(host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
