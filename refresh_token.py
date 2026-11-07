"""מחדש את מפתח הגישה לאינסטגרם (תוקף 60 יום) ושומר אותו כ-secret חדש במאגר."""
import os, subprocess, sys, requests

if not os.environ.get("GH_PAT") and not os.environ.get("GH_TOKEN"):
    print("GH_PAT לא הוגדר – מדלג על חידוש."); sys.exit(0)
if not os.environ["IG_TOKEN"].startswith("IG"):
    print("מפתח מסוג פייסבוק/משתמש מערכת – לא צריך חידוש."); sys.exit(0)

r = requests.get("https://graph.instagram.com/refresh_access_token",
                 params={"grant_type": "ig_refresh_token", "access_token": os.environ["IG_TOKEN"]}, timeout=60)
if r.status_code != 200:
    sys.exit(f"refresh failed {r.status_code}: {r.text}")
token = r.json()["access_token"]
print(f"::add-mask::{token}")
subprocess.run(["gh", "secret", "set", "IG_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"]],
               input=token.encode(), check=True)
print("token refreshed, valid for", r.json().get("expires_in", 0) // 86400, "days")
