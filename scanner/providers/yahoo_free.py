"""ספק חינמי: רשימת סמלים מ-NASDAQ Trader + נרות יומיים מ-yfinance (לא רשמי, עלול להיחסם).
לא נבדק מול רשת אמיתית בסביבת הפיתוח (נחסם) - יש להריץ בדיקת עשן ראשונה בעצמך (ראו README)."""
import io, re, os, json, time, urllib.request
import numpy as np
from .base import DataProvider, Bars

SRC = ["https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
       "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"]
# הרשימה אינה מסמנת "מניה רגילה" - מסננים לפי שם. היוריסטיקה, לא מושלמת.
NOT_COMMON = re.compile(r"warrant|right|unit|preferred|depositary|notes?\b|debenture|trust|fund|etn|acquisition corp", re.I)


class YahooFreeProvider(DataProvider):
    def __init__(self, filt, avg_volume_days=50, chunk=200, only=None, cache_path="data/universe.json", refresh_days=7):
        self.f, self.avg_days, self.chunk = filt, avg_volume_days, chunk   # avg_volume_days: TBD (settings.yaml)
        self.cache_path, self.refresh_days = cache_path, refresh_days; self._bars = {}; self.only = set(only) if only else None

    def _symbols(self):
        out = {}
        for url in SRC:
            txt = urllib.request.urlopen(url, timeout=30).read().decode()
            lines = [l for l in txt.splitlines() if "|" in l and not l.startswith("File Creation")]
            hdr = lines[0].split("|")
            sym_c = "Symbol" if "Symbol" in hdr else "ACT Symbol"
            for l in lines[1:]:
                r = dict(zip(hdr, l.split("|")))
                if r.get("Test Issue") == "Y" or r.get("ETF") == "Y": continue
                s, name = r[sym_c], r.get("Security Name", "")
                if not re.fullmatch(r"[A-Z]{1,5}", s) or NOT_COMMON.search(name): continue
                if self.only is None or s in self.only: out[s] = name
        return out

    def _load_cache(self):
        try: c = json.load(open(self.cache_path))
        except Exception: return None
        if time.time() - c["ts"] > self.refresh_days * 86400: return None
        return c["items"]            # {ticker: {name, market_cap}}

    def _download(self, part):
        import yfinance as yf
        df = yf.download(part, period="2y", interval="1d", auto_adjust=False,
                         group_by="ticker", progress=False, threads=True)
        out = {}
        for t in part:
            try: d = df[t].dropna(subset=["Close"])
            except KeyError: continue
            if len(d) < 60: continue
            out[t] = Bars([x.date().isoformat() for x in d.index], d.Open, d.High, d.Low, d.Close, d.Volume)
        return out

    def universe(self):
        import yfinance as yf
        items = self._load_cache(); fresh = items is None
        if fresh:                                   # גילוי יקום מלא (איטי) - פעם ב-refresh_days
            items = {t: {"name": n, "market_cap": 0.0} for t, n in self._symbols().items()}
        tick = sorted(items); rows = []
        for i in range(0, len(tick), self.chunk):
            for t, b in self._download(tick[i:i + self.chunk]).items():
                self._bars[t] = b
                rows.append(dict(ticker=t, name=items[t]["name"], price=float(b.c[-1]),
                                 avg_volume=float(b.v[-self.avg_days:].mean()), market_cap=items[t]["market_cap"],
                                 is_etf=False, is_common_stock=True))
        for r in rows:        # שווי שוק: רק למי שעובר מחיר+נפח; ממטמון אם קיים
            if fresh and r["price"] > self.f["min_price"] and r["avg_volume"] > self.f["min_avg_volume"]:
                try: r["market_cap"] = float(yf.Ticker(r["ticker"]).fast_info["market_cap"] or 0)
                except Exception: r["market_cap"] = 0.0    # לא ידוע = לא עובר (לא ממציאים)
        if fresh:             # שומרים למטמון רק מי שעבר שווי שוק (עם מרווח 20% לסחף)
            keep = {r["ticker"]: {"name": r["name"], "market_cap": r["market_cap"]} for r in rows
                    if r["market_cap"] > 0.8 * self.f["min_market_cap"]}
            os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
            json.dump({"ts": time.time(), "items": keep}, open(self.cache_path, "w"), ensure_ascii=False)
        return rows

    def history(self, ticker, days):
        b = self._bars[ticker]; n = len(b)
        s = max(0, n - days)
        return Bars(b.dates[s:], b.o[s:], b.h[s:], b.l[s:], b.c[s:], b.v[s:])
