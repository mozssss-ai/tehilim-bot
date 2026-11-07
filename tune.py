"""לומד מהנתונים של אינסטגרם מה השעה הכי טובה להעלאה – משני מקורות:

1. מתי העוקבים מחוברים (online_followers מהתובנות של אינסטגרם) – נותן כיוון כבר מהשבוע הראשון.
2. ניסוי: לכמה אנשים הגיע כל ריל בפועל (reach) לפי שעת ההעלאה – מתקן אם אינסטגרם "מוטה".
   שעה שהוכיחה בניסוי reach גבוה ביותר מ-15% גוברת על השעה לפי העוקבים.

לכל ריל שעלה לפני יומיים לפחות, שואב מאינסטגרם לכמה אנשים הוא הגיע (reach),
מחשב ממוצע לכל שעת העלאה (בנפרד לימי חול ולערבי שבת/חג), ושומר את השעה המנצחת ב-learn.json.
שעה נבחרת רק אם יש לה לפחות 2 ריילס להשוואה.
"""
import datetime as dt, json, os, statistics, sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import bot  # noqa: E402
token = os.environ["IG_TOKEN"]
bot.connect(token)
GRAPH = bot.GRAPH
state = json.loads((ROOT / "state.json").read_text(encoding="utf-8"))
config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
learn_file = ROOT / "learn.json"
learn = json.loads(learn_file.read_text(encoding="utf-8")) if learn_file.exists() else {}

now = dt.datetime.now(dt.timezone.utc)
cache = learn.get("reach", {})
for p in state["posted"]:
    if not p.get("slot") or not p.get("media_id"):
        continue
    age = now - dt.datetime.fromisoformat(p["at"]).astimezone(dt.timezone.utc)
    if age < dt.timedelta(days=2) or p["media_id"] in cache:
        continue
    r = requests.get(f"{GRAPH}/{p['media_id']}/insights",
                     params={"metric": "reach", "access_token": token}, timeout=60)
    if r.status_code != 200:
        print("insights failed for", p["media_id"], r.text)
        continue
    value = r.json()["data"][0]["values"][0]["value"]
    cache[p["media_id"]] = {"reach": value, "slot": p["slot"], "day_kind": p["day_kind"]}

# ---- 1. מתי העוקבים מחוברים
from zoneinfo import ZoneInfo
online = {}  # שעה בשעון ישראל -> ממוצע עוקבים מחוברים
learn.pop("online_error", None)
try:
    r = requests.get(f"{GRAPH}/{bot.connect(token)[0]}/insights", params={
        "metric": "online_followers", "period": "lifetime", "access_token": token}, timeout=60)
    learn["online_raw"] = r.text[:400]
    if r.status_code == 200 and r.json().get("data"):
        sums, counts = {}, {}
        for v in r.json()["data"][0]["values"]:
            day = dt.datetime.fromisoformat(v["end_time"].replace("+0000", "+00:00"))
            for h, n in (v.get("value") or {}).items():
                # מטא מחזירים את השעות לפי שעון החוף המערבי בארה"ב
                pt = dt.datetime(day.year, day.month, day.day, int(h), tzinfo=ZoneInfo("America/Los_Angeles"))
                il = pt.astimezone(bot.TZ).hour
                sums[il] = sums.get(il, 0) + n
                counts[il] = counts.get(il, 0) + 1
        online = {h: sums[h] / counts[h] for h in sums}
    else:
        print("online_followers לא זמין:", r.status_code, r.text[:300])
        learn["online_error"] = f"{r.status_code}: {r.text[:300]}"
except Exception as e:
    print("online_followers נכשל:", e)
    learn["online_error"] = str(e)[:300]


def online_score(slot):
    h, m = map(int, slot.split(":"))
    a, b = online.get(h, 0), online.get((h + 1) % 24, 0)
    return a + (b - a) * m / 60


# אם אינסטגרם לא מחזירים נתוני שעות – משתמשים בנתונים שהוזנו ידנית מלוח הבקרה
if not online and config.get("followers_activity_manual"):
    man = config["followers_activity_manual"]["weekday"]
    for h3, v in man.items():
        for k in range(3):
            online[(int(h3) + k) % 24] = v
    learn["online_source"] = "manual"
else:
    learn["online_source"] = "instagram"

best, report = dict(learn.get("best", {})), {}
by_followers = {}
if online:
    for kind in ("weekday", "erev"):
        by_followers[kind] = max(config["slots"][kind], key=online_score)
    best.update(by_followers)
for kind in ("weekday", "erev"):
    by_slot = {}
    for v in cache.values():
        if v["day_kind"] == kind:
            by_slot.setdefault(v["slot"], []).append(v["reach"])
    scores = {s: statistics.mean(r) for s, r in by_slot.items() if len(r) >= 2}
    report[kind] = {s: {"avg_reach": round(statistics.mean(r)), "reels": len(r),
                        "followers_online": round(online_score(s))} for s, r in by_slot.items()}
    if scores:
        top = max(scores, key=scores.get)
        base = by_followers.get(kind)
        # הניסוי גובר רק אם יש לו נתונים מספיקים וההבדל משמעותי
        if base is None or base not in scores or scores[top] > scores[base] * 1.15:
            best[kind] = top

learn["online_followers"] = {str(h): round(v) for h, v in sorted(online.items())}
learn["by_followers"] = by_followers
learn.update({"best": best, "reach": cache, "report": report, "updated": now.isoformat(timespec="minutes")})
learn_file.write_text(json.dumps(learn, ensure_ascii=False, indent=2), encoding="utf-8")
print("השעות הכי טובות כרגע:", best or config["default_slot"])
print(json.dumps(report, ensure_ascii=False, indent=2))
