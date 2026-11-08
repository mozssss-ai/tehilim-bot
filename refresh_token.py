"""מחדש את מפתח הגישה לאינסטגרם (רק מפתח מסוג 'התחברות עם אינסטגרם', תוקף 60 יום)
ושומר אותו כמשתנה IG_TOKEN החדש בפרויקט ב-GitLab. מפתח של משתמש מערכת לא צריך חידוש."""
import os, sys, requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import forge  # noqa: E402

if not forge.token():
    print("GL_TOKEN לא הוגדר – מדלג על חידוש."); sys.exit(0)
if not os.environ.get("IG_TOKEN", "").startswith("IG"):
    print("מפתח מסוג פייסבוק/משתמש מערכת – לא צריך חידוש."); sys.exit(0)

r = requests.get("https://graph.instagram.com/refresh_access_token",
                 params={"grant_type": "ig_refresh_token", "access_token": os.environ["IG_TOKEN"]}, timeout=60)
if r.status_code != 200:
    sys.exit(f"refresh failed {r.status_code}")
forge.set_variable("IG_TOKEN", r.json()["access_token"])
print("token refreshed, valid for", r.json().get("expires_in", 0) // 86400, "days")
