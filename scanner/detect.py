"""זיהוי תמיכות. כל הפונקציות מקבלות t = אינדקס הנר ה"נוכחי" ולא מסתכלות אחריו
(שפל-ציר מאושר רק k נרות אחרי היווצרותו) - כך אותו קוד משמש לסריקה ול-backtest בלי הצצה לעתיד."""
import numpy as np


def pivot_lows(low, k, t):
    out = []
    for i in range(k, t - k + 1):          # מאושר רק אם יש k נרות אחריו עד t
        if low[i] == low[i - k:i + k + 1].min():
            out.append(i)
    return out


def is_hammer(o, h, l, c, p):
    body = abs(c - o); rng = h - l
    if rng <= 0: return False
    lower = min(o, c) - l; upper = h - max(o, c)
    if body < 1e-9 * max(c, 1):
        return lower >= 0.6 * rng and upper <= 0.1 * rng
    return lower >= p["hammer_lower_shadow_x"] * body and upper <= p["hammer_upper_shadow_max_x"] * body


def channel_lines(bars, piv, t, p):
    """קווי תמיכה משופעים/אופקיים דרך שפלי-ציר. מחזיר את הקו הטוב ביותר שנוגע כעת."""
    tol = p["touch_tolerance_pct"] / 100
    cand = piv[-p["line_lookback_pivots"]:]
    best = None
    for ai in range(len(cand)):
        for bi in range(ai + 1, len(cand)):
            a, b = cand[ai], cand[bi]
            if b - a < p["min_line_span_bars"]: continue
            slope = (bars.l[b] - bars.l[a]) / (b - a)
            line = lambda i: bars.l[a] + slope * (i - a)
            idx = np.arange(a, t + 1)
            vals = bars.l[a] + slope * (idx - a)
            if (bars.c[a:t + 1] < vals * (1 - tol)).any(): continue      # נשבר בסגירה
            touches = [q for q in cand if q >= a and abs(bars.l[q] - line(q)) <= tol * line(q)]
            if len(touches) < p["min_line_touches"]: continue
            lt = line(t)
            if lt <= 0 or abs(bars.l[t] - lt) > tol * lt: continue         # לא נוגע עכשיו
            sp = slope / lt * 100
            kind = "flat" if abs(sp) <= p["flat_slope_pct"] else ("ascending" if sp > 0 else "descending")
            score = (len(touches), b)
            if best is None or score > best[0]:
                best = (score, dict(kind=kind, support=lt, touches=len(touches) + 1, slope_pct=sp,
                                    seg=[(a, float(line(a))), (t, float(lt))]))
    return best[1] if best else None


def levels(bars, piv, t, p):
    """אשכולות שפלי-ציר באותו מחיר = רמות תמיכה אופקיות."""
    tol = p["touch_tolerance_pct"] / 100
    out = []
    for i in sorted(piv, key=lambda i: bars.l[i]):
        if out and abs(bars.l[i] - out[-1]["p"][0]) <= tol * out[-1]["p"][0]:
            out[-1]["i"].append(i)
        else:
            out.append(dict(p=[bars.l[i]], i=[i]))
    res = []
    for g in out:
        idx = sorted(g["i"]); lvl = float(np.mean([bars.l[i] for i in idx]))
        if (bars.c[idx[0]:t + 1] < lvl * (1 - tol)).any(): continue          # נשבר בסגירה
        res.append(dict(level=lvl, idx=idx))
    return res


def analyze(bars, p, t=None):
    """מחזיר {stage1_ascending, stage1_descending, stage1_flat, stage2, stage3, stage4: [..]} לנר t."""
    t = len(bars) - 1 if t is None else t
    if t < 3 * p["pivot_window"]: return {}
    tol = p["touch_tolerance_pct"] / 100
    px = float(bars.c[t])
    piv = pivot_lows(bars.l, p["pivot_window"], t)
    res = {}
    def base(support, **kw):
        return dict(price=px, support=float(support), distance_pct=(px - support) / support * 100, **kw)

    ch = channel_lines(bars, piv, t, p)
    if ch:
        res["stage1_" + ch["kind"]] = base(ch["support"], touches=ch["touches"], slope_pct=ch["slope_pct"],
                                           lines=[ch["seg"]])
    hammer = is_hammer(bars.o[t], bars.h[t], bars.l[t], bars.c[t], p)
    for lv in levels(bars, piv, t, p):
        L, idx = lv["level"], lv["idx"]
        now = abs(bars.l[t] - L) <= tol * L and bars.c[t] >= L * (1 - tol)
        seg = [[(idx[0], L), (t, L)]]
        if now and hammer and len(idx) >= p["min_level_touches"]:
            res.setdefault("stage2", []).append(base(L, touches=len(idx) + 1, lines=seg))
        if now and (len(idx) + 1) in p["stage3_touches"]:
            pts = idx + [t]; ok = True
            for a, b in zip(pts, pts[1:]):
                if bars.h[a:b + 1].max() < L * (1 + p["bounce_pct"] / 100): ok = False
            if ok: res.setdefault("stage3", []).append(base(L, touches=len(idx) + 1, lines=seg))
        if len(idx) in (2, 3) and 0 <= (px - L) / L * 100 <= p["stage4_proximity_pct"]:
            res.setdefault("stage4", []).append(base(L, touches=len(idx),
                                                     kind="double" if len(idx) == 2 else "triple", lines=seg))
    # רמה אחת לשלב (הקרובה ביותר למחיר)
    for k in ("stage2", "stage3", "stage4"):
        if k in res: res[k] = min(res[k], key=lambda r: abs(r["distance_pct"]))
    return res
