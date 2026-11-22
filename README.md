# סורק תמיכות – מניות אמריקאיות

סורק יומי אוטומטי (GitHub Actions) → `docs/data/results.json` → דשבורד ב-GitHub Pages → התראות טלגרם.

> **מצב נוכחי: נתוני דוגמה סינתטיים בלבד.** עדיין לא חובר ספק נתונים אמיתי, לא הופעלה ריצה בענן ולא נשלחה התראה אמיתית.

## מבנה
- `config/settings.yaml` – הפילטר שלך + כל הפרמטרים (ערכי TBD ממתינים לאישורך)
- `scanner/providers/` – שכבת נתונים להחלפה (`base.py` = הממשק, `sample.py` = דוגמה)
- `scanner/detect.py` – זיהוי 4 השלבים (ללא ממוצעים נעים)
- `scanner/alerts.py` – טלגרם + קולדאון + היסטוריה ב-SQLite (`data/alerts.db`)
- `scanner/backtest.py` – בדיקת עבר ללא הצצה (`python -m scanner.backtest 10`)
- `tests/test_no_lookahead.py` – מוכיח שאות ביום t זהה כשחותכים את העתיד

## התקנה והפעלה (צעד אחר צעד)
1. צרו repo ב-GitHub והעלו אליו את התיקייה. (`git remote add origin ... && git push -u origin main`)
2. **Pages:** Settings → Pages → Source: `Deploy from a branch`, Branch: `main`, תיקייה `/docs`.
3. **טלגרם:** ב-Telegram דברו עם `@BotFather` → `/newbot` → שמרו את ה-Token. שלחו הודעה לבוט, ואז פתחו `https://api.telegram.org/bot<TOKEN>/getUpdates` ושמרו את `chat.id`.
4. **Secrets:** Settings → Secrets and variables → Actions → הוסיפו `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` (ו-`DATA_API_KEY` כשיהיה ספק).
5. הריצה היומית מוגדרת ב-`.github/workflows/scan.yml` (21:30 UTC, ימי חול). הרצה ידנית: Actions → daily-scan → Run workflow.
6. מקומית: `pip install -r requirements.txt && python -m scanner.run_scan && python -m pytest tests`, ואז `cd docs && python -m http.server` ופתחו `localhost:8000`.

## איך מוגדר כל שלב
| שלב | הגדרה |
|---|---|
| 1 | קו תמיכה דרך ≥`min_line_touches` שפלי-ציר, שלא נשבר בסגירה, והנר הנוכחי נוגע בו (`touch_tolerance_pct`). סיווג עולה/יורדת/ישרה לפי שיפוע. |
| 2 | נגיעה ברמת תמיכה אופקית (≥`min_level_touches` שפלי-ציר) + נר פטיש בנר הנוכחי |
| 3 | רמה עם 2/3/4 נגיעות (כולל הנוכחית), ובין כל שתי נגיעות עלייה של ≥`bounce_pct` |
| 4 | רמה עם 2 (כפולה) או 3 (משולשת) שפלי-ציר, והמחיר עד `stage4_proximity_pct` מעליה |

מניה שעוברת כמה שלבים מסומנת "בונוס". התראות נשלחות על שלבים 1–3 בלבד (שלב 4 אינו "נגיעה").

## מגבלות ידועות
- ה-backtest מסנן לפי הפילטר של **היום** (הטיית הישרדות) – יש ספקים שנותנים יקום היסטורי; לטפל בעת חיבור ספק.
- מניה אחת לשלב מוצגת עם הרמה הקרובה ביותר למחיר.
- תוצאות backtest על נתוני דוגמה חסרות משמעות.
