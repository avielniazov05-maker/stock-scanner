import os, sqlite3, time, json, urllib.request, urllib.parse

SCHEMA = "CREATE TABLE IF NOT EXISTS alerts(id INTEGER PRIMARY KEY, ticker TEXT, stage TEXT, ts INTEGER, price REAL, support REAL)"

def links(t):
    return (f"https://finviz.com/quote.ashx?t={t}", f"https://www.tradingview.com/chart/?symbol={t}")

def due(db, ticker, stage, cooldown_days, now=None):
    now = now or int(time.time())
    r = db.execute("SELECT MAX(ts) FROM alerts WHERE ticker=? AND stage=?", (ticker, stage)).fetchone()[0]
    return r is None or now - r >= cooldown_days * 86400

def send_telegram(text):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat): return False
    data = urllib.parse.urlencode({"chat_id": chat, "text": text, "parse_mode": "HTML",
                                   "disable_web_page_preview": "true"}).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data, timeout=20).read()
    return True

def process(results, labels, db_path, cooldown_days):
    """results: {ticker: {stage: info}}. מתריע רק על שלבים 1-3 (נגיעה בפועל)."""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    db = sqlite3.connect(db_path); db.execute(SCHEMA)
    sent = skipped = unsent = 0
    for t, stages in results.items():
        for st, info in stages.items():
            if not (st.startswith("stage1") or st in ("stage2", "stage3")): continue
            if not due(db, t, st, cooldown_days): skipped += 1; continue
            fv, tv = links(t)
            msg = (f"<b>{t}</b> נוגעת בתמיכה — {labels[st]}\nמחיר: {info['price']:.2f} | תמיכה: {info['support']:.2f} "
                   f"({info['distance_pct']:+.2f}%) | נגיעות: {info.get('touches','-')}\n"
                   f'<a href="{fv}">Finviz</a> | <a href="{tv}">TradingView</a>')
            if send_telegram(msg):
                db.execute("INSERT INTO alerts(ticker,stage,ts,price,support) VALUES(?,?,?,?,?)",
                           (t, st, int(time.time()), info["price"], info["support"])); db.commit(); sent += 1
            else: unsent += 1     # אין טוקן / שגיאה: לא נרשם, כדי שלא יחסום התראה עתידית
    db.close()
    return dict(sent=sent, cooldown_skipped=skipped, not_sent_no_telegram=unsent)
