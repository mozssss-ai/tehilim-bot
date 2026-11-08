"""יצירות קלאסיות בנחלת הכלל (מאגר Mutopia, LilyPond -> MIDI) לסטוריז של החגים, עם כלים שנבחרו מחדש
(בלי כינור כמנגינה ראשית). הרצה: python midi_tunes.py <sf2> <midi_dir> <out_dir> [seconds]"""
import sys
from pathlib import Path

import mido
import make_music as mm
from make_music import Piece

PIECES = {  # מפתח חג: (קובץ MIDI, {track: GM program}, התחלה בשניות, שינוי עוצמה לפי track)
    "sukkot": ("autumn-score.midi", {1: 73, 2: 73, 3: 46, 4: 49, 5: 42}, 0.0, {1: 1.0, 2: .0, 3: .6, 4: .55, 5: .7}),
    "purim_a_rejected": ("anitrasdance.midi", {1: 73, 2: 68, 3: 45, 4: 45, 5: 45, 6: 45, 7: 45}, 0.0,
              {1: 1.0, 2: .7, 3: .6, 4: .55, 5: .55, 6: .55, 7: .7}),
    "purim": ("autumn-score-2.midi", {1: 73, 2: 73, 3: 48, 4: 48, 5: 42}, 0.0, {1: 1.0, 2: 0, 3: .55, 4: .5, 5: .7}),
    "yom_kippur_a_rejected": ("pathetique-2.midi", {1: 0, 2: 0}, 0.0, {1: 1.0, 2: .8}),
    "yom_kippur": ("waltz-op39-15.midi", {1: 0, 2: 0}, 0.0, {1: 1.0, 2: .8}),
    "tu_beav": ("debussy_Ste_Bergamesq_Clair.midi", {1: 0, 2: 0}, 0.0, {1: 1.0, 2: .85}),
}


def load(path, programs, start, gains):
    mid = mido.MidiFile(path)
    p = Piece("x", 60, {})  # bpm 60 -> פעמה = שנייה
    ch_of = {}
    for ti, track in enumerate(mid.tracks):
        if ti not in programs or gains.get(ti, 1) == 0:
            continue
        ch = len(ch_of)
        ch_of[ti] = ch
        p.programs[ch] = programs[ti]
    for ti, ch in ch_of.items():
        t, on = 0.0, {}
        tempo = 500000
        for msg in mido.merge_tracks([mid.tracks[0], mid.tracks[ti]]):
            t += mido.tick2second(msg.time, mid.ticks_per_beat, tempo)
            if msg.type == "set_tempo":
                tempo = msg.tempo
            elif msg.type == "note_on" and msg.velocity > 0:
                on[msg.note] = (t, msg.velocity)
            elif msg.type in ("note_off", "note_on") and msg.note in on:
                st, v = on.pop(msg.note)
                if st >= start:
                    p.ev.append((st - start, max(.05, t - st), ch, msg.note, int(min(110, v * gains.get(ti, 1)))))
    return p


if __name__ == "__main__":
    sf2, mdir, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    mm.OUT, mm.SECONDS = out, int(sys.argv[4]) if len(sys.argv) > 4 else 14
    for key, (f, progs, start, gains) in PIECES.items():
        p = load(mdir / f, progs, start, gains)
        p.name = key
        print(mm.render(p, sf2))
