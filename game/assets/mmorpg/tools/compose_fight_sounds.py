"""Write the short monster-fight sounds into assets/sounds."""
from __future__ import annotations

import math
import os
import wave

import numpy as np

SR = 22050
OUT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "assets", "sounds"))


def _t(n):
    return np.arange(n, dtype=np.float32) / SR


def _noise(n, rng):
    return rng.standard_normal(n).astype(np.float32)


def _exp(n, seconds):
    return np.exp(-_t(n) / max(0.001, seconds)).astype(np.float32)


def _tone(freq, n, decay):
    tt = _t(n)
    return (np.sin(2 * math.pi * freq * tt) * _exp(n, decay)).astype(np.float32)


def _whoosh(n, rng, darkness=0.4):
    raw = _noise(n, rng)
    acc = 0.0
    out = np.empty(n, dtype=np.float32)
    keep = darkness
    for i in range(n):
        acc = keep * acc + (1 - keep) * float(raw[i])
        out[i] = float(raw[i]) - acc
    env = np.sin(np.linspace(0, math.pi, n)).astype(np.float32)
    return out * env


def _norm(samples, peak=0.82):
    top = float(np.max(np.abs(samples))) or 1.0
    return (samples * (peak / top)).astype(np.float32)


def _pad(chunks):
    n = max(len(c) for c in chunks)
    mix = np.zeros(n, dtype=np.float32)
    for chunk in chunks:
        mix[: len(chunk)] += chunk
    return mix


def blade_hit(rng):
    n = int(0.16 * SR)
    body = _tone(150, n, 0.035) * 0.9
    crack = _whoosh(n, rng, 0.55) * _exp(n, 0.02) * 1.4
    return _norm(_pad([body, crack]))


def blade_miss(rng):
    n = int(0.18 * SR)
    return _norm(_whoosh(n, rng, 0.25) * 0.7, 0.55)


def arrow_loose(rng):
    n = int(0.12 * SR)
    pluck = _tone(640, n, 0.03) + 0.4 * _tone(980, n, 0.02)
    air = _whoosh(n, rng, 0.2) * 0.25
    return _norm(_pad([pluck, air]), 0.6)


def arrow_hit(rng):
    n = int(0.14 * SR)
    tick = _tone(420, int(0.04 * SR), 0.01)
    thud = _tone(110, n, 0.04)
    snap = _whoosh(int(0.05 * SR), rng, 0.6) * 0.8
    return _norm(_pad([tick, thud, snap]))


def spell_hit(rng):
    n = int(0.32 * SR)
    tt = _t(n)
    sweep = 680 * np.exp(-tt * 6)
    phase = 2 * math.pi * np.cumsum(sweep) / SR
    tone = np.sin(phase).astype(np.float32) * _exp(n, 0.12)
    shimmer = np.sin(phase * 1.5).astype(np.float32) * _exp(n, 0.08) * 0.45
    dust = _whoosh(n, rng, 0.35) * _exp(n, 0.06) * 0.35
    return _norm(_pad([tone, shimmer, dust]), 0.75)


def beast_hit(rng):
    n = int(0.28 * SR)
    tt = _t(n)
    growl = _noise(n, rng) * np.sin(2 * math.pi * 70 * tt) * _exp(n, 0.09)
    thud = _tone(80, n, 0.04) * 0.8
    return _norm(_pad([growl, thud]))


def beast_miss(rng):
    n = int(0.16 * SR)
    tt = _t(n)
    growl = _noise(n, rng) * np.sin(2 * math.pi * 90 * tt) * np.sin(np.linspace(0, math.pi, n))
    return _norm(growl.astype(np.float32), 0.5)


def humanoid_hit(rng):
    n = int(0.2 * SR)
    clang = (
        _tone(320, n, 0.05)
        + 0.55 * _tone(510, n, 0.04)
        + 0.25 * _tone(860, n, 0.03)
    )
    thud = _tone(120, n, 0.035) * 0.7
    grit = _whoosh(int(0.05 * SR), rng, 0.5) * 0.5
    return _norm(_pad([clang, thud, grit]))


def dragon_hit(rng):
    n = int(0.48 * SR)
    tt = _t(n)
    freq = 70 * np.exp(-tt * 2.2) + 40
    phase = 2 * math.pi * np.cumsum(freq) / SR
    roar = _noise(n, rng) * np.sin(phase) * _exp(n, 0.16)
    chest = np.sin(phase).astype(np.float32) * _exp(n, 0.1) * 0.45
    return _norm(_pad([roar, chest]), 0.88)


def dragon_miss(rng):
    n = int(0.26 * SR)
    tt = _t(n)
    roar = _noise(n, rng) * np.sin(2 * math.pi * 60 * tt) * np.sin(np.linspace(0, math.pi, n))
    return _norm(roar.astype(np.float32), 0.55)


CLIPS = {
    "blade_hit": blade_hit,
    "blade_miss": blade_miss,
    "arrow_loose": arrow_loose,
    "arrow_hit": arrow_hit,
    "spell_hit": spell_hit,
    "beast_hit": beast_hit,
    "beast_miss": beast_miss,
    "humanoid_hit": humanoid_hit,
    "dragon_hit": dragon_hit,
    "dragon_miss": dragon_miss,
}


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
    rng = np.random.default_rng(17)
    for name, build in CLIPS.items():
        audio = build(rng)
        path = os.path.join(OUT, name + ".wav")
        write_wav(path, audio)
        print(f"{name:14} {len(audio) / SR:4.2f}s")


if __name__ == "__main__":
    main()
