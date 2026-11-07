"""יוצר מנגינות רקע שקטות ומקוריות (בלי מילים) לריילס.
כל מנגינה: פסנתר רך + משטח מיתרים עדין, בסולם מז'ורי/הרמוני מתון, 30 שניות.
הרצה: python make_music.py  ->  assets/music/calm_1.mp3 ...
"""
import subprocess
from pathlib import Path

import numpy as np

SR = 44100
OUT = Path(__file__).resolve().parent / "assets" / "music"
NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def freq(name: str) -> float:
    n, octv = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((NOTE[n] + 12 * (octv + 1) - 69) / 12)


def piano(f, dur, vel=0.5):
    t = np.arange(int(SR * dur)) / SR
    env = np.exp(-t * 2.2) * (1 - np.exp(-t * 200))
    tone = sum(a * np.sin(2 * np.pi * f * k * t) for k, a in [(1, 1), (2, .35), (3, .12), (4, .05)])
    return vel * env * tone


def pad(freqs, dur):
    t = np.arange(int(SR * dur)) / SR
    env = np.minimum(1, t / 1.5) * np.minimum(1, (dur - t) / 1.5)
    sig = sum(np.sin(2 * np.pi * f * t + np.sin(2 * np.pi * .3 * t) * .4) +
              .5 * np.sin(2 * np.pi * f * 1.003 * t) for f in freqs)
    return .06 * env * sig


def reverb(x):
    y = x.copy()
    for d, g in [(0.031, .5), (0.047, .4), (0.071, .3), (0.113, .25), (0.173, .2), (0.29, .15)]:
        n = int(SR * d)
        y[n:] += g * x[:-n]
    return y


TRACKS = [
    # (מהירות שמינית בשניות, אקורדים, מנגינה עליונה)
    (0.42, [["C3", "G3", "E4"], ["A2", "E3", "C4"], ["F2", "C3", "A3"], ["G2", "D3", "B3"]],
     ["E5", "G5", "C5", "D5", "E5", "C5", "A4", "G4"]),
    (0.48, [["D3", "A3", "F#4"], ["B2", "F#3", "D4"], ["G2", "D3", "B3"], ["A2", "E3", "C#4"]],
     ["F#5", "E5", "D5", "A4", "B4", "D5", "C#5", "A4"]),
    (0.45, [["A2", "E3", "C4"], ["F2", "C3", "A3"], ["C3", "G3", "E4"], ["G2", "D3", "B3"]],
     ["C5", "E5", "A4", "B4", "C5", "G4", "B4", "D5"]),
    (0.5, [["F2", "C3", "A3"], ["D3", "A3", "F4"], ["A#2", "F3", "D4"], ["C3", "G3", "E4"]],
     ["A4", "C5", "F5", "E5", "D5", "C5", "D5", "E5"]),
    (0.44, [["G2", "D3", "B3"], ["E3", "B3", "G4"], ["C3", "G3", "E4"], ["D3", "A3", "F#4"]],
     ["B4", "D5", "G5", "F#5", "E5", "D5", "C5", "A4"]),
]


def make(idx, step, chords, melody, seconds=30):
    total = np.zeros(int(SR * (seconds + 3)))
    bar = step * 8
    t0, i = 0.0, 0
    while t0 < seconds:
        ch = chords[i % len(chords)]
        s = int(SR * t0)
        p = pad([freq(n) for n in ch], bar + 1)
        total[s:s + len(p)] += p[:len(total) - s]
        for k in range(8):  # ארפג'ו רך
            n = ch[k % 3] if k % 2 == 0 else ch[(k + 1) % 3]
            note = piano(freq(n), 2.5, .22)
            ss = int(SR * (t0 + k * step))
            total[ss:ss + len(note)] += note[:max(0, len(total) - ss)]
        if i % 2 == 1:  # מנגינה עליונה כל תיבה שנייה
            for k, n in enumerate(melody[(i // 2) % 2 * 4:(i // 2) % 2 * 4 + 4]):
                note = piano(freq(n), 3, .28)
                ss = int(SR * (t0 + k * step * 2))
                total[ss:ss + len(note)] += note[:max(0, len(total) - ss)]
        t0 += bar
        i += 1
    total = reverb(total[:SR * seconds])
    total /= np.max(np.abs(total)) / 0.7
    fade = int(SR * 2)
    total[:fade] *= np.linspace(0, 1, fade)
    total[-fade:] *= np.linspace(1, 0, fade)
    pcm = (total * 32767).astype(np.int16).tobytes()
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"calm_{idx}.mp3"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1",
                    "-i", "-", "-ac", "2", "-b:a", "160k", str(dst)], input=pcm, check=True)
    return dst


if __name__ == "__main__":
    for i, (st, ch, mel) in enumerate(TRACKS, 1):
        print(make(i, st, ch, mel))
