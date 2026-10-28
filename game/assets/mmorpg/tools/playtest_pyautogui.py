#!/usr/bin/env python3
"""Smoke playtest Crownfall with PyAutoGUI (desktop window, not Playwright).

Prereqs:
  - Server on 127.0.0.1:8765
  - Client window titled Crownfall open
  - macOS: System Settings → Privacy & Security → Accessibility → allow Terminal/Cursor

Run:
  cd game/assets/mmorpg
  .venv/bin/python tools/playtest_pyautogui.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "")  # real display

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "screens", "playtest_pyautogui")
os.makedirs(OUT, exist_ok=True)

import pyautogui  # noqa: E402

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.08


def _log(msg: str) -> None:
    print(msg, flush=True)


def _crownfall_window() -> tuple[int, int, int, int, int] | None:
    """Return (pid, x, y, w, h) for the on-screen Crownfall window via Quartz."""
    try:
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGNullWindowID,
            kCGWindowListOptionOnScreenOnly,
        )
    except ImportError:
        _log("Quartz missing — install pyobjc-framework-Quartz")
        return None
    infos = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID) or []
    for info in infos:
        if info.get("kCGWindowName") != "Crownfall":
            continue
        b = info.get("kCGWindowBounds") or {}
        x, y = int(b.get("X", 0)), int(b.get("Y", 0))
        w, h = int(b.get("Width", 0)), int(b.get("Height", 0))
        pid = int(info.get("kCGWindowOwnerPID") or 0)
        if w > 100 and h > 100 and pid:
            return pid, x, y, w, h
    return None


def focus_crownfall() -> bool:
    """Bring Crownfall forward. Prefer AppKit by PID — System Events often misses Python.app."""
    win = _crownfall_window()
    if not win:
        _log("focus_crownfall: FAIL (no Crownfall window in Quartz)")
        return False
    pid = win[0]
    try:
        from AppKit import NSApplicationActivateIgnoringOtherApps, NSRunningApplication

        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
        if app is not None:
            app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
            _log(f"focus_crownfall: ok (AppKit pid={pid})")
            return True
    except Exception as exc:
        _log(f"focus_crownfall: AppKit failed ({exc}); trying osascript")
    script = f'''
    tell application "System Events"
      try
        set frontmost of (first process whose unix id is {pid}) to true
        return "ok"
      end try
    end tell
    return "missing"
    '''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    ok = "ok" in (r.stdout or "")
    _log(f"focus_crownfall: {'ok' if ok else 'FAIL'} pid={pid} {r.stdout.strip()} {r.stderr.strip()}")
    return ok


def window_bounds() -> tuple[int, int, int, int] | None:
    """Return (x, y, w, h) in Cocoa screen points for the Crownfall window."""
    win = _crownfall_window()
    if not win:
        return None
    _, x, y, w, h = win
    return x, y, w, h


def shot(tag: str) -> str:
    path = os.path.join(OUT, f"{int(time.time())}_{tag}.png")
    # Prefer window crop when we know bounds
    b = window_bounds()
    if b:
        x, y, w, h = b
        im = pyautogui.screenshot(region=(x, y, w, h))
    else:
        im = pyautogui.screenshot()
    im.save(path)
    _log(f"shot → {path}")
    return path


# macOS title-bar chrome inside the Quartz window bounds (content is 1200×800 logical).
_TITLE_BAR = 28


def click_win(wx: float, wy: float, bounds) -> None:
    """Click client-relative coords (0..1200, 0..800) mapped into the live window."""
    x, y, w, h = bounds
    content_h = max(h - _TITLE_BAR, 1)
    sx = x + wx * (w / 1200.0)
    sy = y + _TITLE_BAR + wy * (content_h / 800.0)
    pyautogui.click(sx, sy)


def type_slow(text: str) -> None:
    pyautogui.typewrite(text, interval=0.04)


def main() -> int:
    _log("=== Crownfall PyAutoGUI playtest ===")
    if not focus_crownfall():
        _log("Start the client first: cd client && ../.venv/bin/python client.py")
        return 1
    time.sleep(0.5)
    bounds = window_bounds()
    _log(f"window bounds: {bounds}")
    if not bounds:
        _log("Could not locate Crownfall window bounds")
        return 1
    shot("01_login")

    # Register a fresh account via keyboard (more reliable than mockup clicks).
    name = f"pg{int(time.time()) % 100000:05d}"
    password = "pw123456"
    _log(f"register {name}")
    pyautogui.press("f2")  # Create Account
    time.sleep(0.35)
    shot("02_register_tab")

    # Focus username (click field approx), then type
    click_win(600, 300, bounds)  # rough username slot on register layout
    time.sleep(0.15)
    pyautogui.hotkey("command", "a")
    type_slow(name)
    pyautogui.press("tab")
    type_slow(password)
    pyautogui.press("tab")
    type_slow(name.capitalize())
    # Prefer male villager (left gender button area on register)
    click_win(350, 520, bounds)
    time.sleep(0.2)
    shot("03_filled_register")
    pyautogui.press("enter")
    time.sleep(1.2)
    shot("04_after_submit")

    # Stat alloc: Balanced preset (client_screens.stat_alloc_layout) then Confirm
    click_win(408, 572, bounds)  # Balanced center
    time.sleep(0.3)
    click_win(600, 626, bounds)  # Confirm & Enter World
    time.sleep(0.8)
    shot("05_stat_or_comic")

    # Opening comic → Esc skips
    pyautogui.press("escape")
    time.sleep(0.6)
    shot("05b_after_comic")

    # Look creator (cosmetics_ui): Confirm look at Rect(976, 718, 150, 36)
    click_win(1051, 736, bounds)
    time.sleep(1.0)
    shot("05c_after_look")
    # If still on creator (missed click), try Skip then Confirm again
    click_win(911, 736, bounds)  # Skip
    time.sleep(0.4)
    click_win(1051, 736, bounds)
    time.sleep(0.8)
    shot("05d_world_or_look")

    # Walk a few steps and open help / quest hints
    for key in ("right", "right", "up", "up", "left"):
        pyautogui.press(key)
        time.sleep(0.2)
    shot("06_walked")
    pyautogui.press("h")
    time.sleep(0.5)
    shot("07_help")
    pyautogui.press("escape")
    time.sleep(0.3)
    pyautogui.press("q")
    time.sleep(0.4)
    shot("08_quests")
    pyautogui.press("escape")
    time.sleep(0.2)
    shot("09_final")

    _log(f"done — frames in {OUT}")
    _log(f"account (local): {name} / {password}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except pyautogui.FailSafeException:
        _log("FAILSAFE — mouse in corner; abort")
        raise SystemExit(2)
