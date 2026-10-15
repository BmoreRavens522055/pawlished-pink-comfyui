# Remaining decisions and exact template review

No paid pod, network volume, model inference, template modification, shutdown or release publication is authorized by this engineering work. Offline unknowns are not an excuse for a separate paid canary.

| Setting | Required review value |
|---|---|
| Image | R4 **built and container-tested immutable image digest**; do not use an invented digest or overwrite R2 |
| Entry point / start command | No provider override; image runs NVIDIA entrypoint then `/opt/pp-start.sh` |
| Profile | IMAGE `PP_MODE=image`; VIDEO `PP_MODE=video`; BOTH `PP_MODE=both` |
| Jupyter | RunPod Start Jupyter notebook ON; nonempty injected `JUPYTER_PASSWORD`; `JUPYTER_DISABLE_AUTH` absent/false; never paste token into logs/docs |
| Ports | HTTP 8888 and HTTP 8188 |
| Storage | Persistent writable `/workspace`; reviewed volume type, lifecycle, datacenter, capacity and current running/stopped/storage price |
| Storage attestation | `PP_STORAGE_REVIEWED=1` only after actual saved-template/mount review; it is an operator declaration, not machine proof |
| Models | `PP_AUTO_DOWNLOAD_MODELS=1`; `PP_DOWNLOAD_WORKERS=1` default. Existing complete/openable files work with auto=0 |
| Resource budget | At least 12 GiB *available* RAM for one download; +8 GiB per additional admitted worker, max 3. Conservative admission, not measured peak guarantee. No low-memory trial recommended |
| GPU | Ordinary owner-authorized 96 GB BF16 production route per authority; CPU mode only for offline service tests |
| Workspace capacity | Models: image ~30.212 GiB, video ~115.111 GiB, both ~145.324 GiB. Add 30 GiB sync reserve, inputs, temporary/output budget and a second copy for retrieval ZIP; e.g. 300 GiB is planning headroom, not an approved purchase |
| Restart / billing | Read actual provider behavior. Wrapper failure does not stop billing; no indefinite unattended deployment or automatic provider action |
| Private material | Approved ZIPs/assets stay on private workspace; never in image/repo. Public pinned weights download directly on pod |

Free engineering build and integrated container checks now pass; see RESULTS.md. Before production: review/authorize any immutable candidate publication and retain its resulting registry digest; review candidate and saved templates; prepare actual complete approved primary/fallback workflows and inputs. No saved-template access is configured here, so template readback is NOT RUN.

During the next normally authorized real episode only: confirm RunPod browser Jupyter login/terminal/upload, direct 8188 navigation, selected full HF transfers, mounted storage disposition and exact graph/reference/audio wiring. Capture startup/model/Comfy logs and sanitized template facts, prompt history and outputs. Attempt the assumed MULTI/native-physical-sound primary under ordinary Technical GO; do not require a separate paid qualification session. If a material sound/reference capability fails, retain accepted picture and present the concrete fallback choice; never silently replace sound or conditioning.

The owner's actual runtime budget and current provider rates are not available. No numeric spend cap is invented. Before ordinary deployment the owner chooses current cost/maximum session duration and the action on failure. No script exits or alerts promise stopped billing.

Rollback: published `:r2` was not changed. Preserve its registry manifest and original source archive. R2 is a historical partly exercised candidate, **not a safe production fallback** for the startup defects. Do not automatically redeploy it. Source rollback is `git switch` to the baseline commit in a separate checkout, or extract the preserved R2 ZIP; this is tested by byte comparison. No saved-template rollback or prior approved episode graph is claimed tested when not supplied. Any runtime image rollback requires owner decision and verified retained digest/configuration.
