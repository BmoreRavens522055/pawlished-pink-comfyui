"""Real JupyterLab subprocess, HTTP login/XSRF, contents and terminal APIs."""

import json, os, signal, socket, subprocess, sys, tempfile, time, unittest
from pathlib import Path
import requests

CODE = Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class JupyterIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.port = port()
        cls.url = f"http://127.0.0.1:{cls.port}"
        cls.token = "synthetic-test-only-r4"
        env = dict(
            os.environ,
            PP_WORKSPACE=cls.tmp.name,
            PP_JUPYTER_PORT=str(cls.port),
            JUPYTER_PASSWORD=cls.token,
            JUPYTER_RUNTIME_DIR=str(cls.root / "runtime"),
            JUPYTER_DATA_DIR=str(cls.root / "data"),
            IPYTHONDIR=str(cls.root / "ipython"),
        )
        cls.log = (cls.root / "server.log").open("w")
        cls.proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "jupyterlab",
                "--config",
                str(CODE / "jupyter_config.py"),
            ],
            env=env,
            stdout=cls.log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        cls.session = requests.Session()
        cls.session.trust_env = False
        for _ in range(100):
            try:
                if cls.session.get(cls.url + "/login", timeout=0.5).status_code == 200:
                    return
            except requests.RequestException:
                pass
            if cls.proc.poll() is not None:
                break
            time.sleep(0.1)
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        raise RuntimeError((cls.root / "server.log").read_text())

    @classmethod
    def tearDownClass(cls):
        os.killpg(cls.proc.pid, signal.SIGTERM)
        try:
            cls.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(cls.proc.pid, signal.SIGKILL)
            cls.proc.wait(timeout=5)
            raise AssertionError(
                "Jupyter shutdown exceeded 10 seconds:\n"
                + (cls.root / "server.log").read_text()
            )
        finally:
            cls.log.close()
            cls.tmp.cleanup()

    def test_unauthenticated_and_wrong_token_denied(self):
        for headers in [{}, {"Authorization": "token wrong"}]:
            self.session.cookies.clear()
            r = self.session.get(
                self.url + "/api/contents", headers=headers, allow_redirects=False
            )
            self.assertIn(r.status_code, (401, 403))

    def test_authenticated_upload_readback_terminal(self):
        h = {"Authorization": "token " + self.token}
        r = self.session.put(
            self.url + "/api/contents/approved.txt",
            headers=h,
            json={"type": "file", "format": "text", "content": "approved content"},
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual((self.root / "approved.txt").read_text(), "approved content")
        self.assertEqual(
            self.session.get(self.url + "/api/contents/approved.txt", headers=h).json()[
                "content"
            ],
            "approved content",
        )
        r = self.session.post(self.url + "/api/terminals", headers=h)
        self.assertEqual(r.status_code, 200)
        name = r.json()["name"]
        self.assertTrue(
            any(
                t["name"] == name
                for t in self.session.get(self.url + "/api/terminals", headers=h).json()
            )
        )
        self.assertEqual(
            self.session.delete(
                self.url + "/api/terminals/" + name, headers=h
            ).status_code,
            204,
        )

    def test_browser_form_login_and_origin_security(self):
        s = requests.Session()
        s.trust_env = False
        s.get(self.url + "/login")
        xsrf = s.cookies.get("_xsrf")
        r = s.post(
            self.url + "/login",
            data={"password": self.token, "_xsrf": xsrf},
            allow_redirects=False,
        )
        self.assertEqual(r.status_code, 302)
        self.assertEqual(s.get(self.url + "/api/contents").status_code, 200)
        bad = s.put(
            self.url + "/api/contents/evil.txt",
            headers={"Origin": "https://evil.example", "X-XSRFToken": xsrf},
            json={"type": "file", "format": "text", "content": "bad"},
        )
        self.assertIn(bad.status_code, (403, 404))
        self.assertFalse((self.root / "evil.txt").exists())

    def test_forwarded_host_login(self):
        s = requests.Session()
        s.trust_env = False
        headers = {
            "Host": "synthetic-8888.proxy.runpod.net",
            "X-Forwarded-Proto": "https",
        }
        s.get(self.url + "/login", headers=headers)
        xsrf = s.cookies.get("_xsrf")
        r = s.post(
            self.url + "/login",
            headers=headers,
            data={"password": self.token, "_xsrf": xsrf},
            allow_redirects=False,
        )
        self.assertEqual(r.status_code, 302)


if __name__ == "__main__":
    unittest.main()
