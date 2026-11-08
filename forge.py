"""חיבור לשרת שעליו הבוט רץ (GitLab).
כל מה שתלוי באתר עצמו נמצא כאן: כתובות לקבצים, Issues (הכפתורים בדשבורד והתראות),
רשימת ההרצות האחרונות, משתני CI, ותזמון ההרצות.

  python forge.py setup      # יוצר/מעדכן את שעות ההרצה ואת ה-webhook לכפתורי הדשבורד
  python forge.py manage     # מבצע את הבקשות שנפתחו מהדשבורד
  python forge.py usage      # כמה דקות הרצה נוצלו החודש
"""
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
HOST = "https://gitlab.com"
API = f"{HOST}/api/v4"
PRIVATE = "6dd35a90fba60637"  # התיקייה הפרטית של הדשבורד
TZ_NAME = "Asia/Jerusalem"

# שעות ההרצה (שעון ישראל). השעות של הערב והצהריים תואמות לשעות ההעלאה שב-config.json (slots),
# כך שהבוט לא צריך לחכות בתוך ההרצה (כל דקת המתנה נספרת במכסה החינמית).
# בשבת עד הערב אין הרצות בכלל.
SCHEDULES = {
    "בוקר – תגובות, הקדשות ונתונים": "0 7 * * 0-5",
    "צהריים – ערב שבת/חג ונתונים": "30 12 * * 0-5",
    "ערב שבת – 11:00 ו-12:00": "0 11,12 * * 5",
    "ערב שבת – 13:30": "30 13 * * 5",
    "ערב – העלאת הפרק (18:30 עד 21:30)": "30 18,19,20,21 * * 0-4,6",
}


def repo() -> str:
    return os.environ.get("CI_PROJECT_PATH") or CONFIG.get("gitlab_project", "")


def owner() -> str:
    return os.environ.get("CI_PROJECT_NAMESPACE") or repo().split("/")[0]


def pid() -> str:
    return os.environ.get("CI_PROJECT_ID") or urllib.parse.quote(repo(), safe="")


def pages_url() -> str:
    return (os.environ.get("CI_PAGES_URL") or CONFIG.get("pages_url", "")).rstrip("/")


def page_file(rel: str) -> str:
    """כתובת ציבורית לקובץ שבתיקיית docs (מוגש דרך GitLab Pages)."""
    return f"{pages_url()}/{rel.lstrip('/')}"


def raw(path: str, ref: str = "main") -> str:
    return f"{HOST}/{repo()}/-/raw/{ref}/{path}"


def raw_api_base() -> str:
    """בסיס לקריאת קבצים דרך ה-API (מאפשר הורדה מתוך דף אינטרנט – CORS)."""
    return f"{API}/projects/{urllib.parse.quote(repo(), safe='')}/repository/files/"


def issue_new_base() -> str:
    return f"{HOST}/{repo()}/-/issues/new"


# ---------------------------------------------------------------- API
def token() -> str:
    return os.environ.get("GL_TOKEN", "").strip()


def api(method: str, path: str, **kw):
    import requests
    if not token():
        raise RuntimeError("GL_TOKEN לא הוגדר")
    r = requests.request(method, f"{API}{path}", headers={"PRIVATE-TOKEN": token()}, timeout=60, **kw)
    if r.status_code >= 400:
        raise RuntimeError(f"GitLab API {r.status_code}: {r.text[:300]}")
    return r.json() if r.text else {}


def api_all(path: str, **params):
    out, page = [], 1
    while True:
        chunk = api("GET", path, params={**params, "per_page": 100, "page": page})
        out += chunk
        if len(chunk) < 100 or page >= 10:
            return out
        page += 1


def open_issues(author: str | None = None, search: str | None = None):
    params = {"state": "opened", "order_by": "created_at", "sort": "asc"}
    if author:
        params["author_username"] = author
    if search:
        params["search"] = search
    return api_all(f"/projects/{pid()}/issues", **params)


def comment(iid: int, text: str):
    api("POST", f"/projects/{pid()}/issues/{iid}/notes", data={"body": text})


def close_issue(iid: int, text: str | None = None):
    if text:
        comment(iid, text)
    api("PUT", f"/projects/{pid()}/issues/{iid}", data={"state_event": "close"})


def create_issue(title: str, body: str):
    return api("POST", f"/projects/{pid()}/issues", data={"title": title, "description": body})


def recent_pipelines(hours: int = 24):
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).isoformat()
    return api_all(f"/projects/{pid()}/pipelines", updated_after=since)


def set_variable(key: str, value: str):
    api("PUT", f"/projects/{pid()}/variables/{key}", data={"value": value, "masked": "true"})


def token_days() -> int | None:
    """כמה ימים נשארו למפתח של הבוט ב-GitLab (מקסימום שנה)."""
    try:
        info = api("GET", "/personal_access_tokens/self")
        if info.get("expires_at"):
            return (dt.date.fromisoformat(info["expires_at"]) - dt.date.today()).days
    except Exception as e:
        print("בדיקת תוקף GL_TOKEN נכשלה:", e)
    return None


def minutes_this_month() -> float | None:
    """דקות הרצה שנוצלו מתחילת החודש (המכסה החינמית: 400)."""
    f = ROOT / "usage.json"
    try:
        month = dt.date.today().strftime("%Y-%m")
        cache = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        if cache.get("month") != month:
            cache = {"month": month, "pipelines": {}}
        seen = cache["pipelines"]
        start = dt.date.today().replace(day=1).isoformat() + "T00:00:00Z"
        for p in api_all(f"/projects/{pid()}/pipelines", updated_after=start):
            if p.get("status") in ("running", "pending", "created", "waiting_for_resource") or str(p["id"]) in seen:
                continue
            jobs = api("GET", f"/projects/{pid()}/pipelines/{p['id']}/jobs")
            seen[str(p["id"])] = round(sum((j.get("duration") or 0) for j in jobs) / 60, 2)
        f.write_text(json.dumps(cache, indent=1), encoding="utf-8")
        return round(sum(seen.values()), 1)
    except Exception as e:
        print("חישוב דקות נכשל:", e)
        return None


def push_media(video: Path) -> str:
    """גיבוי: מעלה את הסרטון לענף 'media' (רק הסרטון האחרון) ומחזיר כתובת ציבורית."""
    name = f"reel_{int(time.time())}.mp4"
    work = ROOT / "out" / "media"
    work.mkdir(parents=True, exist_ok=True)
    (work / name).write_bytes(video.read_bytes())
    remote = f"https://oauth2:{token()}@gitlab.com/{repo()}.git"
    git = lambda *a: subprocess.run(["git", "-C", str(work), "-c", "user.name=tehilim-bot",
                                     "-c", "user.email=tehilim-bot@noreply.gitlab.com", *a],
                                    check=True, capture_output=True)
    git("init", "-q", "-b", "media")
    git("add", name)
    git("commit", "-q", "-m", "reel [skip ci]")
    git("push", "-q", "-o", "ci.skip", "--force", remote, "media")
    time.sleep(15)
    return raw(name, "media")


# ---------------------------------------------------------------- setup
def setup():
    """יוצר את שעות ההרצה, טוקן הפעלה ו-webhook שמפעיל את הבוט כשנפתחת בקשה מהדשבורד.
    אפשר להריץ שוב ושוב – הוא מעדכן ולא משכפל."""
    have = {s["description"]: s for s in api_all(f"/projects/{pid()}/pipeline_schedules")}
    for desc, cron in SCHEDULES.items():
        data = {"description": desc, "ref": "main", "cron": cron, "cron_timezone": TZ_NAME, "active": "true"}
        if desc in have:
            if have[desc]["cron"] != cron or not have[desc]["active"]:
                api("PUT", f"/projects/{pid()}/pipeline_schedules/{have[desc]['id']}", data=data)
                print("עודכן:", desc)
        else:
            api("POST", f"/projects/{pid()}/pipeline_schedules", data=data)
            print("נוצר:", desc)
    for desc, s in have.items():
        if desc not in SCHEDULES:
            api("DELETE", f"/projects/{pid()}/pipeline_schedules/{s['id']}")
            print("נמחק:", desc)

    # טוקן הפעלה + webhook: פתיחת בקשה מהדשבורד מפעילה הרצה מיד
    trig = [t for t in api("GET", f"/projects/{pid()}/triggers") if t.get("description") == "dashboard"]
    tok = trig[0]["token"] if trig else api("POST", f"/projects/{pid()}/triggers",
                                            data={"description": "dashboard"})["token"]
    url = f"{API}/projects/{pid()}/ref/main/trigger/pipeline?token={tok}"
    hooks = api("GET", f"/projects/{pid()}/hooks")
    if not any("/trigger/pipeline" in h.get("url", "") for h in hooks):
        api("POST", f"/projects/{pid()}/hooks", data={
            "url": url, "issues_events": "true", "push_events": "false",
            "note_events": "false", "enable_ssl_verification": "true"})
        print("נוצר webhook לכפתורי הדשבורד")
    print("ההגדרה הושלמה")


# ---------------------------------------------------------------- manage
def manage():
    """מבצע כל בקשה פתוחה שמשה חיים פתח מהדשבורד (רק בקשות שלו), עונה וסוגר."""
    import manage as m
    done = 0
    for it in open_issues(author=owner()):
        title, body = it["title"], it.get("description") or ""
        try:
            msg = m.run(title, body)
        except Exception as e:
            msg = f"❌ שגיאה: {e}"
        print(f"#{it['iid']} {title} → {msg}")
        try:
            close_issue(it["iid"], f"{msg} – הדשבורד מתעדכן בדקות הקרובות.")
        except Exception as e:
            print("סגירה נכשלה:", e)
        done += 1
    print(f"בוצעו {done} בקשות מהדשבורד")


def trigger_is_relevant() -> bool:
    """בהרצה שהופעלה מה-webhook: רק פתיחת בקשה חדשה רלוונטית (לא סגירה/עריכה)."""
    p = os.environ.get("TRIGGER_PAYLOAD")
    if not p or not Path(p).exists():
        return True
    try:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return True
    attrs = data.get("object_attributes") or {}
    return data.get("object_kind") != "issue" or attrs.get("action") in ("open", "reopen")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "setup":
        setup()
    elif cmd == "manage":
        manage()
    elif cmd == "usage":
        print(minutes_this_month())
    elif cmd == "relevant":
        sys.exit(0 if trigger_is_relevant() else 1)
    else:
        print(__doc__)
