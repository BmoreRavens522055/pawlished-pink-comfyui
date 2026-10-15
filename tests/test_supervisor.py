"""Full supervisor with real CPU ComfyUI/Jupyter, opt-in source path; never inference."""

import json, os, signal, socket, subprocess, sys, tempfile, time, unittest
from pathlib import Path
from test_jupyter import port

CODE = Path(__file__).resolve().parents[1]


@unittest.skipUnless(
    os.environ.get("PP_TEST_COMFY_DIR"), "requires pinned CPU ComfyUI installation"
)
class SupervisorIntegration(unittest.TestCase):
    def start(self, mode):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.log = (self.root / "supervisor.log").open("w")
        env = dict(
            os.environ,
            PP_WORKSPACE=str(self.root),
            PP_COMFY_DIR=os.environ["PP_TEST_COMFY_DIR"],
            PP_COMFY_PY=os.environ["PP_TEST_COMFY_PY"],
            PP_JUPYTER_PY=sys.executable,
            PP_HF_PY=sys.executable,
            PP_JUPYTER_PORT=str(port()),
            PP_COMFY_PORT=str(port()),
            PP_MODE=mode,
            PP_CPU_SMOKE="1",
            PP_AUTO_DOWNLOAD_MODELS="0",
            PP_STORAGE_REVIEWED="1",
            JUPYTER_PASSWORD="synthetic-supervisor-token",
            JUPYTER_DATA_DIR=str(self.root / "jupyter-data"),
            IPYTHONDIR=str(self.root / "ipython"),
        )
        self.child_env = env
        self.proc = subprocess.Popen(
            [sys.executable, str(CODE / "pp_runtime.py")],
            env=env,
            stdout=self.log,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                self.state = json.loads(
                    (self.root / "PP_RunPod_Setup/startup_state.json").read_text()
                )
                if self.state["phase"] == "ACTION_REQUIRED":
                    return
                if self.state["phase"] == "FAILED":
                    self.fail(self.state)
            except (OSError, ValueError):
                pass
            if self.proc.poll() is not None:
                self.fail("supervisor exited")
            time.sleep(0.2)
        self.fail("supervisor timeout")

    def tearDown(self):
        if hasattr(self, "proc"):
            if self.proc.poll() is None:
                self.proc.terminate()
            self.proc.wait(timeout=20)
            self.log.close()
            # All generated logs must redact the configured credential.
            for p in (self.root / "PP_RunPod_Setup").glob("*.log"):
                self.assertNotIn("synthetic-supervisor-token", p.read_text())
            self.tmp.cleanup()

    def test_profiles_start_before_missing_models_then_term(self):
        # One full boot per profile verifies service availability independently of downloads.
        for mode in ("image", "video", "both"):
            with self.subTest(mode=mode):
                self.start(mode)
                self.assertEqual(
                    self.state["services"],
                    {"jupyter": "LOCAL_API_READY", "comfyui": "LOCAL_API_READY"},
                )
                self.proc.terminate()
                self.assertEqual(self.proc.wait(timeout=20), 0)
                s = json.loads(
                    (self.root / "PP_RunPod_Setup/startup_state.json").read_text()
                )
                self.assertEqual(s["phase"], "STOPPED")
                self.tearDown()
                del self.proc

    def test_detached_init_upload_and_retrieval(self):
        import zipfile

        self.start("both")
        with zipfile.ZipFile(self.root / "uploads/PPS-TEST.zip", "w") as z:
            z.writestr("PPS-TEST/Pics/approved.txt", "approved")
        # Capture actual service ports from the environment retained for this test.
        p = subprocess.run(
            [sys.executable, str(CODE / "ppctl.py"), "init"],
            env=self.child_env,
            capture_output=True,
            text=True,
            timeout=5,
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                op = json.loads(
                    (self.root / "PP_RunPod_Setup/operation.json").read_text()
                )
                if op["phase"] in ("COMPLETE", "FAILED"):
                    break
            except (ValueError, OSError):
                pass
            time.sleep(0.1)
        self.assertEqual(op["phase"], "COMPLETE", op)
        self.assertEqual(
            (self.root / "ComfyUI/input/PPS-TEST/Pics/approved.txt").read_text(),
            "approved",
        )
        archives = list((self.root / "retrieval").glob("*.zip"))
        self.assertTrue(archives)
        with zipfile.ZipFile(archives[0]) as z:
            self.assertIsNone(z.testzip())

    def test_unexpected_comfy_exit_detected(self):
        self.start("both")
        victim = self.state["pids"]["comfyui"]
        self.assertIsNotNone(victim)
        os.kill(victim, signal.SIGKILL)
        self.assertEqual(self.proc.wait(timeout=20), 1)
        s = json.loads((self.root / "PP_RunPod_Setup/startup_state.json").read_text())
        self.assertEqual(s["phase"], "FAILED")
        self.assertIn("comfyui", s["error"])
