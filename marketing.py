"""איש השיווק של העמוד.

בכל הרצה (לכל היותר פעם ב-marketing_refresh_hours):
  1. אוסף מאינסטגרם: עוקבים, חשיפה, כניסות לפרופיל, לחיצות על הקישור בביו, ונתונים לכל ריל.
  2. בודק השערות (מתי להעלות, איזה כיתוב מביא הכי הרבה הצטרפויות, אורך הריל, מוזיקה)
     ומסמן כל אחת: בבדיקה / אומת / לא אומת.
  3. מה שאומת – הבוט מיישם לבד (שעת העלאה דרך learn.json, נוסח כיתוב דרך marketing.json).
  4. מוציא המלצות שיווק לפי הנתונים, ובונה את דף הדשבורד לטלפון (docs/<path>/index.html).
"""
import datetime as dt
import json
import os
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import bot  # noqa: E402

FILE = ROOT / "marketing.json"
PAGE_DIR = ROOT / "docs" / "6dd35a90fba60637"
TEMPLATE = ROOT / "dashboard_template.html"
TZ = bot.TZ
REEL_METRICS = ["reach", "views", "likes", "comments", "saved", "shares", "total_interactions",
                "ig_reels_avg_watch_time"]
BASIC_METRICS = ["reach", "saved", "shares", "total_interactions"]
ACCOUNT_METRICS = ["reach", "profile_views", "website_clicks", "accounts_engaged", "total_interactions",
                   "follows_and_unfollows", "profile_links_taps"]


def load(p, default):
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


class Api:
    def __init__(self, token):
        self.token = token
        self.uid, self.username = bot.connect(token)
        self.G = bot.GRAPH
        self.errors = []

    def get(self, path, **params):
        params["access_token"] = self.token
        return bot.ig_request("GET", f"{self.G}/{path}", params=params)

    def safe(self, label, path, **params):
        try:
            return self.get(path, **params)
        except Exception as e:  # מדד שאינסטגרם לא מחזיר לא מפיל את הכל
            self.errors.append(f"{label}: {str(e)[:160]}")
            return None


def insight_values(resp):
    out = {}
    for d in (resp or {}).get("data", []):
        if "total_value" in d:
            out[d["name"]] = d["total_value"].get("value")
            for b in d["total_value"].get("breakdowns", []) or []:
                for r in b.get("results", []):
                    out[f"{d['name']}:{'/'.join(r.get('dimension_values', []))}"] = r.get("value")
        elif d.get("values"):
            out[d["name"]] = d["values"][-1].get("value")
    return out


def collect(api, m):
    now = dt.datetime.now(dt.timezone.utc)
    acc = api.safe("account", api.uid, fields="followers_count,follows_count,media_count,username,website") or {}
    # מדדי החשבון: אתמול ו-7 הימים האחרונים
    account = {}
    for label, days in (("day", 1), ("week", 7), ("month", 28)):
        until = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        since = until - days * 86400
        vals = {}
        for metric in ACCOUNT_METRICS:
            extra = {"breakdown": "follow_type"} if metric == "follows_and_unfollows" else {}
            r = api.safe(f"account {metric}/{label}", f"{api.uid}/insights", metric=metric, period="day",
                         metric_type="total_value", since=since, until=until, **extra)
            vals.update(insight_values(r))
        account[label] = vals
    # עוקבים חדשים לכל יום (30 יום אחורה)
    daily_new = {}
    r = api.safe("follower_count", f"{api.uid}/insights", metric="follower_count", period="day",
                 since=int((now - dt.timedelta(days=29)).timestamp()), until=int(now.timestamp()))
    for d in (r or {}).get("data", []):
        for v in d.get("values", []):
            daily_new[v["end_time"][:10]] = v["value"]

    media = (api.safe("media", f"{api.uid}/media",
                      fields="id,caption,timestamp,permalink,like_count,comments_count,media_product_type",
                      limit=40) or {}).get("data", [])
    cache = m.setdefault("media_cache", {})
    for x in media:
        ts = dt.datetime.fromisoformat(x["timestamp"].replace("+0000", "+00:00"))
        c = cache.setdefault(x["id"], {})
        c.update({"timestamp": x["timestamp"], "permalink": x.get("permalink"),
                  "caption": (x.get("caption") or "").split("\n")[0][:60],
                  "likes": x.get("like_count", 0), "comments": x.get("comments_count", 0),
                  "type": x.get("media_product_type")})
        # נתונים של ריל מתייצבים אחרי כמה ימים; אחרי 14 יום לא שואבים שוב
        if c.get("final") or (now - ts).days > 30:
            continue
        r = api.safe(f"media {x['id']}", f"{x['id']}/insights", metric=",".join(REEL_METRICS)) \
            if x.get("media_product_type") == "REELS" else None
        if r is None:
            r = api.safe(f"media {x['id']} basic", f"{x['id']}/insights", metric=",".join(BASIC_METRICS))
        for d in (r or {}).get("data", []):
            c[d["name"]] = d["values"][0]["value"] if d.get("values") else d.get("total_value", {}).get("value")
        c["final"] = (now - ts).days >= 14

    recent_comments = []
    for x in media[:6]:
        r = api.safe(f"comments {x['id']}", f"{x['id']}/comments", fields="text,username,timestamp", limit=20)
        for c in (r or {}).get("data", []):
            if c.get("username") != api.username:
                recent_comments.append({"text": c.get("text", ""), "user": c.get("username", ""),
                                        "at": c.get("timestamp", ""), "post": cache[x["id"]]["caption"]})
    recent_comments.sort(key=lambda c: c["at"], reverse=True)

    today = dt.datetime.now(TZ).date().isoformat()
    if acc.get("followers_count") is not None:
        m.setdefault("followers_history", {})[today] = acc["followers_count"]
    m["account"] = {"followers": acc.get("followers_count"), "following": acc.get("follows_count"),
                    "media_count": acc.get("media_count"), "username": acc.get("username", api.username),
                    "website": acc.get("website"), **{k: v for k, v in account.items()}}
    m["daily_new_followers"] = daily_new
    m["recent_comments"] = recent_comments[:25]
    m["api_errors"] = api.errors[-15:]


# ------------------------------------------------------------------ analysis
def rate(num, den):
    return round(num / den, 4) if den else 0


def analyse(m, state, replied):
    cfg = bot.CONFIG
    cache = m.get("media_cache", {})
    joins_by_media = defaultdict(int)
    dms_ok = 0
    for r in replied.get("done", []):
        joins_by_media[r["media_id"]] += 1
        dms_ok += 1 if r.get("dm") else 0
    reels = []
    for p in state.get("posted", []):
        c = cache.get(p.get("media_id") or "", {})
        reels.append({**p, **{k: c.get(k) for k in ("reach", "views", "likes", "comments", "saved", "shares",
                                                   "total_interactions", "ig_reels_avg_watch_time", "permalink")},
                      "joins": joins_by_media.get(p.get("media_id"), 0), "cta": p.get("cta", 0)})
    ready = [r for r in reels if r.get("reach")]

    hyps = []

    # 1. שעת העלאה
    by_slot = defaultdict(list)
    for r in ready:
        if r.get("slot"):
            by_slot[(r["day_kind"], r["slot"])].append(r["reach"])
    slot_rows = [{"kind": k, "slot": s, "n": len(v), "avg_reach": round(statistics.mean(v))}
                 for (k, s), v in sorted(by_slot.items())]
    for kind, name in (("weekday", "ימי חול"), ("erev", "ערב שבת/חג")):
        rows = [x for x in slot_rows if x["kind"] == kind and x["n"] >= 2]
        best = max(rows, key=lambda x: x["avg_reach"]) if len(rows) >= 2 else None
        others = [x["avg_reach"] for x in rows if best and x is not best]
        if best and others and best["avg_reach"] > 1.15 * statistics.mean(others):
            st, txt = "validated", f"ב{name} השעה {best['slot']} מביאה בממוצע {best['avg_reach']} חשיפות – " \
                                   f"{round(100 * (best['avg_reach'] / statistics.mean(others) - 1))}% יותר משאר השעות. הבוט מעלה בה."
        elif best:
            st, txt = "rejected", f"ב{name} אין עדיין שעה שבולטת מעל השאר – ממשיכים לנסות שעות שונות."
        else:
            n = sum(x["n"] for x in slot_rows if x["kind"] == kind)
            st, txt = "testing", f"צריך לפחות 2 ריילס בכל אחת משתי שעות כדי להשוות ({n} עד עכשיו)."
        hyps.append({"title": f"השעה הכי טובה להעלאה – {name}", "status": st, "text": txt})

    # 2. נוסח הכיתוב (A/B) – כמה כותבים "תהילים" (= מבקשים להצטרף) ביחס לחשיפה
    variants = cfg.get("cta_variants", [""])
    cta = {}
    for i in range(len(variants)):
        rs = [r for r in ready if r["cta"] == i]
        reach = sum(r["reach"] for r in rs)
        joins = sum(r["joins"] for r in rs)
        shares = sum(r.get("shares") or 0 for r in rs)
        cta[str(i)] = {"n": len([r for r in reels if r["cta"] == i]), "n_ready": len(rs), "reach": reach,
                       "joins": joins, "shares": shares, "join_rate": rate(joins, reach),
                       "score": rate(joins * 3 + shares, reach), "text": variants[i]}
    m["cta"] = cta
    enough = [k for k, v in cta.items() if v["n_ready"] >= 3]
    if len(variants) < 2:
        pass  # ניסוי כיתוב רק בנוסחים שמשה חיים אישר (cta_variants ב-config)
    elif len(enough) == len(variants) and len(variants) > 1:
        best = max(enough, key=lambda k: cta[k]["score"])
        rest = [cta[k]["score"] for k in enough if k != best]
        if cta[best]["score"] > 1.2 * statistics.mean(rest) and cta[best]["joins"] >= 3:
            m["cta_best"] = int(best)
            hyps.append({"title": "איזה כיתוב מביא הכי הרבה הצטרפויות", "status": "validated",
                         "text": f"נוסח {chr(65 + int(best))} מנצח ({cta[best]['joins']} בקשות הצטרפות). הבוט משתמש בו ברוב הימים."})
        else:
            hyps.append({"title": "איזה כיתוב מביא הכי הרבה הצטרפויות", "status": "rejected",
                         "text": "אין הבדל ברור בין הנוסחים – ממשיכים לבדוק."})
    else:
        hyps.append({"title": "איזה כיתוב מביא הכי הרבה הצטרפויות", "status": "testing",
                     "text": f"ניסוי A/B על {len(variants)} נוסחים. צריך 3 ריילס לכל נוסח "
                             f"({', '.join(chr(65 + int(k)) + ':' + str(v['n_ready']) for k, v in cta.items())})."})

    # 3. אורך הריל – כמה מהריל אנשים רואים
    watch = [(r["secs"], r["ig_reels_avg_watch_time"] / 1000) for r in ready
             if r.get("secs") and r.get("ig_reels_avg_watch_time")]
    if len(watch) >= 4:
        short = [w / s for s, w in watch if s <= 45]
        long_ = [w / s for s, w in watch if s > 45]
        avg = statistics.mean(w / s for s, w in watch)
        txt = f"בממוצע צופים ב-{round(100 * avg)}% מהריל."
        if short and long_:
            txt += f" ריילס קצרים (עד 45 שנ'): {round(100 * statistics.mean(short))}%, " \
                   f"ארוכים: {round(100 * statistics.mean(long_))}%."
        hyps.append({"title": "האם ריילס קצרים נצפים עד הסוף יותר", "status":
                     "validated" if short and long_ and statistics.mean(short) > 1.2 * statistics.mean(long_) else "testing",
                     "text": txt})
    else:
        hyps.append({"title": "האם ריילס קצרים נצפים עד הסוף יותר", "status": "testing",
                     "text": f"נאסף זמן צפייה ממוצע לכל ריל ({len(watch)}/4 ריילס)."})

    # 4. מוזיקה
    by_music = defaultdict(list)
    for r in ready:
        if r.get("music"):
            by_music[r["music"]].append(r["reach"])
    music_rows = sorted(({"track": k, "n": len(v), "avg_reach": round(statistics.mean(v))} for k, v in by_music.items()),
                        key=lambda x: -x["avg_reach"])
    hyps.append({"title": "איזו מוזיקה עובדת הכי טוב", "status": "testing" if len(music_rows) < 10 else "validated",
                 "text": (f"מוביל עד עכשיו: {music_rows[0]['track']} ({music_rows[0]['avg_reach']} חשיפות בממוצע). "
                          if music_rows else "") + f"נבדקו {len(music_rows)} מתוך 25 מנגינות."})

    # ---------------------------------------------------------------- recommendations
    acc = m.get("account", {})
    week = acc.get("week", {})
    recs = []
    reach_w, profile_w = week.get("reach") or 0, week.get("profile_views") or 0
    clicks_w = (week.get("website_clicks") or 0) + (week.get("profile_links_taps") or 0)
    if ready:
        avg_reach = statistics.mean(r["reach"] for r in ready)
        saves = sum(r.get("saved") or 0 for r in ready)
        shares = sum(r.get("shares") or 0 for r in ready)
        joins = sum(r["joins"] for r in ready)
        if shares < 0.01 * sum(r["reach"] for r in ready):
            recs.append(("high", "מעט שיתופים",
                         "שיתוף הוא מה שמביא אנשים חדשים. כדאי לבקש מחברי הקבוצה בוואטסאפ לשתף את הריל היומי לסטטוס."))
        if joins == 0 and len(ready) >= 3:
            recs.append(("high", "עוד אף אחד לא כתב \"תהילים\"",
                         "כדאי לנעוץ פוסט \"איך מצטרפים\" ראשון בפרופיל, ולהזכיר בסטורי פעם בשבוע: "
                         "\"כתבו תהילים ונשלח לכם קישור\"."))
        if saves > shares * 2:
            recs.append(("mid", "אנשים שומרים את הפרקים",
                         "סימן שהתוכן חשוב להם. אפשר להעלות פעם בשבוע פוסט מסכם – \"הפרקים של השבוע\" – "
                         "וזה ישמר עוד יותר."))
        if avg_reach < (acc.get("followers") or 0) * 0.3:
            recs.append(("mid", "הריילס מגיעים לחלק קטן מהעוקבים",
                         "תגובות בשעה הראשונה מקדמות ריל. אפשר לבקש מכמה חברים בקבוצה להגיב/לסמן לייק מיד כשהפרק עולה."))
    if reach_w and profile_w and profile_w / reach_w < 0.02:
        recs.append(("mid", "מעט כניסות לפרופיל ביחס לחשיפה",
                     "אנשים רואים אבל לא נכנסים. כדאי שהשורה הראשונה בביו תסביר בחצי משפט מה מקבלים: "
                     "\"פרק תהילים אחד ביום בוואטסאפ – הצטרפו 👇\"."))
    if profile_w and clicks_w / max(profile_w, 1) < 0.05:
        recs.append(("mid", "מי שנכנס לפרופיל כמעט לא לוחץ על הקישור",
                     "כדאי שהקישור לקבוצה יהיה הקישור היחיד בביו, ושהפוסט הנעוץ הראשון יהיה \"גם אני בקבוצת\"."))
    recs.append(("idea", "שיתוף פעולה", "לפנות לעמודי תורה/תפילה בגודל דומה ולהציע Collab על ריל – הריל מופיע אצל שני הקהלים."))
    recs.append(("idea", "רגעי שיא", "בסיום הספר (פרק ק\"נ) – ריל חגיגי \"סיימנו את ספר התהילים יחד\" + הזמנה למחזור הבא. "
                 "זה תוכן שאנשים משתפים."))
    recs.append(("idea", "הקדשות", "להציע בכל ריל \"הפרק מוקדש לרפואת/לעילוי נשמת...\" – אנשים משתפים פרק שמוקדש ליקיריהם."))
    recs.append(("idea", "ערב שבת", "בערב שבת העוקבים פעילים בצהריים – אפשר להוסיף סטורי \"שבת שלום\" עם תזכורת להצטרף."))
    m["recommendations"] = [{"level": a, "title": b, "text": c} for a, b, c in recs]
    m["hypotheses"] = hyps
    m["slot_rows"] = slot_rows
    m["music_rows"] = music_rows[:10]
    m["reels"] = sorted(reels, key=lambda r: r.get("at", ""), reverse=True)[:40]
    m["totals"] = {"posted": len(state.get("posted", [])), "tehilim_comments": len(replied.get("done", [])),
                   "dms_sent": dms_ok, "reach_sum": sum(r["reach"] for r in ready),
                   "views_sum": sum(r.get("views") or 0 for r in ready),
                   "shares_sum": sum(r.get("shares") or 0 for r in ready),
                   "saves_sum": sum(r.get("saved") or 0 for r in ready),
                   "likes_sum": sum(r.get("likes") or 0 for r in ready)}


# ------------------------------------------------------------------ page
def render(m, state):
    now = dt.datetime.now(TZ)
    upcoming = []
    st = json.loads(json.dumps(state))
    t = now
    for _ in range(6):  # הפרקים הבאים
        job = None
        for step in range(0, 60 * 24 * 10, 30):
            j = bot.next_job(t + dt.timedelta(minutes=step), st)
            if j:
                job = (j, t + dt.timedelta(minutes=step))
                break
        if not job:
            break
        (unit, day, kind), when = job
        rel = max(bot.release_time(day), when) if kind == "cycle" else when
        upcoming.append({"chapter": bot.gematria(unit["chapter"]), "at": rel.strftime("%d/%m %H:%M"),
                         "kind": kind})
        st["posted"].append({"chapter": unit["chapter"], "day": day.isoformat(), "kind": kind,
                             "at": rel.isoformat(timespec="minutes")})
        t = rel + dt.timedelta(minutes=26)
    data = {k: m.get(k) for k in ("account", "followers_history", "daily_new_followers", "recent_comments",
                                  "hypotheses", "recommendations", "slot_rows", "music_rows", "reels",
                                  "totals", "cta", "api_errors")}
    data["upcoming"] = upcoming
    import extras
    ded = extras.load_ded()
    data["dedications"] = {"queue": [{**q, "eta": extras.queue_eta(i)} for i, q in enumerate(ded.get("queue", []))],
                           "done": ded.get("done", [])[-10:][::-1], "inbox_error": ded.get("inbox_error")}
    import manage
    data["switches"] = [{"key": k, "label": v, "on": bool(bot.CONFIG.get(k))} for k, v in manage.SWITCHES.items()]
    data["repo"] = os.environ.get("GITHUB_REPOSITORY", "mozssss-ai/tehilim-bot")
    data["updated"] = now.strftime("%d/%m/%Y %H:%M")
    data["next_post"] = upcoming[0] if upcoming else None
    for r in data["reels"] or []:
        r["chapter_h"] = bot.gematria(r["chapter"])
    PAGE_DIR.mkdir(parents=True, exist_ok=True)
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*DATA*/null", json.dumps(data, ensure_ascii=False))
    (PAGE_DIR / "index.html").write_text(html, encoding="utf-8")
    (ROOT / "docs" / "index.html").write_text("<!doctype html><meta charset=utf-8><title>.</title>", encoding="utf-8")
    (ROOT / "docs" / ".nojekyll").write_text("", encoding="utf-8")


def main():
    m = load(FILE, {})
    state = load(bot.STATE_FILE, {"posted": []})
    replied = load(ROOT / "replied.json", {"done": []})
    token = os.environ.get("IG_TOKEN", "").strip()
    last = m.get("refreshed")
    hours = bot.CONFIG.get("marketing_refresh_hours", 3)
    just_posted = state["posted"] and state["posted"][-1].get("media_id") not in m.get("media_cache", {})
    due = "--force" in sys.argv or just_posted or not last or \
        dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(last) > dt.timedelta(hours=hours)
    if token and due:
        collect(Api(token), m)
        m["refreshed"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")
        print("נאספו נתונים מאינסטגרם. שגיאות:", len(m["api_errors"]))
        for e in m["api_errors"]:
            print("  ", e)
    analyse(m, state, replied)
    FILE.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    render(m, state)
    print("הדשבורד עודכן.")


if __name__ == "__main__":
    main()
