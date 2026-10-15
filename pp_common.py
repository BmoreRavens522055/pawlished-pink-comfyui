"""Local state and resource helpers; no provider API operations."""

import json
import os
from pathlib import Path
import time
import urllib.request

ROOT = Path(os.environ.get("PP_WORKSPACE", "/workspace"))
SETUP = ROOT / "PP_RunPod_Setup"
CODE = Path(__file__).resolve().parent
GIB = 1024**3


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with tmp.open("w") as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def read(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def request(port, path, token=None, method="GET", data=None, timeout=2):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "token " + token
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        headers=headers,
        method=method,
        data=json.dumps(data).encode() if data is not None else None,
    )
    # Local service checks never traverse a configured outbound proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(req, timeout=timeout) as response:
        body = response.read()
        return json.loads(body) if body else None


def memory_available(cgroup=Path("/sys/fs/cgroup")):
    info = dict(
        (l.split(":")[0], int(l.split()[1]) * 1024)
        for l in Path("/proc/meminfo").read_text().splitlines()
    )
    available = info["MemAvailable"]
    # Walk ancestors: a nested cgroup can say max while a parent is constrained.
    for base in (cgroup, *cgroup.parents):
        if not str(base).startswith("/sys/fs/cgroup") and cgroup == Path(
            "/sys/fs/cgroup"
        ):
            continue
        for limit, used in [
            ("memory.max", "memory.current"),
            ("memory/memory.limit_in_bytes", "memory/memory.usage_in_bytes"),
        ]:
            try:
                available = min(
                    available,
                    int((base / limit).read_text()) - int((base / used).read_text()),
                )
            except (OSError, ValueError):
                pass
    return max(0, available)


def fresh(state, boot, age=15):
    return bool(
        state
        and state.get("boot_id") == boot
        and 0 <= time.time() - state.get("updated", 0) <= age
    )
