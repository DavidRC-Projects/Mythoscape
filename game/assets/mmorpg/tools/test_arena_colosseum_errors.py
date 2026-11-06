"""Colosseum presentation failures must be visible, not swallowed (5 Nov review)."""
import io, os, sys, types, contextlib
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ["HOME"] = os.path.join(ROOT, "tools", ".tmp_home_colosseum")   # keep the log out of the real home
os.makedirs(os.environ["HOME"], exist_ok=True)
sys.path.insert(0, os.path.join(ROOT, "server")); sys.path.insert(0, os.path.join(ROOT, "client"))
os.chdir(os.path.join(ROOT, "client")); sys.argv = ["client.py"]
import client as _C  # noqa: F401  (sets up the client import paths)
import arena_colosseum as AC, castle_realm_renderer as CRR
FAIL = []
def ok(c, label):
    print(("ok   " if c else "FAIL ") + label)
    if not c: FAIL.append(label)
chat = []
client = types.SimpleNamespace(add_chat=lambda text, color=None: chat.append(text))
err = io.StringIO()
with contextlib.redirect_stderr(err):
    try:
        raise ValueError("boom layer")
    except ValueError as exc:
        CRR._colosseum_report(client, "world layers", exc)
        CRR._colosseum_report(client, "world layers", exc)      # repeat: counted, not re-spammed
ok("Traceback" in err.getvalue() and "boom layer" in err.getvalue(), "full traceback printed to stderr")
ok(len(chat) == 1 and "boom layer" in chat[0], "one in-game chat line names the failure")
ok(len(client._colosseum_errors) == 2, "every occurrence recorded on client._colosseum_errors")
log = os.path.join(os.environ["HOME"], ".crownfall_arena_errors.log")
ok(os.path.isfile(log) and "boom layer" in open(log).read(), "written to the arena error log")
# queue() failure path in the renderer goes through the reporter (no silent first-error-only print)
src = open(os.path.join(ROOT, "client", "castle_realm_renderer.py")).read()
ok('_colosseum_report(client, "world layers", exc)' in src and 'print("[arena_colosseum]", exc)' not in src,
   "renderer guard reports instead of printing once")
import shutil; shutil.rmtree(os.environ["HOME"], ignore_errors=True)
print("ALL PASS" if not FAIL else f"FAILED {FAIL}")
sys.exit(1 if FAIL else 0)
