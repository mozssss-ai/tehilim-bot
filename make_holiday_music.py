"""מנגינות לסטוריז של החגים – לחנים מקוריים ברוח כל חג (בלי זכויות יוצרים של אף אחד).
הרצה: python make_holiday_music.py <soundfont.sf2>  ->  assets/music/holiday/<חג>.mp3
"""
import random
import sys
from pathlib import Path

import make_music as mm
from make_music import Piece, m

mm.OUT = Path(__file__).resolve().parent / "assets" / "music" / "holiday"
mm.SECONDS = 14

BELLS, GLOCK, CLARINET, ACCORDION, VIOLIN, HORN, MARIMBA, BANJO, OCARINA, CHOIR = 14, 9, 71, 21, 40, 60, 12, 105, 79, 52


def tune(name, bpm, chords, inst, mel_inst, seed, rhythms, bass=None, mel_vel=78, arp=True):
    rnd = random.Random(seed)
    progs = {0: inst, 2: mel_inst}
    if bass is not None:
        progs[1] = bass
    p = Piece(name, bpm, progs)
    t, prev = 0, None
    for rep in range(2):
        for c in chords:
            root, rest = c[0], c[1:]
            if arp:
                pat = [root, rest[0], rest[1], rest[2], rest[1], rest[0], rest[1], rest[2]]
                for j, n in enumerate(pat):
                    p.note(0, t + j * .5, 1.2, n, 60 if j else 70)
            else:  # "אום-צ'ה" – ליווי קצבי לריקוד
                for j in range(4):
                    if j % 2 == 0:
                        p.note(0, t + j, .45, root, 74)
                    else:
                        p.chord(0, t + j, rest, .45, 58)
            if bass is not None:
                p.note(1, t, 3.8, root, 52)
            tones = [m(x) + 12 for x in rest] + [m(rest[0]) + 24]
            tt = t
            for d in rnd.choice(rhythms):
                cand = sorted(tones, key=lambda k: abs(k - prev) if prev else 0)
                k = cand[0] if prev and rnd.random() < .55 else rnd.choice(tones)
                p.note(2, tt, d * .92, k, mel_vel)
                prev, tt = k, tt + d
            t += 4
    return p


def shofar_then(name):
    """ראש השנה: תקיעה, שברים, תרועה, תקיעה – ואחריה מנגינה מתוקה."""
    p = Piece(name, 72, {3: HORN, 0: mm.HARP, 2: mm.FLUTE, 1: mm.PAD})
    t = 0
    p.note(3, t, 3, "Bb3", 92); p.note(3, t + 2.6, .6, "F4", 96); t += 3.6          # תקיעה
    for _ in range(3):
        p.note(3, t, .55, "Bb3", 88); p.note(3, t + .45, .3, "F4", 90); t += .9     # שברים
    t += .3
    for _ in range(9):
        p.note(3, t, .18, "F4", 84); t += .22                                         # תרועה
    t += .3
    p.note(3, t, 2.8, "Bb3", 92); p.note(3, t + 2.4, .8, "F4", 100); t += 3.6       # תקיעה
    sweet = tune("tmp", 72, [["F2", "A3", "C4", "F4"], ["D3", "A3", "D4", "F4"], ["Bb2", "F3", "Bb3", "D4"],
                             ["C3", "G3", "C4", "E4"]], mm.HARP, mm.FLUTE, 7, [[2, 1, 1], [1, 1, 2], [3, 1]], mm.PAD)
    for (tt, d, ch, k, v) in sweet.ev:
        p.ev.append((tt + t, d, ch, k, v))
    return p


FREYGISH = [["D3", "F#3", "A3", "D4"], ["Eb3", "G3", "Bb3", "Eb4"], ["C3", "Eb3", "G3", "C4"], ["D3", "F#3", "A3", "D4"]]


def pieces():
    yield shofar_then("rosh_hashana")
    yield tune("yom_kippur", 54, [["D3", "A3", "D4", "F4"], ["Bb2", "F3", "Bb3", "D4"], ["G2", "D3", "G3", "Bb3"],
                                  ["A2", "E3", "A3", "C#4"]], mm.PIANO, mm.CELLO, 3, [[4], [2, 2], [3, 1]], mm.SLOW_STR, 70)
    yield tune("sukkot", 104, [["G2", "B3", "D4", "G4"], ["C3", "E3", "G3", "C4"], ["D3", "F#3", "A3", "D4"],
                               ["G2", "B3", "D4", "G4"]], mm.NYLON, mm.FLUTE, 11, [[1, 1, 1, 1], [1.5, .5, 2], [1, 1, 2]], None, 80, False)
    yield tune("simchat_torah", 128, FREYGISH, ACCORDION, CLARINET, 12, [[1, 1, 1, 1], [.5, .5, 1, 2], [1, .5, .5, 2]], None, 84, False)
    yield tune("chanukah", 92, [["C3", "E3", "G3", "C4"], ["A2", "C3", "E3", "A3"], ["F2", "A2", "C3", "F3"],
                                ["G2", "B2", "D3", "G3"]], GLOCK, BELLS, 21, [[2, 1, 1], [1, 1, 2], [1, 1, 1, 1]], mm.STRINGS, 72)
    yield tune("purim", 132, FREYGISH, ACCORDION, CLARINET, 31, [[.5, .5, 1, 2], [1, 1, 1, 1], [1, .5, .5, 2]], None, 86, False)
    yield tune("pesach", 96, [["D3", "F#3", "A3", "D4"], ["G2", "B2", "D3", "G3"], ["A2", "C#3", "E3", "A3"],
                              ["D3", "F#3", "A3", "D4"]], mm.HARP, mm.FLUTE, 41, [[1, 1, 2], [2, 1, 1], [1.5, .5, 2]], mm.STRINGS)
    yield tune("shavuot", 88, [["F2", "A3", "C4", "F4"], ["Bb2", "D3", "F3", "Bb3"], ["C3", "E3", "G3", "C4"],
                               ["F2", "A3", "C4", "F4"]], mm.NYLON, OCARINA, 51, [[2, 2], [1, 1, 2], [3, 1]], mm.PAD)
    yield tune("tu_bishvat", 84, [["G2", "D3", "G3", "B3"], ["E2", "B2", "E3", "G3"], ["C3", "G3", "C4", "E4"],
                                  ["D3", "A3", "D4", "F#4"]], MARIMBA, mm.FLUTE, 61, [[1, 1, 2], [2, 1, 1], [1, 1, 1, 1]], None)
    yield tune("lag_baomer", 100, [["E2", "B2", "E3", "G#3"], ["A2", "E3", "A3", "C#4"], ["B2", "F#3", "B3", "D#4"],
                                   ["E2", "B2", "E3", "G#3"]], mm.NYLON, BANJO, 71, [[1, 1, 1, 1], [1.5, .5, 2], [2, 1, 1]], None, 76, False)
    yield tune("tu_beav", 76, [["A2", "E3", "A3", "C#4"], ["F#2", "C#3", "F#3", "A3"], ["D3", "A3", "D4", "F#4"],
                               ["E3", "B3", "E4", "G#4"]], mm.PIANO, VIOLIN, 81, [[2, 1, 1], [3, 1], [1, 1, 2]], mm.SLOW_STR)


if __name__ == "__main__":
    sf2 = sys.argv[1]
    for p in pieces():
        print(mm.render(p, sf2))
