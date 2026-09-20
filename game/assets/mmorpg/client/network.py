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
            self.incoming.put({"type": "_CONN_ERROR", "message": f"Could not reach server: {e}"})
        finally:
            self.connected = False
            self.incoming.put({"type": "_DISCONNECTED"})

    async def _sender(self, ws):
        loop = asyncio.get_event_loop()
        while True:
            msg = await loop.run_in_executor(None, self.outgoing.get)
            try:
                await ws.send(json.dumps(msg))
            except websockets.exceptions.ConnectionClosed:
                return
