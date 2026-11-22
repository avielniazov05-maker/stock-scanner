"""ספק חינמי: רשימת סמלים מ-NASDAQ Trader + נרות יומיים מ-yfinance (לא רשמי, עלול להיחסם).
לא נבדק מול רשת אמיתית בסביבת הפיתוח (נחסם) - יש להריץ בדיקת עשן ראשונה בעצמך (ראו README)."""
import io, re, urllib.request
import numpy as np
from .base import DataProvider, Bars

SRC = ["https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
       "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"]
# הרשימה אינה מסמנת "מניה רגילה" - מסננים לפי שם. היוריסטיקה, לא מושלמת.
NOT_COMMON = re.compile(r"warrant|right|unit|preferred|depositary|notes?\b|debenture|trust|fund|etn|acquisition corp", re.I)


class YahooFreeProvider(DataProvider):
    def __init__(self, filt, avg_volume_days=50, chunk=200):
        self.f, self.avg_days, self.chunk = filt, avg_volume_days, chunk   # avg_volume_days: TBD (settings.yaml)
        self._bars = {}

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
                out[s] = name
        return out

    def universe(self):
        import yfinance as yf
        syms = self._symbols(); tick = sorted(syms); rows = []
        for i in range(0, len(tick), self.chunk):
            part = tick[i:i + self.chunk]
            df = yf.download(part, period="2y", interval="1d", auto_adjust=False,
                             group_by="ticker", progress=False, threads=True)
            for t in part:
                try: d = df[t].dropna(subset=["Close"])
                except KeyError: continue
                if len(d) < 60: continue
                self._bars[t] = Bars([x.date().isoformat() for x in d.index], d.Open, d.High, d.Low, d.Close, d.Volume)
                price, vol = float(d.Close.iloc[-1]), float(d.Volume.iloc[-self.avg_days:].mean())
                rows.append(dict(ticker=t, name=syms[t], price=price, avg_volume=vol, market_cap=0.0,
                                 is_etf=False, is_common_stock=True))
        # שווי שוק רק לאלה שעוברים מחיר+נפח (חוסך אלפי קריאות)
        for r in rows:
            if r["price"] > self.f["min_price"] and r["avg_volume"] > self.f["min_avg_volume"]:
                try: r["market_cap"] = float(yf.Ticker(r["ticker"]).fast_info["market_cap"] or 0)
                except Exception: r["market_cap"] = 0.0     # לא ידוע = לא עובר (לא ממציאים)
        return rows

    def history(self, ticker, days):
        b = self._bars[ticker]; n = len(b)
        s = max(0, n - days)
        return Bars(b.dates[s:], b.o[s:], b.h[s:], b.l[s:], b.c[s:], b.v[s:])
