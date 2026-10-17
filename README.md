# Pawlished & Pink — ComfyUI on RunPod

> **Current status (17 October 2026):** R4 passed its **RunPod startup, service access, and seven-file model download/verification test** on 15–16 October 2026. **Actual GPU image/video generation, episode-graph compatibility, audio capability, and owner-local retrieval are not yet verified.** R4 is a **published test candidate**, not a production-approved release.

## Which version is where?

| Item | Actual status |
|---|---|
| Repository default branch (`main`) | **Historical R2 source** — the code on `main` is not the R4 image |
| R4 candidate source | [Open draft pull request #1](https://github.com/BmoreRavens522055/pawlished-pink-comfyui/pull/1), branch `codex/r4-offline-candidate` |
| R4 source used to publish/test the image | Commit `2ca3cdcdb6323803ec21063610eef8e11ca7b6a0` |
| R4 published image | See the **immutable digest** below |
| R2 `:r2` tag | Historical separate candidate; **do not silently substitute it for R4** |
| Next qualification | A normal authorized episode generation, followed by actual output QC and verified local retrieval |

**R4 image — use this immutable digest for the tested candidate:**

```text
ghcr.io/bmoreravens522055/pawlished-pink-comfyui@sha256:0b1c8a52a6d76bef4a52378bf8fe910527a9e85800935f4258547c26b075b16e
```

The successful [R4 GitHub Actions publish run](https://github.com/BmoreRavens522055/pawlished-pink-comfyui/actions/runs/38832778807) built and pushed this image. IMAGE, VIDEO, and BOTH passed the workflow's **offline container smoke** tests. The subsequent **real RunPod test used BOTH mode**. Do not treat IMAGE or VIDEO as separately RunPod-tested.

**A README update does not merge the R4 source, republish the image, update RunPod templates, or constitute production approval.**

## What the October RunPod test actually proved

**Observed PASS, scoped to the owner-operated R4 BOTH session:**

- Pinned image pulled successfully by the RunPod host, with the expected registry digest.
- After supplying a nonempty Jupyter authentication token, the R4 supervisor started authenticated JupyterLab and ComfyUI. Both local API checks reported `LOCAL_API_READY`.
- JupyterLab's main browser interface opened. Its **built-in terminal did not accept typing**; the **RunPod Web Terminal worked** and was used successfully.
- ComfyUI's initial RunPod proxy URL returned **403**; selecting the same URL in the browser address bar and pressing **Enter** opened ComfyUI. No service-code change was needed.
- R4 downloaded and opened all **seven** pinned Qwen/MiniMax model files: `VERIFIED_BYTES_OPENABLE`, **156,039,970,848 of 156,039,970,848 bytes**. Active download workers reached zero.
- The owner confirmed that the test pod was terminated.

**Not yet passed / not established:**

- An actual Qwen image or MiniMax video inference and pixel-level output QC.
- The compatible production episode JSON, required role-matched references, model-native graph capabilities, MULTI conditioning, and native physical-audio output.
- JupyterLab built-in terminal reliability (RunPod Web Terminal is the accepted workaround for the test).
- The retrieval archive: the attempted snapshot reported `file changed while archiving; retry when idle`. A successful replacement archive and **owner-local file/CRC/media readback were not evidenced**.
- Provider-backed volume persistence beyond pod termination. **Do not assume files survive termination** just because they lived under `/workspace`.

Keep the **passed download evidence** separate from unfinished generation, archive, and production qualification.

## RunPod template checklist for R4

The saved RunPod configurations must be reviewed individually. The successful BOTH pod **does not prove** the separate IMAGE or VIDEO saved templates are current. The assistant does not have a verified live readback of those templates.

| Saved-template role | R4 environment value | Expected model files | Cloud evidence |
|---|---|---|---|
| IMAGE | `PP_MODE=image` | Qwen image: 3 | Offline container smoke only |
| VIDEO | `PP_MODE=video` | MiniMax video: 4 | Offline container smoke only |
| BOTH | `PP_MODE=both` | Both: 7 | RunPod startup/models PASS |

For **each** saved R4 template that will be used, check:

1. **Container image:** pin the exact R4 digest above. Avoid `latest` and avoid the R2 tag.
2. **HTTP ports:** `8888` for JupyterLab and `8188` for ComfyUI.
3. **Authentication:** nonempty, privately configured `JUPYTER_PASSWORD` (RunPod Secret if supported); **do not set** `JUPYTER_DISABLE_AUTH=1`. A token or private password must never be committed to this public repository.
4. **Mode:** one exact `PP_MODE` value from the table.
5. **Model sync:** `PP_AUTO_DOWNLOAD_MODELS=1` and **`PP_DOWNLOAD_WORKERS=1`** (sequential, owner-preferred setting).
6. **Storage:** writable mounted `/workspace`; review the actual volume type, lifecycle, capacity, free space, and billed compute/storage rates. Set `PP_STORAGE_REVIEWED=1` **only after the owner genuinely reviews the deployed storage configuration**. Do not assume a network volume is necessary or an ordinary pod volume survives termination.
7. **Container entrypoint:** leave the image's default start command intact. Do not replace it with historical R2 startup commands.

BOTH mode needs approximately **145.324 GiB** of pinned model weights alone, plus transfer headroom, outputs, and any retrieval archive. The prior **300 GiB** plan was **planning headroom**, not proof of an installed/reusable network volume or a purchase requirement. A single model-download worker needs at least about **12 GiB available RAM** per the R4 review gate, and actual resource adequacy must be assessed for each GPU/pod. Ordinary final video production favors the separately approved **96 GB BF16** route, not a smaller test GPU merely because downloads passed.

A provider/saved-template edit must be **saved and read back** before describing a template as updated. **No RunPod template edits are performed by this README.**

## R4 operator commands

The R4 image starts its supervisor, JupyterLab, ComfyUI, and eligible pinned model sync at container startup. When the pod is ready, use **two working terminals**, preferably the RunPod Web Terminal if JupyterLab's built-in terminal does not accept input:

Terminal 1 — detached initialization/staging:

```bash
python3 /opt/pp/ppctl.py init
```

Terminal 2 — read-only monitoring:

```bash
python3 /opt/pp/ppctl.py monitor
```

One-time status (does not loop):

```bash
python3 /opt/pp/ppctl.py monitor --once
```

The `init` command may produce a retrieval snapshot **only while ComfyUI is idle and files are not changing**. The `monitor` command reports model-byte verification, **not** complete production readiness or local retrieval. Re-run `init` after a finished approved episode upload or when retrying an idle archive, then inspect the reported outcome. Never re-download verified models without an actual need.

For the tested 8188 RunPod proxy symptom, first select the **same current proxy URL** in the browser address bar and press **Enter**. Do not disable authentication or blindly reconfigure ComfyUI. If the direct navigation still fails, inspect the current provider and service diagnostics before editing any configuration.

## Before the next paid production session

- Prepare the full Creative-approved episode handoff, actual inputs and versioned compatible workflows **locally**, before starting paid compute.
- Review and confirm the **specific** saved RunPod template, current prices, storage lifecycle, public model accessibility, and the required GPU/memory profile.
- In the ordinary authorized episode session, load the workflow, confirm actual ComfyUI node/socket compatibility and input paths, then perform a **real generation**. A valid static graph check is not inference proof.
- Inspect generated picture, subject identity, action, room geometry and any required native physical sound independently. Keep successful outputs even if audio alone fails; do not silently invent replacement sound.
- Retrieve the real workflow/history/log/output package to the owner computer and **test archive CRC/openability and important media** there before choosing a destructive cloud shutdown. A pod-side archive is not a local readback.
- The owner controls provider **Stop → observe Stopped → Terminate → confirm Gone**. Pod termination and provider billing are not controlled by R4's terminal commands.

## Historical R2 content

This repository's current `main` branch retains the earlier R2 implementation, including its original `.github/workflows/build.yml` and historical `r2` tag target. The former R2 README's instructions to use `PP_DOWNLOAD_WORKERS=3`, ephemeral-only storage, `/opt/pp-monitor.py`, or the R2 base startup do **not** define the working R4 procedure. They must not be copied into new R4 templates.

R4 source, review gates and commands reside in the [R4 candidate branch](https://github.com/BmoreRavens522055/pawlished-pink-comfyui/tree/codex/r4-offline-candidate), not in `main` until a separately reviewed and authorized merge. In particular, consult the candidate's [deployment review gates](https://github.com/BmoreRavens522055/pawlished-pink-comfyui/blob/2ca3cdcdb6323803ec21063610eef8e11ca7b6a0/docs/REVIEW-GATES.md).

**Public-repository safety:** Do not commit Pawlished & Pink episode assets, private reference images, provider credentials, access tokens, or generated customer material. Model weights remain external downloads, not Docker image contents.
