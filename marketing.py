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
from PIL import Image  # noqa: E402

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
    for label, days, back in (("day", 1, 0), ("week", 7, 0), ("prevweek", 7, 7), ("month", 28, 0)):
        until = int(now.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()) - back * 86400
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
        # כמה עוקבים וכניסות לפרופיל הביא כל פוסט (אם אינסטגרם מאפשר למדד הזה)
        if not m.get("no_media_follows"):
            r2 = api.safe(f"media {x['id']} follows", f"{x['id']}/insights", metric="follows,profile_visits")
            if r2 is None and x.get("media_product_type") == "REELS":
                m["no_media_follows"] = True  # לא נתמך בריילס – לא מנסים שוב
            for d in (r2 or {}).get("data", []):
                c[d["name"]] = d["values"][0]["value"] if d.get("values") else d.get("total_value", {}).get("value")
        c["final"] = (now - ts).days >= 14

    # סטוריז – אינסטגרם שומר את הנתונים שלהם רק 24 שעות, לכן אוספים כל שעה ושומרים
    story_types = {}
    for p in load(bot.STATE_FILE, {"posted": []}).get("posted", []):
        for sid in (p.get("story_id") or "").split(","):
            if sid:
                story_types[sid] = f"פרק {bot.gematria(p['chapter'])}"
        for kind, sid in (p.get("extras") or []):
            story_types[sid] = {"shabbat_story": "שבת/חג", "invite_story": "הזמנה להקדשות",
                                "holiday_story": "חג", "siyum_story": "סיום הספר"}.get(kind, kind)
    sc = m.setdefault("story_cache", {})
    for s in (api.safe("stories", f"{api.uid}/stories", fields="id,timestamp,permalink") or {}).get("data", []):
        r = api.safe(f"story {s['id']}", f"{s['id']}/insights", metric="reach,replies,views,shares,total_interactions,navigation",
                     breakdown="story_navigation_action_type")
        if r is None:
            r = api.safe(f"story {s['id']} basic", f"{s['id']}/insights", metric="reach,replies")
        c = sc.setdefault(s["id"], {"timestamp": s["timestamp"], "type": story_types.get(s["id"], "סטורי")})
        for d in (r or {}).get("data", []):
            if d["name"] == "navigation":
                for b in d.get("total_value", {}).get("breakdowns", []) or []:
                    for res in b.get("results", []):
                        c["nav_" + "_".join(res.get("dimension_values", []))] = res.get("value")
            else:
                c[d["name"]] = d["values"][0]["value"] if d.get("values") else d.get("total_value", {}).get("value")
    for k in sorted(sc, key=lambda k: sc[k]["timestamp"])[:-60]:
        sc.pop(k)
    # תוקף מפתח הגישה
    dbg = api.safe("token", "debug_token", input_token=api.token)
    if dbg and dbg.get("data"):
        m["token_expires"] = dbg["data"].get("expires_at", 0)

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
    # יומן עוקבים: כמה התחילו לעקוב וכמה הפסיקו – לכל יום (אתמול), נשמר להיסטוריה
    yday = (dt.datetime.now(TZ).date() - dt.timedelta(days=1)).isoformat()
    day = account.get("day", {})
    if acc.get("followers_count") is not None:
        log = m.setdefault("follow_log", {})
        log[yday] = {"follows": day.get("follows_and_unfollows:FOLLOWER", 0) or 0,
                     "unfollows": day.get("follows_and_unfollows:NON_FOLLOWER", 0) or 0,
                     "profile_views": day.get("profile_views", 0) or 0,
                     "followers": m.get("followers_history", {}).get(yday)}
        for k in sorted(log)[:-120]:
            log.pop(k)
    # מאיפה העוקבים (עיר, גיל, מגדר) – פעם ביום מספיק
    demo = m.get("demographics") or {}
    if demo.get("date") != today:
        new = {"date": today}
        for br in ("city", "age", "gender"):
            r = api.safe(f"demographics {br}", f"{api.uid}/insights", metric="follower_demographics",
                         period="lifetime", metric_type="total_value", breakdown=br)
            vals = {}
            for d in (r or {}).get("data", []):
                for b in d.get("total_value", {}).get("breakdowns", []) or []:
                    for res in b.get("results", []):
                        vals["/".join(res.get("dimension_values", []))] = res.get("value")
            if vals:
                new[br] = dict(sorted(vals.items(), key=lambda kv: -kv[1])[:8])
        if len(new) > 1:
            m["demographics"] = new
    m["recent_comments"] = recent_comments[:25]
    m["api_errors"] = api.errors[-15:]


# ------------------------------------------------------------------ insights
REC_FILE = ROOT / "rec_status.json"


def pct(a, b):
    return round(100 * a / b) if b else 0


def insights(m, reels, ready, replied):
    """כל תובנה: id, level (high/mid/info/idea), title, text, evidence. נבנית רק מנתונים אמיתיים,
    ונעלמת לבד כשהמצב משתנה. משה חיים יכול לסמן "בוצע"/"לא רלוונטי" מהדשבורד (rec_status.json)."""
    out = []
    # משווים רק ריילס שעברו לפחות יום מאז שעלו (ריל חדש עוד לא צבר חשיפה)
    day_ago = dt.datetime.now(TZ) - dt.timedelta(hours=24)
    ready_all = ready
    ready = [r for r in ready if r.get("slot") and dt.datetime.fromisoformat(r["at"]) < day_ago]
    add = lambda i, lvl, title, text, ev="": out.append({"id": i, "level": lvl, "title": title, "text": text, "evidence": ev})
    acc = m.get("account", {})
    week, month = acc.get("week", {}), acc.get("month", {})
    now = dt.datetime.now(TZ)
    reach_w, prof_w = week.get("reach") or 0, week.get("profile_views") or 0
    clicks_w = (week.get("website_clicks") or 0) + (week.get("profile_links_taps") or 0)
    week_ago = now - dt.timedelta(days=7)
    joins_w = sum(1 for r in replied.get("done", []) if dt.datetime.fromisoformat(r["at"]) > week_ago)

    # 0. עוקבים: כמה מצטרפים מול כמה עוזבים
    f_m = month.get("follows_and_unfollows:FOLLOWER") or 0
    u_m = month.get("follows_and_unfollows:NON_FOLLOWER") or 0
    if f_m + u_m >= 8 and u_m >= 0.5 * f_m:
        add("followers-churn", "high", "הרבה עוקבים עוזבים",
            f"על כל 10 שמתחילים לעקוב, בערך {round(10 * u_m / f_m) if f_m else 10} מפסיקים. בדרך כלל עוזבים כשהתוכן "
            "לא מה שציפו לו או כשיש יותר מדי פוסטים ביום. כדאי לשמור על פרק אחד קבוע ביום ולהבהיר בביו מה מקבלים.",
            f"28 ימים: {f_m} התחילו לעקוב · {u_m} הפסיקו · נטו {f_m - u_m:+d}")
    by_f = [r for r in ready_all if r.get("follows") is not None]
    if len(by_f) >= 3 and max(r["follows"] for r in by_f) > 0:
        top = max(by_f, key=lambda r: r["follows"])
        add(f"followers-top-{top.get('chapter')}", "info", f"הריל שהביא הכי הרבה עוקבים: פרק {bot.gematria(top['chapter'])}",
            "כדאי לבדוק מה היה שונה בו (שעה, מוזיקה, אורך) ולנסות לחזור על זה.",
            " · ".join(f"פרק {bot.gematria(r['chapter'])}: {r['follows']}" for r in
                       sorted(by_f, key=lambda r: -r["follows"])[:5]))
    prof_m = month.get("profile_views") or 0
    if prof_m >= 50 and f_m and f_m / prof_m < 0.05:
        add("followers-profile", "mid", "נכנסים לפרופיל ולא מתחילים לעקוב",
            f"רק {pct(f_m, prof_m)}% מהכניסות לפרופיל הפכו לעוקבים. הפרופיל הוא חלון הראווה: תמונת פרופיל ברורה, "
            "שורה ראשונה בביו שמסבירה מה מקבלים, ושלושה ריילס מוצמדים חזקים.",
            f"28 ימים: {prof_m} כניסות לפרופיל → {f_m} עוקבים חדשים")

    # 1. משפך: חשיפה -> כניסה לפרופיל -> לחיצה על הקישור / "תהילים" בתגובה
    if reach_w >= 100:
        ev = f"7 ימים: {reach_w} חשיפות → {prof_w} כניסות לפרופיל ({pct(prof_w, reach_w)}%) → " \
             f"{clicks_w} לחיצות על הקישור · {joins_w} כתבו \"תהילים\""
        steps = [("profile", prof_w / reach_w, .03, "רואים את הריילס, אבל מעט נכנסים לפרופיל",
                  "החיבור בין הריל לעמוד חלש. הכי משפיע: לבקש בכיתוב משהו פשוט לעשות עכשיו (כתבו \"תהילים\"), "
                  "ובפינה של הריל יש כבר QR – אפשר לשקול להזכיר בסוף הריל \"הקישור בביו\"."),
                 ("link", (clicks_w / prof_w) if prof_w else 1, .08, "נכנסים לפרופיל, אבל לא לוחצים על הקישור",
                  "הביו הוא המקום שבו מחליטים. כדאי שהשורה הראשונה תסביר מה מקבלים (\"פרק תהילים אחד ביום בוואטסאפ\") "
                  "ושהקישור לקבוצה יהיה היחיד בביו.")]
        weak = [s for s in steps if s[1] < s[2]]
        if weak:
            w = min(weak, key=lambda s: s[1] / s[2])
            add(f"funnel-{w[0]}", "high", w[3], w[4], ev)
        else:
            add("funnel-ok", "info", "המשפך עובד", "החשיפה הופכת לכניסות ולחיצות ביחס טוב – השלב הבא הוא להגדיל חשיפה (שיתופים).", ev)

    # 2. מה מבדיל ריל חזק מריל חלש
    if len(ready) >= 6:
        rs = sorted(ready, key=lambda r: r["reach"])
        q = max(2, len(rs) // 4)
        low, high = rs[:q], rs[-q:]
        avg = lambda xs, k: statistics.mean([x[k] for x in xs if x.get(k)] or [0])
        hour = lambda r: int(r["at"][11:13])
        diffs = []
        if avg(high, "secs") and avg(low, "secs"):
            diffs.append(("len", abs(avg(high, "secs") - avg(low, "secs")) / max(avg(low, "secs"), 1),
                          f"ריילס חזקים: {round(avg(high, 'secs'))} שנ' בממוצע, חלשים: {round(avg(low, 'secs'))} שנ'"))
        hh, hl = statistics.mean(map(hour, high)), statistics.mean(map(hour, low))
        diffs.append(("hour", abs(hh - hl) / 12, f"ריילס חזקים עלו בממוצע ב-{hh:.0f}:00, חלשים ב-{hl:.0f}:00"))
        dh = sum(1 for r in high if r.get("dedication")) / len(high)
        dl = sum(1 for r in low if r.get("dedication")) / len(low)
        if dh or dl:
            diffs.append(("ded", abs(dh - dl), f"{pct(dh, 1)}% מהחזקים היו מוקדשים, לעומת {pct(dl, 1)}% מהחלשים"))
        best = max(diffs, key=lambda x: x[1])
        add(f"top-vs-low-{best[0]}", "mid", "מה מבדיל ריל חזק מחלש",
            f"השוואה בין {q} הריילס החזקים ל-{q} החלשים. ההבדל הבולט: {best[2]}. "
            f"הבוט ממשיך לבדוק את זה ככל שמצטברים ריילס.",
            f"הכי חזק: פרק {bot.gematria(high[-1]['chapter'])} ({high[-1]['reach']} חשיפות) · "
            f"הכי חלש: פרק {bot.gematria(low[0]['chapter'])} ({low[0]['reach']})")
    else:
        add("learning-reels", "info", "הבוט עדיין לומד",
            f"להשוואות נכנסים רק ריילס של הפרק היומי שעלו בשעה המתוכננת – לא ההשלמות שעלו בלילה. "
            f"יש כרגע {len(ready)} כאלה; מ-6 הבוט יתחיל להשוות בין ריילס חזקים לחלשים (אורך, שעה, הקדשה, מוזיקה).")
    if m.get("music_best_style"):
        add(f"style-{m['music_best_style']}", "mid", f"סגנון \"{m['music_best_style']}\" מוביל",
            "הבוט כבר בוחר ממנו ברוב הפרקים. אם תרצה, אכין עוד מנגינות בסגנון הזה (רק באישורך) כדי לגוון בלי לאבד את מה שעובד.",
            " · ".join(f"{s['style']}: {s['avg_reach']} ({s['n']})" for s in m.get("style_rows", [])[:4]))

    # 3. שיתופים ושמירות – מה מביא אנשים חדשים (כל הריילס)
    ready = ready_all
    if len(ready) >= 3:
        reach = sum(r["reach"] for r in ready)
        sh = sum(r.get("shares") or 0 for r in ready)
        sv = sum(r.get("saved") or 0 for r in ready)
        ev = f"{sh} שיתופים ו-{sv} שמירות על {reach} חשיפות ({len(ready)} ריילס)"
        if sh / reach < .01:
            add("shares-low", "high", "מעט שיתופים",
                "שיתוף הוא הדרך העיקרית שבה אנשים חדשים מגיעים. הכי יעיל: לבקש בקבוצת הוואטסאפ לשתף את הריל היומי לסטטוס "
                "(הקישור לכל ריל נמצא בדשבורד, תחת \"ריילס אחרונים\").", ev)
        elif sv > 2 * sh:
            add("saves-high", "info", "אנשים שומרים את הפרקים", "סימן שהתוכן חשוב להם וחוזרים אליו – טוב לאלגוריתם.", ev)

    # 4. כמה מהריל רואים
    watch = [(r["secs"], r["ig_reels_avg_watch_time"] / 1000) for r in ready if r.get("secs") and r.get("ig_reels_avg_watch_time")]
    if len(watch) >= 4:
        comp = statistics.mean(w / s for s, w in watch)
        ev = f"זמן צפייה ממוצע {statistics.mean(w for _, w in watch):.1f} שנ' מתוך {statistics.mean(s for s, _ in watch):.0f} שנ' ({pct(comp, 1)}%)"
        if comp < .35:
            add("watch-low", "mid", "רוב הצופים עוזבים מוקדם",
                "השניות הראשונות קובעות. אפשר לשקול ריילס קצרים יותר בפרקים ארוכים, או להתחיל את הריל בשורה מושכת – "
                "תגיד לי אם לבדוק את זה כניסוי.", ev)
        else:
            add("watch-ok", "info", "צופים בחלק גדול מהריל", "אורך הריילס מתאים לקהל.", ev)

    # 5. עוקבים
    hist = m.get("followers_history", {})
    keys = sorted(hist)
    if len(keys) >= 7:
        a, b = hist[keys[-7]], hist[keys[-1]]
        add("followers-trend", "info" if b >= a else "mid",
            "צמיחה בעוקבים" if b > a else ("העוקבים יציבים" if b == a else "ירידה בעוקבים"),
            "מעקב שבועי אחרי מספר העוקבים." + ("" if b >= a else " כדאי לבדוק בדשבורד מה השתנה השבוע (שעות, תוכן)."),
            f"לפני שבוע {a} → היום {b} ({b - a:+d})")

    # 6. הקדשות
    try:
        import extras
        ded = extras.load_ded()
        done, queue = ded.get("done", []), ded.get("queue", [])
        if done or queue:
            dmed = [r for r in ready if r.get("dedication")]
            plain = [r for r in ready if not r.get("dedication")]
            ev = f"{len(done)} פרקים הוקדשו, {len(queue)} בתור"
            if len(dmed) >= 2 and len(plain) >= 2:
                s1 = statistics.mean([(r.get("shares") or 0) / r["reach"] for r in dmed])
                s0 = statistics.mean([(r.get("shares") or 0) / r["reach"] for r in plain])
                ev += f" · שיתופים לכל 100 חשיפות: מוקדש {100 * s1:.1f}, רגיל {100 * s0:.1f}"
            add("dedications", "info", "הקדשות מהצופים", "ההקדשות יוצרות קשר אישי עם העמוד – מי שהקדיש נוטה לשתף.", ev)
    except Exception:
        pass

    # 7. רעיונות שעדיין לא בוצעו
    add("idea-collab", "idea", "שיתוף פעולה עם עמוד דומה",
        "ריל משותף (Collab) מופיע אצל שני הקהלים בבת אחת. אם תסגור שיתוף עם עמוד תורה/תפילה, הבוט יכול להוסיף אותו כשותף לריל.")

    status = load(REC_FILE, {})
    hidden = {k for k, v in status.items()
              if v.get("state") == "not_relevant" or (now - dt.datetime.fromisoformat(v["at"])).days < 30}
    order = {"high": 0, "mid": 1, "info": 2, "idea": 3}
    return sorted([x for x in out if x["id"] not in hidden], key=lambda x: order[x["level"]])


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
                                                   "total_interactions", "ig_reels_avg_watch_time", "permalink",
                                                   "follows", "profile_visits")},
                      "joins": joins_by_media.get(p.get("media_id"), 0), "cta": p.get("cta", 0)})
    ready = [r for r in reels if r.get("reach")]
    # "הוגנים": ריילס של הפרק היומי שעלו בשעה המתוכננת (בלי השלמות לילה) – רק הם נכנסים להשוואות
    fair = [r for r in ready if r.get("slot")]

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

    # 4. מוזיקה – לפי מנגינה ולפי סגנון (רק ריילס הוגנים)
    from music_styles import style_of
    by_music, by_style = defaultdict(list), defaultdict(list)
    for r in fair:
        if r.get("music"):
            by_music[r["music"]].append(r["reach"])
            if style_of(r["music"]):
                by_style[style_of(r["music"])].append(r["reach"])
    music_rows = sorted(({"track": k, "n": len(v), "avg_reach": round(statistics.mean(v))} for k, v in by_music.items()),
                        key=lambda x: -x["avg_reach"])
    style_rows = sorted(({"style": k, "n": len(v), "avg_reach": round(statistics.mean(v))} for k, v in by_style.items()),
                        key=lambda x: -x["avg_reach"])
    ok = [s for s in style_rows if s["n"] >= 3]
    if len(ok) >= 2 and ok[0]["avg_reach"] > 1.2 * statistics.mean(s["avg_reach"] for s in ok[1:]):
        m["music_best_style"] = ok[0]["style"]
        hyps.append({"title": "איזה סגנון מוזיקה עובד הכי טוב", "status": "validated",
                     "text": f"סגנון \"{ok[0]['style']}\" מביא בממוצע {ok[0]['avg_reach']} חשיפות – יותר משאר הסגנונות. "
                             "הבוט בוחר ממנו ברוב הפרקים, וממשיך לבדוק את השאר."})
    else:
        m.pop("music_best_style", None)
        hyps.append({"title": "איזה סגנון מוזיקה עובד הכי טוב", "status": "testing",
                     "text": f"נבדקים 5 סגנונות (פסנתר, נבל, גיטרה, מיתרים, פעמונים). צריך 3 ריילס בשעה המתוכננת "
                             f"לפחות בשני סגנונות ({len(fair)} ריילס כאלה עד עכשיו)."})

    # ---------------------------------------------------------------- תובנות והמלצות (נבנות מהנתונים בכל הרצה)
    m["recommendations"] = insights(m, reels, ready, replied)
    m["hypotheses"] = hyps
    m["slot_rows"] = slot_rows
    m["music_rows"] = music_rows[:10]
    m["style_rows"] = style_rows
    m["fair_count"] = len(fair)
    m["reels"] = sorted(reels, key=lambda r: r.get("at", ""), reverse=True)[:40]
    m["totals"] = {"posted": len(state.get("posted", [])), "tehilim_comments": len(replied.get("done", [])),
                   "dms_sent": dms_ok, "reach_sum": sum(r["reach"] for r in ready),
                   "views_sum": sum(r.get("views") or 0 for r in ready),
                   "shares_sum": sum(r.get("shares") or 0 for r in ready),
                   "saves_sum": sum(r.get("saved") or 0 for r in ready),
                   "likes_sum": sum(r.get("likes") or 0 for r in ready)}


# ------------------------------------------------------------------ previews & holidays
PREVIEW = PAGE_DIR / "preview"


def save_jpg(im, path, size=(360, 640)):
    """שומר רק אם התוכן השתנה – כדי לא ליצור שינויים מיותרים במאגר."""
    import io
    buf = io.BytesIO()
    im.convert("RGB").resize(size, Image.LANCZOS).save(buf, "JPEG", quality=80)
    if not path.exists() or path.read_bytes() != buf.getvalue():
        path.write_bytes(buf.getvalue())
    return path.name


def previews(upcoming, now):
    import design
    import extras
    PREVIEW.mkdir(parents=True, exist_ok=True)
    out = {}
    if upcoming:
        nxt = upcoming[0]
        unit = next(u for u in bot.UNITS if u["chapter"] == nxt["ch"])
        ded = extras.load_ded()["queue"][0] if bot.CONFIG.get("dedications") and extras.load_ded()["queue"] else None
        u2 = extras.apply_dedication(unit, ded) if ded else unit
        frames = []
        for i, f in enumerate(u2["images"], 1):
            p = bot.ROOT / f
            if bot.CONFIG.get("replace_phone_with_qr", True) and "out" not in p.parts:
                p = design.clean_footer(p, bot.ROOT / "out" / "clean" / p.name, bot.CONFIG["whatsapp_link"])
            frames.append(save_jpg(Image.open(p), PREVIEW / f"reel_{i}.jpg"))
        for old in PREVIEW.glob("reel_*.jpg"):
            if old.name not in frames:
                old.unlink()
        day = dt.date.fromisoformat(nxt["day"])
        text = bot.caption(unit, max(day, now.date()), bot.cta_index(now.date()))
        if ded:
            text = extras.dedication_caption(text, ded)
        ovr = extras.load_ovr().get("caption", {}).get(str(unit["chapter"]))
        out["reel"] = {"chapter": nxt["chapter"], "ch": unit["chapter"], "when": nxt["iso"], "at": nxt["at"],
                       "frames": frames, "caption": ovr or text, "edited": bool(ovr),
                       "dedication": ded["text"] if ded else None}
    # סטורי שבת/חג הבא
    d = now.date()
    for _ in range(400):
        if bot.day_kind(d) == "erev" and bot.release_time(d) > now - dt.timedelta(minutes=5):
            break
        d += dt.timedelta(days=1)
    base = extras.shabbat_texts(d)
    title, sub, q = extras.story_override(d, base)
    save_jpg(Image.open(design.shabbat_story(title, sub, bot.ROOT / "out" / "prev_story.png", q)), PREVIEW / "story.jpg")
    out["story"] = {"day": d.isoformat(), "when": bot.release_time(d).isoformat(), "date_h": bot.hebrew_date(d),
                    "title": title, "subtitle": sub, "edited": (title, sub) != base[:2], "img": "story.jpg"}
    save_jpg(Image.open(design.invite_story(bot.ROOT / "out" / "prev_invite.png")), PREVIEW / "invite.jpg")
    return out


def holidays(now, n=8):
    """החגים הקרובים: שם, תאריך, מתי נכנס, מתי עולה הסטורי, תמונת הסטורי והמנגינה שלו."""
    import design
    import extras
    skip = {"פורים קטן", "שושן פורים", "פסח שני", "שושן פורים קטן"}
    res, d = [], now.date()
    PREVIEW.mkdir(parents=True, exist_ok=True)
    raw = "https://raw.githubusercontent.com/mozssss-ai/tehilim-bot/main/assets/music/holiday/"
    for _ in range(800):
        if len(res) >= n:
            break
        f = extras._fest(d, True)
        prev = d - dt.timedelta(days=1)
        if f and f not in skip and extras._fest(prev, True) != f:
            start = bot.sunset(prev)
            if start > now:
                item = {"date_h": bot.hebrew_date(d), "date": d.strftime("%d/%m/%Y"), "start": start.isoformat()}
                if extras._fest(d, False):  # יום טוב – סטורי בערב החג
                    t, sub, q = extras.story_override(prev, extras.shabbat_texts(prev))
                    key = extras.HOLIDAY_TRACK.get(f, "yt")
                    img = design.shabbat_story(t, sub, bot.ROOT / "out" / f"prev_{key}.png", q)
                    track = extras.erev_track(prev)
                    item.update({"name": sub.replace("שבת שלום · ", ""), "greeting": t})
                else:
                    ms = extras.minor_story(prev)
                    if not ms:
                        d += dt.timedelta(days=1)
                        continue
                    key, track = ms["key"], ms["track"]
                    img = design.shabbat_story(ms["title"], ms["subtitle"], bot.ROOT / "out" / f"prev_{key}.png",
                                               ms["question"], ms["icon"], ms["lit"])
                    item.update({"name": f.replace("״", '"'), "greeting": ms["title"]})
                item.update({"story": bot.release_time(prev).isoformat(), "img": save_jpg(Image.open(img), PREVIEW / f"hol_{key}.jpg"),
                             "audio": raw + f"{track}.mp3" if track and (bot.ROOT / "assets/music/holiday" / f"{track}.mp3").exists() else None, "day": prev.isoformat()})
                res.append(item)
        d += dt.timedelta(days=1)
    return res


def health(m, state, now):
    """מצב הבוט: הרצה אחרונה, העלאה אחרונה, תקלות, תוקף המפתח."""
    h = {"run": now.isoformat(), "ok": True, "issues": []}
    posted = state.get("posted", [])
    if posted:
        h["last_post"] = {"chapter": bot.gematria(posted[-1]["chapter"]), "at": posted[-1]["at"]}
    # פרק שהיה צריך לעלות ולא עלה (יותר משעה וחצי באיחור)
    j = bot.next_job(now - dt.timedelta(minutes=90), state)
    if j:
        h["ok"] = False
        h["issues"].append(f"פרק {bot.gematria(j[0]['chapter'])} באיחור – הבוט עוד לא העלה אותו")
    runs = os.environ.get("RECENT_RUNS")
    if runs:
        fails = [r for r in json.loads(runs) if r.get("conclusion") == "failure"]
        h["fails_24h"] = len(fails)
        if fails:
            h["issues"].append(f"{len(fails)} הרצות נכשלו ב-24 השעות האחרונות")
    exp = m.get("token_expires")
    if exp:
        days = (dt.datetime.fromtimestamp(exp, TZ) - now).days
        h["token_days"] = days
        if days < 10:
            h["ok"] = False
            h["issues"].append(f"מפתח הגישה לאינסטגרם פג בעוד {days} ימים")
    elif exp == 0:
        h["token_days"] = None  # לא פג
    errs = m.get("api_errors") or []
    if any("comments" in e or "media" == e.split(":")[0] for e in errs):
        h["issues"].append("חלק מהנתונים מאינסטגרם לא נקראו בהרצה האחרונה")
    return h


# ------------------------------------------------------------------ page
def next_times(now, state, upcoming):
    """מתי כל תוסף אמור לעלות בפעם הבאה (לשעון הספירה לאחור בדשבורד)."""
    posted_cycle = {p["day"] for p in state.get("posted", []) if p.get("kind") == "cycle"}

    def daily_release(day):
        return bot.release_time(day)

    def next_day(cond, start=None):
        day = start or now.date()
        for _ in range(400):
            if cond(day) and day.isoformat() not in posted_cycle and daily_release(day) > now - dt.timedelta(minutes=5):
                return day
            day += dt.timedelta(days=1)
        return None

    out = {}
    nxt = upcoming[0] if upcoming else None
    if nxt:
        out["also_story"] = {"when": nxt["iso"], "what": f"יחד עם פרק {nxt['chapter']}"}
        out["replace_phone_with_qr"] = {"when": nxt["iso"], "what": f"בריל של פרק {nxt['chapter']}"}
    d = next_day(lambda x: bot.day_kind(x) == "erev")
    if d:
        out["shabbat_story"] = {"when": daily_release(d).isoformat(), "what": "אחרי הפרק של " + bot.hebrew_date(d)}
    days = bot.CONFIG.get("dedication_invite_days", [6, 2])
    d = next_day(lambda x: x.weekday() in days)
    if d:
        out["dedications"] = {"when": daily_release(d).isoformat(), "what": "סטורי הזמנה להקדשות, " + bot.hebrew_date(d)}
    start = dt.date.fromisoformat(bot.CONFIG["cycle_start"])
    d = start + dt.timedelta(days=149)
    while d < now.date() or d.isoformat() in posted_cycle:
        d += dt.timedelta(days=150)
    out["siyum_reel"] = {"when": daily_release(d).isoformat(), "what": "אחרי פרק ק\"נ, " + bot.hebrew_date(d)}
    return out


def render(m, state):
    now = dt.datetime.now(TZ)
    (bot.ROOT / "out" / "clean").mkdir(parents=True, exist_ok=True)  # בהרצה נקייה התיקייה לא קיימת
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
                         "iso": rel.isoformat(), "kind": kind, "ch": unit["chapter"], "day": day.isoformat()})
        st["posted"].append({"chapter": unit["chapter"], "day": day.isoformat(), "kind": kind,
                             "at": rel.isoformat(timespec="minutes")})
        t = rel + dt.timedelta(minutes=26)
    data = {k: m.get(k) for k in ("account", "followers_history", "daily_new_followers", "recent_comments",
                                  "follow_log", "demographics",
                                  "hypotheses", "recommendations", "slot_rows", "music_rows", "reels",
                                  "totals", "cta", "api_errors", "style_rows", "fair_count")}
    data["upcoming"] = upcoming
    try:
        data["preview"] = previews(upcoming, now)
    except Exception as e:
        data["preview"] = {}
        print("תצוגה מקדימה נכשלה:", e)
    data["holidays"] = holidays(now)
    data["health"] = health(m, state, now)
    data["stories"] = sorted(m.get("story_cache", {}).values(), key=lambda s: s["timestamp"], reverse=True)[:10]
    wa = load(ROOT / "whatsapp.json", {})
    data["whatsapp"] = [{"date": k, "n": v} for k, v in sorted(wa.items())]
    import extras
    ded = extras.load_ded()
    data["dedications"] = {"queue": [{**q, "eta": extras.queue_eta(i)} for i, q in enumerate(ded.get("queue", []))],
                           "done": ded.get("done", [])[-10:][::-1], "inbox_error": ded.get("inbox_error")}
    import manage
    data["switches"] = [{"key": k, "label": v, "on": bool(bot.CONFIG.get(k)), **next_times(now, state, upcoming).get(k, {})}
                        for k, v in manage.SWITCHES.items()]
    data["repo"] = os.environ.get("GITHUB_REPOSITORY", "mozssss-ai/tehilim-bot")
    data["updated"] = now.strftime("%d/%m/%Y %H:%M")
    data["updated_iso"] = now.isoformat()
    data["data_refreshed"] = m.get("refreshed")
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
