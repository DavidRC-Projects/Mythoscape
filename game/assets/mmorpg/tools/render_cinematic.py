"""Export an arena finisher cinematic exactly as the client draws it.
  python tools/render_cinematic.py BOSS KIND OUT_DIR [W H FPS]
Writes OUT_DIR/frames/%04d.png, contact.png, and (if ffmpeg is on PATH) BOSS_KIND.mp4 with sfx."""
import os
import subprocess
import sys
import wave

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "client"))
import pygame  # noqa: E402

pygame.init()
import arena_cinematic as C  # noqa: E402

boss, kind, out = sys.argv[1], sys.argv[2], sys.argv[3]
W, H, FPS = (int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])) if len(sys.argv) > 6 else (1280, 720, 24)
pygame.display.set_mode((W, H))
os.makedirs(os.path.join(out, "frames"), exist_ok=True)
sc = C.SCRIPTS[(boss, kind)]
surf = pygame.Surface((W, H))
n = int(sc["length"] * FPS / 1000)
for i in range(n):
    C.render(surf, boss, kind, i * 1000.0 / FPS)
    pygame.image.save(surf, os.path.join(out, "frames", f"{i:04d}.png"))
# mix sfx track
try:
    import numpy as np
    SR = 22050
    mix = np.zeros(int(SR * sc["length"] / 1000) + SR * 5)
    for at, name in sc["sfx"]:
        with wave.open(os.path.join(C.CIN_DIR, "sfx", name + ".wav")) as w:
            x = np.frombuffer(w.readframes(w.getnframes()), "<i2").astype(float) / 32767
        s0 = int(SR * at / 1000)
        mix[s0:s0 + len(x)] += x * (0.6 if name == "crowd_roar" else 0.8)
    mix = mix[: int(SR * sc["length"] / 1000)]
    mix = np.clip(mix / max(1.0, abs(mix).max() / 0.9), -1, 1)
    wav = os.path.join(out, "sfx.wav")
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((mix * 32767).astype("<i2").tobytes())
    mp4 = os.path.join(out, f"{boss}_{kind}_finisher.mp4")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", os.path.join(out, "frames", "%04d.png"),
                    "-i", wav, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-c:a", "aac", "-shortest", mp4],
                   check=True)
    print("mp4", mp4)
except Exception as e:  # noqa: BLE001
    print("no mp4:", e)
print("frames", n)
