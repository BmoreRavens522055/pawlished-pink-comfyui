#!/usr/bin/env python3
"""Download the selected, pinned model family with <=3 concurrent hf_xet jobs.

Model weights are *not* part of the public Docker image. This code performs
size verification only (not cryptographic verification). It does not infer.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import threading
import time

ROOT = Path('/workspace')
MODEL_ROOT = ROOT / 'models'
SETUP = ROOT / 'PP_RunPod_Setup'
STAGING = ROOT / '.pp-model-staging'
HF = '/opt/pp-hf-venv/bin/hf'
REPOS = {
    'image': ('Comfy-Org/Qwen-Image-2.1', 'df94239739eef7205973a145ffa6f441f7b64e84'),
    'video': ('Comfy-Org/MiniMax-H3', 'e5eb578a89295337b8ff433a035929ce0279e0b6'),
}
MODELS = (
    ('image', 'diffusion_models/qwen_image_2.1_bf16.safetensors', 14230280616),
    ('image', 'text_encoders/qwen3vl_8b_bf16.safetensors', 17534334616),
    ('image', 'vae/qwen_image_2.1_vae_bf16.safetensors', 675509688),
    ('video', 'diffusion_models/minimax_h3_fl2va_bf16.safetensors', 66280487368),
    ('video', 'text_encoders/qwen3vl_32b_minimax_h3_bf16.safetensors', 51506295256),
    ('video', 'vae/minimax_h3_video_vae_fp16.safetensors', 5207808496),
    ('video', 'vae/minimax_h3_audio_vae_fp32.safetensors', 605254808),
)
LOCK = threading.Lock()
STATUS = {'mode': None, 'phase': 'STARTING', 'workers': 0, 'files': {}, 'updated_utc': None,
          'network_receive_mib_s': None, 'network_note': 'Total pod receive rate, not per-file payload rate'}

def utc():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def log(msg):
    print(f'[{utc()}] {msg}', flush=True)

def save():
    SETUP.mkdir(parents=True, exist_ok=True)
    STATUS['updated_utc'] = utc()
    temp = SETUP / 'model_state.json.tmp'
    temp.write_text(json.dumps(STATUS, indent=2), encoding='utf-8')
    temp.replace(SETUP / 'model_state.json')

def set_status(name, status, detail=None):
    with LOCK:
        STATUS['files'].setdefault(name, {})['status'] = status
        STATUS['files'][name]['updated_utc'] = utc()
        if detail is not None:
            STATUS['files'][name]['detail'] = detail
        save()

def download_one(entry):
    family, rel, expected = entry
    dst = MODEL_ROOT / rel
    if dst.is_file() and dst.stat().st_size == expected:
        set_status(rel, 'VERIFIED', 'Already present, correct byte count')
        return
    if dst.exists():
        raise RuntimeError(f'Existing model file has incorrect size: {dst}')
    repo, revision = REPOS[family]
    # Each process gets its own local-dir metadata and HF cache directory.
    # Completed files are moved atomically on the same /workspace filesystem.
    stage = STAGING / family / dst.name
    stage.mkdir(parents=True, exist_ok=True)
    source = stage / rel
    cmd = [HF, 'download', repo, rel, '--revision', revision, '--local-dir', str(stage)]
    env = os.environ.copy()
    env.update(HF_HOME=str(stage / '.hf-home'), HF_XET_HIGH_PERFORMANCE='1',
               HF_HUB_DISABLE_TELEMETRY='1', HF_XET_CHUNK_CACHE_SIZE_BYTES='0')
    logfile = SETUP / 'downloads' / (dst.name + '.log')
    logfile.parent.mkdir(parents=True, exist_ok=True)
    set_status(rel, 'DOWNLOADING', f'{repo}@{revision}; expected {expected} bytes')
    log(f'DOWNLOAD START {rel} ({expected / 1024**3:.2f} GiB)')
    with logfile.open('a', encoding='utf-8') as out:
        proc = subprocess.run(cmd, env=env, stdout=out, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        set_status(rel, 'FAILED', f'hf download exit {proc.returncode}; see {logfile}')
        raise RuntimeError(f'Download failed ({proc.returncode}): {rel}; {logfile}')
    if not source.is_file() or source.stat().st_size != expected:
        actual = source.stat().st_size if source.exists() else 'missing'
        set_status(rel, 'FAILED', f'Expected {expected} bytes; found {actual}')
        raise RuntimeError(f'Size verification failed: {rel}: {actual} != {expected}')
    dst.parent.mkdir(parents=True, exist_ok=True)
    source.replace(dst)
    # Do not delete other staging directories: their workers may be downloading.
    shutil.rmtree(stage, ignore_errors=True)
    set_status(rel, 'VERIFIED', f'Exact byte count: {expected}')
    log(f'VERIFIED {rel} ({expected} bytes)')

def main():
    mode = os.environ.get('PP_MODE', 'both').strip().lower()
    if mode not in {'image', 'video', 'both'}:
        raise RuntimeError(f'Invalid PP_MODE={mode!r}; use image, video, or both')
    workers = int(os.environ.get('PP_DOWNLOAD_WORKERS', '3'))
    if not 1 <= workers <= 3:
        raise RuntimeError('PP_DOWNLOAD_WORKERS must be between 1 and 3')
    chosen = [m for m in MODELS if mode == 'both' or m[0] == mode]
    MODEL_ROOT.mkdir(parents=True, exist_ok=True)
    SETUP.mkdir(parents=True, exist_ok=True)
    STATUS.update(mode=mode, workers=workers, phase='PRECHECK')
    for _,rel,expected in chosen:
        STATUS['files'][rel] = {'status': 'PENDING', 'expected_bytes': expected}
    save()
    missing = sum(expected for _, rel, expected in chosen
                  if not (MODEL_ROOT / rel).is_file() or (MODEL_ROOT / rel).stat().st_size != expected)
    free = shutil.disk_usage(MODEL_ROOT).free
    # Parallel Xet downloads may use scratch space. Reserve 30 GiB.
    reserve = 30 * 1024**3
    log(f'MODE={mode} FILES={len(chosen)} WORKERS={workers} '
        f'MISSING={missing/1024**3:.2f}GiB FREE={free/1024**3:.2f}GiB '
        f'RESERVE={reserve/1024**3:.0f}GiB')
    if free < missing + reserve:
        raise RuntimeError('Insufficient storage for selected model files plus 30 GiB reserve')
    STATUS['phase'] = 'DOWNLOADING'
    save()
    failures = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(download_one, m): m[1] for m in chosen}
        for future in as_completed(jobs):
            try:
                future.result()
            except Exception as exc:
                log(f'ERROR {jobs[future]}: {exc}')
                failures.append(str(exc))
    if failures:
        STATUS['phase'] = 'FAILED'
        STATUS['errors'] = failures
        save()
        raise RuntimeError('; '.join(failures))
    STATUS['phase'] = 'VERIFIED'
    save()
    log(f'ALL {len(chosen)} {mode.upper()} MODEL FILES VERIFIED. NO INFERENCE.')

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        STATUS['phase'] = 'FAILED'
        STATUS['error'] = str(exc)
        save()
        log('MODEL SYNC FAILED: ' + str(exc))
        sys.exit(1)
