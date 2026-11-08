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
    VIOLIN, STRINGS, CHOIR, CELESTA = 40, 48, 52, 8
    p = Piece(name, bpm, {0: VIOLIN, 1: STRINGS, 2: STRINGS, 3: CHOIR})
    for ch, voice, vel, shift in ((0, "S", 84, 12), (1, "A", 52, 0), (2, "T", 48, -12), (3, "S", 40, 0)):
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
