"""Synthesise assets/music/fairy_glade.wav: a seamless 48 s loop of a soft
pad, celesta arpeggios and twinkles (mono 22.05 kHz, like the other tracks)."""
import os, wave
import numpy as np
SR = 22050; BPM = 80; BEAT = 60 / BPM; BARS = 16; L = int(SR * BEAT * 4 * BARS)
t = np.arange(L) / SR
rng = np.random.default_rng(7)
def f(n): return 440 * 2 ** ((n - 69) / 12)
prog = [(62, 66, 69, 74), (59, 62, 66, 71), (55, 59, 62, 67), (57, 61, 64, 69)]  # D Bm G A
out = np.zeros(L)
bar = int(SR * BEAT * 4)
for b in range(BARS):
    ch = prog[b % 4]; s0 = b * bar
    # pad: detuned sines with slow swell, wrapped for seamless loop
    idx = (np.arange(int(bar * 1.5)) + s0) % L
    tt = np.arange(len(idx)) / SR
    env = np.sin(np.pi * np.arange(len(idx)) / len(idx)) ** 2
    for n in ch[:3]:
        for d in (-0.15, 0.15):
            np.add.at(out, idx, 0.035 * env * np.sin(2 * np.pi * f(n - 12 + d / 1) * tt))
    # celesta arpeggio, 8 notes per bar
    pat = [0, 1, 2, 3, 2, 1, 3, 2]
    for i, p in enumerate(pat):
        if b % 8 == 7 and i > 4: continue
        n = ch[p] + 12
        st = s0 + int(i * bar / 8); ln = int(SR * 1.4)
        idx = (np.arange(ln) + st) % L; tt = np.arange(ln) / SR
        e = np.exp(-tt * 3.2) * (1 - np.exp(-tt * 300))
        tone = np.sin(2 * np.pi * f(n) * tt) + 0.3 * np.sin(2 * np.pi * f(n) * 4 * tt) * np.exp(-tt * 6)
        np.add.at(out, idx, 0.11 * e * tone)
    # twinkles
    for _ in range(3):
        st = s0 + int(rng.random() * bar); n = rng.choice(ch) + 24
        ln = int(SR * 0.6); idx = (np.arange(ln) + st) % L; tt = np.arange(ln) / SR
        np.add.at(out, idx, 0.04 * np.exp(-tt * 7) * np.sin(2 * np.pi * f(n) * tt))
# simple feedback echo (circular, keeps the loop seamless)
d = int(SR * BEAT * 0.75); wet = np.zeros(L)
for k in range(1, 5): wet += (0.35 ** k) * np.roll(out, d * k)
out = out + wet
out = out / np.max(np.abs(out)) * 0.6
pcm = (out * 32767).astype("<i2")
path = os.path.join(os.path.dirname(__file__), "..", "assets", "music", "fairy_glade.wav")
with wave.open(path, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print(path, L / SR, "s")
