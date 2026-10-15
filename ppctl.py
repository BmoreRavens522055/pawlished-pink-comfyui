#!/usr/bin/env python3
"""The two stable operator commands: init and monitor."""

import argparse
import fcntl
import os
import subprocess
import sys
from pathlib import Path
import time
from pp_common import ROOT, SETUP, atomic, read, fresh, request
from episode import stage_uploads, snapshot
from graph_check import check


def init():
    SETUP.mkdir(parents=True, exist_ok=True)
    with (SETUP / "intake.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        s = read(SETUP / "startup_state.json")
        boot = s.get("boot_id")
        atomic(
            SETUP / "operation.json",
            {"phase": "RUNNING", "boot_id": boot, "updated": time.time()},
        )
        if not fresh(s, boot) or s.get("phase") in ("FAILED", "STOPPED"):
            raise RuntimeError(
                "supervisor unavailable; read monitor and preserve evidence before stopping compute"
            )
        queue = request(int(os.environ.get("PP_COMFY_PORT", "8188")), "/queue")
        if queue.get("queue_running") or queue.get("queue_pending"):
            raise RuntimeError(
                "wait for queue to finish before staging/retrieval snapshot"
            )
        episodes = stage_uploads()
        schema = request(int(os.environ.get("PP_COMFY_PORT", "8188")), "/object_info")
        graph_results = {}
        for name in episodes:
            for path in (ROOT / "ComfyUI/input" / name / "JSON/Cloud").rglob("*.json"):
                graph_results[str(path.relative_to(ROOT))] = check(
                    read(path), schema, ROOT / "ComfyUI/input"
                )
        atomic(
            SETUP / "graph_checks.json",
            {
                "checks": graph_results,
                "scope": "static API schema only; no inference or creative approval",
            },
        )
        atomic(
            SETUP / "intake_state.json",
            {
                "boot_id": boot,
                "updated": time.time(),
                "episodes": episodes,
                "workflow_status": "NOT_VALIDATED",
                "next_action": "Load approved JSON unchanged; verify actual paths/sockets",
            },
        )
        history = request(int(os.environ.get("PP_COMFY_PORT", "8188")), "/history")
        atomic(SETUP / "history.json", history)
        archive = snapshot(boot)
        atomic(
            SETUP / "retrieval_state.json",
            {"archive": archive, "pod_crc": "PASS", "local_readback": "NOT_CONFIRMED"},
        )
        if s.get("model_phase") != "VERIFIED_BYTES_OPENABLE":
            atomic(SETUP / "continue.json", {"boot_id": boot})
        print("Staged:", ", ".join(episodes) or "no uploaded ZIPs")
        print(
            "Retrieval snapshot:",
            archive,
            "(pod CRC checked; local download/media readback still required)",
        )
        print(
            "Continue requested if needed. Monitor is read-only; closing either tab does not stop the supervisor."
        )


def display():
    s = read(SETUP / "startup_state.json")
    boot = s.get("boot_id")
    if not fresh(s, boot) or s.get("phase") in ("STOPPED", "FAILED"):
        print(
            "STALE/STOPPED/FAILED — no current readiness claim. Billing may continue."
        )
    print("Init/staging:", read(SETUP / "operation.json"))
    print("Retrieval:", read(SETUP / "retrieval_state.json"))
    graphs = read(SETUP / "graph_checks.json").get("checks", {})
    for path, errors in graphs.items():
        print("Workflow:", path, "; ".join(errors) if errors else "SCHEMA CHECKED ONLY")
    print(
        "Phase:", s.get("phase", "UNKNOWN"), "Services:", s.get("services", "UNKNOWN")
    )
    print("Storage:", s.get("storage", "UNKNOWN"))
    print("Next:", s.get("next_action", "Inspect deployment startup logs"))
    if s.get("error"):
        print("Error:", s["error"])
    m = read(SETUP / "model_state.json")
    if m.get("boot_id") != boot:
        print("Models: UNKNOWN (other boot)")
        return
    print(
        "Model phase:",
        m.get("phase", "UNKNOWN"),
        "Active workers:",
        m.get("workers", "UNKNOWN"),
    )
    complete = 0
    done = 0
    total = 0
    for rel, f in m.get("files", {}).items():
        n = f.get("bytes")
        size = f["expected_bytes"]
        total += size
        valid = f.get("status") == "VERIFIED_BYTES_OPENABLE"
        if valid:
            complete += 1
            done += size
        if n is None:
            bar = "[ progress UNKNOWN ]"
        else:
            fraction = min(1, n / size)
            ticks = int(fraction * 20)
            bar = (
                "["
                + "#" * ticks
                + "-" * (20 - ticks)
                + f"] {fraction:6.2%} {int(n)}/{size} bytes"
            )
        rate = f.get("payload_bytes_s")
        rate = "unknown" if rate is None else f"{rate/1024**2:.2f} MiB/s"
        wire_rate = f.get("transfer_bytes_s")
        wire_label = (
            "unknown" if wire_rate is None else f"{wire_rate/1024**2:.2f} MiB/s"
        )
        print(
            "Xet per-file transfer:",
            f.get("transfer_bytes", "unknown"),
            "bytes; rate:",
            wire_label,
        )
        print(
            rel,
            f.get("status"),
            bar,
            "reconstructed-file rate:",
            rate,
            "idle:",
            f.get("idle_seconds", 0),
            "s",
        )
    print(
        f'Completed files {complete}/{len(m.get("files",{}))}; verified bytes {done}/{total}'
    )
    if m.get("error"):
        print("Download error:", m["error"])
    if time.time() - m.get("updated", 0) > 15 and m.get("phase") not in (
        "FAILED",
        "VERIFIED_BYTES_OPENABLE",
    ):
        print("Download state STALE; progress is last observed, not live")
    print(
        "Graph/native audio, external browser/proxy, local retrieval: NOT PROVEN by this monitor"
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=["init", "monitor", "_init-worker"])
    p.add_argument("--once", action="store_true")
    a = p.parse_args()
    if a.action == "_init-worker":
        try:
            init()
            atomic(
                SETUP / "operation.json", {"phase": "COMPLETE", "updated": time.time()}
            )
        except BlockingIOError:
            print("An init operation is already running; see monitor.")
            return
        except Exception as e:
            atomic(
                SETUP / "operation.json",
                {"phase": "FAILED", "error": str(e), "updated": time.time()},
            )
            raise
        return
    if a.action == "init":
        SETUP.mkdir(parents=True, exist_ok=True)
        with (SETUP / "operator.log").open("a") as log:
            subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "_init-worker"],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        print(
            "Initialization/staging runs detached. Read the monitor for completion and retrieval path."
        )
        return
    try:
        while True:
            if os.isatty(1):
                print("\033[2J\033[H", end="")
            display()
            if a.once:
                return
            time.sleep(3)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
