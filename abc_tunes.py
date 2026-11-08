"""שירי חג מסורתיים (נחלת הכלל) בכתיב ABC, וממיר קטן ל-Piece של make_music.
מקורות התווים: Maoz Tsur (כתב יד מודפס, 3 קולות) ו-Dayeinu (Favorite Hebrew Songs, Rozin)
מתוך האוסף של John Chambers ב-folktunefinder.
"""
import re

from make_music import Piece

BASE = {"C": 60, "D": 62, "E": 64, "F": 65, "G": 67, "A": 69, "B": 71}
KEYS = {"F": {"B": -1}, "C": {}, "G": {"F": 1}, "D": {"F": 1, "C": 1}, "Am": {}, "Dm": {"B": -1}}
TOKEN = re.compile(r'"([^"]*)"|(\^|_|=)?([A-Ga-gz])([,\']*)(\d*)(/?)(\d*)(-?)')


def parse(body, key="C", unit=0.5):
    """body: שורות תווים (בלי סימני חזרה). unit = אורך L ברבעים (1/8 => 0.5).
    מחזיר [(midi|None, beats)], ורשימת אקורדים [(time, name)]."""
    acc = KEYS[key]
    out, chords, t, tie = [], [], 0.0, False
    for bar in body.split("|"):
        bar_acc = {}
        for m in TOKEN.finditer(bar):
            if m.group(1) is not None:
                chords.append((t, m.group(1)))
                continue
            sign, letter, octs, num, slash, den, tied = m.groups()[1:]
            d = float(num) if num else 1.0
            if slash:
                d = d / (float(den) if den else 2.0)
            beats = d * unit
            if letter == "z":
                out.append((None, beats))
                t += beats
                tie = False
                continue
            up = letter.upper()
            k = BASE[up] + (12 if letter.islower() else 0) + 12 * octs.count("'") - 12 * octs.count(",")
            if sign:
                bar_acc[up] = {"^": 1, "_": -1, "=": 0}[sign]
            k += bar_acc.get(up, acc.get(up, 0))
            if tie and out and out[-1][0] == k:
                out[-1] = (k, out[-1][1] + beats)
            else:
                out.append((k, beats))
            t += beats
            tie = bool(tied)
    return out, chords


CHORD_NOTES = {"C": [48, 55, 60, 64], "G7": [43, 55, 59, 65], "G": [43, 55, 59, 62], "F": [41, 53, 57, 60],
               "Am": [45, 52, 57, 60], "Dm": [50, 57, 62, 65], "E": [40, 52, 56, 59], "A": [45, 52, 57, 61]}

# ---------------------------------------------------------------- מעוז צור (3 קולות, פה מז'ור)
MAOZ = {
    "S": "F2C2 F2B2 | A2G2 F4 | c2d2 G2B2 | A2G2 F4 | F2C2 F2B2 | A2G2 F4 | c2d2 G2B2 | A2G2 F4 |"
         " c2c2 d2e2 | f4 c4 | f2e2 d2c2 | cBAB G4 | A3B c4 | G3A B4 | A2G2 F2B2 | A4 G3F | F8 |",
    "A": "F2C2 F2F2 | F2E2 F4 | A2B2 G2G2 | F2E2 C2B,2 | A,2B,2 C2F2 | F2E2 D4 | F2F2 E2F2 | E4 F4 |"
         " A2A2 B2G2 | A4 A4 | c2B2 A2G2 | F2F2 F2E2 | F4 G4 | G4 F4 | E2D2 C2D2 | C2 F4 E2 | C8 |",
    "T": "f2c2 f2d2 | c2c2 f4 | f4 f2e2 | f2c2 A2G2 | F2G2 A2d2 | c2^c2 d2B2 | A2B2 =c2_d2 | c4 f4 |"
         " f2f2 f2f2 | f4 f4 | a2g2 f2e2 | d2_d2 c4 | f4 e4 | _e4 d2_d2 | c2B2 A2G2 | c4 c4 | F8 |",
}

# ---------------------------------------------------------------- דיינו (דו מז'ור)
DAYENU_A = '"C"EG GG | GA "G7"GF | "C"EG GG | GA "G7"GF | "C"EG "G7"DF | "C"EG "G7"DF | "C"E2 "G7"D2 | "C"C4 |'
DAYENU_B = ('"C"E2 E2 | "G7"GF- F2 | F2 F2 | "C"AG- G2 | G2 G2 | "G7"cB- BB | BG AB | "C"cG EC |'
            '"C"E2 E2 | "G7"GF- F2 | F2 F2 | "C"AG- G2 | G2 G2 | "G7"cB- BB | BG AB | "C"c4 |')


def maoz_tzur(name="chanukah", bpm=84):
    PIANO, HARP, SLOW_STR, CELESTA = 0, 46, 49, 8
    p = Piece(name, bpm, {0: PIANO, 1: HARP, 2: SLOW_STR, 3: CELESTA})
    for ch, voice, vel, shift in ((0, "S", 88, 12), (1, "A", 50, 0), (2, "T", 40, -12), (3, "S", 34, 24)):
        seq, _ = parse(MAOZ[voice], "F")
        t = 0.0
        for k, d in seq:
            if k is not None:
                p.note(ch, t, d * 0.97, k + shift, vel)
            t += d
    return p


def dayenu(name="pesach", bpm=126):
    CLARINET, ACCORDION, BASS = 71, 21, 32
    p = Piece(name, bpm, {0: CLARINET, 1: ACCORDION, 2: BASS})
    t0 = 0.0
    for part in (DAYENU_A, DAYENU_A, DAYENU_B):
        seq, chords = parse(part, "C")
        t = t0
        for k, d in seq:
            if k is not None:
                p.note(0, t, d * 0.9, k + 12, 86)
            t += d
        total = t - t0
        chords.append((total, None))
        for (ct, nm), (nt, _) in zip(chords, chords[1:]):
            notes = CHORD_NOTES.get(nm, CHORD_NOTES["C"])
            b = ct
            while b < nt - 1e-6:  # אום-צ'ה בשמיניות
                p.note(2, t0 + b, 0.45, notes[0] - 12, 70)
                for n in notes[1:]:
                    p.note(1, t0 + b + 0.5, 0.4, n, 50)
                b += 1.0
        t0 = t
    return p


# ---------------------------------------------------------------- שושנת יעקב (לחן עממי, לפי ויקיטקסט "ביאור:שושנת יעקב/לחן 1")
# (פיץ', אורך ברבעים) – 8 התיבות הראשונות + אנקרוזה
SHOSHANAT = [("E4", .5),
             ("C5", .5), ("C5", .5), ("B4", .5), ("B4", .5), ("A4", 1.5), ("E4", .5),
             ("A4", .5), ("A4", .25), ("A4", .25), ("G4", .5), ("F4", .5), ("E4", 1.5), ("A4", .5),
             ("A4", .5), ("A4", 1), ("B4", .5), ("C5", .5), ("C5", 1), ("D5", .5),
             ("E5", .5), ("F5", .5), ("E5", .5), ("D5", .5), ("E5", 1.5), (None, .5),
             ("C5", 1), ("B4", 1), ("A4", .5), ("A4", 1), ("E4", .5),
             ("A4", .5), ("A4", .5), ("G4", .5), ("F4", .5), ("E4", 2),
             ("A4", 1.5), ("B4", .5), ("C5", .5), ("C5", 1), ("D5", .5),
             ("E5", .5), ("F5", .5), ("E5", .5), ("D5", .5), ("A4", .5), ("A4", .5), ("B4", .5), ("C5", .5)]
SHOSH_CHORDS = ["Am", "Dm", "Am", "Dm", "Am", "Dm", "Am", "E"]  # אקורד לכל חצי תיבה בערך


def shoshanat_yaakov(name="purim", bpm=132):
    from make_music import m
    CLARINET, ACCORDION, BASS = 71, 21, 32
    p = Piece(name, bpm, {0: CLARINET, 1: ACCORDION, 2: BASS})
    t = 0.0
    for n, d in SHOSHANAT:
        if n:
            p.note(0, t, d * .9, m(n), 88)
        t += d
    bars = int(t // 4) + 1
    prog = ["Am", "Am", "Am", "E", "Am", "Dm", "Am", "E", "Am"]
    for b in range(bars):
        notes = CHORD_NOTES[prog[b % len(prog)]]
        for beat in range(4):
            bt = .5 + b * 4 + beat  # אחרי האנקרוזה
            p.note(2, bt, .45, notes[0] - 12, 70) if beat % 2 == 0 else [p.note(1, bt, .4, k, 50) for k in notes[1:]]
    return p


# ---------------------------------------------------------------- יגדל (לחן ליאוני, ניגון בית כנסת; נחלת הכלל – Mutopia "Leoni")
# לשבועות: "תורת אמת נתן לעמו אל". סופרן + אלט (פה מינור), אנקרוזה של רבע.
YIGDAL_S = [("C4", 1), ("F4", 1), ("G4", 1), ("Ab4", 1), ("Bb4", 1), ("C5", 3),
            ("Ab4", 1), ("Bb4", 1), ("C5", 1), ("Db5", 1), ("Eb5", 1), ("C5", 3),
            ("G4", 1), ("Ab4", 1), ("Bb4", 1), ("C5", 1), ("Db5", 1), ("Eb5", 1), ("G4", 1), ("Ab4", 1),
            ("Db5", 1), ("C5", 2), ("Bb4", 2), ("Ab4", 3),
            ("Ab4", .5), ("Bb4", .5), ("C5", 1), ("C5", 1), ("C5", 1), ("C5", 1), ("Bb4", 3),
            ("Ab4", .5), ("G4", .5), ("F4", .5), ("G4", .5), ("Ab4", .5), ("Bb4", .5), ("C5", 1), ("F4", 1), ("F4", 1), ("E4", 2),
            ("C4", 1), ("F4", 1), ("G4", 1), ("Ab4", 1), ("Bb4", 1), ("C5", 1), ("Bb4", .5), ("C5", .5), ("Db5", 1),
            ("C5", .5), ("Bb4", .5), ("Ab4", 2), ("G4", 2), ("F4", 3)]
YIGDAL_A = [("C4", 1), ("C4", 1), ("E4", 1), ("F4", 1), ("F4", 1), ("E4", 3),
            ("Eb4", 1), ("Eb4", 1), ("Eb4", 1), ("Ab4", 1), ("G4", 1), ("Eb4", 3),
            ("Eb4", 1), ("Eb4", 1), ("Eb4", 1), ("Eb4", 1), ("Ab4", 1), ("G4", 1), ("Eb4", 1), ("Eb4", 1),
            ("Db4", 1), ("Eb4", 2), ("Eb4", 1), ("Db4", 1), ("C4", 3)]


def yigdal(name="shavuot", bpm=76):
    from make_music import m
    PIANO, CHOIR, SLOW_STR = 0, 52, 49
    p = Piece(name, bpm, {0: PIANO, 1: CHOIR, 2: SLOW_STR})
    for ch, seq, vel, sh in ((0, YIGDAL_S, 86, 12), (1, YIGDAL_S, 44, 0), (2, YIGDAL_A, 46, 0)):
        t = 0.0
        for n, d in seq:
            p.note(ch, t, d * .96, m(n) + sh, vel)
            t += d
    return p
