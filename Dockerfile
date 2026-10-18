# syntax=docker/dockerfile:1
# R4 offline candidate; immutable amd64 base, inspected 2026-10-15.
FROM runpod/pytorch@sha256:4d1721e62b56d345c83b4fd6090664be6daf9312caab5b2e76f23d8231941851

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PP_COMFY_DIR=/opt/ComfyUI \
    PP_COMFY_PY=/opt/pp-venv/bin/python \
    PP_AUTO_DOWNLOAD_MODELS=1 \
    PP_MODE=both \
    PP_VIDEO_VARIANT=hybrid \
    PP_DOWNLOAD_WORKERS=1

# ComfyUI stays outside /workspace, which RunPod can mount as a volume.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca PIP_CERT=/run/secrets/proxy_ca GIT_SSL_CAINFO=/run/secrets/proxy_ca; fi; \
    apt-get update && apt-get install -y --no-install-recommends \
    git ffmpeg ca-certificates curl libgl1 libglib2.0-0 python3-venv && \
    rm -rf /var/lib/apt/lists/*

RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca PIP_CERT=/run/secrets/proxy_ca GIT_SSL_CAINFO=/run/secrets/proxy_ca; fi; \
    git clone https://github.com/Comfy-Org/ComfyUI.git /opt/ComfyUI && \
    git -C /opt/ComfyUI checkout --detach 6b747c0428c343e1417219641db93a4fb7cb69ae && \
    test "$(git -C /opt/ComfyUI rev-parse HEAD)" = '6b747c0428c343e1417219641db93a4fb7cb69ae'

COPY constraints.txt /opt/pp-install/constraints.txt
COPY torch-constraints.txt /opt/pp-install/torch-constraints.txt

# Inherit CUDA-enabled torch from the pinned base. Do not download CPU torch into image.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca PIP_CERT=/run/secrets/proxy_ca GIT_SSL_CAINFO=/run/secrets/proxy_ca; fi; \
    python3 -m venv --system-site-packages /opt/pp-venv && \
    /opt/pp-venv/bin/python -m pip install --no-cache-dir \
      --prefer-binary --default-timeout 90 --retries 4 \
      -c /opt/pp-install/torch-constraints.txt \
      -c /opt/pp-install/constraints.txt \
      -r /opt/ComfyUI/requirements.txt

RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca PIP_CERT=/run/secrets/proxy_ca GIT_SSL_CAINFO=/run/secrets/proxy_ca; fi; \
    git clone https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git \
      /opt/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite && \
    git -C /opt/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite \
      checkout --detach 4d907bee61e92c2e65af3bd6383a4e4d356126d1 && \
    /opt/pp-venv/bin/python -m pip install --no-cache-dir --prefer-binary \
      -c /opt/pp-install/torch-constraints.txt \
      -c /opt/pp-install/constraints.txt \
      -r /opt/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt

# Pin the owner's MiniMax MASTER combined first-frame + reference-image node.
# Its Python implementation uses the pinned ComfyUI built-in H3 helpers; no unpinned pip install.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca PIP_CERT=/run/secrets/proxy_ca GIT_SSL_CAINFO=/run/secrets/proxy_ca; fi; \
    git clone https://github.com/BigStationW/ComfyUi-MiniMax-H3-Image-And-Reference-To-Video.git \
      /opt/ComfyUI/custom_nodes/ComfyUi-MiniMax-H3-Image-And-Reference-To-Video && \
    git -C /opt/ComfyUI/custom_nodes/ComfyUi-MiniMax-H3-Image-And-Reference-To-Video \
      checkout --detach f12a48fe9f1c8ee313a081a91327c31b5bfb9895 && \
    test "$(git -C /opt/ComfyUI/custom_nodes/ComfyUi-MiniMax-H3-Image-And-Reference-To-Video rev-parse HEAD)" = 'f12a48fe9f1c8ee313a081a91327c31b5bfb9895'

# Separate small download environment; models NEVER build into the public image.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca PIP_CERT=/run/secrets/proxy_ca GIT_SSL_CAINFO=/run/secrets/proxy_ca; fi; \
    python3 -m venv /opt/pp-hf-venv && \
    /opt/pp-hf-venv/bin/pip install --no-cache-dir \
       'huggingface_hub==2.2.0' 'hf_xet==1.7.0' 'safetensors==0.8.0' 'numpy==2.5.2'

# Jupyter remains the normal JupyterLab application with an explicit tested config.
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca PIP_CERT=/run/secrets/proxy_ca GIT_SSL_CAINFO=/run/secrets/proxy_ca; fi; \
    python3 -m venv /opt/pp-jupyter && /opt/pp-jupyter/bin/pip install \
    'jupyterlab==4.4.10' 'jupyter_server==2.17.0'
COPY *.py models.json /opt/pp/
COPY pp-start.sh /opt/pp-start.sh
COPY extra_model_paths.yaml /opt/ComfyUI/extra_model_paths.yaml
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export SSL_CERT_FILE=/run/secrets/proxy_ca PIP_CERT=/run/secrets/proxy_ca GIT_SSL_CAINFO=/run/secrets/proxy_ca; fi; \
    chmod +x /opt/pp-start.sh && \
    /opt/pp-venv/bin/python -c 'import torch; assert torch.__version__.startswith("2.8.")' && \
    /opt/pp-venv/bin/python -m pip check && /opt/pp-jupyter/bin/python -m pip check
EXPOSE 8188 8888
WORKDIR /workspace
# Preserve CUDA's environment setup. Deliberately avoid the unmonitored /start.sh.
ENTRYPOINT ["/opt/nvidia/nvidia_entrypoint.sh", "/opt/pp-start.sh"]
