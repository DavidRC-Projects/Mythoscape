"""
Runs the asyncio websocket connection on a background thread so the main
thread can run a normal blocking Pygame loop. Communication between the
two threads happens through plain thread-safe queues.
"""
import asyncio
import json
import queue
import threading

import websockets


class NetworkClient:
    def __init__(self, uri):
        self.uri = uri
        self.incoming = queue.Queue()
        self.outgoing = queue.Queue()
        self.connected = False
        self.connect_error = None
        self._loop = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def reconnect(self):
        """Open a fresh websocket after logout / disconnect (old thread exits)."""
        if self._thread.is_alive():
            self._thread.join()
        self.connected = False
        self.connect_error = None
        # Drain stale messages so a prior _DISCONNECTED doesn't clobber login.
        try:
            while True:
                self.incoming.get_nowait()
        except queue.Empty:
            pass
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def send(self, msg_type, **fields):
        self.outgoing.put({"type": msg_type, **fields})

    def poll(self):
        """Call once per frame from the main thread. Returns a list of received messages."""
        msgs = []
        while True:
            try:
                msgs.append(self.incoming.get_nowait())
            except queue.Empty:
                break
        return msgs

    def _run(self):
        try:
            asyncio.run(self._main())
        except Exception as e:  # noqa - surface any fatal networking error to the UI
            self.connect_error = str(e)
            self.incoming.put({"type": "_CONN_ERROR", "message": str(e)})

    async def _main(self):
        try:
            async with websockets.connect(self.uri, ping_interval=20, ping_timeout=20) as ws:
                self.connected = True
                sender = asyncio.create_task(self._sender(ws))
                try:
                    async for raw in ws:
                        try:
                            self.incoming.put(json.loads(raw))
                        except json.JSONDecodeError:
                            pass
                finally:
                    sender.cancel()
        except OSError as e:
            self.connect_error = str(e)
            # "[Errno 61] Connect call failed ('127.0.0.1', 8765)" is true but
            # tells a player nothing. Lead with the thing they can act on, and
            # keep the detail after it for troubleshooting.
            self.incoming.put({
                "type": "_CONN_ERROR",
                "message": ("Could not reach the server. Is it running? "
                            "Start it with `python3 server.py` in the server folder. "
                            f"({e})"),
            })
        finally:
            self.connected = False
            self.incoming.put({"type": "_DISCONNECTED"})

    async def _sender(self, ws):
        # Poll the queue instead of `run_in_executor(None, queue.get)`.
        #
        # queue.get() blocks forever until a message arrives, and the default
        # executor's threads are non-daemon. Python joins them at interpreter
        # shutdown, so the process could never exit while the socket was open
        # — the client appeared to freeze on quit, and every reconnect leaked
        # another never-ending thread.
        while True:
            try:
                msg = self.outgoing.get_nowait()
            except queue.Empty:
                await asyncio.sleep(0.016)      # ~one frame; imperceptible latency
                continue
            try:
                await ws.send(json.dumps(msg))
            except websockets.exceptions.ConnectionClosed:
                return
