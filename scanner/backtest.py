"""Backtest בלי הטיית הצצה: בכל יום t הסורק מקבל רק נרות 0..t (ראו detect.py).
כניסה: בפתיחת נר t+1 (אחרי שהאות נוצר בסגירת t). בדיקה: מה קרה H ימים אחרי, ובמקביל
האם המחיר שבר את התמיכה לפני כן. זו מדידה סטטיסטית, לא המלצת מסחר."""
import sys, yaml, numpy as np
from .providers import get_provider
from .detect import analyze
from .run_scan import passes

def run(cfg_path="config/settings.yaml", horizon=10, step=1):
    cfg = yaml.safe_load(open(cfg_path)); p = cfg["params"]
    prov = get_provider(cfg["provider"], cfg)
    stats = {}
    for u in prov.universe():
        if not passes(u, cfg["filter"]): continue   # הערה: פילטר לפי היום, לא היסטורי (הטיית הישרדות - ראו README)
        bars = prov.history(u["ticker"], p["history_days"])
        for t in range(p["pivot_window"] * 6, len(bars) - horizon - 1, step):
            for st, info in analyze(bars, p, t).items():
                entry = bars.o[t + 1]
                fut = (bars.c[t + horizon] - entry) / entry * 100
                broke = bool((bars.c[t + 1:t + horizon + 1] < info["support"] * (1 - p["touch_tolerance_pct"] / 100)).any())
                stats.setdefault(st, []).append((fut, broke))
    print(f"horizon={horizon} ימים | {'נתוני דוגמה!' if prov.is_sample else cfg['provider']}")
    for st, v in sorted(stats.items()):
        r = np.array([x[0] for x in v]); b = np.mean([x[1] for x in v]) * 100
        print(f"{st:20s} אותות={len(r):4d} ממוצע={r.mean():+.2f}% חציון={np.median(r):+.2f}% עלו={np.mean(r>0)*100:.0f}% נשברה תמיכה={b:.0f}%")
    return stats

if __name__ == "__main__":
    run(horizon=int(sys.argv[1]) if len(sys.argv) > 1 else 10)
