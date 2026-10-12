#!/usr/bin/env bash
set -Eeuo pipefail
umask 022
mkdir -p /workspace/models/diffusion_models /workspace/models/text_encoders /workspace/models/vae /workspace/PP_RunPod_Setup

# Docker explicitly launches this script. Keep RunPod's Jupyter/SSH services.
if [[ -x /start.sh ]]; then
  echo '[PP] Starting RunPod Jupyter/SSH services in background'
  /start.sh > /workspace/PP_RunPod_Setup/base_services.log 2>&1 &
  echo "[PP] RunPod base services PID: $!"
else
  echo '[PP] WARNING: /start.sh was not found. Jupyter/SSH not started by this script.'
fi

MODE="${PP_MODE:-both}"
case "$MODE" in image|video|both) ;; *) echo "[PP] ERROR: PP_MODE must be image, video, both"; exit 2;; esac
echo "[PP] Profile: $MODE; download workers: ${PP_DOWNLOAD_WORKERS:-3}"

if [[ "${PP_AUTO_DOWNLOAD_MODELS:-1}" == '1' ]]; then
  echo '[PP] Checking/downloading selected models. See /workspace/PP_RunPod_Setup/models.log'
  /opt/pp-hf-venv/bin/python -u /opt/model_sync.py 2>&1 | tee -a /workspace/PP_RunPod_Setup/models.log
else
  echo '[PP] Downloads disabled. ComfyUI may start with missing models.'
fi

# Download + exact-byte verification must complete before ComfyUI starts.
echo '[PP] Starting ComfyUI on port 8188'
cd /opt/ComfyUI
exec /opt/pp-venv/bin/python -u main.py --listen 0.0.0.0 --port 8188
