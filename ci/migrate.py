"""העברה חד-פעמית לפרויקט ב-GitLab (מורץ מקומית, לא ב-CI).
  GL_TOKEN=<טוקן זמני> python ci/migrate.py <username>/tehilim-bot
1. מעדכן את config.json, 2. דוחף את כל הקוד, 3. בודק שהמשתנים הוגדרו,
4. מפעיל הרצה ראשונה (שיוצרת את שעות ההרצה וה-webhook עם המפתח הקבוע של הבוט)."""
import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
project = sys.argv[1]
tok = os.environ["GL_TOKEN"].strip()
API = "https://gitlab.com/api/v4"
pid = urllib.parse.quote(project, safe="")
H = {"PRIVATE-TOKEN": tok}


def api(method, path, **kw):
    r = requests.request(method, f"{API}{path}", headers=H, timeout=60, **kw)
    if r.status_code >= 400:
        sys.exit(f"GitLab API {r.status_code} {path}: {r.text[:300]}")
    return r.json() if r.text else {}


info = api("GET", f"/projects/{pid}")
print("פרויקט:", info["web_url"], "| נראות:", info["visibility"])
if info["visibility"] != "public":
    print("⚠️ הפרויקט לא ציבורי – הגלריה והתמונות לאינסטגרם צריכים פרויקט ציבורי.")

# 1. config
cfg_p = ROOT / "config.json"
cfg = json.loads(cfg_p.read_text(encoding="utf-8"))
cfg["gitlab_project"] = project
cfg_p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], check=True)
git("add", "config.json")
subprocess.run(["git", "-C", str(ROOT), "commit", "-q", "-m", f"move to GitLab: {project}"])

# 2. push
remote = f"https://oauth2:{tok}@gitlab.com/{project}.git"
git("push", "-o", "ci.skip", remote, "HEAD:main")
print("✅ הקוד הועלה")

# 3. variables
keys = {v["key"] for v in api("GET", f"/projects/{pid}/variables")}
missing = {"IG_TOKEN", "GL_TOKEN"} - keys
if missing:
    sys.exit(f"⚠️ חסרים משתנים ב-Settings → CI/CD → Variables: {', '.join(sorted(missing))}")
print("✅ המשתנים מוגדרים")

# 4. first run
p = api("POST", f"/projects/{pid}/pipeline", data={"ref": "main"})
print("▶ הרצה ראשונה:", p["web_url"])
for _ in range(90):
    time.sleep(20)
    st = api("GET", f"/projects/{pid}/pipelines/{p['id']}")["status"]
    print("  ", st)
    if st in ("success", "failed", "canceled"):
        break
try:
    pages = api("GET", f"/projects/{pid}/pages")
    url = pages.get("url")
    if url:
        cfg["pages_url"] = url.rstrip("/")
        cfg_p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        print("🌐 הדשבורד:", f"{url.rstrip('/')}/6dd35a90fba60637/")
except SystemExit:
    print("עוד לא ניתן לקרוא את כתובת האתר")
