"""Pinned resumable transfers, bounded workers, measured payload progress.

Exact size + safetensors metadata openability, never a full-weight hash or inference.
"""

import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import threading
import uuid
from pp_common import CODE, ROOT, SETUP, GIB, atomic, read, memory_available

MANIFEST = json.loads((CODE / "models.json").read_text())
REPOS, MODELS = MANIFEST["REPOS"], MANIFEST["MODELS"]


def verify(path, expected):
    if path.is_symlink() or not path.is_file() or path.stat().st_size != expected:
        raise ValueError("missing, symlink, or wrong byte count: " + str(path))
    from safetensors import safe_open

    with safe_open(str(path), framework="numpy") as f:
        if not f.keys():
            raise ValueError("empty model: " + str(path))
        # Metadata only, does not load giant tensors into RAM.
        for key in f.keys():
            f.get_slice(key).get_shape()


def run(
    mode,
    boot,
    auto=True,
    entries=None,
    worker_command=None,
    reserve=30 * GIB,
    stall=600,
    deadline=14400,
    poll=1,
):
    entries = [
        m
        for m in (MODELS if entries is None else entries)
        if mode == "both" or m[0] == mode
    ]
    if mode not in ("image", "video", "both") or not entries:
        raise ValueError("invalid or empty model profile")
    SETUP.mkdir(parents=True, exist_ok=True)
    lock = (SETUP / "model.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    attempt = uuid.uuid4().hex
    state = {
        "boot_id": boot,
        "attempt": attempt,
        "mode": mode,
        "phase": "CHECKING",
        "files": {},
    }
    active = {}

    def save():
        state["updated"] = time.time()
        state["workers"] = len(active)
        atomic(SETUP / "model_state.json", state)

    def stop(*_):
        raise InterruptedError("model sync interrupted")

    old = {}
    if threading.current_thread() is threading.main_thread():
        for sig in (signal.SIGTERM, signal.SIGINT):
            old[sig] = signal.signal(sig, stop)
    try:
        pending = []
        for family, rel, size in entries:
            dst = ROOT / "models" / rel
            s = state["files"][rel] = {
                "expected_bytes": size,
                "bytes": None,
                "status": "CHECKING",
            }
            save()
            if dst.exists() or dst.is_symlink():
                verify(dst, size)
                s.update(status="VERIFIED_BYTES_OPENABLE", bytes=size)
            else:
                s["status"] = "PENDING"
                pending.append((family, rel, size))
        save()
        if pending and not auto:
            raise RuntimeError("downloads disabled and selected models missing")
        if pending:
            requested = int(os.environ.get("PP_DOWNLOAD_WORKERS", "1"))
            if not 1 <= requested <= 3:
                raise ValueError("workers must be 1..3")
            # Conservative admission budget, not a claim of proven Xet peak RAM.
            capacity = (memory_available() - 4 * GIB) // (8 * GIB)
            if capacity < 1:
                raise RuntimeError(
                    "insufficient available RAM: require 12 GiB for a transfer"
                )
            workers = min(requested, capacity)
            if shutil.disk_usage(ROOT).free < sum(m[2] for m in pending) + reserve:
                raise RuntimeError("insufficient disk for missing models plus reserve")
        else:
            workers = 0
        start = time.monotonic()
        state["phase"] = "DOWNLOADING"
        save()
        while pending or active:
            if time.monotonic() - start > deadline:
                raise TimeoutError("model sync wall-clock deadline exceeded")
            while pending and len(active) < workers:
                family, rel, size = pending.pop(0)
                stage = ROOT / ".pp-model-staging" / family / Path(rel).name
                stage.mkdir(parents=True, exist_ok=True)
                event = stage / "progress.json"
                event.unlink(missing_ok=True)
                logfile = SETUP / "downloads" / (Path(rel).name + ".log")
                logfile.parent.mkdir(exist_ok=True)
                log = logfile.open("a")
                repo, rev = REPOS[family]
                cmd = (
                    worker_command or [sys.executable, str(CODE / "hf_worker.py")]
                ) + [repo, rev, rel, str(stage), str(event), boot, attempt]
                env = os.environ.copy()
                env.update(
                    HF_HOME=str(stage / ".hf-home"),
                    HF_XET_HIGH_PERFORMANCE="0",
                    HF_HUB_DISABLE_TELEMETRY="1",
                    HF_XET_CHUNK_CACHE_SIZE_BYTES="0",
                    HF_XET_NUM_CONCURRENT_RANGE_GETS="4",
                )
                proc = subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                active[rel] = (proc, stage, event, log, time.monotonic(), None)
                state["files"][rel].update(status="DOWNLOADING", pid=proc.pid)
            for rel, (proc, stage, event, log, last, previous) in list(active.items()):
                s = state["files"][rel]
                progress = read(event)
                if (
                    progress.get("attempt") == attempt
                    and progress.get("boot_id") == boot
                ):
                    count = progress.get("bytes")
                    if (
                        isinstance(count, (int, float))
                        and 0 <= count <= s["expected_bytes"]
                    ):
                        now = time.monotonic()
                        elapsed = now - s.get("sample_time", now)
                        s["payload_bytes_s"] = (
                            max(0, count - previous) / elapsed
                            if previous is not None and elapsed > 0
                            else None
                        )
                        wire = progress.get("transfer_bytes", 0)
                        old_wire = s.get("transfer_bytes", 0)
                        s["transfer_bytes_s"] = (
                            max(0, wire - old_wire) / elapsed if elapsed > 0 else None
                        )
                        if count != previous or wire > old_wire:
                            last = now
                        previous = count
                        s.update(bytes=count, transfer_bytes=wire, sample_time=now)
                active[rel] = (proc, stage, event, log, last, previous)
                s["idle_seconds"] = round(time.monotonic() - last)
                code = proc.poll()
                if code is not None:
                    log.close()
                    if code != 0:
                        s.update(status="FAILED", exit_code=code)
                        raise RuntimeError(
                            f"{rel}: downloader exit {code}; -9 alone does not prove OOM"
                        )
                    verify(stage / rel, s["expected_bytes"])
                    dst = ROOT / "models" / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    # No replacement, even if another actor created the destination.
                    os.link(stage / rel, dst)
                    (stage / rel).unlink()
                    del active[rel]
                    s.update(
                        status="VERIFIED_BYTES_OPENABLE",
                        bytes=s["expected_bytes"],
                        payload_bytes_s=None,
                    )
                elif time.monotonic() - last > stall:
                    s["status"] = "STALLED"
                    raise TimeoutError(
                        f"{rel}: no measured reconstruction or transfer progress for {stall}s"
                    )
            save()
            time.sleep(poll)
        state["phase"] = "VERIFIED_BYTES_OPENABLE"
        save()
    except BaseException as exc:
        state.update(phase="FAILED", error=str(exc))
        save()
        raise
    finally:
        for proc, _, _, log, _, _ in active.values():
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
            log.close()
        for sig, handler in old.items():
            signal.signal(sig, handler)
        active.clear()
        save()
        lock.close()


if __name__ == "__main__":
    run(
        os.environ.get("PP_MODE", "both"),
        os.environ["PP_BOOT_ID"],
        os.environ.get("PP_AUTO_DOWNLOAD_MODELS", "1") == "1",
    )
