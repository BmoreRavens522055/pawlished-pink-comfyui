# Pawlished & Pink — ComfyUI GitHub image R2 (BUILD CANDIDATE)

**Not yet built on GitHub or tested on RunPod.** No model weights or Pawlished & Pink episode assets are included. Public repository files are visible to everyone.

## 1. First build (free public-repo GitHub Actions attempt)

1. Upload this directory's **contents**, keeping `.github/workflows/build.yml` nested exactly as shown.
2. On GitHub: **Actions** → **Build and publish Pawlished Pink ComfyUI** → **Run workflow** → `main` → **Run workflow**.
3. Wait for the GitHub action. If it fails, keep RunPod off and inspect the log. A standard runner has a **14 GB SSD** and may not have enough disk for this large CUDA image. No paid runner is automatically used.
4. If successful, find the container package under your GitHub profile's **Packages** and make its visibility **Public** (package visibility is distinct from repository visibility).
5. Image name: `ghcr.io/bmoreravens522055/pawlished-pink-comfyui:r2`. This is a **target**, not a verified published image.

## 2. The three saved RunPod templates (not created yet)

All three use the **same** image from GitHub, but set an environment variable differently:

| Template | Environment | Models |
|---|---|---|
| Pawlished Pink VIDEO | `PP_MODE=video` | MiniMax H3, 4 files |
| Pawlished Pink IMAGE | `PP_MODE=image` | Qwen 2.1, 3 files |
| Pawlished Pink BOTH | `PP_MODE=both` | Both, 7 files |

Also set `PP_DOWNLOAD_WORKERS=3`, expose `8888/http` and `8188/http`, and use adequate **ephemeral** disk. No persistent RunPod volume is required. Allow model transfers to complete before starting ComfyUI. This is a **candidate** startup design. Use a pinned image tag (never `latest` for production).

Model downloads use version-pinned `hf download` + `hf_xet` with **up to three simultaneous file downloads**. Each model file is verified by exact byte count before being moved to `/workspace/models`. **Byte-size checks are not cryptographic hashes.** Large downloads may contend for network/storage resources; three parallel jobs may not prove fastest until benchmarked.

Current expected total weights: image ~30.2 GiB, video ~115.1 GiB, both ~145.3 GiB. The model sources are the exact pinned revisions in `model_sync.py`. Model weights download from **Hugging Face** when a pod starts, not from the GitHub registry image.

## 3. What is packaged, what is not

- Included: ComfyUI `v0.38.0` at commit `6b747c0428c343e1417219641db93a4fb7cb69ae`, CUDA-compatible PyTorch **inherited from the RunPod base**, pinned Stage 1 pip dependencies, VideoHelperSuite at commit `4d907bee61e92c2e65af3bd6383a4e4d356126d1`, the three-mode downloader, and read-only monitor.
- Not included: weight files, approved episode-specific workflow files, inputs/outputs, private images/credentials. Workflow fixtures still require separate private staging and runtime validation.
- Model placement: `/workspace/models/{diffusion_models,text_encoders,vae}`; ComfyUI install under `/opt/ComfyUI` to avoid the `/workspace` mount hiding installed software.
- Jupyter: original RunPod base startup `/start.sh` is launched in background; this **must be runtime-tested** on the built image.
- Optional console monitor: `python3 -u /opt/pp-monitor.py` (refreshes every 3 seconds, measured total pod receive speed; **not per-model speed**).

## 4. Known testing limits

GitHub Actions Docker image build, startup, Jupyter, ComfyUI HTTP/API, model downloads, source access, CUDA, and real inference have **not** been runtime tested for this R2 image. This package has static and offline simulations only. If GitHub runner runs out of storage, stop and investigate; don't buy a GitHub runner or RunPod session by default.
