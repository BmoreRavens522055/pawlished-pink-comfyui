# PAWLISHED & PINK — GHCR R2 CANDIDATE. No model weights or private assets.
# Base matches the tested Stage 2 R2 RunPod recipe. Exact base digest still needs recording.
FROM runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PP_COMFY_DIR=/opt/ComfyUI \
    PP_COMFY_PY=/opt/pp-venv/bin/python \
    PP_AUTO_DOWNLOAD_MODELS=1 \
    PP_MODE=both \
    PP_DOWNLOAD_WORKERS=3

# ComfyUI stays outside /workspace, which RunPod can mount as a volume.
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ffmpeg ca-certificates curl libgl1 libglib2.0-0 python3-venv && \
    rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/Comfy-Org/ComfyUI.git /opt/ComfyUI && \
    git -C /opt/ComfyUI checkout --detach 6b747c0428c343e1417219641db93a4fb7cb69ae && \
    test "$(git -C /opt/ComfyUI rev-parse HEAD)" = '6b747c0428c343e1417219641db93a4fb7cb69ae'

COPY constraints.txt /opt/pp-install/constraints.txt
COPY torch-constraints.txt /opt/pp-install/torch-constraints.txt

# Inherit CUDA-enabled torch from the pinned base. Do not download CPU torch into image.
RUN python3 -m venv --system-site-packages /opt/pp-venv && \
    /opt/pp-venv/bin/python -m pip install --no-cache-dir \
      --prefer-binary --default-timeout 90 --retries 4 \
      -c /opt/pp-install/torch-constraints.txt \
      -c /opt/pp-install/constraints.txt \
      -r /opt/ComfyUI/requirements.txt

RUN git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git \
      /opt/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite && \
    git -C /opt/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite \
      checkout --detach 4d907bee61e92c2e65af3bd6383a4e4d356126d1 && \
    /opt/pp-venv/bin/python -m pip install --no-cache-dir --prefer-binary \
      -c /opt/pp-install/torch-constraints.txt \
      -c /opt/pp-install/constraints.txt \
      -r /opt/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt

# Separate small download environment; models NEVER build into the public image.
RUN python3 -m venv /opt/pp-hf-venv && \
    /opt/pp-hf-venv/bin/pip install --no-cache-dir \
       'huggingface_hub==2.2.0' 'hf_xet==1.7.0'

COPY pp-start.sh /opt/pp-start.sh
COPY model_sync.py /opt/model_sync.py
COPY pp-monitor.py /opt/pp-monitor.py
COPY extra_model_paths.yaml /opt/ComfyUI/extra_model_paths.yaml
RUN chmod +x /opt/pp-start.sh && \
    /opt/pp-venv/bin/python -c 'import torch; assert torch.__version__.startswith("2.8."); print("Torch installed:",torch.__version__)' && \
    /opt/pp-venv/bin/python -m pip check

EXPOSE 8188 8888
WORKDIR /workspace
# Explicit startup so the base entrypoint cannot silently ignore our commands.
# The wrapper launches /start.sh separately for RunPod Jupyter/SSH.
ENTRYPOINT ["/opt/pp-start.sh"]
