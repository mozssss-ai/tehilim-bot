"""עיצובים שהבוט מייצר לבד, בעיצוב של העמוד (רקע, לוגו, כחול-זהב):
  - shabbat_story(day): סטורי "שבת שלום" לערב שבת/חג
  - siyum_card(): תמונת סיום ספר התהילים (לריל החגיגי אחרי פרק ק"נ)
  - dedicate(image, text): מוסיף פס הקדשה בתחתית תמונת הפרק
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent
A = ROOT / "assets" / "design"
NAVY, GOLD, WHITE = (9, 4, 70), (173, 131, 48), (255, 255, 255)


def SEC(s):
    return ImageFont.truetype(str(A / "secular.ttf"), s)


def HEB(s, w=700):
    f = ImageFont.truetype(str(A / "heebo.ttf"), s)
    try:
        f.set_variation_by_axes([w])
    except Exception:
        pass
    return f


def text(d, xy, s, font, fill=NAVY, anchor="mm"):
    d.text(xy, s, font=font, fill=fill, anchor=anchor, direction="rtl", language="he")


def logo(im, cx, cy, w):
    l = Image.open(A / "logo.png").convert("RGBA")
    l = l.crop(l.getbbox())
    l = l.resize((w, int(l.height * w / l.width)), Image.LANCZOS)
    im.paste(l, (cx - l.width // 2, cy - l.height // 2), l)


def divider(d, cy, x0=260, x1=820):
    d.line((x0, cy, x1, cy), fill=GOLD, width=6)
    for x in (x0, x1):
        d.polygon([(x - 12, cy), (x, cy - 9), (x + 12, cy), (x, cy + 9)], fill=GOLD)


def label(d, cy, s, size=72, max_w=860):
    f = SEC(size)
    while d.textlength(s, font=f, direction="rtl") > max_w and size > 40:
        size -= 4
        f = SEC(size)
    bb = d.textbbox((540, cy), s, font=f, anchor="mm", direction="rtl")
    d.rectangle((bb[0] - 36, cy - size * 0.8, bb[2] + 36, cy + size * 0.8), fill=NAVY)
    text(d, (540, cy), s, f, fill=WHITE)


def candles(d, cx, cy):
    for dx in (-70, 70):
        x = cx + dx
        d.rounded_rectangle((x - 22, cy, x + 22, cy + 170), 8, fill=WHITE, outline=GOLD, width=5)
        d.line((x, cy - 4, x, cy - 22), fill=NAVY, width=4)
        d.ellipse((x - 18, cy - 78, x + 18, cy - 18), fill=(240, 180, 60))
        d.ellipse((x - 8, cy - 52, x + 8, cy - 24), fill=(255, 236, 170))
    d.rounded_rectangle((cx - 130, cy + 166, cx + 130, cy + 196), 12, fill=GOLD)


def fit(d, s, size, max_w=900):
    f = SEC(size)
    while d.textlength(s, font=f, direction="rtl") > max_w and size > 30:
        size -= 2
        f = SEC(size)
    return f


FLAME, FLAME_IN = (240, 180, 60), (255, 236, 170)


def flame(d, x, y, h=58):
    d.ellipse((x - h * .31, y - h, x + h * .31, y), fill=FLAME)
    d.ellipse((x - h * .14, y - h * .55, x + h * .14, y - h * .06), fill=FLAME_IN)


def chanukiah(d, cx, cy, lit):
    """חנוכייה: 8 נרות + שמש מוגבה. lit = מספר הנרות הדולקים (מימין לשמאל)."""
    xs = [cx + (i - 4) * 70 for i in range(9)]  # i=4 שמש
    d.rounded_rectangle((cx - 120, cy + 230, cx + 120, cy + 250), 10, fill=GOLD)
    d.rectangle((cx - 9, cy + 60, cx + 9, cy + 232), fill=GOLD)
    d.rectangle((xs[0] - 6, cy + 105, xs[-1] + 6, cy + 120), fill=GOLD)
    for i, x in enumerate(xs):
        top = cy - 40 if i == 4 else cy
        d.rectangle((x - 6, top + 70, x + 6, cy + 112), fill=GOLD)
        d.rounded_rectangle((x - 13, top, x + 13, top + 72), 5, fill=WHITE, outline=GOLD, width=4)
        order = 8 - i if i > 4 else 7 - i  # מימין: 0..3 ואז משמאל לשמש 4..7
        if i == 4 or order < lit:
            d.line((x, top - 2, x, top - 14), fill=NAVY, width=3)
            flame(d, x, top - 12, 44)


def crown(d, cx, cy):
    pts = [(cx - 150, cy + 90), (cx - 150, cy - 40), (cx - 75, cy + 20), (cx, cy - 80), (cx + 75, cy + 20),
           (cx + 150, cy - 40), (cx + 150, cy + 90)]
    d.polygon(pts, fill=GOLD)
    d.rounded_rectangle((cx - 160, cy + 80, cx + 160, cy + 120), 10, fill=GOLD)
    for x, y in [(cx - 150, cy - 40), (cx, cy - 80), (cx + 150, cy - 40)]:
        d.ellipse((x - 18, y - 18, x + 18, y + 18), fill=NAVY)
    for x in (cx - 80, cx, cx + 80):
        d.ellipse((x - 14, cy + 86, x + 14, cy + 114), fill=WHITE)


def tree(d, cx, cy):
    d.rounded_rectangle((cx - 22, cy + 20, cx + 22, cy + 170), 10, fill=(120, 86, 40))
    green = (110, 140, 90)
    for dx, dy, r in [(0, -60, 100), (-85, 0, 75), (85, 0, 75), (-45, 40, 70), (45, 40, 70), (0, -130, 70)]:
        d.ellipse((cx + dx - r, cy + dy - r, cx + dx + r, cy + dy + r), fill=green)
    for dx, dy in [(-60, -40), (40, -90), (70, 20), (-20, 30), (10, -150), (-90, 10)]:
        d.ellipse((cx + dx - 10, cy + dy - 10, cx + dx + 10, cy + dy + 10), fill=(250, 230, 235))


def bonfire(d, cx, cy):
    for a in (-1, 1):
        d.line((cx - 120 * a, cy + 150, cx + 120 * a, cy + 90), fill=(120, 86, 40), width=26)
    d.polygon([(cx - 110, cy + 120), (cx - 60, cy - 40), (cx - 20, cy + 30), (cx, cy - 120), (cx + 30, cy + 20),
               (cx + 70, cy - 50), (cx + 110, cy + 120)], fill=FLAME)
    d.polygon([(cx - 55, cy + 120), (cx - 20, cy + 10), (cx, cy - 40), (cx + 25, cy + 20), (cx + 55, cy + 120)], fill=FLAME_IN)


def grapes(d, cx, cy):
    d.line((cx, cy - 150, cx + 10, cy - 100), fill=(120, 86, 40), width=10)
    d.polygon([(cx + 10, cy - 120), (cx + 120, cy - 160), (cx + 70, cy - 90)], fill=(110, 140, 90))
    purple = (92, 52, 110)
    rows = [5, 4, 3, 2, 1]
    for r, n in enumerate(rows):
        for i in range(n):
            x = cx + (i - (n - 1) / 2) * 52
            y = cy - 80 + r * 48
            d.ellipse((x - 27, y - 27, x + 27, y + 27), fill=purple)
            d.ellipse((x - 14, y - 16, x - 4, y - 6), fill=(170, 140, 190))


def shabbat_story(title, subtitle, out, question="השבת הזאת – גם אתם איתנו?", icon="candles", lit=0):
    """title: 'שבת שלום' / 'חג שמח' / 'שנה טובה' ... subtitle: למשל 'פרשת תולדות' / 'ראש השנה'."""
    im = Image.open(A / "bg_card.png").convert("RGB")
    d = ImageDraw.Draw(im)
    text(d, (960, 120), 'בס"ד', HEB(30, 800), anchor="rm")
    logo(im, 540, 330, 560)
    if icon == "chanukiah":
        chanukiah(d, 540, 600, lit)
    elif icon == "crown":
        crown(d, 540, 680)
    elif icon == "tree":
        tree(d, 540, 680)
    elif icon == "bonfire":
        bonfire(d, 540, 700)
    elif icon == "grapes":
        grapes(d, 540, 720)
    else:
        candles(d, 540, 640)
    label(d, 990, title, 110)
    if subtitle:
        text(d, (540, 1135), subtitle, fit(d, subtitle, 70), fill=GOLD)
    divider(d, 1235)
    text(d, (540, 1320), question, fit(d, question, 56))
    text(d, (540, 1400), "פרק תהילים אחד בכל יום, ישר לוואטסאפ", HEB(42, 600))
    text(d, (540, 1530), "הקישור לקבוצה בביו", SEC(58), fill=GOLD)
    im.save(out)
    return out


def siyum_card(out, book_no=None):
    im = Image.open(A / "bg_card.png").convert("RGB")
    d = ImageDraw.Draw(im)
    text(d, (960, 120), 'בס"ד', HEB(30, 800), anchor="rm")
    logo(im, 540, 330, 560)
    label(d, 600, "סיימנו!", 120)
    text(d, (540, 760), "ביחד, פרק אחרי פרק", SEC(66))
    text(d, (540, 850), "סיימנו את כל ספר התהילים", SEC(66))
    divider(d, 950)
    text(d, (540, 1050), "מחר מתחילים מחזור חדש מפרק א'", SEC(60), fill=GOLD)
    text(d, (540, 1140), "זה הזמן הכי טוב להצטרף", HEB(46, 600))
    text(d, (540, 1300), 'כתבו "תהילים" בתגובה', SEC(62))
    text(d, (540, 1380), "ונשלח לכם קישור לקבוצה בפרטי", HEB(44, 600))
    text(d, (540, 1530), "תודה לכל מי שאמר איתנו", SEC(54), fill=GOLD)
    text(d, (540, 1605), '"תהילים - כל יום"', SEC(60), fill=NAVY)
    im.save(out)
    return out


def invite_story(out):
    """סטורי שמזמין את הצופים לשלוח הקדשה בהודעה פרטית."""
    im = Image.open(A / "bg_card.png").convert("RGB")
    d = ImageDraw.Draw(im)
    text(d, (960, 120), 'בס"ד', HEB(30, 800), anchor="rm")
    logo(im, 540, 330, 560)
    label(d, 600, "רוצים להקדיש פרק?", 92)
    text(d, (540, 760), "לרפואה, להצלחה או לעילוי נשמת", SEC(60))
    text(d, (540, 840), "של מישהו יקר לכם", SEC(60))
    divider(d, 940)
    text(d, (540, 1040), "שלחו לנו הודעה פרטית:", HEB(48, 700))
    d.rounded_rectangle((150, 1100, 930, 1300), 30, fill=WHITE, outline=GOLD, width=6)
    text(d, (540, 1165), "לרפואת יוסף בן שרה", SEC(58))
    text(d, (540, 1240), "(שם + שם האם)", HEB(40, 500), fill=GOLD)
    text(d, (540, 1420), "הפרק יוקדש בכיתוב ובתמונה,", SEC(54))
    text(d, (540, 1495), "ונשלח לכם הודעה כשהוא עולה", SEC(54))
    im.save(out)
    return out


def clean_footer(src, out, link):
    """מוריד מתמונת הפרק את השורות "השאירו הודעה למספר" + מספר הטלפון,
    משחזר במקומן את הרקע המקורי (bg_card), ושם קוד QR לקבוצה."""
    import numpy as np
    import qrcode
    im = Image.open(src).convert("RGB")
    bg = Image.open(A / "bg_card.png").convert("RGB")
    if im.size != bg.size:
        im.save(out)
        return out
    diff = (np.abs(np.asarray(im, dtype=int) - np.asarray(bg, dtype=int)).max(axis=2) > 40)
    rows = diff[:, 150:930].sum(axis=1) > 3
    # קבוצות שורות עם טקסט בתחתית הכרטיס – שתי האחרונות הן "השאירו הודעה" והמספר
    blocks, y = [], 1500
    while y < 1880:
        if rows[y]:
            y0 = y
            while y < 1880 and rows[y]:
                y += 1
            blocks.append((y0, y))
        y += 1
    blocks = [b for b in blocks if b[1] - b[0] >= 6]
    if len(blocks) < 3:
        im.save(out)
        return out
    top, bottom = blocks[-2][0] - 4, blocks[-1][1] + 4
    above = blocks[-3][1]
    # משחזרים רקע רק ברוחב הטקסט של הטלפון – לא נוגעים בעלים שבצדדים (הם במיקום אחר מהרקע הנקי)
    cols = np.where(diff[top:bottom, 150:830].any(axis=0))[0]
    X0, X1 = 150 + int(cols.min()) - 10, 150 + int(cols.max()) + 11
    im.paste(bg.crop((X0, top, X1, bottom)), (X0, top))
    # QR באמצע הרווח שהתפנה
    space_top, space_bottom = above + 10, min(bottom + 40, 1850)
    avail = max(90, space_bottom - space_top)
    q = qrcode.QRCode(border=2, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1)
    q.add_data(link)
    q.make(fit=True)
    modules = q.modules_count + 2 * q.border
    box = max(2, avail // modules)            # כל ריבוע בקוד = מספר שלם של פיקסלים -> חד ומיושר
    q.box_size = box
    qr = q.make_image(fill_color=NAVY, back_color="white").convert("RGB")
    size = qr.width
    im.paste(bg.crop((X0, above + 2, X1, space_bottom)), (X0, above + 2))
    d = ImageDraw.Draw(im)
    f = SEC(36)
    label_w = max(d.textlength(w, font=f, direction="rtl") for w in ("סרקו", "והצטרפו"))
    gap = 24
    group = size + gap + label_w                  # QR + כיתוב ממורכזים יחד
    x_qr = int(540 + group / 2 - size)            # QR מימין (עברית), הכיתוב משמאלו
    y_qr = space_top + (avail - size) // 2
    im.paste(qr, (x_qr, y_qr))
    cy = y_qr + size // 2
    tx = x_qr - gap
    text(d, (tx, cy - 22), "סרקו", f, fill=GOLD, anchor="rm")
    text(d, (tx, cy + 22), "והצטרפו", f, fill=GOLD, anchor="rm")
    im.save(out)
    return out


def chapter_label(h):
    """'קי"ט' -> 'קיט' (בלי גרשיים באמצע); 'ד\'' נשאר 'ד\''."""
    return h.replace('"', "").replace("״", "").replace("'", "").replace("׳", "")


def reel_cover(chapter_h, out, variant="a"):  # אושר: עיגול (a), בלי גרש/גרשיים
    """תמונת שער אחידה לריל (מופיעה בפרופיל)."""
    im = Image.open(A / "bg_card.png").convert("RGB")
    d = ImageDraw.Draw(im)
    text(d, (960, 120), 'בס"ד', HEB(30, 800), anchor="rm")
    logo(im, 540, 460, 700)
    lab = chapter_label(chapter_h)
    if variant == "a":  # מסגרת זהב עגולה, בלי מילוי
        d.ellipse((540 - 290, 970 - 290, 540 + 290, 970 + 290), outline=GOLD, width=8)
        d.ellipse((540 - 266, 970 - 266, 540 + 266, 970 + 266), outline=GOLD, width=2)
        text(d, (540, 850), "פרק", SEC(100), fill=NAVY)
        text(d, (540, 1015), lab, fit(d, lab, 260, 440), fill=GOLD)
    else:  # בסגנון הכותרת של דפי הפרקים – פסים מעוטרים
        divider(d, 760, 300, 780)
        text(d, (540, 860), "פרק", SEC(110), fill=NAVY)
        text(d, (540, 1040), lab, fit(d, lab, 300, 700), fill=GOLD)
        divider(d, 1200, 300, 780)
    divider(d, 1400, 380, 700)
    text(d, (540, 1500), "פרק אחד בכל יום", SEC(72), fill=NAVY)
    im.save(out)
    return out


def intro_frames(out_dir, secs=1.6, fps=30):
    """פתיח: הלוגו צף פנימה (מתקרב ונכנס מלמטה בעדינות) על רקע הכרטיס. מחזיר תיקיית פריימים."""
    import math
    out_dir.mkdir(parents=True, exist_ok=True)
    bg = Image.open(A / "bg_card.png").convert("RGB")
    l0 = Image.open(A / "logo.png").convert("RGBA")
    l0 = l0.crop(l0.getbbox())
    n = int(secs * fps)
    for i in range(n):
        t = i / (n - 1)
        e = 1 - (1 - min(1, t / .75)) ** 3            # ease-out
        w = int(560 + 260 * e)
        lg = l0.resize((w, int(l0.height * w / l0.width)), Image.LANCZOS)
        a = lg.split()[3].point(lambda v: int(v * min(1, t / .45)))
        lg.putalpha(a)
        y = int(960 + 120 * (1 - e) + 8 * math.sin(t * math.pi * 2) * (t > .75))
        fr = bg.copy()
        fr.paste(lg, (540 - lg.width // 2, y - lg.height // 2), lg)
        if t > .55:
            d = ImageDraw.Draw(fr)
            k = min(1, (t - .55) / .3)
            col = tuple(int(c1 + (c2 - c1) * k) for c1, c2 in zip((235, 233, 225), GOLD))
            text(d, (540, y + lg.height // 2 + 70), "פרק אחד בכל יום", SEC(64), fill=col)
        fr.save(out_dir / f"f{i:03d}.png")
    return out_dir


def dedicate(src, line, out):
    """פס הקדשה בתחתית התמונה, בלי לכסות את הטקסט של הפרק."""
    im = Image.open(src).convert("RGB")
    w, h = im.size
    band = int(h * 0.075)
    canvas = Image.new("RGB", (w, h + band), NAVY)
    canvas.paste(im, (0, 0))
    d = ImageDraw.Draw(canvas)
    d.line((0, h, w, h), fill=GOLD, width=max(3, band // 18))
    size = int(band * 0.42)
    f = SEC(size)
    while d.textlength(line, font=f, direction="rtl") > w * 0.9 and size > 12:
        size -= 2
        f = SEC(size)
    text(d, (w // 2, h + band // 2), line, f, fill=WHITE)
    canvas.save(out)
    return out


if __name__ == "__main__":
    import sys
    o = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "out")
    o.mkdir(parents=True, exist_ok=True)
    shabbat_story("שבת שלום", "פרשת תולדות", o / "shabbat.png")
    siyum_card(o / "siyum.png")
    invite_story(o / "invite.png")
    clean_footer(ROOT / "images" / "001_1.png", o / "clean_001.png", "https://chat.whatsapp.com/Eh40Iv0LO9r9ZjLUgxeHQn")
    clean_footer(ROOT / "images" / "119_3.png", o / "clean_119.png", "https://chat.whatsapp.com/Eh40Iv0LO9r9ZjLUgxeHQn")
    dedicate(ROOT / "images" / "001_1.png", "הפרק מוקדש לרפואת פלוני בן פלונית", o / "dedication.png")
    print("ok", o)
