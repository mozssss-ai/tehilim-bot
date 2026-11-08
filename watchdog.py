"""שומר: אם פרק שהיה אמור לעלות מתעכב ביותר משעה וחצי – פותח Issue בפרויקט ומתייג את משה חיים
(GitLab שולח לו התראה במייל). כשהבעיה נפתרת – סוגר את ה-Issue לבד."""
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import bot  # noqa: E402
import forge  # noqa: E402

TITLE = "⚠️ התראה מהבוט: פרק לא עלה בזמן"


def main():
    now = dt.datetime.now(bot.TZ)
    state = bot.load_state()
    late = bot.next_job(now - dt.timedelta(minutes=90), state)
    if late and bot.is_forbidden(now):
        late = None  # בשבת/חג לא מתריעים
    found = [i for i in forge.open_issues(search="התראה מהבוט") if i["title"] == TITLE]
    if late:
        unit, day, kind = late
        body = (f"פרק {bot.gematria(unit['chapter'])} (של {day}) היה אמור לעלות ועדיין לא עלה.\n\n"
                f"הבוט ימשיך לנסות בכל הרצה. אם זה נמשך – כדאי לבדוק ב-GitLab תחת Build ← Pipelines.\n\n@{forge.owner()}")
        if not found:
            forge.create_issue(TITLE, body)
            print("נפתחה התראה")
    else:
        for i in found:
            forge.close_issue(i["iid"], "✅ הבעיה נפתרה – הפרק עלה.")
            print("ההתראה נסגרה")


if __name__ == "__main__":
    main()
