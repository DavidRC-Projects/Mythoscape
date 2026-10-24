"""Production hardening helpers: env config, rate limits, input coercion."""
from __future__ import annotations

import os
import re
import time
from collections import defaultdict

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
PASSWORD_MIN = 8
PASSWORD_MAX = 128

# Tunables (override via env where noted)
MAX_CONNECTIONS = int(os.environ.get("CROWNFALL_MAX_CONNECTIONS", "200"))
MAX_CONNECTIONS_PER_IP = int(os.environ.get("CROWNFALL_MAX_PER_IP", "10"))
LOGIN_FAIL_MAX = int(os.environ.get("CROWNFALL_LOGIN_FAIL_MAX", "8"))
LOGIN_LOCK_SECONDS = int(os.environ.get("CROWNFALL_LOGIN_LOCK_SECONDS", "60"))
MSG_PER_SECOND = int(os.environ.get("CROWNFALL_MSG_PER_SECOND", "40"))
REGISTER_PER_IP_HOUR = int(os.environ.get("CROWNFALL_REGISTER_PER_IP_HOUR", "10"))
WS_MAX_SIZE = int(os.environ.get("CROWNFALL_WS_MAX_SIZE", str(64 * 1024)))


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def crownfall_env() -> str:
    return (os.environ.get("CROWNFALL_ENV") or "development").strip().lower()


def is_production() -> bool:
    return crownfall_env() == "production"


def bind_host() -> str:
    override = os.environ.get("CROWNFALL_HOST")
    if override:
        return override.strip()
    return "127.0.0.1" if is_production() else "0.0.0.0"


def bind_port() -> int:
    return int(os.environ.get("CROWNFALL_PORT", "8765"))


def allow_register() -> bool:
    return env_flag("CROWNFALL_ALLOW_REGISTER", True)


def dev_mode_enabled() -> bool:
    return env_flag("CROWNFALL_DEV", False)


def dev_usernames() -> set[str]:
    raw = os.environ.get("CROWNFALL_DEV_USERS") or ""
    return {p.strip().lower() for p in raw.split(",") if p.strip()}


def is_dev_user(username: str) -> bool:
    if not dev_mode_enabled():
        return False
    allowed = dev_usernames()
    if not allowed:
        return False
    return (username or "").strip().lower() in allowed


def validate_username(username: str) -> str | None:
    """Return error message or None if ok."""
    if not USERNAME_RE.fullmatch(username or ""):
        return "Usernames need 3-20 letters, numbers, or underscores."
    return None


def validate_password(password: str) -> str | None:
    if not isinstance(password, str):
        return "Invalid password."
    if len(password) < PASSWORD_MIN:
        return f"Password must be at least {PASSWORD_MIN} characters."
    if len(password) > PASSWORD_MAX:
        return f"Password must be at most {PASSWORD_MAX} characters."
    return None


def safe_int(value, default=None, min_v=None, max_v=None):
    try:
        n = int(value)
    except (TypeError, ValueError):
        return default
    if min_v is not None and n < min_v:
        return default
    if max_v is not None and n > max_v:
        return default
    return n


def peer_ip(ws) -> str:
    try:
        addr = ws.remote_address
        if isinstance(addr, tuple) and addr:
            return str(addr[0])
        if addr:
            return str(addr)
    except Exception:
        pass
    return "unknown"


class AbuseGuard:
    """In-memory connection / auth / message rate limits."""

    def __init__(self):
        self.connections_global = 0
        self.connections_per_ip: dict[str, int] = defaultdict(int)
        self._login_fails: dict[str, list] = {}  # key -> [timestamps]
        self._locks_until: dict[str, float] = {}
        self._msg_windows: dict[int, list] = {}  # id(ws) -> [window_start, count]
        self._registers: dict[str, list] = {}  # ip -> [timestamps]

    def allow_connection(self, ip: str) -> bool:
        if self.connections_global >= MAX_CONNECTIONS:
            return False
        if self.connections_per_ip[ip] >= MAX_CONNECTIONS_PER_IP:
            return False
        self.connections_global += 1
        self.connections_per_ip[ip] += 1
        return True

    def release_connection(self, ip: str) -> None:
        self.connections_global = max(0, self.connections_global - 1)
        if ip in self.connections_per_ip:
            self.connections_per_ip[ip] = max(0, self.connections_per_ip[ip] - 1)
            if self.connections_per_ip[ip] == 0:
                del self.connections_per_ip[ip]

    def auth_locked(self, ip: str, username: str) -> bool:
        now = time.time()
        for key in (f"ip:{ip}", f"user:{(username or '').lower()}"):
            until = self._locks_until.get(key, 0)
            if until > now:
                return True
            if until and until <= now:
                self._locks_until.pop(key, None)
        return False

    def record_auth_failure(self, ip: str, username: str) -> None:
        now = time.time()
        for key in (f"ip:{ip}", f"user:{(username or '').lower()}"):
            stamps = [t for t in self._login_fails.get(key, []) if now - t < LOGIN_LOCK_SECONDS]
            stamps.append(now)
            self._login_fails[key] = stamps
            if len(stamps) >= LOGIN_FAIL_MAX:
                self._locks_until[key] = now + LOGIN_LOCK_SECONDS

    def clear_auth_failures(self, ip: str, username: str) -> None:
        for key in (f"ip:{ip}", f"user:{(username or '').lower()}"):
            self._login_fails.pop(key, None)
            self._locks_until.pop(key, None)

    def allow_register(self, ip: str) -> bool:
        now = time.time()
        stamps = [t for t in self._registers.get(ip, []) if now - t < 3600]
        if len(stamps) >= REGISTER_PER_IP_HOUR:
            self._registers[ip] = stamps
            return False
        stamps.append(now)
        self._registers[ip] = stamps
        return True

    def allow_message(self, ws) -> bool:
        wid = id(ws)
        now = time.time()
        window = self._msg_windows.get(wid)
        if not window or now - window[0] >= 1.0:
            self._msg_windows[wid] = [now, 1]
            return True
        window[1] += 1
        return window[1] <= MSG_PER_SECOND

    def clear_message_window(self, ws) -> None:
        self._msg_windows.pop(id(ws), None)


GUARD = AbuseGuard()
