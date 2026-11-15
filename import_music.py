"""מחליף את המנגינות הממוחשבות בהקלטות האמיתיות שמשה חיים אישר (assets/music/import.json).
רץ ב-GitHub Actions (workflow "import music"): מוריד מ-Wikimedia Commons, חותך קטע של עד 90 שניות
מנקודת ההתחלה שנשמעה בעמוד הבחירה, בעוצמה נמוכה ואחידה, ושומר רישום רישיונות.
"""
import json, re, subprocess, sys, time
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
MUSIC = ROOT / "assets" / "music"
UA = {"User-Agent": "TehilimKolYomBot/1.0 (https://github.com/mozssss-ai/tehilim-bot)"}
items = json.loads((MUSIC / "import.json").read_text(encoding="utf-8"))
tmp = ROOT / "out" / "music_raw"
tmp.mkdir(parents=True, exist_ok=True)


def get(url):
    for _ in range(12):
        try:
            r = requests.get(url, headers=UA, timeout=300)
        except Exception as e:
            print("net", e, flush=True); time.sleep(20); continue
        if r.status_code == 429:
            w = min(int(r.headers.get("retry-after", "30")), 300) + 3
            print("wait", w, flush=True); time.sleep(w); continue
        return r
    return r


def dur(p):
    o = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)],
                       capture_output=True, text=True).stdout.strip()
    try: return float(o)
    except ValueError: return 0


done, failed = [], []
for i, it in enumerate(items, 1):
    out = MUSIC / it["file"]
    raw = tmp / f"{i:03d}{Path(it['src']).suffix or '.bin'}"
    r = get(it["src"])
    if r.status_code != 200 or len(r.content) < 20000:
        print("FAIL", r.status_code, it["title"], flush=True); failed.append(it); continue
    raw.write_bytes(r.content)
    out.parent.mkdir(parents=True, exist_ok=True)
    new = out.with_suffix(".new.mp3")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(it["start"]), "-t", "90", "-i", str(raw),
                    "-af", "highpass=f=40,afade=t=in:d=1.5,loudnorm=I=-24:TP=-4:LRA=11",
                    "-ar", "44100", "-ac", "2", "-b:a", "160k", str(new)], check=False)
    if new.exists() and dur(new) >= 30:
        new.replace(out); done.append(it); print("ok", i, it["file"], round(dur(out)), flush=True)
    else:
        new.unlink(missing_ok=True); failed.append(it); print("FAIL cut", it["title"], flush=True)
    time.sleep(3)

regular = [it for it in done if not it["file"].startswith("holiday/")]
if len(regular) < 20:
    sys.exit(f"רק {len(regular)} מנגינות ירדו – לא מחליפים את המאגר הקיים")

# מוחקים את המנגינות הממוחשבות הישנות (01_… עד 25_…) ואת מנגינות החג הממוחשבות שאין להן תחליף אמיתי –
# בחגים האלה הבוט ישתמש במנגינה השקטה הרגילה.
for p in MUSIC.glob("[0-9][0-9]_*.mp3"):
    p.unlink()
keep_holiday = {Path(it["file"]).name for it in done if it["file"].startswith("holiday/")}
for p in (MUSIC / "holiday").glob("*.mp3"):
    if p.name not in keep_holiday:
        p.unlink()

styles = {}
for it in regular:
    styles.setdefault(it["style"], []).append(it["file"].split("_")[0])
src = (ROOT / "music_styles.py").read_text(encoding="utf-8")
src = re.sub(r"STYLES = \{.*?\n\}", "STYLES = " + json.dumps(styles, ensure_ascii=False, indent=4), src, flags=re.S)
(ROOT / "music_styles.py").write_text(src, encoding="utf-8")

(MUSIC / "LICENSES.json").write_text(json.dumps(
    [{k: it[k] for k in ("file", "title", "license", "page")} for it in done], ensure_ascii=False, indent=1), encoding="utf-8")
print(f"done {len(done)} ok, {len(failed)} failed:", [f["title"] for f in failed])
