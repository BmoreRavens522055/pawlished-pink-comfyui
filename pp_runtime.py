"""R4 service supervisor. Exits are visible; exiting never means provider billing stopped."""

import fcntl
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import uuid
import tempfile
import shutil
from pp_common import CODE, ROOT, SETUP, atomic, read, request


class Supervisor:
    def __init__(self):
        self.boot = uuid.uuid4().hex
        self.children = {}
        self.stop = False
        self.state = {
            "boot_id": self.boot,
            "phase": "PREFLIGHT",
            "services": {},
            "model_phase": "UNKNOWN",
            "storage": "OPERATOR_DECLARATION_REQUIRED",
            "next_action": "Wait for service checks",
        }

    def save(self):
        self.state["updated"] = time.time()
        atomic(SETUP / "startup_state.json", self.state)

    def preflight(self):
        if os.environ.get("JUPYTER_DISABLE_AUTH", "").lower() not in ("", "0", "false"):
            raise ValueError(
                "unauthenticated Jupyter configuration refused before service launch"
            )
        if not os.environ.get("JUPYTER_PASSWORD", "").strip():
            raise ValueError("enable RunPod Start Jupyter notebook: token missing")
        if os.environ.get("PP_MODE", "both") not in ("image", "video", "both"):
            raise ValueError("invalid PP_MODE")
        if os.environ.get("PP_AUTO_DOWNLOAD_MODELS", "1") not in ("0", "1"):
            raise ValueError("invalid auto-download setting")
        if os.environ.get("PP_STORAGE_REVIEWED") != "1":
            raise ValueError("template storage review required: PP_STORAGE_REVIEWED=1")
        if not ROOT.is_dir() or ROOT.is_symlink():
            raise ValueError("workspace missing or symlink")
        self.state["storage"] = "DECLARED_PERSISTENT_NOT_PROVIDER_VERIFIED"
        self.state["mountinfo"] = Path("/proc/self/mountinfo").read_text()
        for d in [
            "uploads",
            "retrieval",
            "ComfyUI/input",
            "ComfyUI/output",
            "ComfyUI/temp",
            "ComfyUI/user",
        ]:
            (ROOT / d).mkdir(parents=True, exist_ok=True)
        self.save()

    def launch(self, name, cmd, env=None, cwd=None):
        proc = subprocess.Popen(
            cmd,
            env=env,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            text=True,
            bufsize=1,
        )
        self.children[name] = proc
        self.state.setdefault("pids", {})[name] = proc.pid
        token = os.environ.get("JUPYTER_PASSWORD", "")

        def log():
            with (SETUP / (name + ".log")).open("a") as out:
                for line in proc.stdout:
                    if token:
                        line = line.replace(token, "[REDACTED]")
                    line = re.sub(r"(?i)(token[= :]+)[^\s&]+", r"\1[REDACTED]", line)
                    out.write(line)
                    out.flush()

        threading.Thread(target=log, daemon=True).start()
        return proc

    def jupyter_ready(self):
        port = int(os.environ.get("PP_JUPYTER_PORT", "8888"))
        token = os.environ["JUPYTER_PASSWORD"]
        try:
            request(port, "/api/contents")
        except urllib.error.HTTPError as e:
            if e.code not in (401, 403):
                raise
        else:
            raise RuntimeError("Jupyter accepts unauthenticated contents API")
        request(port, "/api/contents", token)
        request(port, "/api/terminals", token)

    def comfy_ready(self):
        port = int(os.environ.get("PP_COMFY_PORT", "8188"))
        request(port, "/system_stats")
        nodes = request(port, "/object_info", timeout=2)
        required = {"UNETLoader", "VAELoader", "VHS_VideoCombine"}
        mode = os.environ.get("PP_MODE", "both")
        if mode in ("image", "both"):
            required.add("TextEncodeQwenImage21")
        if mode in ("video", "both"):
            required.add("MiniMaxH3ImageToVideo")
        if required - set(nodes):
            raise RuntimeError(
                "selected node classes missing: " + str(sorted(required - set(nodes)))
            )
        atomic(SETUP / "object_info.json", nodes)

    def sync(self):
        env = os.environ.copy()
        env["PP_BOOT_ID"] = self.boot
        return self.launch(
            "models",
            [
                os.environ.get("PP_HF_PY", "/opt/pp-hf-venv/bin/python"),
                str(CODE / "model_sync.py"),
            ],
            env,
        )

    def run(self):
        SETUP.mkdir(parents=True, exist_ok=True)
        self.lock = (SETUP / "supervisor.lock").open("a")
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        self.signal_handlers = {}
        for sig in (signal.SIGTERM, signal.SIGINT):
            self.signal_handlers[sig] = signal.signal(
                sig, lambda *_: setattr(self, "stop", True)
            )
        try:
            self.save()
            self.preflight()
            self.jupyter_runtime = tempfile.mkdtemp(prefix="pp-jupyter-")
            jenv = dict(os.environ, JUPYTER_RUNTIME_DIR=self.jupyter_runtime)
            self.launch(
                "jupyter",
                [
                    os.environ.get("PP_JUPYTER_PY", "/opt/pp-jupyter/bin/python"),
                    "-m",
                    "jupyterlab",
                    "--config",
                    str(CODE / "jupyter_config.py"),
                ],
                env=jenv,
            )
            comfy = os.environ.get("PP_COMFY_DIR", "/opt/ComfyUI")
            cmd = [
                os.environ.get("PP_COMFY_PY", "/opt/pp-venv/bin/python"),
                "-u",
                str(Path(comfy) / "main.py"),
                "--listen",
                "0.0.0.0",
                "--port",
                os.environ.get("PP_COMFY_PORT", "8188"),
            ]
            for kind in ("input", "output", "temp", "user"):
                cmd += ["--" + kind + "-directory", str(ROOT / "ComfyUI" / kind)]
            if os.environ.get("PP_CPU_SMOKE") == "1":
                cmd += ["--cpu"]
            self.launch("comfyui", cmd, cwd=comfy)
            self.state["phase"] = "STARTING_SERVICES"
            self.save()
            deadline = time.monotonic() + int(
                os.environ.get("PP_SERVICE_TIMEOUT", "120")
            )
            ready = set()
            while len(ready) < 2:
                if self.stop:
                    raise InterruptedError("shutdown requested")
                if time.monotonic() >= deadline:
                    raise TimeoutError("service startup exceeded wall-clock budget")
                for name, probe in [
                    ("jupyter", self.jupyter_ready),
                    ("comfyui", self.comfy_ready),
                ]:
                    if self.children[name].poll() is not None:
                        raise RuntimeError(name + " exited during startup")
                    if name not in ready:
                        try:
                            probe()
                            ready.add(name)
                            self.state["services"][name] = "LOCAL_API_READY"
                        except Exception as e:
                            self.state["services"][name] = type(e).__name__
                self.save()
                time.sleep(0.5)
            self.sync()
            self.state["phase"] = "SERVICES_READY_MODELS_CHECKING"
            self.state["next_action"] = (
                "Monitor model sync; upload approved ZIP to uploads, then run init"
            )
            last_probe = 0
            while not self.stop:
                for name in ("jupyter", "comfyui"):
                    if self.children[name].poll() is not None:
                        raise RuntimeError(name + " unexpectedly exited")
                if time.monotonic() - last_probe > 10:
                    self.jupyter_ready()
                    request(
                        int(os.environ.get("PP_COMFY_PORT", "8188")), "/system_stats"
                    )
                    last_probe = time.monotonic()
                models = read(SETUP / "model_state.json")
                if models.get("boot_id") == self.boot:
                    self.state["model_phase"] = models.get("phase", "UNKNOWN")
                done = self.children["models"].poll()
                if done is not None:
                    good = (
                        done == 0
                        and models.get("boot_id") == self.boot
                        and models.get("phase") == "VERIFIED_BYTES_OPENABLE"
                    )
                    self.state["phase"] = (
                        "SERVICES_AND_MODELS_READY" if good else "ACTION_REQUIRED"
                    )
                    self.state["next_action"] = (
                        "Upload/stage approved episode; workflow and browser readiness still require checks"
                        if good
                        else "Save evidence; stop paid compute promptly if unresolved. Init permits one explicit retry. Billing continues."
                    )
                # Requests are correlated to this process; old boots cannot restart downloads.
                command = read(SETUP / "continue.json")
                if command.get("boot_id") == self.boot:
                    (SETUP / "continue.json").unlink(missing_ok=True)
                    if done is not None:
                        self.sync()
                self.save()
                time.sleep(1)
            raise InterruptedError("shutdown requested")
        except BaseException as e:
            self.state.update(
                phase="STOPPED" if isinstance(e, InterruptedError) else "FAILED",
                error=str(e),
                next_action="Retrieve evidence. Provider compute/storage billing is NOT stopped by this process.",
            )
            self.save()
            if not isinstance(e, InterruptedError):
                print(str(e), file=sys.stderr)
                return 1
            return 0
        finally:
            for proc in self.children.values():
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait()
            if hasattr(self, "jupyter_runtime"):
                shutil.rmtree(self.jupyter_runtime, ignore_errors=True)
            for sig, handler in self.signal_handlers.items():
                signal.signal(sig, handler)
            self.lock.close()


if __name__ == "__main__":
    sys.exit(Supervisor().run())
