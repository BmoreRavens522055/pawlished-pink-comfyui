"""Real local HTTP payload through pinned huggingface_hub.http_get; no HF weights."""

import http.server, json, tempfile, threading, unittest
from pathlib import Path
from huggingface_hub.file_download import http_get
from hf_worker import progress_class


class HTTPTransfer(unittest.TestCase):
    def test_actual_http_payload_and_resume(self):
        payload = bytes(range(256)) * 16384

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                offset = int(
                    self.headers.get("Range", "bytes=0-").split("=")[1].split("-")[0]
                )
                data = payload[offset:]
                self.send_response(206 if offset else 200)
                self.send_header("Content-Length", str(len(data)))
                if offset:
                    self.send_header(
                        "Content-Range",
                        f"bytes {offset}-{len(payload)-1}/{len(payload)}",
                    )
                self.end_headers()
                self.wfile.write(data)

        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / "payload"
                event = Path(tmp) / "progress.json"
                p.write_bytes(payload[: 1024 * 1024])
                with p.open("ab") as f:
                    http_get(
                        f"http://127.0.0.1:{server.server_port}/file",
                        f,
                        resume_size=1024 * 1024,
                        expected_size=len(payload),
                        tqdm_class=progress_class(event, "boot", "attempt"),
                    )
                self.assertEqual(p.read_bytes(), payload)
                self.assertEqual(json.loads(event.read_text())["bytes"], len(payload))
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
