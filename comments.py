"""עונה אוטומטית למי שכותב "תהילים" בתגובה לריל:
  1. תגובה מתחת לתגובה שלו ("שלחנו לך את הקישור בפרטי").
  2. הודעה פרטית (Private Reply) עם הודעה מעודדת וקישור לקבוצה.
רץ בכל הרצה של הבוט (כל חצי שעה). כל תגובה מטופלת פעם אחת בלבד (replied.json).
"""
import datetime as dt
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import bot  # noqa: E402

FILE = ROOT / "replied.json"


def main():
    token = os.environ.get("IG_TOKEN", "").strip()
    if not token:
        print("אין IG_TOKEN – מדלג.")
        return
    cfg = bot.CONFIG
    keywords = cfg.get("comment_keywords", ["תהילים"])
    data = json.loads(FILE.read_text(encoding="utf-8")) if FILE.exists() else {"done": []}
    done_ids = {x["comment_id"] for x in data["done"]}

    uid, username = bot.connect(token)
    G = bot.GRAPH
    media = bot.ig_request("GET", f"{G}/{uid}/media", params={
        "fields": "id,timestamp", "limit": 25, "access_token": token}).get("data", [])
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=7)  # הודעה פרטית אפשרית עד 7 ימים
    changed = False
    for m in media:
        ts = dt.datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
        if ts < cutoff:
            continue
        try:
            comments = bot.ig_request("GET", f"{G}/{m['id']}/comments", params={
                "fields": "id,text,username,timestamp", "limit": 100, "access_token": token}).get("data", [])
        except RuntimeError as e:
            print("לא הצלחתי לקרוא תגובות:", str(e)[:300])
            continue
        for c in comments:
            if c["id"] in done_ids or c.get("username") == username:
                continue
            if not any(k in (c.get("text") or "") for k in keywords):
                continue
            rec = {"comment_id": c["id"], "media_id": m["id"], "at": dt.datetime.now(bot.TZ).isoformat(timespec="minutes"),
                   "dm": False, "reply": False}
            try:
                bot.ig_request("POST", f"{G}/{uid}/messages", json={
                    "recipient": {"comment_id": c["id"]},
                    "message": {"text": cfg["dm_message"].format(group_link=cfg["whatsapp_link"])}},
                    params={"access_token": token})
                rec["dm"] = True
            except RuntimeError as e:
                rec["dm_error"] = str(e)[:300]
                print("הודעה פרטית נכשלה:", rec["dm_error"])
            try:
                text = cfg["comment_reply"] if rec["dm"] else \
                    "תודה! 🙏 הקישור לקבוצה נמצא בביו 👆"
                bot.ig_request("POST", f"{G}/{c['id']}/replies", data={"message": text, "access_token": token})
                rec["reply"] = True
            except RuntimeError as e:
                rec["reply_error"] = str(e)[:300]
                print("תגובה נכשלה:", rec["reply_error"])
            data["done"].append(rec)
            done_ids.add(c["id"])
            changed = True
            print(f"טופלה תגובה {c['id']}: הודעה פרטית={rec['dm']}, תגובה={rec['reply']}")
    if changed or not FILE.exists():
        FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"סה\"כ טופלו עד היום: {len(data['done'])}")
    try:
        import extras
        extras.check_inbox(token)
    except Exception as e:
        print("בדיקת הודעות פרטיות (הקדשות) נכשלה:", str(e)[:300])


if __name__ == "__main__":
    main()
