"""לומד מהנתונים של אינסטגרם מה השעה הכי טובה להעלאה.

לכל ריל שעלה לפני יומיים לפחות, שואב מאינסטגרם לכמה אנשים הוא הגיע (reach),
מחשב ממוצע לכל שעת העלאה (בנפרד לימי חול ולערבי שבת/חג), ושומר את השעה המנצחת ב-learn.json.
שעה נבחרת רק אם יש לה לפחות 2 ריילס להשוואה.
"""
import datetime as dt, json, os, statistics, sys
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
GRAPH = "https://graph.instagram.com/v21.0"
token = os.environ["IG_TOKEN"]
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

best, report = dict(learn.get("best", {})), {}
for kind in ("weekday", "erev"):
    by_slot = {}
    for v in cache.values():
        if v["day_kind"] == kind:
            by_slot.setdefault(v["slot"], []).append(v["reach"])
    scores = {s: statistics.mean(r) for s, r in by_slot.items() if len(r) >= 2}
    report[kind] = {s: {"avg_reach": round(statistics.mean(r)), "reels": len(r)} for s, r in by_slot.items()}
    if scores:
        best[kind] = max(scores, key=scores.get)

learn.update({"best": best, "reach": cache, "report": report, "updated": now.isoformat(timespec="minutes")})
learn_file.write_text(json.dumps(learn, ensure_ascii=False, indent=2), encoding="utf-8")
print("השעות הכי טובות כרגע:", best or config["default_slot"])
print(json.dumps(report, ensure_ascii=False, indent=2))
