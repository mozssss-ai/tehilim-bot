"""מחדש את מפתח הגישה לאינסטגרם (תוקף 60 יום) ושומר אותו כ-secret חדש במאגר."""
import os, subprocess, sys, requests

r = requests.get("https://graph.instagram.com/refresh_access_token",
                 params={"grant_type": "ig_refresh_token", "access_token": os.environ["IG_TOKEN"]}, timeout=60)
if r.status_code != 200:
    sys.exit(f"refresh failed {r.status_code}: {r.text}")
token = r.json()["access_token"]
print(f"::add-mask::{token}")
subprocess.run(["gh", "secret", "set", "IG_TOKEN", "--repo", os.environ["GITHUB_REPOSITORY"]],
               input=token.encode(), check=True)
print("token refreshed, valid for", r.json().get("expires_in", 0) // 86400, "days")
