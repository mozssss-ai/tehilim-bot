"""מנגינות רקע לריילס – יצירות קלאסיות בנחלת הכלל + בלדות מקוריות, בלי מילים.

כל היצירות הקלאסיות כאן הן בנחלת הכלל (המלחינים נפטרו לפני יותר מ-70 שנה),
והביצוע נוצר כאן מחדש, כך שאין בהן זכויות יוצרים של אף אחד.
הרצה: python make_music.py <soundfont.sf2>  ->  assets/music/*.mp3
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import tinysoundfont

SR = 44100
OUT = Path(__file__).resolve().parent / "assets" / "music"
SECONDS = 30
NAMES = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6,
         "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}


def m(n):
    return NAMES[n[:-1]] + 12 * (int(n[-1]) + 1)


# GM instruments
PIANO, HARP, STRINGS, SLOW_STR, PAD, FLUTE, OBOE, NYLON, CELLO, CELESTA, VIBES = 0, 46, 48, 49, 89, 73, 68, 24, 42, 8, 11


class Piece:
    def __init__(self, name, bpm, programs):
        self.name, self.bpm, self.programs, self.ev = name, bpm, programs, []

    def note(self, ch, t, dur, n, vel=80):
        if n is None:
            return
        k = m(n) if isinstance(n, str) else n
        self.ev.append((t, dur, ch, k, vel))

    def line(self, ch, t, seq, vel=80):
        """seq: [(note|None, beats), ...]; returns end time."""
        for n, d in seq:
            self.note(ch, t, d * 0.98, n, vel)
            t += d
        return t

    def chord(self, ch, t, notes, dur, vel=60):
        for n in notes:
            self.note(ch, t, dur, n, vel)

    def length(self):
        return max(t + d for t, d, *_ in self.ev)


def render(p: Piece, sf2: str):
    s = tinysoundfont.Synth(samplerate=SR, gain=-6)
    sf = s.sfload(sf2)
    for ch, prog in p.programs.items():
        s.program_select(ch, sf, 0, prog)
    spb = 60.0 / p.bpm
    total_beats = p.length()
    loops = max(1, int(np.ceil(SECONDS / (total_beats * spb))))
    events = []
    for L in range(loops):
        off = L * total_beats
        for t, d, ch, k, v in p.ev:
            events.append(((t + off) * spb, 1, ch, k, v))
            events.append(((t + d + off) * spb, 0, ch, k, 0))
    events.sort(key=lambda e: (e[0], e[1]))
    out, now = [], 0.0
    for t, on, ch, k, v in events:
        if t > SECONDS + 3:
            break
        n = int((t - now) * SR)
        if n > 0:
            out.append(np.frombuffer(s.generate(n), dtype=np.float32).copy())
            now += n / SR
        (s.noteon(ch, k, v) if on else s.noteoff(ch, k))
    s.notes_off()
    out.append(np.frombuffer(s.generate(int(3 * SR)), dtype=np.float32).copy())
    a = np.concatenate(out).reshape(-1, 2)[: SR * SECONDS]
    # רוורב עדין
    y = a.copy()
    for d, g in [(0.029, .28), (0.043, .22), (0.067, .18), (0.11, .14), (0.17, .1), (0.26, .07)]:
        n = int(SR * d)
        y[n:] += g * a[:-n][:, ::-1]
    y /= max(1e-6, np.abs(y).max()) / 0.8
    fi, fo = int(SR * 0.6), int(SR * 2.5)
    y[:fi] *= np.linspace(0, 1, fi)[:, None]
    y[-fo:] *= np.linspace(1, 0, fo)[:, None]
    pcm = (y * 32767).astype(np.int16).tobytes()
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"{p.name}.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(SR), "-ac", "2",
                    "-i", "-", "-b:a", "160k", str(dst)], input=pcm, check=True)
    return dst


# ------------------------------------------------------------------ pieces
def canon():  # פכלבל – קאנון ברה מז'ור
    p = Piece("01_pachelbel_canon", 64, {0: SLOW_STR, 1: PIANO, 2: CELLO})
    bass = ["D3", "A2", "B2", "F#2", "G2", "D2", "G2", "A2"]
    chords = [["D4", "F#4", "A4"], ["C#4", "E4", "A4"], ["B3", "D4", "F#4"], ["A3", "C#4", "F#4"],
              ["B3", "D4", "G4"], ["A3", "D4", "F#4"], ["B3", "D4", "G4"], ["C#4", "E4", "A4"]]
    t = 0
    for rep in range(3):
        for i, b in enumerate(bass):
            p.note(2, t + i * 2, 2, b, 70)
            p.chord(0, t + i * 2, chords[i], 2, 45)
        t += 16
    p.line(1, 16, [(n, 2) for n in ["F#5", "E5", "D5", "C#5", "B4", "A4", "B4", "C#5"]], 72)
    p.line(1, 32, [(n, 1) for n in ["D4", "F#4", "A4", "G4", "F#4", "D4", "F#4", "E4",
                                    "D4", "B3", "D4", "A4", "G4", "B4", "A4", "G4"]], 75)
    return p


def prelude():  # באך – פרלוד בדו מז'ור
    p = Piece("02_bach_prelude", 66, {0: HARP})
    bars = [("C4", "E4", "G4", "C5", "E5"), ("C4", "D4", "A4", "D5", "F5"), ("B3", "D4", "G4", "D5", "F5"),
            ("C4", "E4", "G4", "C5", "E5"), ("C4", "E4", "A4", "E5", "A5"), ("C4", "D4", "F#4", "A4", "D5"),
            ("B3", "D4", "G4", "D5", "G5"), ("B3", "C4", "E4", "G4", "C5"), ("A3", "C4", "E4", "G4", "C5"),
            ("D3", "A3", "D4", "F#4", "C5"), ("G3", "B3", "D4", "G4", "B4")]
    t = 0
    for b in bars:
        for half in range(2):
            h = t + half * 2
            p.note(0, h, 2, b[0], 70)
            p.note(0, h + .25, 1.75, b[1], 62)
            for j, n in enumerate([b[2], b[3], b[4], b[2], b[3], b[4]]):
                p.note(0, h + .5 + j * .25, .5, n, 66)
        t += 4
    return p


def morning():  # גריג – מצב רוח של בוקר
    p = Piece("03_grieg_morning", 72, {0: FLUTE, 1: STRINGS, 2: HARP})
    a = [("G#5", .5), ("E5", .5), ("D#5", .5), ("C#5", .5), ("D#5", .5), ("E5", 1.5)]
    b = [("G#5", .5), ("E5", .5), ("D#5", .5), ("C#5", .5), ("D#5", .5), ("E5", .5), ("D#5", .5), ("E5", .5),
         ("G#5", .5), ("E5", .5), ("G#5", .5), ("A5", .5), ("E5", .5), ("A5", .5), ("G#5", .5), ("E5", .5),
         ("D#5", .5), ("C#5", 1.5)]
    t = p.line(0, 0, a, 78)
    t = p.line(0, t, a, 74)
    t = p.line(0, t, b, 78)
    for i in range(int(t // 4) + 1):
        ch = ["E3", "B3", "E4", "G#4"] if i % 2 == 0 else ["A2", "E3", "A3", "C#4"]
        p.chord(1, i * 4, ch, 4, 42)
        for j, n in enumerate(ch * 2):
            p.note(2, i * 4 + j * .5, .5, n, 50)
    return p


def largo():  # דבוז'אק – לרגו מהסימפוניה "מן העולם החדש"
    p = Piece("04_dvorak_largo", 58, {0: OBOE, 1: SLOW_STR, 2: CELLO})
    mel = [("E4", 1.5), ("G4", .5), ("G4", 2), ("E4", 1.5), ("D4", .5), ("C4", 2), ("D4", 1), ("E4", 1),
           ("G4", 1), ("E4", 1), ("D4", 4),
           ("E4", 1.5), ("G4", .5), ("G4", 2), ("E4", 1.5), ("D4", .5), ("C4", 2), ("D4", 1), ("E4", 1),
           ("D4", 1), ("C4", 1), ("C4", 4)]
    t = p.line(0, 0, mel, 76)
    prog = [["C3", "E3", "G3"], ["C3", "E3", "G3"], ["F2", "A3", "C4"], ["G2", "B3", "D4"],
            ["C3", "E3", "G3"], ["A2", "C3", "E3"], ["F2", "A3", "C4"], ["G2", "B3", "F4"], ["C3", "E3", "G3"]]
    for i in range(int(t // 4) + 1):
        c = prog[i % len(prog)]
        p.note(2, i * 4, 4, c[0], 60)
        p.chord(1, i * 4, c[1:], 4, 42)
    return p


def lullaby():  # ברהמס – שיר ערש
    p = Piece("05_brahms_lullaby", 76, {0: CELESTA, 1: HARP})
    mel = [("E4", .5), ("E4", .5), ("G4", 2), ("E4", .5), ("E4", .5), ("G4", 2),
           ("E4", .5), ("G4", .5), ("C5", 1), ("B4", 1.5), ("A4", .5), ("A4", 1), ("G4", 1),
           ("D4", .5), ("E4", .5), ("F4", 1), ("D4", 1), ("D4", .5), ("E4", .5), ("F4", 2),
           ("D4", .5), ("F4", .5), ("B4", .5), ("A4", 1), ("G4", 1), ("B4", 1), ("C5", 3)]
    t = p.line(0, 1, mel, 80)
    for i in range(int(t // 3) + 1):
        c = ["C3", "G3", "E4"] if (i // 2) % 2 == 0 else ["G2", "F3", "B3"]
        for j, n in enumerate(c):
            p.note(1, i * 3 + j, 1, n, 50)
    return p


def moonlight():  # בטהובן – סונטת אור הירח
    p = Piece("06_beethoven_moonlight", 54, {0: PIANO})
    bars = [("C#2", "C#3", [("G#3", "C#4", "E4")] * 4), ("B1", "B2", [("G#3", "C#4", "E4")] * 4),
            ("A1", "A2", [("A3", "C#4", "E4")] * 2 + [("A3", "D4", "F#4")] * 2),
            ("G#1", "G#2", [("G#3", "C4", "F#4")] * 2 + [("G#3", "C#4", "E4"), ("F#3", "C4", "D#4")]),
            ("C#2", "C#3", [("E3", "G#3", "C#4")] * 4)]
    t = 0
    for lo, hi, tri in bars:
        p.note(0, t, 4, lo, 55)
        p.note(0, t, 4, hi, 55)
        for q, trip in enumerate(tri):
            for j, n in enumerate(trip):
                p.note(0, t + q + j / 3, .4, n, 52)
        t += 4
    return p


def gymnopedie():  # סאטי – ג'ימנופדי מס' 1
    p = Piece("07_satie_gymnopedie", 72, {0: PIANO})
    for i in range(12):
        t = i * 3
        if i % 2 == 0:
            p.note(0, t, 3, "G2", 55)
            p.chord(0, t + 1, ["B3", "D4", "F#4"], 2, 45)
        else:
            p.note(0, t, 3, "D2", 55)
            p.chord(0, t + 1, ["A3", "C#4", "F#4"], 2, 45)
    p.line(0, 12, [(None, 1), ("F#5", 1), ("A5", 1), ("G5", 1), ("F#5", 1), ("C#5", 1),
                   ("B4", 1), ("C#5", 1), ("D5", 1), ("A4", 3), ("F#4", 6)], 70)
    return p


def ode():  # בטהובן – אודה לשמחה (איטי, גיטרה)
    p = Piece("08_beethoven_ode", 68, {0: NYLON, 1: STRINGS})
    q = lambda ns: [(n, 1) for n in ns]
    mel = q(["F#4", "F#4", "G4", "A4", "A4", "G4", "F#4", "E4", "D4", "D4", "E4", "F#4"]) + \
        [("F#4", 1.5), ("E4", .5), ("E4", 2)] + \
        q(["F#4", "F#4", "G4", "A4", "A4", "G4", "F#4", "E4", "D4", "D4", "E4", "F#4"]) + \
        [("E4", 1.5), ("D4", .5), ("D4", 2)]
    t = p.line(0, 0, mel, 82)
    prog = [["D3", "A3", "D4"], ["D3", "A3", "D4"], ["D3", "A3", "D4"], ["A2", "E3", "A3"]] * 2
    for i in range(int(t // 4)):
        p.chord(1, i * 4, prog[i % len(prog)], 4, 38)
    return p


def ballad(name, prog, inst, bpm, mel_inst=None, melody=None):  # בלדות מקוריות
    progs = {0: inst, 1: PAD}
    if mel_inst is not None:
        progs[2] = mel_inst
    p = Piece(name, bpm, progs)
    t = 0
    for rep in range(2):
        for c in prog:
            root, rest = c[0], c[1:]
            pattern = [root, rest[0], rest[1], rest[2], rest[1], rest[0], rest[1], rest[2]]
            for j, n in enumerate(pattern):
                p.note(0, t + j * .5, 1.5, n, 64 if j else 72)
            p.chord(1, t, rest, 4, 30)
            t += 4
    if melody:
        p.line(2, 8, melody, 70)
    return p


def pieces():
    yield canon()
    yield prelude()
    yield morning()
    yield largo()
    yield lullaby()
    yield moonlight()
    yield gymnopedie()
    yield ode()
    yield ballad("09_ballad_guitar_G", [["G2", "B3", "D4", "G4"], ["D3", "A3", "D4", "F#4"], ["E2", "B3", "E4", "G4"],
                                        ["C3", "G3", "C4", "E4"]], NYLON, 72, FLUTE,
                 [("D5", 2), ("B4", 1), ("A4", 1), ("G4", 2), ("A4", 2), ("B4", 3), ("A4", 1), ("G4", 4)])
    yield ballad("10_ballad_piano_C", [["C3", "E4", "G4", "C5"], ["A2", "E4", "A4", "C5"], ["F2", "F4", "A4", "C5"],
                                       ["G2", "D4", "G4", "B4"]], PIANO, 66, SLOW_STR,
                 [("E5", 2), ("D5", 1), ("C5", 1), ("A4", 3), ("C5", 1), ("B4", 2), ("G4", 2), ("C5", 4)])
    yield ballad("11_ballad_harp_D", [["D3", "F#4", "A4", "D5"], ["B2", "F#4", "B4", "D5"], ["G2", "G4", "B4", "D5"],
                                      ["A2", "E4", "A4", "C#5"]], HARP, 70)
    yield ballad("12_ballad_minor_Am", [["A2", "E4", "A4", "C5"], ["F2", "F4", "A4", "C5"], ["C3", "E4", "G4", "C5"],
                                        ["G2", "D4", "G4", "B4"]], NYLON, 64, CELLO,
                 [("E4", 2), ("A4", 2), ("G4", 2), ("E4", 2), ("F4", 2), ("E4", 1), ("D4", 1), ("E4", 4)])
    yield ballad("13_ballad_vibes_F", [["F2", "A3", "C4", "F4"], ["D3", "A3", "D4", "F4"], ["Bb2", "F3", "Bb3", "D4"],
                                       ["C3", "G3", "C4", "E4"]], VIBES, 68)


if __name__ == "__main__":
    sf2 = sys.argv[1]
    for old in OUT.glob("*.mp3"):
        old.unlink()
    for p in pieces():
        print(render(p, sf2))
