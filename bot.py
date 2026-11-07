"""
בוט "תהילים כל יום" – מעלה כל יום ריל של הפרק היומי לאינסטגרם.

כללים:
  * פרק אחד ביום, לפי הסדר (יחידה = פרק, עם כל החלקים שלו).
  * ימי חול: העלאה בשעה POST_TIME (ברירת מחדל 19:30, שעון ישראל).
  * ערב שבת / ערב חג: העלאה מוקדמת, לפחות שעתיים לפני השקיעה.
  * שבת / חג: לא מעלים. הפרק של השבת עולה שעה אחרי צאת השבת/החג.
  * הבוט רץ כל חצי שעה (GitHub Actions) ומחליט לבד אם הגיע הזמן להעלות.

הרצה:
  python bot.py                 # בודק אם צריך להעלות, ומעלה
  python bot.py --dry-run       # מראה מה היה קורה, בלי להעלות
  python bot.py --check         # רק בודק אם הגיע זמן העלאה (ל-GitHub Actions)
  python bot.py --plan 21       # מדפיס תוכנית העלאות ל-21 הימים הבאים
  python bot.py --build N       # בונה את הסרטון של יחידה N לבדיקה (out/)
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun
from pyluach import dates as hdates

ROOT = Path(__file__).resolve().parent
TZ = ZoneInfo("Asia/Jerusalem")
CITY = LocationInfo("Ashkelon", "Israel", "Asia/Jerusalem", 31.668, 34.571)
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
# רשימת הפרקים נבנית לבד מתיקיית images: 001_1.png, 001_2.png ... 150_1.png
UNITS = [{"chapter": c, "images": sorted(f"images/{p.name}" for p in (ROOT / "images").glob(f"{c:03d}_*.png"))}
         for c in range(1, 151)]
STATE_FILE = ROOT / "state.json"
LEARN_FILE = ROOT / "learn.json"
LEARN = json.loads(LEARN_FILE.read_text(encoding="utf-8")) if LEARN_FILE.exists() else {}

GRAPH = "https://graph.instagram.com/v21.0"   # מתעדכן לבד לפי סוג המפתח (connect())
IG_GRAPH = "https://graph.instagram.com/v21.0"
FB_GRAPH = "https://graph.facebook.com/v21.0"


# ---------------------------------------------------------------- dates
def sunset(day: dt.date) -> dt.datetime:
    return sun(CITY.observer, date=day, tzinfo=TZ)["sunset"]


def is_holy(day: dt.date) -> bool:
    """שבת או יום טוב (לפי לוח ארץ ישראל)."""
    if day.weekday() == 5:
        return True
    h = hdates.HebrewDate.from_pydate(day)
    return bool(h.festival(israel=True, include_working_days=False))


def holy_end(day: dt.date) -> dt.datetime:
    """הרגע שבו מותר להעלות אחרי רצף של שבת/חג שמכיל את day."""
    while is_holy(day + dt.timedelta(days=1)):
        day += dt.timedelta(days=1)
    return sunset(day) + dt.timedelta(minutes=CONFIG["minutes_after_holy_end"])


def day_kind(day: dt.date) -> str:
    if is_holy(day):
        return "holy"
    return "erev" if is_holy(day + dt.timedelta(days=1)) else "weekday"


def planned_slot(day: dt.date) -> str:
    """השעה המתוכננת להעלאה ביום הזה.
    ברוב הימים: השעה הכי טובה שהבוט למד מהנתונים (learn.json).
    בחלק מהימים (explore_rate) הוא מנסה שעה אחרת מהרשימה, כדי להמשיך ללמוד."""
    import random
    kind = day_kind(day)
    slots = CONFIG["slots"][kind]
    best = LEARN.get("best", {}).get(kind, CONFIG["default_slot"][kind])
    rng = random.Random(day.toordinal())  # אותה החלטה בכל הרצה באותו יום
    if rng.random() < CONFIG["explore_rate"]:
        return rng.choice(slots)
    return best


def release_time(day: dt.date) -> dt.datetime:
    """מתי הפרק של היום הזה מותר/אמור לעלות."""
    if is_holy(day):
        return holy_end(day)
    hh, mm = map(int, planned_slot(day).split(":"))
    target = dt.datetime.combine(day, dt.time(hh, mm), TZ)
    if day_kind(day) == "erev":  # ערב שבת / ערב חג – לעולם לא מאוחר משעתיים לפני השקיעה
        latest = sunset(day) - dt.timedelta(minutes=CONFIG["minutes_before_sunset_on_erev"])
        target = min(target, latest)
    return target


def is_forbidden(now: dt.datetime) -> bool:
    """האם עכשיו שבת/חג (כולל מרווח ביטחון)."""
    for offset in (-1, 0):
        day = (now + dt.timedelta(days=offset)).date()
        if is_holy(day + dt.timedelta(days=1)) and not is_holy(day):
            start = sunset(day) - dt.timedelta(minutes=40)
            end = holy_end(day + dt.timedelta(days=1))
            if start <= now < end:
                return True
    day = now.date()
    if is_holy(day) and now < holy_end(day):
        return True
    return False


# ---------------------------------------------------------------- hebrew text
def gematria(n: int) -> str:
    ones = "אבגדהוזחט"
    tens = "יכלמנסעפצ"
    hundreds = "קרשת"
    s = ""
    while n >= 400:
        s += "ת"; n -= 400
    if n >= 100:
        s += hundreds[n // 100 - 1]; n %= 100
    if n == 15:
        s += "טו"; n = 0
    elif n == 16:
        s += "טז"; n = 0
    if n >= 10:
        s += tens[n // 10 - 1]; n %= 10
    if n:
        s += ones[n - 1]
    return s[:-1] + '"' + s[-1] if len(s) > 1 else s + "'"


def hebrew_date(day: dt.date) -> str:
    return (hdates.HebrewDate.from_pydate(day).hebrew_date_string()
            .replace("״", '"').replace("׳", "'").replace(" חשון ", " מרחשוון "))


def caption(unit: dict, day: dt.date) -> str:
    return CONFIG["caption"].format(
        chapter=gematria(unit["chapter"]),
        hebrew_date=hebrew_date(day),
        group_link=CONFIG["whatsapp_link"],
    )


# ---------------------------------------------------------------- state
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"posted": []}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def slots_released(now: dt.datetime) -> list:
    """רשימת הימים (מתחילת המחזור) שהפרק שלהם כבר מותר לעלות."""
    start = dt.date.fromisoformat(CONFIG["cycle_start"])
    out, day = [], start
    while day <= now.date():
        if release_time(day) <= now:
            out.append(day)
        day += dt.timedelta(days=1)
    return out


def next_job(now: dt.datetime, state: dict):
    """מחזיר (יחידה, יום) אם צריך להעלות עכשיו, אחרת None.
    קודם משלימים את פרקי ההשלמה (catch_up), ואז ממשיכים במחזור לפי הסדר.
    כל עוד יש פיגור, אפשר עד max_posts_per_day ריילס ביום, בהפרש של חצי שעה לפחות."""
    if is_forbidden(now):
        return None
    posted = state["posted"]
    if posted:
        last = dt.datetime.fromisoformat(posted[-1]["at"])
        if now - last < dt.timedelta(minutes=25):
            return None
        today_count = sum(1 for p in posted if dt.datetime.fromisoformat(p["at"]).date() == now.date())
        if today_count >= CONFIG["max_posts_per_day"]:
            return None
    by_chapter = {u["chapter"]: u for u in UNITS}
    done_catch = {p["chapter"] for p in posted if p.get("kind") == "catch_up"}
    for ch in CONFIG.get("catch_up", []):
        if ch not in done_catch:
            return by_chapter[ch], now.date(), "catch_up"
    released = slots_released(now)
    done = sum(1 for p in posted if p.get("kind", "cycle") == "cycle")
    if done >= len(released):
        return None
    idx = done % len(UNITS)  # בסוף הספר מתחילים מחזור חדש
    return UNITS[idx], released[done], "cycle"


# ---------------------------------------------------------------- video
def build_video(unit: dict, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    frames = [(ROOT / p, CONFIG["seconds_per_page"]) for p in unit["images"]]
    missing = [str(p) for p, _ in frames if not p.exists()]
    # חלקים צריכים להיות רצופים (_1, _2, ...). אם חסר חלק – לא מעלים פרק חלקי.
    nums = sorted(int(Path(p).stem.split("_")[1]) for p in unit["images"])
    if not nums or nums != list(range(1, len(nums) + 1)):
        missing.append(f"חלק חסר (קיימים: {nums})")
    if missing:
        raise FileNotFoundError(f"חסרות תמונות לפרק {unit['chapter']}: {missing}")
    join = ROOT / CONFIG["join_image"]
    if join.exists():
        frames.append((join, CONFIG["seconds_join"]))
    total = sum(s for _, s in frames)

    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    for path, secs in frames:
        cmd += ["-loop", "1", "-t", str(secs), "-i", str(path)]
    music = ROOT / CONFIG["music"]
    if music.exists():
        cmd += ["-stream_loop", "-1", "-i", str(music)]
    else:
        cmd += ["-f", "lavfi", "-t", str(total), "-i", "anullsrc=r=44100:cl=stereo"]
    a = len(frames)
    fx = "".join(
        f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
        f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=white,setsar=1,fps=30,format=yuv420p[v{i}];"
        for i in range(a))
    fx += "".join(f"[v{i}]" for i in range(a)) + f"concat=n={a}:v=1:a=0[v];"
    fx += f"[{a}:a]atrim=0:{total},afade=t=in:d=0.8,afade=t=out:st={max(total - 1.5, 0)}:d=1.5,asetpts=N/SR/TB[a]"
    cmd += ["-filter_complex", fx, "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-profile:v", "high", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
            "-movflags", "+faststart", "-t", str(total), str(out)]
    subprocess.run(cmd, check=True)
    return out


# ---------------------------------------------------------------- instagram
def ig_request(method, url, **kw):
    import requests
    for attempt in range(3):
        r = requests.request(method, url, timeout=120, **kw)
        if r.status_code < 500:
            break
        time.sleep(10 * (attempt + 1))
    if r.status_code >= 400:
        raise RuntimeError(f"Instagram API {r.status_code}: {r.text}")
    return r.json()


def host_video(video: Path) -> str:
    """מעלה את הסרטון לענף 'media' במאגר (ציבורי) ומחזיר כתובת שאינסטגרם יכול להוריד ממנה.
    בענף נשמר תמיד רק הסרטון האחרון (force push), כדי שהמאגר לא יתנפח."""
    repo = os.environ["GITHUB_REPOSITORY"]
    name = f"reel_{int(time.time())}.mp4"
    work = ROOT / "out" / "media"
    work.mkdir(parents=True, exist_ok=True)
    (work / name).write_bytes(video.read_bytes())
    remote = f"https://x-access-token:{os.environ['GITHUB_TOKEN']}@github.com/{repo}.git"
    git = lambda *a: subprocess.run(["git", "-C", str(work), *a], check=True, capture_output=True)
    git("init", "-q", "-b", "media")
    git("-c", "user.name=tehilim-bot", "-c", "user.email=bot@users.noreply.github.com",
        "add", name)
    git("-c", "user.name=tehilim-bot", "-c", "user.email=bot@users.noreply.github.com",
        "commit", "-q", "-m", "reel")
    git("push", "-q", "--force", remote, "media")
    time.sleep(15)
    return f"https://raw.githubusercontent.com/{repo}/media/{name}"


def create_container(uid: str, video: Path, text: str, token: str) -> str:
    base = {"media_type": "REELS", "caption": text, "share_to_feed": "true",
            "thumb_offset": "500", "access_token": token}
    # דרך 1: העלאה ישירה של הקובץ
    try:
        c = ig_request("POST", f"{GRAPH}/{uid}/media", data={**base, "upload_type": "resumable"})
        if "uri" in c:
            data = video.read_bytes()
            ig_request("POST", c["uri"], headers={
                "Authorization": f"OAuth {token}", "offset": "0", "file_size": str(len(data))}, data=data)
            return c["id"]
    except RuntimeError as e:
        print("resumable upload not available, falling back to video_url:", e)
    # דרך 2: אינסטגרם מוריד את הסרטון מכתובת ציבורית
    url = host_video(video)
    c = ig_request("POST", f"{GRAPH}/{uid}/media", data={**base, "video_url": url})
    return c["id"]


def connect(token: str):
    """מזהה את סוג המפתח ומחזיר (מזהה חשבון האינסטגרם, שם המשתמש).
    מפתח של 'התחברות עם אינסטגרם' עובד מול graph.instagram.com;
    מפתח של פייסבוק / משתמש מערכת (Unified login) עובד מול graph.facebook.com."""
    global GRAPH
    try:
        me = ig_request("GET", f"{IG_GRAPH}/me", params={"fields": "user_id,username", "access_token": token})
        GRAPH = IG_GRAPH
        return me["user_id"], me.get("username")
    except RuntimeError as e:
        print("not an Instagram-login token, trying Facebook Graph:", str(e)[:200])
    GRAPH = FB_GRAPH
    pages = ig_request("GET", f"{FB_GRAPH}/me/accounts", params={
        "fields": "name,instagram_business_account{id,username}", "access_token": token, "limit": 100})
    for pg in pages.get("data", []):
        ig = pg.get("instagram_business_account")
        if ig:
            return ig["id"], ig.get("username")
    me = ig_request("GET", f"{FB_GRAPH}/me", params={"fields": "id,name", "access_token": token})
    raise RuntimeError(f"לא נמצא חשבון אינסטגרם מקושר למפתח הזה (משתמש: {me})")


def publish_reel(video: Path, text: str, token: str) -> str:
    uid, _ = connect(token)
    c = {"id": create_container(uid, video, text, token)}
    for _ in range(60):  # עד 10 דקות עיבוד
        st = ig_request("GET", f"{GRAPH}/{c['id']}", params={"fields": "status_code,status", "access_token": token})
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram processing error: {st}")
        time.sleep(10)
    else:
        raise RuntimeError("Instagram processing timeout")
    pub = ig_request("POST", f"{GRAPH}/{uid}/media_publish", data={"creation_id": c["id"], "access_token": token})
    return pub["id"]


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="only report whether a post is due")
    ap.add_argument("--plan", type=int, metavar="DAYS")
    ap.add_argument("--build", type=int, metavar="UNIT")
    ap.add_argument("--now", help="ISO time, for testing")
    ap.add_argument("--whoami", action="store_true", help="בדיקת חיבור לאינסטגרם")
    args = ap.parse_args()

    if args.whoami:
        uid, username = connect(os.environ["IG_TOKEN"])
        print(f"מחובר לאינסטגרם: @{username} (id {uid}) דרך {GRAPH}")
        lim = ig_request("GET", f"{GRAPH}/{uid}/content_publishing_limit",
                         params={"fields": "quota_usage,config", "access_token": os.environ["IG_TOKEN"]})
        print("מכסת פרסום:", lim)
        return

    if args.plan:
        start = max(dt.date.fromisoformat(CONFIG["cycle_start"]), dt.datetime.now(TZ).date())
        first = dt.date.fromisoformat(CONFIG["cycle_start"])
        for i in range(args.plan):
            day = start + dt.timedelta(days=i)
            n = (day - first).days % len(UNITS)
            rt = release_time(day)
            tag = "שבת/חג" if is_holy(day) else ("ערב שבת/חג" if is_holy(day + dt.timedelta(days=1)) else "")
            print(f"{day} {day.strftime('%a')}  {hebrew_date(day):<16} פרק {gematria(UNITS[n]['chapter']):<5} "
                  f"עולה ב-{rt.strftime('%a %d/%m %H:%M')}  {tag}")
        return

    if args.build:
        unit = UNITS[args.build - 1]
        out = build_video(unit, ROOT / "out" / f"unit_{args.build:03d}.mp4")
        print(out)
        print(caption(unit, dt.datetime.now(TZ).date()))
        return

    now = dt.datetime.fromisoformat(args.now).astimezone(TZ) if args.now else dt.datetime.now(TZ)
    state = load_state()
    job = next_job(now, state)
    if not job:
        print(f"{now:%Y-%m-%d %H:%M} – אין מה להעלות עכשיו.")
        return
    unit, day, kind = job
    if args.check:
        if os.environ.get("IG_TOKEN_SET", "true") != "true":
            print("IG_TOKEN עדיין לא הוגדר – מדלג (שום פרק לא מסומן כהועלה).")
            return
        print(f"due: chapter {unit['chapter']} of {day}")
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write("post=true\n")
        return
    text = caption(unit, day if day == now.date() else now.date())
    print(f"מעלה את פרק {gematria(unit['chapter'])} (של {day})\n{text}")
    if args.dry_run:
        return
    video = build_video(unit, ROOT / "out" / "reel.mp4")
    media_id = publish_reel(video, text, os.environ["IG_TOKEN"])
    slot = planned_slot(day) if (kind == "cycle" and day == now.date() and day_kind(day) != "holy") else None
    state["posted"].append({"chapter": unit["chapter"], "day": day.isoformat(), "kind": kind,
                            "day_kind": day_kind(day), "slot": slot,
                            "at": now.isoformat(timespec="minutes"), "media_id": media_id})
    save_state(state)
    print(f"הועלה בהצלחה: {media_id}")


if __name__ == "__main__":
    sys.exit(main())
