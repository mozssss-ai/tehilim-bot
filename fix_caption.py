"""מתקן כיתוב של ריל שכבר עלה (לפי state.json) לכיתוב המוסכם."""
import datetime as dt, json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import bot
token = os.environ["IG_TOKEN"]
bot.connect(token)
state = json.loads((ROOT / "state.json").read_text(encoding="utf-8"))
for p in state["posted"]:
    if p.get("cta", 0) != 0:
        unit = next(u for u in bot.UNITS if u["chapter"] == p["chapter"])
        text = bot.caption(unit, dt.datetime.fromisoformat(p["at"]).date(), 0)
        try:
            r = bot.ig_request("POST", f"{bot.GRAPH}/{p['media_id']}", data={"caption": text, "access_token": token})
            print("עודכן", p["chapter"], r)
            p["cta"] = 0
        except Exception as e:
            print("עדכון נכשל", p["chapter"], e)
(ROOT / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
