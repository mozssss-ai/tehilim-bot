"""גלריית כל תמונות הפרקים לדשבורד – בשתי גרסאות: עם מספר הטלפון (המקור) ועם קוד QR לקבוצה.
כדי לא לנפח את המאגר: לכל תמונה נשמרת רק "מדבקה" קטנה של התחתית בגרסת ה-QR, והדף מרכיב אותה
על התמונה המקורית (בתצוגה ובהורדה). רץ מחדש רק לתמונות שהשתנו.
"""
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import bot  # noqa: E402
import design  # noqa: E402

G = ROOT / "docs" / "6dd35a90fba60637" / "gallery"
MAN = G / "manifest.json"


def sha(p):
    return hashlib.sha1(p.read_bytes()).hexdigest()[:12]


def main():
    (G / "patch").mkdir(parents=True, exist_ok=True)
    (G / "thumb").mkdir(parents=True, exist_ok=True)
    old = json.loads(MAN.read_text(encoding="utf-8")) if MAN.exists() else {}
    known = {pg["file"]: pg for ch in old.get("chapters", []) for pg in ch["pages"]}
    link = bot.CONFIG["whatsapp_link"]
    chapters, changed = [], 0
    tmp = ROOT / "out" / "gallery_tmp.png"
    tmp.parent.mkdir(exist_ok=True)
    for u in bot.UNITS:
        pages = []
        for i, f in enumerate(u["images"], 1):
            src = ROOT / f
            h = sha(src) + "-v1"  # להעלות את v1 אם משנים את עיצוב ה-QR
            name = Path(f).stem
            if f in known and known[f].get("hash") == h and (G / "thumb" / f"{name}.jpg").exists():
                pages.append(known[f])
                continue
            changed += 1
            orig = Image.open(src).convert("RGB")
            clean = Image.open(design.clean_footer(src, tmp, link)).convert("RGB")
            diff = np.abs(np.asarray(orig, dtype=int) - np.asarray(clean, dtype=int)).max(axis=2) > 0
            ys, xs = np.where(diff)
            rect = None
            if len(ys):
                x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
                clean.crop((x0, y0, x1, y1)).save(G / "patch" / f"{name}.png", optimize=True)
                rect = [x0, y0, x1 - x0, y1 - y0]
            orig.resize((270, 480), Image.LANCZOS).save(G / "thumb" / f"{name}.jpg", quality=78)
            pages.append({"file": f, "name": name, "part": i, "hash": h, "patch": rect})
        chapters.append({"ch": u["chapter"], "h": bot.gematria(u["chapter"]), "pages": pages})
    MAN.write_text(json.dumps({"repo": "mozssss-ai/tehilim-bot", "chapters": chapters}, ensure_ascii=False),
                   encoding="utf-8")
    print(f"גלריה: {sum(len(c['pages']) for c in chapters)} תמונות, {changed} עודכנו")


if __name__ == "__main__":
    main()
