"""נתוני דוגמה סינתטיים בלבד - לא נתוני שוק אמיתיים. הטיקרים SMP### בדויים."""
import numpy as np, datetime as dt
from .base import DataProvider, Bars

class SampleProvider(DataProvider):
    is_sample = True

    def __init__(self, n=60, seed=7):
        self.rng = np.random.default_rng(seed)
        self.n = n
        self._u = []
        for i in range(n):
            self._u.append(dict(
                ticker=f"SMP{i:03d}", name=f"Sample Corp {i} (דוגמה)",
                market_cap=float(self.rng.choice([5e8, 1.5e9, 3e9, 8e9, 5e10])),
                price=0.0, avg_volume=float(self.rng.choice([2e5, 8e5, 3e6])),
                is_etf=bool(i % 17 == 0), is_common_stock=True))
        self._cache = {}

    def _gen(self, i, days):
        r = np.random.default_rng(1000 + i)
        kind = i % 6
        t = np.arange(days)
        if kind == 0:   base = 50 + 0.08 * t + 4 * np.sin(t / 7)      # עולה
        elif kind == 1: base = 90 - 0.08 * t + 4 * np.sin(t / 7)      # יורדת
        elif kind == 2: base = 40 + 4 * np.sin(t / 9)                 # אופקית
        else:           base = 30 + 0.02 * t + r.normal(0, 1, days).cumsum() * 0.4
        base = np.maximum(base + r.normal(0, 0.5, days), 11 if kind != 5 else 5)
        o = np.r_[base[0], base[:-1]] + r.normal(0, .2, days)
        c = base
        h = np.maximum(o, c) + np.abs(r.normal(0, .5, days))
        l = np.minimum(o, c) - np.abs(r.normal(0, .5, days))
        v = r.uniform(5e5, 3e6, days)
        return o, h, l, c, v

    def universe(self):
        for i, u in enumerate(self._u):
            u["price"] = float(self._gen(i, 250)[3][-1])
        return self._u

    def history(self, ticker, days):
        i = int(ticker[3:])
        o, h, l, c, v = self._gen(i, days)
        end = dt.date(2026, 1, 2)
        dates, d = [], end
        while len(dates) < days:
            if d.weekday() < 5: dates.append(d.isoformat())
            d -= dt.timedelta(days=1)
        return Bars(dates[::-1], o, h, l, c, v)
