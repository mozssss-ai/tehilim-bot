"""ניהול מהדשבורד: כל כפתור בדשבורד פותח Issue מוכן ב-GitHub, וה-workflow manage.yml מריץ את זה.
רק Issue שפתח בעל המאגר מבוצע. פקודות (בכותרת ה-Issue):
  הקדשה: לרפואת יוסף בן שרה      ← מוסיף לתור
  מחק הקדשה <id>                 ← מוחק מהתור
  הקדם הקדשה <id>                ← מעביר לראש התור
  הדלק <מפתח> / כבה <מפתח>        ← מדליק/מכבה תוסף
"""
import datetime as dt, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import bot, extras  # noqa: E402

SWITCHES = {"shabbat_story": "סטורי שבת שלום", "siyum_reel": "ריל סיום הספר", "dedications": "הקדשות מהצופים",
            "also_story": "העלאת הריל גם לסטורי", "replace_phone_with_qr": "QR במקום מספר הטלפון"}


def run(title: str) -> str:
    t = title.strip()
    d = extras.load_ded()
    if t.startswith("הקדשה"):
        text = extras.parse_dedication(t.split(":", 1)[-1] if ":" in t else t[5:])
        if not text:
            return "❌ לא הבנתי את ההקדשה. הנוסח צריך להתחיל ב'לרפואת' / 'לעילוי נשמת' / 'להצלחת' וכו'."
        item = {"id": f"m{int(dt.datetime.now().timestamp())}", "user_id": None, "username": "ידני", "text": text,
                "received": dt.datetime.now(bot.TZ).isoformat(timespec="minutes")}
        d["queue"].append(item)
        extras.save_ded(d)
        return f"✅ נוסף לתור: {text} (יעלה בפרק של {extras.queue_eta(len(d['queue']) - 1)})"
    for verb in ("מחק הקדשה", "הקדם הקדשה"):
        if t.startswith(verb):
            i = t[len(verb):].strip()
            item = next((q for q in d["queue"] if q["id"] == i), None)
            if not item:
                return "❌ ההקדשה לא נמצאה בתור (אולי כבר עלתה)."
            d["queue"].remove(item)
            if verb == "הקדם הקדשה":
                d["queue"].insert(0, item)
            extras.save_ded(d)
            return f"✅ {'נמחקה' if verb == 'מחק הקדשה' else 'הוקדמה לראש התור'}: {item['text']}"
    for verb, val in (("הדלק", True), ("כבה", False)):
        if t.startswith(verb):
            key = t[len(verb):].strip()
            if key not in SWITCHES:
                return "❌ מפתח לא מוכר."
            p = ROOT / "config.json"
            cfg = json.loads(p.read_text(encoding="utf-8"))
            cfg[key] = val
            p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            return f"✅ {SWITCHES[key]}: {'דולק' if val else 'כבוי'}"
    return "❌ פקודה לא מוכרת."


if __name__ == "__main__":
    msg = run(os.environ.get("ISSUE_TITLE", " ".join(sys.argv[1:])))
    print(msg)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"msg={msg}\n")
