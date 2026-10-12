#!/usr/bin/env python3
"""Read-only three-second startup monitor. No commands issued to ComfyUI or HF."""
import json
from datetime import datetime
from pathlib import Path
import shutil
import time
import urllib.request

ROOT = Path('/workspace')
STATE = ROOT / 'PP_RunPod_Setup' / 'model_state.json'

def net_total_rx():
    try:
        pairs = [line.strip().split(':', 1) for line in Path('/proc/net/dev').read_text().splitlines()[2:] if ':' in line]
        return sum(int(v.strip().split()[0]) for nic,v in pairs if nic.strip() != 'lo')
    except (OSError, ValueError, IndexError):
        return None

def comfy_online():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8188/system_stats', timeout=1.2) as res:
            return res.status == 200
    except Exception:
        return False

def display(current_rx, previous_rx, elapsed):
    print('\033[2J\033[H', end='')
    print('PAWLISHED & PINK | RUNPOD MODEL SYNC | every 3 seconds')
    print('System time:',datetime.now().astimezone().isoformat(timespec='seconds'))
    try:
        state = json.loads(STATE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        print('Waiting for /workspace/PP_RunPod_Setup/model_state.json ...')
        return
    files = state.get('files', {})
    verified = sum(1 for row in files.values() if row.get('status') == 'VERIFIED')
    print(f'MODE: {state.get("mode")} | PHASE: {state.get("phase")} | FILES VERIFIED: {verified}/{len(files)}')
    print(f'ACTIVE DOWNLOADS: {sum(1 for row in files.values() if row.get("status") == "DOWNLOADING")} | CONFIGURED WORKERS: {state.get("workers")}')
    if previous_rx is not None and current_rx is not None and elapsed > 0:
        speed = (current_rx - previous_rx) / elapsed / 1024**2
        print(f'TOTAL POD NETWORK RECEIVE: {max(speed, 0):.2f} MiB/s (NOT per-file payload rate)')
    print(f'COMFYUI HTTP: {"READY" if comfy_online() else "NOT READY (waiting for downloads/startup)"}')
    try:
        d = shutil.disk_usage(ROOT)
        print(f'/workspace FREE SPACE: {d.free / 1024**3:.1f} GiB')
    except OSError:
        pass
    print('-' * 86)
    for filename,row in files.items():
        print(f'{row.get("status", "UNKNOWN"):12} {Path(filename).name}')
        if row.get('status') == 'FAILED':
            print(f'  {row.get("detail", "")}')
    if state.get('error'):
        print('ERROR:',state['error'])
    print('-' * 86)
    print('Source: model_state.json; sizes verified only after transfer completes.')
    print('Detailed download logs: /workspace/PP_RunPod_Setup/downloads/')

if __name__ == '__main__':
    prev = net_total_rx()
    tprev = time.monotonic()
    try:
        while True:
            t = time.monotonic()
            current = net_total_rx()
            display(current,prev,t-tprev)
            prev,tprev = current,t
            time.sleep(3)
    except KeyboardInterrupt:
        pass
