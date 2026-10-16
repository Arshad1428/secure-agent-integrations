"""Minimal in-process stand-in for Ollama's /api/chat endpoint.

It lets tests drive the agent loop deterministically. It checks
the plumbing (tool filtering, gateway enforcement, error mapping),
not the quality of a real model.
"""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def tool_call(name, arguments):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {"function": {"name": name, "arguments": arguments}}
        ],
    }


def answer(text):
    return {"role": "assistant", "content": text}


class FakeOllama:
    def __init__(self):
        self.behavior = lambda messages, tools: answer("ok")
        self.delay = 0.0
        self.seen = []  # one entry per /api/chat round

        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                length = int(self.headers["Content-Length"])
                body = json.loads(self.rfile.read(length))

                tools = [
                    t["function"]["name"]
                    for t in body.get("tools", [])
                ]

                outer.seen.append(tools)

                if outer.delay:
                    time.sleep(outer.delay)

                message = outer.behavior(body["messages"], tools)
                data = json.dumps({"message": message}).encode()

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True
        )

    @property
    def url(self):
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self):
        self._thread.start()

    def stop(self):
        self._server.shutdown()
        self._server.server_close()
