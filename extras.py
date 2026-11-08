"""תוספות שיווק: סטורי שבת שלום, ריל סיום הספר, והקדשות שמגיעות מהצופים בהודעה פרטית.
כל תוספת נדלקת רק אם היא מסומנת true ב-config.json (אחרי אישור של משה חיים):
  shabbat_story, siyum_reel, dedications
"""
import datetime as dt
import json
import re
import subprocess
from pathlib import Path

import bot
import design

ROOT = Path(__file__).resolve().parent
DED_FILE = ROOT / "dedications.json"
OUT = ROOT / "out"
CFG = bot.CONFIG

PREFIXES = ["לרפואה שלמה של", "לרפואה שלמה ל", "לרפואה שלמה", "לרפואת", "לעילוי נשמת", "לעלוי נשמת", "לעילוי נשמתו של",
            "להצלחת", "להצלחה של", "לזיווג הגון ל", "לזיווגו של", "לזיווגה של", "לזיווג", "לזרע של קיימא ל",
            "לזרע של קיימא", "לשמירת", "לישועת", "לשלום", "לפרנסה טובה ל", "לשחרור"]
ALLOWED = re.compile(r"^[א-ת\s'\"׳״\-\(\),\.]+$")
BAD = ["זין", "כוס", "שרמוט", "זונה", "מניאק", "חרא", "בן זונה", "מזדיין", "הומו", "נאצי", "ערבי", "מוות ל"]


def load_ded():
    return json.loads(DED_FILE.read_text(encoding="utf-8")) if DED_FILE.exists() else {"queue": [], "done": [], "seen": []}


def save_ded(d):
    DED_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_dedication(msg: str):
    """מחזיר נוסח הקדשה תקין (למשל 'לרפואת יוסף בן שרה') או None."""
    t = re.sub(r"\s+", " ", (msg or "").replace("\n", " ")).strip()
    t = re.sub(r"^(הפרק|פרק)?\s*(מוקדש|להקדיש|הקדשה|אשמח להקדיש|נא להקדיש)[:\s]*", "", t).strip()
    start = min((t.find(p) for p in PREFIXES if p in t), default=-1)
    if start < 0:
        return None
    t = t[start:].strip(" .,")
    if not (6 <= len(t) <= 60) or not ALLOWED.match(t) or any(b in t for b in BAD):
        return None
    return t


def card_video(png: Path, out: Path, secs: float = 8) -> Path:
    """תמונה סטטית -> סרטון קצר עם מנגינה שקטה (כמו הריילס)."""
    tracks = sorted((ROOT / "assets" / "music").glob("*.mp3"))
    music = tracks[dt.date.today().toordinal() % len(tracks)] if tracks else None
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-t", str(secs), "-i", str(png)]
    cmd += ["-stream_loop", "-1", "-i", str(music)] if music else ["-f", "lavfi", "-t", str(secs), "-i", "anullsrc=r=44100:cl=stereo"]
    cmd += ["-filter_complex",
            "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=white,"
            f"setsar=1,fps=30,format=yuv420p[v];[1:a]atrim=0:{secs},afade=t=in:d=0.6,afade=t=out:st={secs - 1.2}:d=1.2[a]",
            "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", "-t", str(secs), str(out)]
    subprocess.run(cmd, check=True)
    return out


# ---------------------------------------------------------------- dedication applied to a reel
def take_dedication():
    """מוציא את ההקדשה הבאה מהתור (או None)."""
    if not CFG.get("dedications"):
        return None
    d = load_ded()
    return d["queue"][0] if d["queue"] else None


def apply_dedication(unit: dict, ded: dict) -> dict:
    """מחזיר עותק של הפרק שבו לתמונה הראשונה נוסף פס הקדשה."""
    OUT.mkdir(exist_ok=True)
    first = ROOT / unit["images"][0]
    (OUT / "ded").mkdir(parents=True, exist_ok=True)
    new = OUT / "ded" / first.name
    if CFG.get("replace_phone_with_qr", True):
        first = design.clean_footer(first, OUT / "ded" / ("clean_" + first.name), CFG["whatsapp_link"])
    design.dedicate(first, f"הפרק מוקדש {ded['text']}", new)
    return {**unit, "images": [str(new.relative_to(ROOT))] + unit["images"][1:]}


def dedication_caption(text: str, ded: dict) -> str:
    lines = text.split("\n")
    lines.insert(1, f"🕯️ הפרק מוקדש {ded['text']}")
    return "\n".join(lines)


def finish_dedication(ded: dict, unit: dict, media_id: str, token: str):
    d = load_ded()
    d["queue"] = [q for q in d["queue"] if q["id"] != ded["id"]]
    rec = {**ded, "chapter": unit["chapter"], "media_id": media_id,
           "posted": dt.datetime.now(bot.TZ).isoformat(timespec="minutes")}
    try:
        link = bot.ig_request("GET", f"{bot.GRAPH}/{media_id}",
                              params={"fields": "permalink", "access_token": token}).get("permalink", "")
        send_dm(ded["user_id"], f"הפרק של היום – פרק {bot.gematria(unit['chapter'])} – מוקדש {ded['text']} 🕯️\n"
                                f"{link}\nשתפו אותו עם המשפחה והחברים, ושתהיה בשורה טובה 🙏", token)
        rec["notified"] = True
    except Exception as e:  # מחוץ לחלון של 24 שעות אינסטגרם לא מאפשר לשלוח – הם כבר קיבלו תאריך מראש
        rec["notify_error"] = str(e)[:200]
    d["done"].append(rec)
    save_ded(d)


# ---------------------------------------------------------------- messaging
def _page(token):
    for p in bot.ig_request("GET", f"{bot.FB_GRAPH}/me/accounts",
                            params={"fields": "id,access_token,instagram_business_account", "access_token": token}).get("data", []):
        if (p.get("instagram_business_account") or {}).get("id") == CFG.get("ig_user_id"):
            return p
    return None


def send_dm(user_id: str, text: str, token: str):
    uid, _ = bot.connect(token)
    body = {"recipient": {"id": user_id}, "message": {"text": text}}
    try:
        return bot.ig_request("POST", f"{bot.GRAPH}/{uid}/messages", json=body, params={"access_token": token})
    except RuntimeError:
        page = _page(token)
        if not page:
            raise
        return bot.ig_request("POST", f"{bot.FB_GRAPH}/{page['id']}/messages", json=body,
                              params={"access_token": page["access_token"]})


def conversations(token):
    uid, username = bot.connect(token)
    fields = "participants,messages.limit(5){id,message,from,created_time}"
    try:
        r = bot.ig_request("GET", f"{bot.GRAPH}/{uid}/conversations",
                           params={"platform": "instagram", "fields": fields, "access_token": token})
    except RuntimeError:
        page = _page(token)
        if not page:
            raise
        r = bot.ig_request("GET", f"{bot.FB_GRAPH}/{page['id']}/conversations",
                           params={"platform": "instagram", "fields": fields, "access_token": page["access_token"]})
    return r.get("data", []), uid, username


def queue_eta(position: int) -> str:
    """באיזה יום תעלה ההקדשה במקום ה-position בתור (פרק אחד ביום, בלי שבת)."""
    day = dt.datetime.now(bot.TZ).date()
    st = bot.load_state()
    if any(p["day"] == day.isoformat() and p["kind"] == "cycle" for p in st["posted"]):
        day += dt.timedelta(days=1)
    day += dt.timedelta(days=position)  # פרק אחד בכל יום; הפרק של שבת/חג עולה במוצאי השבת/החג
    return bot.hebrew_date(day) + (" (במוצאי השבת/החג)" if bot.is_holy(day) else "")


def check_inbox(token):
    """קורא הודעות פרטיות חדשות. הקדשה בפורמט תקין נכנסת לתור, והשולח מקבל אישור עם התאריך."""
    if not CFG.get("dedications"):
        return
    d = load_ded()
    seen = set(d["seen"])
    convs, uid, username = conversations(token)
    for c in convs:
        for m in (c.get("messages") or {}).get("data", []):
            frm = m.get("from") or {}
            if m["id"] in seen or frm.get("id") == uid or frm.get("username") == username:
                continue
            seen.add(m["id"])
            d["seen"].append(m["id"])
            age = dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(m["created_time"].replace("+0000", "+00:00"))
            if age > dt.timedelta(hours=23):
                continue
            text = parse_dedication(m.get("message", ""))
            if text:
                if any(q["text"] == text for q in d["queue"]):
                    continue
                item = {"id": m["id"], "user_id": frm.get("id"), "username": frm.get("username", ""),
                        "text": text, "received": dt.datetime.now(bot.TZ).isoformat(timespec="minutes")}
                d["queue"].append(item)
                eta = queue_eta(len(d["queue"]) - 1)
                try:
                    send_dm(item["user_id"], f"קיבלנו, תודה 🙏\nהפרק יוקדש {text}.\n"
                                             f"ההקדשה תעלה בפרק של {eta} – בתמונה ובכיתוב.", token)
                except Exception as e:
                    item["confirm_error"] = str(e)[:200]
                print("הקדשה חדשה בתור:", text)
            elif re.search(r"הקדש|מוקדש|לרפוא|לעילוי|נשמת", m.get("message", "")):
                try:
                    send_dm(frm.get("id"), "כדי להקדיש פרק, שלחו הודעה אחת בנוסח הזה:\n"
                                           "לרפואת יוסף בן שרה / לעילוי נשמת יוסף בן שרה\n(שם + שם האם)", token)
                except Exception:
                    pass
    d["seen"] = d["seen"][-500:]
    save_ded(d)


# ---------------------------------------------------------------- stories / reels around the daily reel
def shabbat_texts(day: dt.date):
    """day = ערב שבת/חג. מחזיר (כותרת, תת-כותרת)."""
    from pyluach import dates as hd, parshios
    nxt = day + dt.timedelta(days=1)
    h = hd.HebrewDate.from_pydate(nxt)
    fest = h.festival(israel=True, hebrew=True, include_working_days=False)
    if nxt.weekday() == 5:
        p = parshios.getparsha_string(hd.GregorianDate.from_pydate(nxt), israel=True, hebrew=True)
        return ("שבת שלום" if not fest else "שבת שלום וחג שמח", f"פרשת {p}" if p else (fest or ""))
    return ("חג שמח", fest or "")


def after_reel(unit, day, kind, media_id, token, publish):
    """רץ אחרי שהריל היומי (והסטורי שלו) עלו."""
    OUT.mkdir(exist_ok=True)
    done = []
    if CFG.get("shabbat_story") and bot.day_kind(day) == "erev" and day == dt.datetime.now(bot.TZ).date():
        title, sub = shabbat_texts(day)
        v = card_video(design.shabbat_story(title, sub, OUT / "shabbat.png"), OUT / "shabbat.mp4", 8)
        done.append(("shabbat_story", publish(v, "", token, "STORIES")))
    if CFG.get("dedications") and dt.datetime.now(bot.TZ).weekday() in CFG.get("dedication_invite_days", [6, 2]):
        v = card_video(design.invite_story(OUT / "invite.png"), OUT / "invite.mp4", 8)
        done.append(("invite_story", publish(v, "", token, "STORIES")))
    if CFG.get("siyum_reel") and unit["chapter"] == 150 and kind == "cycle":
        v = card_video(design.siyum_card(OUT / "siyum.png"), OUT / "siyum.mp4", 12)
        cap = ("סיימנו יחד את ספר התהילים! 🎉📖\nתודה לכל מי שאמר איתנו, פרק אחרי פרק.\n"
               "מחר מתחילים מחזור חדש מפרק א' – זה הזמן הכי טוב להצטרף.\n"
               "כתבו \"תהילים\" בתגובה ונשלח לכם קישור בפרטי 💬\n\n#תהילים #תהיליםכליום #סיוםספרתהילים")
        rid = publish(v, cap, token, "REELS")
        done.append(("siyum_reel", rid))
        try:
            done.append(("siyum_story", publish(v, "", token, "STORIES")))
        except Exception as e:
            print("סטורי סיום נכשל:", e)
    return done
