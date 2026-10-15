"""Transactional, non-overwriting episode intake and retrieval snapshots."""

from pathlib import Path, PurePosixPath
import os
import shutil
import stat
import tempfile
import time
import zipfile
import zlib
from pp_common import ROOT, SETUP, atomic

REQUIRED = [
    "Blueprint & Shot Prompts/" + p
    for p in [
        "Image Prompts",
        "Technical Companions",
        "Still Generation Dashboard",
        "Audio Execution",
        "Editing Execution",
    ]
] + ["JSON/Local", "JSON/Cloud", "Pics", "Videos/Narration", "Videos/SFX"]


def safe_members(z):
    seen = set()
    roots = set()
    result = []
    for i in z.infolist():
        name = i.filename
        p = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or ":" in name
            or p.is_absolute()
            or any(s in ("", ".", "..") for s in name.rstrip("/").split("/"))
            or any(ord(c) < 32 for c in name)
            or i.flag_bits & 1
        ):
            raise ValueError("unsafe archive path or encrypted entry")
        key = name.rstrip("/")
        if key in seen:
            raise ValueError("duplicate archive entry: " + key)
        seen.add(key)
        roots.add(p.parts[0])
        kind = stat.S_IFMT(i.external_attr >> 16)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
            raise ValueError("non-regular ZIP entry")
        if len(p.parts) == 1 and not i.is_dir():
            raise ValueError("files must be inside Episode-ID root")
        result.append(i)
    if len(roots) != 1:
        raise ValueError("exactly one Episode-ID root required")
    root = next(iter(roots))
    if root.startswith("."):
        raise ValueError("hidden episode root")
    return root, result


def crc(path):
    value = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            value = zlib.crc32(chunk, value)
    return value & 0xFFFFFFFF


def ingest(source, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as z:
        root, members = safe_members(z)
        total = sum(i.file_size for i in members)
        if (
            len(members) > 100000
            or total > shutil.disk_usage(destination).free - 1024**3
        ):
            raise ValueError("archive exceeds file count or available storage reserve")
        target = destination / root
        if target.is_symlink():
            raise ValueError("episode root is a symlink")
        # Existing intake is repeatable only when every uploaded member is identical.
        if target.exists():
            for i in members:
                p = destination / i.filename
                if any(
                    a.is_symlink() for a in [p, *p.parents] if a != destination.parent
                ):
                    raise ValueError("symlink in existing episode")
                if i.is_dir():
                    if not p.is_dir():
                        raise ValueError("existing episode directory conflict")
                elif (
                    not p.is_file()
                    or p.stat().st_size != i.file_size
                    or crc(p) != i.CRC
                ):
                    raise ValueError(
                        "existing episode conflict; upload a new versioned root"
                    )
            return root
        temp = Path(tempfile.mkdtemp(prefix=".pp-intake-", dir=destination))
        try:
            for i in members:
                p = temp / i.filename
                if i.is_dir():
                    p.mkdir(parents=True, exist_ok=True)
                else:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    with z.open(i) as src, p.open("xb") as dst:
                        shutil.copyfileobj(src, dst, 1024 * 1024)
                    # zipfile verifies CRC during the copy.
            for d in REQUIRED:
                (temp / root / d).mkdir(parents=True, exist_ok=True)
            if target.exists():
                raise ValueError("episode appeared during intake")
            os.rename(temp / root, target)
        finally:
            shutil.rmtree(temp, ignore_errors=True)
        return root


def stage_uploads():
    inbox = ROOT / "uploads"
    inbox.mkdir(exist_ok=True)
    results = []
    for source in sorted(inbox.glob("*.zip")):
        if source.is_symlink():
            raise ValueError("upload ZIP is a symlink")
        before = source.stat()
        # Jupyter uploads must finish before init is invoked. Detect ordinary concurrent change.
        root = ingest(source, ROOT / "ComfyUI/input")
        after = source.stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError(
                "upload changed during intake; re-run after upload completes"
            )
        results.append(root)
    return results


def snapshot(boot):
    """No provider shutdown; archive readback on this machine is not local retrieval."""
    out = ROOT / "retrieval"
    out.mkdir(exist_ok=True)
    final = out / (time.strftime("PP-R4-%Y%m%dT%H%M%S-") + boot[:8] + ".zip")
    tmp = final.with_suffix(".partial")
    if final.exists():
        return str(final)
    files = []
    for base in [
        ROOT / "ComfyUI/input",
        ROOT / "ComfyUI/output",
        ROOT / "ComfyUI/user",
        SETUP,
    ]:
        for p in sorted(base.rglob("*")):
            if p.is_symlink():
                raise ValueError("snapshot refuses symlink: " + str(p))
            if p.is_file() and not p.name.endswith((".lock", ".tmp")):
                files.append((p, p.stat()))
    if shutil.disk_usage(out).free < sum(st.st_size for _, st in files) + 1024**3:
        raise RuntimeError(
            "insufficient space for retrieval snapshot plus 1 GiB reserve"
        )
    with zipfile.ZipFile(
        tmp, "x", compression=zipfile.ZIP_STORED, allowZip64=True
    ) as z:
        for p, before in files:
            z.write(p, p.relative_to(ROOT).as_posix())
            after = p.stat()
            if (before.st_size, before.st_mtime_ns) != (
                after.st_size,
                after.st_mtime_ns,
            ):
                raise RuntimeError("file changed while archiving; retry when idle")
    with zipfile.ZipFile(tmp) as z:
        if z.testzip():
            raise ValueError("snapshot CRC failed")
    tmp.rename(final)
    return str(final)
