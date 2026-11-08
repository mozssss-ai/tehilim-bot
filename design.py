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


def shabbat_story(title, subtitle, out, question="השבת הזאת – גם אתם איתנו?"):
    """title: 'שבת שלום' / 'חג שמח' / 'שנה טובה' ... subtitle: למשל 'פרשת תולדות' / 'ראש השנה'."""
    im = Image.open(A / "bg_card.png").convert("RGB")
    d = ImageDraw.Draw(im)
    text(d, (960, 120), 'בס"ד', HEB(30, 800), anchor="rm")
    logo(im, 540, 330, 560)
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
    im.paste(bg.crop((90, top, 990, bottom)), (90, top))
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
    im.paste(bg.crop((90, above + 2, 990, space_bottom)), (90, above + 2))
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
