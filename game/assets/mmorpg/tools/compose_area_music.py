"""Write the looping area tunes into assets/music.

The login theme and the overworld tunes are an original fanfare: major
key, a horn lead, and a marching bass. The line is not taken from any
existing game theme. Village shares that melody. The deep places stay
on the older modal flute.

Run from game/assets/mmorpg with a Python that has numpy.
"""
from __future__ import annotations

import math
import os
import wave

import numpy as np

SR = 22050
OUT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "music"))

SCALES = {
    "dorian": [0, 2, 3, 5, 7, 9, 10],
    "minor": [0, 2, 3, 5, 7, 8, 10],
    "major": [0, 2, 4, 5, 7, 9, 11],
    "mixolydian": [0, 2, 4, 5, 7, 9, 10],
    "phrygian": [0, 1, 3, 5, 7, 8, 10],
    "penta": [0, 2, 4, 7, 9],
}

# (degree or None, beats)
MOTIF_A = [
    (0, 0.5), (2, 0.5), (3, 0.5), (4, 1.0), (None, 0.5),
    (3, 0.5), (2, 0.5), (0, 1.0), (None, 0.5),
    (4, 0.5), (7, 0.5), (4, 0.5), (3, 1.0),
    (2, 0.5), (0, 0.5), (None, 0.5), (0, 1.5),
    (None, 5.0),
]
MOTIF_B = [
    (4, 1.0), (5, 0.5), (4, 0.5), (3, 1.0),
    (2, 1.0), (0, 1.0),
    (-1, 0.5), (0, 1.5),
    (2, 0.5), (3, 0.5), (4, 1.0),
    (3, 0.5), (2, 0.5), (0, 2.0),
    (None, 4.0),
]
HARBOUR = [
    (0, 1.0), (1, 0.5), (2, 0.5), (3, 1.0), (2, 0.5), (1, 0.5), (0, 1.0), (None, 1.0),
    (3, 1.0), (4, 1.0), (3, 0.5), (2, 0.5), (1, 1.0), (0, 2.0), (None, 4.0),
]
WILD = [
    (0, 1.5), (3, 0.5), (2, 1.0), (0, 1.0), (None, 2.0),
    (-1, 1.0), (0, 2.0), (None, 7.0),
]
MOUNTAIN = [
    (0, 4.0), (4, 4.0), (2, 4.0), (0, 4.0),
]
MINE = [
    (0, 0.5), (0, 0.5), (3, 0.5), (None, 2.5),
]
DELVE = [
    (0, 0.5), (2, 0.5), (3, 0.5), (7, 1.0),
    (5, 0.5), (3, 0.5), (2, 1.0), (0, 1.5), (None, 2.0),
]
VOID = [
    (0, 3.0), (1, 1.0), (0, 4.0), (None, 8.0),
]
EMBER = [
    (0, 0.5), (1, 0.5), (0, 1.0), (3, 0.5), (1, 0.5), (0, 1.0), (None, 4.0),
]
WYRM = [
    (0, 0.5), (1, 0.5), (0, 0.5), (3, 0.5),
    (4, 0.5), (3, 0.5), (1, 0.5), (0, 0.5),
]
# Original overworld fanfare. Eight-beat phrases, major degrees.
FANFARE = [
    (4, 0.75), (4, 0.25), (5, 0.5), (7, 0.5),
    (9, 1.0), (7, 0.5), (5, 0.5),
    (4, 1.0), (2, 1.0), (4, 2.0),
]
ANSWER = [
    (7, 0.5), (5, 0.5), (4, 0.5), (2, 0.5),
    (0, 1.0), (2, 0.5), (4, 0.5),
    (5, 1.0), (4, 0.5), (2, 0.5),
    (0, 2.0),
]
LIFT = [
    (0, 0.5), (2, 0.5), (4, 0.5), (5, 0.5),
    (7, 1.0), (9, 1.0),
    (7, 0.5), (5, 0.5), (4, 1.0),
    (5, 2.0),
]
JOURNEY = [
    (4, 0.5), (5, 0.5), (7, 1.0),
    (9, 0.5), (7, 0.5), (5, 1.0),
    (4, 0.5), (2, 0.5), (4, 1.0),
    (0, 2.0),
    (2, 0.5), (4, 0.5), (5, 0.5), (4, 0.5),
    (2, 0.5), (0, 0.5), (-1, 1.0),
    (0, 2.0), (None, 2.0),
]
CADENCE = [
    (4, 1.0), (5, 1.0), (4, 0.5), (2, 0.5),
    (0, 1.0), (4, 1.0),
    (2, 1.0), (0, 2.0),
]
WAVE = [
    (0, 1.0), (2, 0.5), (4, 0.5), (5, 1.0), (4, 0.5), (2, 0.5),
    (0, 1.0), (4, 1.0), (2, 1.0), (0, 1.0),
]
RIDGE = [
    (0, 2.0), (4, 2.0), (7, 2.0), (5, 2.0),
    (4, 2.0), (2, 2.0), (0, 4.0),
]
HERO = [
    (0, FANFARE), (0, ANSWER), (0, LIFT), (0, JOURNEY),
    (0, FANFARE), (0, ANSWER), (0, CADENCE),
]


def _span(seq):
    return sum(dur for _, dur in seq)


def _stretch(seq, factor):
    return [(deg, dur * factor) for deg, dur in seq]


# name, root midi, scale, bpm, harp, pulse, echo, chords, flute phrases (shift, seq)
# build: slow harp alone, then the beat enters and quickens.
SONGS = {
    "theme": dict(root=62, scale="major", bpm=104, harp="march", pulse=None, echo=False,
                  lead="horn", drone=0.0, build=True,
                  chords=[0, 5, 3, 4, 0, 3, 4, 0],
                  flute=HERO),
    "village": dict(root=62, scale="major", bpm=100, harp="march", pulse=None, echo=False,
                    lead="horn", drone=0.0, build=True,
                    chords=[0, 5, 3, 4, 0, 3, 4, 0],
                    flute=HERO),
    "city": dict(root=65, scale="major", bpm=108, harp="march", pulse=None, echo=False,
                 lead="horn", drone=0.0, build=True,
                 chords=[0, 5, 3, 4, 0, 3, 4, 0],
                 flute=[(0, FANFARE), (0, ANSWER), (0, LIFT), (0, CADENCE),
                        (0, FANFARE), (0, ANSWER), (0, LIFT), (0, CADENCE)]),
    "harbour": dict(root=60, scale="major", bpm=92, harp="lilt", pulse=None, echo=False,
                    lead="flute", drone=0.0, build=True,
                    chords=[0, 5, 3, 0],
                    flute=[(0, WAVE), (0, WAVE), (4, WAVE), (0, WAVE),
                           (0, WAVE), (2, WAVE), (0, ANSWER), (0, CADENCE)]),
    "forest": dict(root=58, scale="major", bpm=96, harp="march", pulse=None, echo=False,
                   lead="horn", drone=0.0, build=True,
                   chords=[0, 5, 3, 4, 0, 3, 4, 0],
                   flute=[(0, JOURNEY), (0, LIFT), (0, FANFARE),
                          (0, JOURNEY), (0, ANSWER), (0, CADENCE)]),
    "mountains": dict(root=57, scale="major", bpm=92, harp="march", pulse=None, echo=False,
                      lead="horn", drone=0.0, build=True,
                      chords=[0, 4, 3, 0],
                      flute=[(0, RIDGE), (0, RIDGE), (4, RIDGE), (0, RIDGE)]),
    "wilderness": dict(root=62, scale="major", bpm=104, harp="march", pulse=None, echo=False,
                       lead="horn", drone=0.0, build=True,
                       chords=[0, 5, 3, 4, 0, 3, 4, 0],
                       flute=[(0, FANFARE), (0, JOURNEY), (0, ANSWER), (0, LIFT),
                              (0, FANFARE), (0, ANSWER), (0, CADENCE)]),
    "mine": dict(root=50, scale="minor", bpm=104, harp="off", pulse="beat", echo=False,
                 chords=[0, 0, 3, 0],
                 flute=[(0, MINE)] * 16),
    "dungeon": dict(root=57, scale="minor", bpm=88, harp="half", pulse="half", echo=False,
                    chords=[0, 5, 3, 0],
                    flute=[(0, DELVE), (0, DELVE), (3, DELVE), (0, DELVE),
                           (5, DELVE), (3, DELVE), (0, DELVE), (0, DELVE)]),
    "depths": dict(root=48, scale="minor", bpm=72, harp="sparse", pulse="half", echo=False,
                   chords=[0, 3, 5, 0],
                   flute=[(0, _stretch(DELVE, 2)), (0, _stretch(DELVE, 2)),
                          (-2, _stretch(DELVE, 2)), (0, _stretch(DELVE, 2))]),
    "void": dict(root=64, scale="phrygian", bpm=66, harp="off", pulse=None, echo=False,
                 chords=[0, 0, 0, 0],
                 flute=[(0, VOID), (0, VOID), (4, VOID), (0, VOID)]),
    "emberdeep": dict(root=52, scale="phrygian", bpm=82, harp="sparse", pulse=None, echo=False,
                      chords=[0, 1, 0, 3],
                      flute=[(0, EMBER)] * 8),
    "wyrm": dict(root=52, scale="phrygian", bpm=120, harp="off", pulse="beat", echo=False,
                 chords=[0, 1, 0, 1],
                 flute=[(0, WYRM)] * 16),
    "castle": dict(root=58, scale="major", bpm=96, harp="march", pulse=None, echo=False,
                   lead="horn", drone=0.0, build=True,
                   chords=[0, 5, 3, 0],
                   flute=[(0, _stretch(FANFARE, 2)), (0, _stretch(ANSWER, 2)),
                          (0, _stretch(LIFT, 2)), (0, _stretch(CADENCE, 2))]),
}


def semi(scale, degree):
    step = SCALES[scale]
    octave, index = divmod(int(degree), len(step))
    return step[index] + 12 * octave


def hz_of(midi):
    return 440.0 * (2.0 ** ((midi - 69) / 12.0))


def locked(hz, seconds):
    cycles = max(1, round(hz * seconds))
    return cycles / seconds


def horn(hz, dur, vel, rng):
    """Trumpet section tone: tongued attack, bright partials, a slow vibrato."""
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    vib = np.sin(2 * math.pi * 5.2 * t) * (1 - np.exp(-t * 6)) * 0.007
    freq = hz * (1.0 + 0.018 * np.exp(-t * 45)) * (1.0 + vib)
    phase = 2 * math.pi * np.cumsum(freq) / SR
    y = np.zeros(n, dtype=np.float64)
    for partial, amp in ((1, 1.0), (2, 0.78), (3, 0.5), (4, 0.32), (5, 0.16), (6, 0.08)):
        y += amp * np.sin(partial * phase)
    y += rng.normal(0, 1.0, n) * np.exp(-t * 90) * 0.4
    attack = np.minimum(1.0, t / 0.018) ** 0.5
    release = np.clip((dur - t) / 0.055, 0, 1)
    return (y * attack * release * vel).astype(np.float32)


def strings(hz, dur, vel):
    """Bowed chord tone, the motor under an overworld march."""
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    phase = 2 * math.pi * hz * t
    y = np.zeros(n, dtype=np.float64)
    for partial in range(1, 7):
        y += (0.55 / partial) * np.sin(partial * phase)
    bow = 0.82 + 0.18 * np.sin(2 * math.pi * 5.5 * t)
    env = np.minimum(1.0, t / 0.05) * np.clip((dur - t) / 0.04, 0, 1)
    return (y * bow * env * vel).astype(np.float32)


def timpani(hz, dur, vel):
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    freq = hz * (1.0 + 0.55 * np.exp(-t * 22))
    phase = 2 * math.pi * np.cumsum(freq) / SR
    y = np.sin(phase) * np.exp(-t * 3.8)
    y += 0.35 * np.sin(1.5 * phase) * np.exp(-t * 7)
    y += np.random.uniform(-1, 1, n) * np.exp(-t * 28) * 0.25
    return (y * vel).astype(np.float32)


def bass(hz, dur, vel):
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    slide = hz * (1.0 - 0.06 * np.minimum(1.0, t / 0.04))
    phase = 2 * math.pi * np.cumsum(slide) / SR
    y = np.sin(phase) + 0.28 * np.sin(2 * phase)
    env = np.exp(-t * 5.5) * np.minimum(1.0, t / 0.02)
    return (y * env * vel).astype(np.float32)


def flute(hz, dur, vel, rng):
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    vib = np.sin(2 * math.pi * 5.1 * t) * (1 - np.exp(-t * 4)) * 0.012
    phase = 2 * math.pi * hz * t + vib
    y = np.sin(phase)
    y += 0.18 * np.sin(2 * phase)
    y += 0.04 * np.sin(3 * phase)
    breath = rng.normal(0, 0.015, n)
    y += breath * (0.3 + 0.7 * np.sin(phase) ** 2)
    attack = np.minimum(1.0, t / 0.07)
    release = np.clip((dur - t) / 0.09, 0, 1)
    return (y * attack * release * vel).astype(np.float32)


def harp(hz, dur, vel):
    period = max(2, int(SR / hz))
    n = max(period, int(dur * SR))
    buf = np.random.uniform(-1, 1, period).astype(np.float32)
    y = np.empty(n, dtype=np.float32)
    idx = 0
    damp = 0.994
    for i in range(n):
        y[i] = buf[idx]
        nxt = (idx + 1) % period
        buf[idx] = damp * 0.5 * (buf[idx] + buf[nxt])
        idx = nxt
    t = np.arange(n) / SR
    y *= np.exp(-t * 2.4) * vel
    return y


def drone(hz, n, vel):
    seconds = n / SR
    t = np.arange(n) / SR
    base = locked(hz, seconds)
    fifth = locked(base * 1.5, seconds)
    wobble = 0.82 + 0.18 * np.sin(2 * math.pi * locked(0.1, seconds) * t)
    y = np.sin(2 * math.pi * base * t)
    y += 0.55 * np.sin(2 * math.pi * fifth * t)
    y += 0.12 * np.sin(2 * math.pi * locked(base * 2, seconds) * t)
    return (y * wobble * vel).astype(np.float32)


def thud(dur, vel):
    n = max(1, int(dur * SR))
    t = np.arange(n) / SR
    y = np.sin(2 * math.pi * 70 * t) * np.exp(-t * 10)
    y += 0.25 * np.sin(2 * math.pi * 140 * t) * np.exp(-t * 16)
    return (y * vel).astype(np.float32)


def lowpass(x, fc=4200):
    coeff = math.exp(-2 * math.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    keep = 1 - coeff
    for i in range(len(x)):
        acc = coeff * acc + keep * float(x[i])
        y[i] = acc
    return y


def mix_build(name, spec, rng):
    """Harp alone, then the beat arrives and quickens under the tune."""
    scale = spec["scale"]
    root = spec["root"]
    intro_beats = 16.0
    total_beats = 64.0
    intro_spb = 60.0 / 62.0
    end_spb = 60.0 / spec["bpm"]
    start_spb = 60.0 / max(70.0, spec["bpm"] - 26.0)
    accel = 32.0

    def body_sec(beat):
        beat = max(0.0, float(beat))
        if beat < accel:
            slope = (end_spb - start_spb) / accel
            return start_spb * beat + 0.5 * slope * beat * beat
        done = start_spb * accel + 0.5 * (end_spb - start_spb) * accel
        return done + (beat - accel) * end_spb

    intro_sec = intro_beats * intro_spb
    seconds = intro_sec + body_sec(total_beats) + 0.5
    buf = np.zeros(int(seconds * SR) + 8, dtype=np.float32)

    def add(sec, samples):
        i = int(max(0.0, sec) * SR)
        j = min(len(buf), i + len(samples))
        if i >= len(buf) or j <= i:
            return
        buf[i:j] += samples[: j - i]

    roll = [0, 2, 4, 7, 4, 2, 0, 4, 5, 7, 9, 7, 5, 4, 2, 0]
    for index, deg in enumerate(roll):
        midi = root + semi(scale, deg) - 12
        add(index * intro_spb, harp(hz_of(midi), intro_spb * 1.8, 0.7))
        if index % 4 == 0:
            low = root + semi(scale, 0 if index < 8 else 5) - 24
            add(index * intro_spb, harp(hz_of(low), intro_spb * 3.4, 0.4))

    lead = spec.get("lead", "flute")
    lead_vel = 0.6 if lead == "horn" else 0.52
    beat = 0.0
    for shift, seq in spec["flute"]:
        for deg, dur in seq:
            if beat >= total_beats:
                break
            use = min(dur, total_beats - beat)
            if deg is not None and use > 0.05:
                sec = intro_sec + body_sec(beat)
                dur_sec = max(0.08, body_sec(beat + use) - body_sec(beat))
                vel = lead_vel * (0.7 if beat < 16 else 1.0)
                midi = root + semi(scale, deg + shift)
                if lead == "horn":
                    add(sec, horn(hz_of(midi), dur_sec * 0.96, vel, rng))
                    if beat >= 28:
                        harm = root + semi(scale, deg + shift - 2)
                        add(sec, horn(hz_of(harm), dur_sec * 0.96, vel * 0.36, rng))
                else:
                    add(sec, flute(hz_of(midi), dur_sec * 0.96, vel, rng))
            beat += dur
        if beat >= total_beats - 0.01:
            break

    chords = spec["chords"]
    chord_len = total_beats / len(chords)
    cursor = 0.0
    while cursor < total_beats - 0.05:
        chord = chords[min(len(chords) - 1, int(cursor / chord_len))]
        sec = intro_sec + body_sec(cursor)
        beat_sec = max(0.15, body_sec(cursor + 1.0) - body_sec(cursor))
        low = root + semi(scale, chord) - 24
        if cursor < 16:
            for tone in (0, 2, 4):
                midi = root + semi(scale, chord + tone) - 12
                add(sec, harp(hz_of(midi), beat_sec * 3.2, 0.28))
            cursor += 4.0
        elif cursor < 32:
            add(sec, bass(hz_of(low), beat_sec * 1.4, 0.32))
            add(sec, timpani(hz_of(low), beat_sec * 1.6, 0.22))
            for tone in (0, 2, 4):
                midi = root + semi(scale, chord + tone)
                add(sec, harp(hz_of(midi), beat_sec * 1.5, 0.2))
            cursor += 2.0
        else:
            add(sec, bass(hz_of(low), beat_sec * 0.85, 0.46))
            if int(round(cursor)) % 2 == 0:
                add(sec, timpani(hz_of(low), beat_sec * 1.3, 0.4))
            for tone in (0, 2, 4):
                midi = root + semi(scale, chord + tone) - 12
                add(sec, strings(hz_of(midi), beat_sec * 0.9, 0.11))
            cursor += 1.0

    buf = lowpass(buf, 6400)
    peak = float(np.max(np.abs(buf))) or 1.0
    buf *= 0.62 / peak
    fade = int(0.02 * SR)
    ramp = np.linspace(0, 1, fade, dtype=np.float32)
    buf[:fade] *= ramp
    buf[-fade:] *= ramp[::-1]
    return buf, seconds


def mix_song(name, spec):
    rng = np.random.default_rng(sum(ord(ch) for ch in name) * 997)
    if spec.get("build"):
        return mix_build(name, spec, rng)
    bpm = spec["bpm"]
    spb = 60.0 / bpm
    total_beats = 64.0
    seconds = total_beats * spb
    buf = np.zeros(int(round(seconds * SR)), dtype=np.float32)
    scale = spec["scale"]
    root = spec["root"]

    def at(beat):
        return int(beat * spb * SR)

    def add(beat, samples):
        i = at(beat)
        j = min(len(buf), i + len(samples))
        if i >= len(buf) or j <= i:
            return
        buf[i:j] += samples[: j - i]

    lead = spec.get("lead", "flute")
    lead_vel = 0.74 if lead == "horn" else 0.62
    events = []
    beat = 0.0
    for shift, seq in spec["flute"]:
        for deg, dur in seq:
            if beat >= total_beats:
                break
            use = min(dur, total_beats - beat)
            if deg is not None and use > 0.05:
                jitter = float(rng.uniform(-0.012, 0.012))
                events.append((max(0.0, beat + jitter), deg + shift, use * 0.96, lead, lead_vel))
                if lead == "horn":
                    events.append((max(0.0, beat + jitter), deg + shift - 2, use * 0.96, "horn", lead_vel * 0.48))
            beat += dur
        if beat >= total_beats - 0.01:
            break
    if spec["echo"]:
        echoed = []
        for start, deg, dur, kind, vel in events:
            landed = start + 4.0
            if landed >= total_beats:
                landed -= total_beats
            echoed.append((landed, deg - 7, dur, kind, vel * 0.28))
        events.extend(echoed)

    chord_len = total_beats / len(spec["chords"])
    for index, chord in enumerate(spec["chords"]):
        start = index * chord_len
        mode = spec["harp"]
        if mode == "off":
            continue
        if mode == "march":
            pos = start
            while pos < start + chord_len - 0.05:
                low = root + semi(scale, chord) - 24
                events.append((pos, None, 0.9, "timpani", 0.55, low))
                events.append((pos, None, 0.45, "bass", 0.5, low))
                fifth = root + semi(scale, chord + 4) - 24
                events.append((pos + 2.0, None, 0.55, "timpani", 0.28, fifth))
                events.append((pos + 2.0, None, 0.3, "bass", 0.28, fifth))
                for step in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5):
                    if pos + step >= start + chord_len - 0.02:
                        break
                    for tone in (0, 2, 4):
                        midi = root + semi(scale, chord + tone) - 12
                        events.append((pos + step, None, 0.42, "strings", 0.16, midi))
                pos += 4.0
            continue
        step = {"roll": 1.0, "half": 2.0, "sparse": 4.0, "lilt": 1.5, "fifth": 4.0}[mode]
        tones = (0, 4) if mode == "fifth" else (0, 2, 4)
        pos = start
        while pos < start + chord_len - 0.05:
            for n, tone in enumerate(tones):
                midi = root + semi(scale, chord + tone) - 12
                events.append((pos + n * 0.03, None, 0.9, "harp", 0.28, midi))
            pos += step

    if spec["pulse"] == "beat":
        pulse_at = np.arange(0, total_beats, 1.0)
    elif spec["pulse"] == "half":
        pulse_at = np.arange(0, total_beats, 2.0)
    else:
        pulse_at = []
    for pos in pulse_at:
        events.append((float(pos), None, 0.3, "thud", 0.34, 0))

    drone_vel = spec.get("drone", 0.16 if name == "void" else 0.11)
    if drone_vel:
        buf += drone(hz_of(root - 12), len(buf), drone_vel)

    for event in events:
        start, deg, dur, kind, vel = event[:5]
        if kind == "horn":
            midi = root + semi(scale, deg)
            samples = horn(hz_of(midi), dur * spb, vel, rng)
        elif kind == "flute":
            midi = root + semi(scale, deg)
            samples = flute(hz_of(midi), dur * spb, vel, rng)
        elif kind == "harp":
            samples = harp(hz_of(event[5]), dur * spb, vel)
        elif kind == "bass":
            samples = bass(hz_of(event[5]), dur * spb, vel)
        elif kind == "strings":
            samples = strings(hz_of(event[5]), dur * spb, vel)
        elif kind == "timpani":
            samples = timpani(hz_of(event[5]), dur * spb, vel)
        else:
            samples = thud(dur * spb, vel)
        add(start, samples)

    buf = lowpass(buf, 7600 if spec.get("bright") else 4200)
    peak = float(np.max(np.abs(buf))) or 1.0
    buf *= 0.62 / peak
    fade = int(0.012 * SR)
    ramp = np.linspace(0, 1, fade, dtype=np.float32)
    buf[:fade] *= ramp
    buf[-fade:] *= ramp[::-1]
    return buf, seconds


def write_wav(path, samples):
    pcm = np.clip(samples, -1, 1)
    pcm = (pcm * 32767).astype(np.int16)
    with wave.open(path, "w") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(SR)
        handle.writeframes(pcm.tobytes())


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, spec in SONGS.items():
        audio, seconds = mix_song(name, spec)
        path = os.path.join(OUT, name + ".wav")
        write_wav(path, audio)
        print(f"{name:12} {seconds:5.1f}s  {os.path.getsize(path) // 1024:5}KB")
    for seq in (MOTIF_A, MOTIF_B, HARBOUR, WILD, MOUNTAIN, MINE, DELVE, VOID, EMBER, WYRM,
                FANFARE, ANSWER, LIFT, JOURNEY, CADENCE, WAVE, RIDGE):
        assert abs(_span(seq) % 4) < 0.01, _span(seq)


if __name__ == "__main__":
    main()
