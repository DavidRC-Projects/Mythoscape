"""Crownfall calendar: shared day/season/weather for the realm.

Pacing (real time):
  1 game day  = 2 hours
  1 game week = 8 hours (4 days)
  1 season    = 1 week
  1 year      = 4 seasons
"""
from __future__ import annotations

import json
import os
import random
import time

DAY_SECONDS = 2 * 3600
DAYS_PER_WEEK = 4
WEEK_SECONDS = DAYS_PER_WEEK * DAY_SECONDS  # 8h
SEASON_SECONDS = WEEK_SECONDS
YEAR_SECONDS = 4 * SEASON_SECONDS
PHASE_SECONDS = DAY_SECONDS // 4  # ~30 min each

START_YEAR = 412

SEASONS = ("spring", "summer", "autumn", "winter")
MONTHS = {
    "spring": "Budmoon",
    "summer": "Highsun",
    "autumn": "Emberfall",
    "winter": "Frostmere",
}
WEEKDAYS = ("Sunwake", "Moonday", "Emberday", "Starday")
PHASES = ("dawn", "day", "dusk", "night")
PHASE_LABELS = {
    "dawn": "Dawn",
    "day": "Midday",
    "dusk": "Dusk",
    "night": "Night",
}
WEATHER_LABELS = {
    "clear": "Clear",
    "light_rain": "Light rain",
    "rain": "Rain",
    "windy_clear": "Windy",
    "light_snow": "Light snow",
    "snow": "Snow",
}
WEATHER_BY_SEASON = {
    "spring": (("clear", 50), ("light_rain", 30), ("rain", 20)),
    "summer": (("clear", 70), ("light_rain", 30)),
    "autumn": (("clear", 40), ("rain", 35), ("windy_clear", 25)),
    "winter": (("clear", 35), ("light_snow", 35), ("snow", 30)),
}
WEATHER_INTENSITY = {
    "clear": 0.0,
    "windy_clear": 0.25,
    "light_rain": 0.45,
    "rain": 0.85,
    "light_snow": 0.45,
    "snow": 0.9,
}

_PATH = os.path.join(os.path.dirname(__file__), "world_clock.json")
_STATE = None
_OVERRIDE = None  # dict season/weather/phase or None
_LAST_SIG = None


def _load():
    global _STATE
    if _STATE is not None:
        return _STATE
    # Fresh realms start "now" so Year 412 begins at first boot.
    state = {
        "epoch": time.time(),
        "weather": "clear",
        "weather_until": 0.0,
        "rng_salt": 1,
    }
    if os.path.isfile(_PATH):
        try:
            with open(_PATH, encoding="utf-8") as handle:
                saved = json.load(handle)
            if isinstance(saved, dict):
                state.update(saved)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    else:
        _STATE = state
        _save()
    _STATE = state
    return _STATE


def _save():
    state = _load()
    try:
        with open(_PATH, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=1)
    except OSError:
        pass


def _roll_weather(season, now, salt):
    table = WEATHER_BY_SEASON.get(season) or WEATHER_BY_SEASON["summer"]
    total = sum(w for _, w in table)
    rng = random.Random(int(now) ^ int(salt) ^ (hash(season) & 0xFFFFFFFF))
    pick = rng.uniform(0, total)
    acc = 0.0
    weather = table[0][0]
    for name, weight in table:
        acc += weight
        if pick <= acc:
            weather = name
            break
    hold = rng.uniform(15 * 60, 25 * 60)
    return weather, now + hold


def _ensure_weather(season, now):
    state = _load()
    if float(state.get("weather_until") or 0) > now and state.get("weather"):
        return
    weather, until = _roll_weather(season, now, state.get("rng_salt", 1))
    state["weather"] = weather
    state["weather_until"] = until
    state["rng_salt"] = int(state.get("rng_salt", 1)) + 1
    _save()


def game_elapsed(now=None):
    now = time.time() if now is None else float(now)
    return max(0.0, now - float(_load().get("epoch") or EPOCH_DEFAULT))


def _calendar(elapsed):
    year_i = int(elapsed // YEAR_SECONDS)
    year_rem = elapsed - year_i * YEAR_SECONDS
    season_i = int(year_rem // SEASON_SECONDS) % 4
    season = SEASONS[season_i]
    season_rem = year_rem - season_i * SEASON_SECONDS
    day_in_season = int(season_rem // DAY_SECONDS)  # 0..3 within the week
    day_rem = season_rem - day_in_season * DAY_SECONDS
    phase_i = min(3, int(day_rem // PHASE_SECONDS))
    phase = PHASES[phase_i]
    # One month per season; day_of_month 1..4
    day_of_month = day_in_season + 1
    weekday = WEEKDAYS[day_in_season % DAYS_PER_WEEK]
    return {
        "year": START_YEAR + year_i,
        "month": MONTHS[season],
        "day_of_month": day_of_month,
        "weekday": weekday,
        "season": season,
        "phase": phase,
        "day_progress": day_rem / DAY_SECONDS,
        "phase_progress": (day_rem % PHASE_SECONDS) / PHASE_SECONDS,
    }


def snapshot(now=None):
    """Public env payload for WORLD_STATE / ENV_UPDATE."""
    now = time.time() if now is None else float(now)
    cal = _calendar(game_elapsed(now))
    if _OVERRIDE:
        if _OVERRIDE.get("season"):
            cal["season"] = _OVERRIDE["season"]
            cal["month"] = MONTHS.get(cal["season"], cal["month"])
        if _OVERRIDE.get("phase"):
            cal["phase"] = _OVERRIDE["phase"]
        if _OVERRIDE.get("weather"):
            weather = _OVERRIDE["weather"]
        else:
            _ensure_weather(cal["season"], now)
            weather = _load().get("weather") or "clear"
    else:
        _ensure_weather(cal["season"], now)
        weather = _load().get("weather") or "clear"
    intensity = WEATHER_INTENSITY.get(weather, 0.0)
    season_label = cal["season"].title()
    phase_label = PHASE_LABELS.get(cal["phase"], cal["phase"].title())
    weather_label = WEATHER_LABELS.get(weather, weather.replace("_", " ").title())
    date_label = f"{cal['month']} {cal['day_of_month']}, Year {cal['year']} of Crownfall"
    return {
        "year": cal["year"],
        "month": cal["month"],
        "day_of_month": cal["day_of_month"],
        "weekday": cal["weekday"],
        "season": cal["season"],
        "phase": cal["phase"],
        "weather": weather,
        "intensity": intensity,
        "day_progress": round(cal["day_progress"], 4),
        "label": {
            "phase": phase_label,
            "season": season_label,
            "weather": weather_label,
            "date": date_label,
            "line": f"{phase_label} · {season_label} · {weather_label}",
        },
    }


def signature(snap=None):
    snap = snap or snapshot()
    return (
        snap["year"],
        snap["month"],
        snap["day_of_month"],
        snap["season"],
        snap["phase"],
        snap["weather"],
    )


def poll_update(now=None):
    """Return snapshot if season/phase/weather changed since last poll, else None."""
    global _LAST_SIG
    snap = snapshot(now)
    sig = signature(snap)
    if sig == _LAST_SIG:
        return None
    _LAST_SIG = sig
    return snap


def force_env(season=None, weather=None, phase=None):
    """Dev override. Pass season/weather/phase; None fields keep computed values."""
    global _OVERRIDE, _LAST_SIG
    if season is None and weather is None and phase is None:
        _OVERRIDE = None
    else:
        ov = dict(_OVERRIDE or {})
        if season is not None:
            s = season.lower()
            if s not in SEASONS:
                raise ValueError(f"season must be one of {SEASONS}")
            ov["season"] = s
        if weather is not None:
            w = weather.lower()
            if w not in WEATHER_LABELS:
                raise ValueError(f"unknown weather {weather}")
            ov["weather"] = w
        if phase is not None:
            p = phase.lower()
            if p not in PHASES:
                raise ValueError(f"phase must be one of {PHASES}")
            ov["phase"] = p
        _OVERRIDE = ov
    _LAST_SIG = None
    return snapshot()


def clear_override():
    return force_env()


def advance(seconds):
    """Move the calendar forward by shifting the epoch backward."""
    state = _load()
    state["epoch"] = float(state.get("epoch") or time.time()) - float(seconds)
    # Force a weather re-roll soon after big jumps
    state["weather_until"] = 0.0
    _save()
    global _LAST_SIG
    _LAST_SIG = None
    return snapshot()


def advance_days(n=1):
    return advance(float(n) * DAY_SECONDS)
