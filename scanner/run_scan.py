import json, sys, os, datetime as dt, yaml
from .providers import get_provider
from .detect import analyze
from . import alerts

LABELS = {"stage1_ascending": "שלב 1 – תעלה עולה", "stage1_descending": "שלב 1 – תעלה יורדת",
          "stage1_flat": "שלב 1 – תעלה ישרה", "stage2": "שלב 2 – תמיכה + פטיש",
          "stage3": "שלב 3 – נגיעות חוזרות", "stage4": "שלב 4 – תמיכה כפולה/משולשת"}
CHART_BARS = 120

def passes(u, f):
    return (u["market_cap"] > f["min_market_cap"] and u["price"] > f["min_price"] and
            u["avg_volume"] > f["min_avg_volume"] and not (f["common_stock_only"] and (u["is_etf"] or not u["is_common_stock"])))

def chart(bars, infos):
    n = len(bars); s = max(0, n - CHART_BARS); lines = []
    for info in infos.values():
        for seg in info.get("lines", []):
            (a, va), (b, vb) = seg; sl = (vb - va) / (b - a) if b != a else 0
            a2 = max(a, s); lines.append([a2 - s, va + sl * (a2 - a), b - s, vb])
    return dict(dates=bars.dates[s:], candles=[[round(float(x), 2) for x in r] for r in zip(bars.o[s:], bars.h[s:], bars.l[s:], bars.c[s:])],
                lines=[[round(v, 2) for v in l] for l in lines])

def main(cfg_path="config/settings.yaml", out="docs/data/results.json", db_path=None):
    cfg = yaml.safe_load(open(cfg_path)); p = cfg["params"]
    prov = get_provider(cfg["provider"]); uni = prov.universe()
    kept = [u for u in uni if passes(u, cfg["filter"])]
    results, rows = {}, {k: [] for k in LABELS}
    asof = None
    for u in kept:
        bars = prov.history(u["ticker"], p["history_days"]); asof = bars.dates[-1]
        res = analyze(bars, p)
        if not res: continue
        results[u["ticker"]] = res
        for st, info in res.items():
            fv, tv = alerts.links(u["ticker"])
            row = dict(ticker=u["ticker"], name=u["name"], **{k: v for k, v in info.items() if k != "lines"},
                       bonus=[LABELS[o] for o in res if o != st], finviz=fv, tradingview=tv,
                       chart=chart(bars, {st: info}))
            rows[st].append(row)
    for k in rows: rows[k].sort(key=lambda r: abs(r["distance_pct"]))
    doc = dict(meta=dict(generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), as_of=asof,
                         is_sample=prov.is_sample, provider=cfg["provider"], universe=len(uni), passed_filter=len(kept),
                         params=p, filter=cfg["filter"]), labels=LABELS, stages=rows)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(doc, open(out, "w"), ensure_ascii=False)
    print({k: len(v) for k, v in rows.items()}, "universe", len(uni), "passed", len(kept))
    if prov.is_sample:
        print("מצב דוגמה: לא נשלחות התראות."); return doc
    print(alerts.process(results, LABELS, db_path or cfg["alerts"]["db_path"], cfg["alerts"]["cooldown_days"]))
    return doc

if __name__ == "__main__":
    main()
