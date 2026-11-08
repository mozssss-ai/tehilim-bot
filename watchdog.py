"""שומר: אם פרק שהיה אמור לעלות מתעכב ביותר משעה וחצי – פותח Issue במאגר (GitHub שולח למשה חיים התראה
במייל ובאפליקציה). כשהבעיה נפתרת – סוגר את ה-Issue לבד."""
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import bot  # noqa: E402

TITLE = "⚠️ התראה מהבוט: פרק לא עלה בזמן"


def gh(*args):
    return subprocess.run(["gh", *args, "--repo", os.environ["GITHUB_REPOSITORY"]], capture_output=True, text=True)


def main():
    now = dt.datetime.now(bot.TZ)
    state = bot.load_state()
    late = bot.next_job(now - dt.timedelta(minutes=90), state)
    if late and bot.is_forbidden(now):
        late = None  # בשבת/חג לא מתריעים
    found = json.loads(gh("issue", "list", "--state", "open", "--search", TITLE, "--json", "number,title").stdout or "[]")
    found = [i for i in found if i["title"] == TITLE]
    if late:
        unit, day, kind = late
        body = (f"פרק {bot.gematria(unit['chapter'])} (של {day}) היה אמור לעלות ועדיין לא עלה.\n\n"
                f"הבוט ימשיך לנסות בכל הרצה. אם זה נמשך – כדאי לבדוק את לשונית Actions במאגר.")
        if not found:
            gh("issue", "create", "--title", TITLE, "--body", body)
            print("נפתחה התראה")
    else:
        for i in found:
            gh("issue", "close", str(i["number"]), "--comment", "✅ הבעיה נפתרה – הפרק עלה.")
            print("ההתראה נסגרה")


if __name__ == "__main__":
    main()
