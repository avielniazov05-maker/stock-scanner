"""זיהוי תמיכות (גרסה 2). כל הפונקציות מקבלות t = אינדקס הנר ה"נוכחי" ולא מסתכלות אחריו,
ולכן אותו קוד משמש לסריקה ול-backtest בלי הצצה לעתיד.

עיקרון: "נגיעה" היא אפיזודה. רצף נרות שהנמוך שלהם מגיע לתמיכה נחשב לנגיעה אחת.
נגיעה חדשה נספרת רק אם בינה לבין הקודמת המחיר עלה לפחות bounce_pct מעל התמיכה
ועברו לפחות min_touch_gap_bars נרות. נגיעה "עכשיו" = האפיזודה האחרונה מסתיימת בנר t,
אורכה לכל היותר max_touch_days, ולפניה המחיר הגיע מלמעלה (עלייה של bounce_pct).
תמיכה שנשברה (סגירה מתחתיה) נפסלת."""
import numpy as np


def pivot_lows(low, k, t):
    return [i for i in range(k, t - k + 1) if low[i] == low[i - k:i + k + 1].min()]


def pivot_highs(high, k, t):
    return [i for i in range(k, t - k + 1) if high[i] == high[i - k:i + k + 1].max()]


def is_hammer(o, h, l, c, p):
    body = abs(c - o); rng = h - l
    if rng <= 0: return False
    lower = min(o, c) - l; upper = h - max(o, c)
    if body < 1e-9 * max(c, 1):
        return lower >= 0.6 * rng and upper <= 0.1 * rng
    return lower >= p["hammer_lower_shadow_x"] * body and upper <= p["hammer_upper_shadow_max_x"] * body


def episodes(bars, start, t, sup, p):
    """sup: ערכי התמיכה לאינדקסים start..t. מחזיר רשימת [התחלה, סוף] (אינדקסים מוחלטים) או None אם נשברה."""
    tol = p["touch_tolerance_pct"] / 100; bounce = p["bounce_pct"] / 100; gap = p["min_touch_gap_bars"]
    lo, hi, cl = bars.l[start:t + 1], bars.h[start:t + 1], bars.c[start:t + 1]
    if (cl < sup * (1 - tol)).any(): return None
    near = lo <= sup * (1 + tol)
    eps, rise, prev_near = [], 0.0, False
    for j in range(len(lo)):
        if near[j]:
            if prev_near: eps[-1][1] = j
            elif eps and (rise < bounce or j - eps[-1][1] < gap): eps[-1][1] = j     # אין עלייה אמיתית: אותה נגיעה
            else: eps.append([j, j])
            rise = 0.0
        else:
            rise = max(rise, hi[j] / sup[j] - 1)
        prev_near = near[j]
    return [[a + start, b + start] for a, b in eps]


def touching_now(eps, t, p):
    if not eps or eps[-1][1] != t: return False
    if eps[-1][1] - eps[-1][0] + 1 > p["max_touch_days"]: return False    # "דשדוש" על הקו, לא נגיעה
    return len(eps) >= 2 or eps[-1][0] > 0


def best_line(bars, piv, t, p):
    """קו תמיכה משופע/אופקי דרך שני שפלי-ציר, עם קו עליון מקביל (תעלה)."""
    tol = p["touch_tolerance_pct"] / 100
    hp = pivot_highs(bars.h, p["pivot_window"], t)
    best = None
    for ai in range(len(piv)):
        a = piv[ai]
        if t - a < p["min_channel_bars"]: continue
        for b in piv[ai + 1:]:
            if b - a < p["min_line_span_bars"]: continue
            slope = (bars.l[b] - bars.l[a]) / (b - a)
            idx = np.arange(a, t + 1); sup = bars.l[a] + slope * (idx - a)
            if sup[-1] <= 0: continue
            eps = episodes(bars, a, t, sup, p)
            if not eps or not touching_now(eps, t, p) or len(eps) < p["min_line_touches"]: continue
            if p.get("require_upper_line", True):
                off = (bars.h[a:t + 1] - sup).max(); up = lambda i: bars.l[a] + slope * (i - a) + off
                if off / sup[-1] < p["bounce_pct"] / 100: continue
                ut = [i for i in hp if i >= a and bars.h[i] >= up(i) - 2 * tol * up(i)]
                if len(ut) < p["min_upper_touches"]: continue
            sp = slope / sup[-1] * 100
            kind = "flat" if abs(sp) <= p["flat_slope_pct"] else ("ascending" if sp > 0 else "descending")
            score = (len(eps), t - a)
            if best is None or score > best[0]:
                best = (score, dict(kind=kind, support=float(sup[-1]), touches=len(eps), slope_pct=sp,
                                    seg=[(a, float(sup[0])), (t, float(sup[-1]))]))
    return best[1] if best else None


def levels(bars, piv, t, p):
    """רמות אופקיות: כל שפל-ציר (או אשכול) מציע רמה; מחזיר את הרמות שלא נשברו עם האפיזודות שלהן."""
    tol = p["touch_tolerance_pct"] / 100
    groups = []
    for i in sorted(piv, key=lambda i: bars.l[i]):
        if groups and abs(bars.l[i] - np.mean([bars.l[j] for j in groups[-1]])) <= tol * bars.l[i]:
            groups[-1].append(i)
        else:
            groups.append([i])
    out = []
    for g in groups:
        g = sorted(g); L = float(np.mean([bars.l[i] for i in g])); a = g[0]
        eps = episodes(bars, a, t, np.full(t - a + 1, L), p)
        if eps: out.append(dict(level=L, start=a, eps=eps))
    return out


def confirmed(bars, p, t):
    """נגיעה בתמיכה בנר t-1 (שלבים 1-3) + נר אישור בנר t."""
    if t < 1 or not p.get("confirm_enabled", True): return None
    prev = analyze(bars, p, t - 1, _confirm=False)
    tol = p["touch_tolerance_pct"] / 100
    o, h, l, c = bars.o[t], bars.h[t], bars.l[t], bars.c[t]
    ref = bars.h[t - 1] if p["confirm_mode"] == "close_above_prev_high" else bars.c[t - 1]
    if not (c > o and c > ref): return None
    for st in ("stage1_ascending", "stage1_descending", "stage1_flat", "stage2", "stage3"):
        if st not in prev: continue
        info = prev[st]; sup = info["support"]
        if "slope_pct" in info: sup = sup * (1 + info["slope_pct"] / 100)     # הקו ממשיך נר אחד
        if l < sup * (1 - tol) or c <= sup: continue                           # נר האישור לא שבר את התמיכה
        (a, va), (b, vb) = info["lines"][0]
        return dict(price=float(c), support=float(sup), distance_pct=(c - sup) / sup * 100, touches=info["touches"],
                    from_stage=st, lines=[[(a, va), (t, float(sup))]])
    return None


def analyze(bars, p, t=None, _confirm=True):
    """מחזיר {stage1_ascending|descending|flat, stage2, stage3, stage4: info} לנר t."""
    t = len(bars) - 1 if t is None else t
    if t < 3 * p["pivot_window"]: return {}
    px = float(bars.c[t])
    piv = pivot_lows(bars.l, p["pivot_window"], t)
    res = {}
    def base(support, **kw):
        return dict(price=px, support=float(support), distance_pct=(px - support) / support * 100, **kw)

    ch = best_line(bars, piv, t, p)
    if ch:
        res["stage1_" + ch["kind"]] = base(ch["support"], touches=ch["touches"], slope_pct=ch["slope_pct"], lines=[ch["seg"]])

    hammer = is_hammer(bars.o[t], bars.h[t], bars.l[t], bars.c[t], p) and p.get("hammer_enabled", True)
    for lv in levels(bars, piv, t, p):
        L, eps = lv["level"], lv["eps"]; n = len(eps); now = touching_now(eps, t, p)
        seg = [[(lv["start"], L), (t, L)]]
        if now and hammer and n >= p["min_level_touches"]:
            res.setdefault("stage2", []).append(base(L, touches=n, lines=seg))
        if now and n in p["stage3_touches"]:
            res.setdefault("stage3", []).append(base(L, touches=n, lines=seg))
        if n in (2, 3) and 0 <= (px - L) / L * 100 <= p["stage4_proximity_pct"] and (now or eps[-1][1] < t):
            res.setdefault("stage4", []).append(base(L, touches=n, kind="double" if n == 2 else "triple", lines=seg))
    for k in ("stage2", "stage3", "stage4"):
        if k in res: res[k] = max(res[k], key=lambda r: (r["touches"], -abs(r["distance_pct"])))
    if _confirm:
        cf = confirmed(bars, p, t)
        if cf: res["confirmed"] = cf
    return res
