"""Simulated siege capacity on a disposable server.

This does not open the live world, the sandbox databases, or ports 8765 and 8789.
Sockets here are scripted clients, not the pygame client. Tick time is the
server loop. Action time is how long a scripted client waits for a reply.
"""
from __future__ import annotations

import asyncio
import json
import os
import platform
import socket
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "server"
PORT = 8794
STAGES = (1, 40, 60, 100)
FIGHT_SECONDS = 8
RAMS = 8

TMP = tempfile.mkdtemp(prefix="kcs_capacity_")
GAME_DB = os.path.join(TMP, "game.db")
KCS_DB = os.path.join(TMP, "siege.db")
CLOCK = os.path.join(TMP, "world_clock.json")
TICKS = os.path.join(TMP, "ticks.log")
SERVER_LOG = os.path.join(TMP, "server.log")
RUNNER = os.path.join(TMP, "run_server.py")


def fail(msg):
    raise SystemExit(msg)


def port_open(port):
    sock = socket.socket()
    sock.settimeout(0.2)
    try:
        return sock.connect_ex(("127.0.0.1", port)) == 0
    finally:
        sock.close()


def hardware():
    brand = ""
    try:
        brand = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"], text=True,
        ).strip()
    except Exception:
        brand = platform.processor()
    mem = ""
    try:
        mem = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
    except Exception:
        mem = ""
    return {
        "machine": platform.platform(),
        "cpu": brand,
        "cores": os.cpu_count(),
        "memory_bytes": mem,
        "python": platform.python_version(),
    }


def ram_spots(limit):
    sys.path.insert(0, str(SERVER))
    sys.path.insert(0, str(SERVER / "kcs_parity"))
    from kings_castle_siege_map.layout import build_battlefield
    from kings_castle_siege_map.placement import PlacedEngine, validate_placement
    bf = build_battlefield()
    found = []
    existing = []
    for y in range(160, 210):
        for x in range(90, 170):
            res = validate_placement(bf, "ram", x, y, 0, existing)
            if not res.ok:
                continue
            found.append((x, y))
            existing.append(PlacedEngine(str(len(found)), "ram", x, y, 0))
            if len(found) >= limit:
                return found
    return found


class Box:
    def __init__(self):
        self.count = 0
        self.nbytes = 0
        self.states = []
        self.snaps = 0
        self.openings = 0
        self.closed = False
        self.inbox = []
        self.pending = None
        self.action_ms = []
        self.errors = 0
        self.deployed = False
        self.placed = False


async def read_loop(ws, box):
    try:
        async for raw in ws:
            box.count += 1
            box.nbytes += len(raw) if isinstance(raw, (bytes, str)) else 0
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            kind = msg.get("type")
            now = time.perf_counter()
            if kind == "STATE_UPDATE":
                box.states.append(now)
            elif kind == "KCS_SNAPSHOT":
                box.snaps += 1
                box.deployed = True
            elif kind == "KCS_PLACE_OK":
                box.placed = True
            elif kind == "KCS_DELTA" and msg.get("kind") == "opening":
                box.openings += 1
            elif kind == "ERROR":
                box.errors += 1
            if box.pending is not None and kind in ("CHAT_MSG", "ERROR", "KCS_PLACE_OK"):
                box.action_ms.append((now - box.pending) * 1000)
                box.pending = None
            box.inbox.append(msg)
    except Exception:
        box.closed = True


async def send(ws, box, payload, timed=False):
    if timed:
        box.pending = time.perf_counter()
    await ws.send(json.dumps(payload))


async def one_client(index, side, spot, url, tag, ready, do_begin, began, deployed, fight, stop):
    import websockets
    name = f"{tag}{side[0]}{index:03d}"
    box = Box()
    try:
        async with websockets.connect(url, max_size=2 ** 22, open_timeout=15) as ws:
            reader = asyncio.create_task(read_loop(ws, box))
            await send(ws, box, {
                "type": "CREATE_CHARACTER",
                "username": name,
                "password": "password1",
                "char_name": name[:16],
                "gender": "male",
            })
            if not await wait_type(box, "LOGIN_OK", 20):
                raise RuntimeError(f"{name} login failed")
            await send(ws, box, {
                "type": "ALLOCATE_STATS",
                "stats": {"attack": 4, "strength": 3, "defence": 3, "archery": 0},
                "gender": "male",
            })
            await asyncio.sleep(0.05)
            await send(ws, box, {"type": "KCS_ENLIST", "side": side})
            ready.append(name)
            if index == 0 and side == "attack":
                await do_begin.wait()
                await send(ws, box, {"type": "KCS_BEGIN"})
                deadline = time.perf_counter() + 15
                while time.perf_counter() < deadline:
                    if any(
                        msg.get("type") in ("KCS_LOBBY", "KCS_STATUS")
                        and (msg.get("status") == "active" or msg.get("phase") == "active")
                        for msg in box.inbox
                    ):
                        break
                    await asyncio.sleep(0.05)
                began.set()
            else:
                await began.wait()
            await send(ws, box, {"type": "ENTER_DUNGEON", "dungeon_id": "kings_castle_siege"})
            deadline = time.perf_counter() + 20
            while not box.deployed and time.perf_counter() < deadline:
                await asyncio.sleep(0.05)
            if box.deployed:
                deployed.append(name)
            if spot is not None and box.deployed:
                await send(ws, box, {
                    "type": "KCS_PLACE",
                    "engine_type": "ram",
                    "x": spot[0], "y": spot[1], "rotation": 0,
                    "request_id": f"cap-{name}",
                }, timed=True)
                deadline = time.perf_counter() + 8
                while not box.placed and time.perf_counter() < deadline:
                    await asyncio.sleep(0.05)
            await fight.wait()
            end = time.perf_counter() + FIGHT_SECONDS
            while time.perf_counter() < end and not stop.is_set():
                if spot is not None and box.placed:
                    await send(ws, box, {"type": "KCS_ACT", "engine_type": "ram"}, timed=True)
                else:
                    await send(ws, box, {"type": "KCS_STRIKE"}, timed=True)
                await asyncio.sleep(0.5)
            await send(ws, box, {"type": "LOGOUT"})
            reader.cancel()
    except Exception as exc:
        box.closed = True
        box.errors += 1
        box.inbox.append({"type": "LOCAL", "message": str(exc)})
    return box


async def wait_type(box, kind, seconds):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        if any(msg.get("type") == kind for msg in box.inbox):
            return True
        if any(msg.get("type") == "LOGIN_FAIL" for msg in box.inbox):
            return False
        await asyncio.sleep(0.02)
    return False


def percentile(values, pct):
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100) * (len(ordered) - 1)))))
    return ordered[index]


def server_sample(pid):
    try:
        text = subprocess.check_output(["ps", "-o", "rss=,pcpu=", "-p", str(pid)], text=True).strip()
    except Exception:
        return {"rss_kb": None, "cpu": None}
    parts = text.split()
    if len(parts) < 2:
        return {"rss_kb": None, "cpu": None}
    return {"rss_kb": int(float(parts[0])), "cpu": float(parts[1])}


def tick_stats(path, start_size):
    try:
        lines = Path(path).read_text().splitlines()[start_size:]
    except Exception:
        lines = []
    values = []
    for line in lines:
        try:
            values.append(float(line) * 1000)
        except ValueError:
            continue
    if not values:
        return {"samples": 0}
    return {
        "samples": len(values),
        "median_ms": round(statistics.median(values), 1),
        "p95_ms": round(percentile(values, 95), 1),
        "max_ms": round(max(values), 1),
    }


async def stage(per_side, url, pid, spots, tag, tick_path):
    import websockets  # noqa: F401
    ready = []
    deployed = []
    do_begin = asyncio.Event()
    began = asyncio.Event()
    fight = asyncio.Event()
    stop = asyncio.Event()
    tasks = []
    for index in range(per_side):
        spot = spots[index] if index < len(spots) else None
        tasks.append(asyncio.create_task(
            one_client(index, "attack", spot, url, tag, ready, do_begin, began, deployed, fight, stop)
        ))
        tasks.append(asyncio.create_task(
            one_client(index, "defend", None, url, tag, ready, do_begin, began, deployed, fight, stop)
        ))
    expected = per_side * 2
    deadline = time.perf_counter() + max(40, per_side * 2)
    while len(ready) < expected and time.perf_counter() < deadline:
        await asyncio.sleep(0.1)
    enlisted = len(ready)
    rss_before = server_sample(pid)
    begun_at = time.perf_counter()
    do_begin.set()
    try:
        await asyncio.wait_for(began.wait(), min(20, 5 + per_side))
    except asyncio.TimeoutError:
        began.set()
    place_deadline = time.perf_counter() + min(30, 5 + per_side * 0.15)
    while len(deployed) < expected and time.perf_counter() < place_deadline:
        await asyncio.sleep(0.1)
    await asyncio.sleep(1.5)
    fight_at = time.perf_counter()
    tick_from = len(Path(tick_path).read_text().splitlines()) if Path(tick_path).exists() else 0
    fight.set()
    await asyncio.sleep(FIGHT_SECONDS + 1)
    stop.set()
    boxes = await asyncio.gather(*tasks)
    rss_after = server_sample(pid)
    ticks = tick_stats(tick_path, tick_from)
    actions = [ms for box in boxes for ms in box.action_ms]
    deployed = sum(1 for box in boxes if box.deployed)
    placed = sum(1 for box in boxes if box.placed)
    closed = sum(1 for box in boxes if box.closed)
    messages = sum(box.count for box in boxes)
    nbytes = sum(box.nbytes for box in boxes)
    snaps = sum(box.snaps for box in boxes)
    openings = sum(box.openings for box in boxes)
    gaps = []
    for box in boxes:
        for a, b in zip(box.states, box.states[1:]):
            gaps.append((b - a) * 1000)
    fight_s = time.perf_counter() - fight_at
    setup_s = fight_at - begun_at
    local_errors = [
        msg.get("message") for box in boxes for msg in box.inbox
        if msg.get("type") == "LOCAL"
    ]
    report = {
        "per_side": per_side,
        "participants": expected,
        "enlisted": enlisted,
        "deployed": deployed,
        "rams_placed": placed,
        "setup_s": round(setup_s, 1),
        "fight_s": round(fight_s, 1),
        "disconnects": closed,
        "messages": messages,
        "megabytes": round(nbytes / (1024 * 1024), 2),
        "messages_per_s": round(messages / fight_s, 1) if fight_s else None,
        "snapshots": snaps,
        "opening_deltas_seen": openings,
        "state_gap_median_ms": None if not gaps else round(statistics.median(gaps), 1),
        "action_ms_median": None if not actions else round(statistics.median(actions), 1),
        "action_ms_p95": None if not actions else round(percentile(actions, 95), 1),
        "action_samples": len(actions),
        "tick": ticks,
        "rss_before_kb": rss_before["rss_kb"],
        "rss_after_kb": rss_after["rss_kb"],
        "cpu_after": rss_after["cpu"],
        "local_errors": local_errors[:5],
    }
    healthy = (
        enlisted >= expected
        and deployed >= int(expected * 0.95)
        and closed <= max(1, int(expected * 0.02))
        and ticks.get("samples", 0) > 0
        and ticks.get("median_ms", 9999) <= 1000
        and (report["action_ms_p95"] is None or report["action_ms_p95"] <= 3000)
    )
    report["healthy"] = healthy
    return report


def start_server(stage_dir):
    if PORT in (8765, 8789):
        fail("refusing live or sandbox port")
    if port_open(PORT):
        fail(f"port {PORT} is already in use")
    game_db = os.path.join(stage_dir, "game.db")
    kcs_db = os.path.join(stage_dir, "siege.db")
    clock = os.path.join(stage_dir, "world_clock.json")
    ticks = os.path.join(stage_dir, "ticks.log")
    env = os.environ.copy()
    env.update({
        "PYTHONNOUSERSITE": "1",
        "CROWNFALL_DB_PATH": game_db,
        "KCS_DB_PATH": kcs_db,
        "KCS_SANDBOX_CLOCK": clock,
        "KCS_TICK_LOG": ticks,
        "USE_KINGS_CASTLE_SIEGE": "1",
        "KCS_COOLDOWN_SCALE": "0",
        "KCS_WAR_SECONDS": "3600",
        "CROWNFALL_HOST": "127.0.0.1",
        "CROWNFALL_PORT": str(PORT),
        "CROWNFALL_MAX_CONNECTIONS": "240",
        "CROWNFALL_MAX_PER_IP": "240",
        "CROWNFALL_REGISTER_PER_IP_HOUR": "500",
        "CROWNFALL_MSG_PER_SECOND": "40",
    })
    Path(RUNNER).write_text(
        "import os, runpy, sys\n"
        "from pathlib import Path\n"
        f"root = Path({str(SERVER)!r})\n"
        "sys.path.insert(0, str(root))\n"
        "os.chdir(root)\n"
        "import world_clock\n"
        f"world_clock._PATH = {clock!r}\n"
        "runpy.run_path(str(root / 'server.py'), run_name='__main__')\n",
        encoding="utf-8",
    )
    log = open(SERVER_LOG, "w")
    proc = subprocess.Popen([sys.executable, RUNNER], cwd=str(SERVER), env=env, stdout=log, stderr=subprocess.STDOUT)
    for _ in range(60):
        if port_open(PORT):
            return proc, ticks
        if proc.poll() is not None:
            fail("capacity server exited\n" + Path(SERVER_LOG).read_text()[-2000:])
        time.sleep(0.25)
    proc.terminate()
    fail("capacity server did not listen\n" + Path(SERVER_LOG).read_text()[-2000:])


def stop_server(proc):
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
    for _ in range(20):
        if not port_open(PORT):
            return
        time.sleep(0.25)


def main():
    if port_open(8765):
        print("note: live port 8765 is open and was not used", flush=True)
    if port_open(8789):
        print("note: sandbox port 8789 is open and was not used", flush=True)
    print("hardware", json.dumps(hardware()), flush=True)
    print("temp", TMP, flush=True)
    spots = ram_spots(RAMS)
    print("ram spots", len(spots), flush=True)
    url = f"ws://127.0.0.1:{PORT}"
    reports = []
    proc = None
    try:
        for per_side in STAGES:
            print(f"stage {per_side}+{per_side}", flush=True)
            stop_server(proc)
            stage_dir = os.path.join(TMP, f"stage{per_side}")
            os.makedirs(stage_dir, exist_ok=True)
            proc, ticks = start_server(stage_dir)
            report = asyncio.run(stage(per_side, url, proc.pid, spots, f"s{per_side}", ticks))
            reports.append(report)
            print("result", json.dumps(report), flush=True)
            if not report["healthy"] or proc.poll() is not None:
                print("stopped: this stage was not healthy", flush=True)
                break
    finally:
        stop_server(proc)
    print("SUMMARY", json.dumps(reports), flush=True)
    if not reports or not reports[-1]["healthy"] or reports[-1]["per_side"] < 100:
        if not reports or not all(row["healthy"] for row in reports):
            fail("capacity stopped before a healthy 100+100")
    print("capacity stages that ran were healthy", flush=True)


if __name__ == "__main__":
    main()
