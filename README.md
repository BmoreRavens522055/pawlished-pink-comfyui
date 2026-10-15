# Pawlished & Pink R4.0.0-rc1

Review candidate, not production-approved. No paid deployment or inference has been performed. See `docs/RESULTS.md` for the actual test/build results, `docs/EVIDENCE.md` for causes versus unknowns, and `docs/REVIEW-GATES.md` before any deployment. R2 and the supplied R3 evidence remain unchanged.

## Two locally saved commands

After this candidate has passed its image gate and the owner has authorized deployment, terminal one:

```sh
python3 /opt/pp/ppctl.py init
```

Terminal two:

```sh
python3 /opt/pp/ppctl.py monitor
```

Exact one-line TXT copies are in `commands/`. These commands are **for an R4 image containing `/opt/pp`**, not R2 or an arbitrary RunPod image. No installer, token search or model upload is needed. Closing either terminal does not stop services, downloads or detached intake. Reuse init after an upload, to explicitly retry failed model sync, and when ready to retrieve an idle session. Monitor makes no changes.

## One-page operator runbook

1. Before paid time, Technical supplies the approved episode ZIP and compatible complete shot workflows. Review the saved IMAGE/VIDEO/BOTH template against `docs/REVIEW-GATES.md`; do not change templates or deploy this unbuilt/unapproved candidate from this README. Obtain normal episode authorization and current price/budget. No separate paid canary is prescribed.
2. Once the image and template gates pass, deploy **one** approved pod with persistent `/workspace`, HTTP 8888 and 8188, and RunPod **Start Jupyter notebook** enabled. Boot automatically starts authenticated normal JupyterLab and ComfyUI, then selected pinned model sync. Run the two commands above in two terminals. Read phase, errors and next action; local APIs ready is not production/graph approval.
3. Open normal JupyterLab from RunPod Connect. The token comes from RunPod's configured Jupyter setting. Upload the complete approved ZIP into **`/workspace/uploads/`** and wait for the browser upload to finish. Repeat terminal-one init. It preserves the one Episode-ID root under **`/workspace/ComfyUI/input/<Episode-ID>/`**, fills standard empty folders, refuses conflicts and never rewrites approved JSON or filenames. Follow-on changes use a new versioned root; this candidate does not merge conflicting revisions.
4. Open the current 8188 URL directly in the browser address bar. If RunPod's cross-site link returns 403, directly navigate/reload that same URL. Core origin checks are unchanged. Load the approved workflow from its episode `JSON/Cloud` folder. API JSON receives a read-only current-schema check; UI JSON still needs native loading. Referenced input paths must already be `<Episode-ID>/Pics/...` relative to ComfyUI input. A package with incompatible paths is reported, never silently rewritten. Technical resolves an affected workflow before paid use; owner does not rewire nodes.
5. After services and models pass, ordinary Technical GO and current graph/reference/audio checks govern the authorized real episode. Queue heavy inference serially. This package never queues inference. ComfyUI input/output/user/temp are explicitly under `/workspace/ComfyUI/`. Storage is declared by reviewed template, not proven persistent by a mount-point heuristic. Record actual native-audio/MULTI results only after actual production.
6. At idle queue, repeat init. It stages any new upload and produces an uncompressed, CRC-read-back ZIP in **`/workspace/retrieval/`**, including episode inputs/JSON, outputs, user workflows, redacted logs, current history and node schema. Allow space for the additional archive. Monitor shows the exact archive path and failures. Do not change files or queue work during archiving. Download it using Jupyter. On the owner computer, open/test ZIP CRC and important media (picture, duration and required audio), confirm required JSON and accepted outputs exist, and retain the original approved ZIP. **Pod-side CRC is not proof of local retrieval.** Keep cloud originals until local readback passes.
7. Only after verified local retrieval and owner shutdown action: **Stop → observe Stopped → Terminate → confirm Gone** in the actual RunPod UI. Review remaining volume/storage charges separately; never delete persistent storage automatically. A script exit, FAILED or ACTION_REQUIRED does not stop provider billing.

If a startup/download failure cannot be resolved immediately by the prepared init retry, preserve available evidence and stop compute promptly through the owner-controlled provider workflow. Do not spend another session troubleshooting. No process here can promise a provider billing cutoff or safely authorize termination. Services remain available after model failures; fatal service failure stops the supervisor and may trigger provider restart policy.

## Engineering

`python -m unittest discover -s tests -v` after installing `tests/requirements.txt`. Real supervisor tests additionally use `PP_TEST_COMFY_DIR` and `PP_TEST_COMFY_PY` for the pinned CPU installation; no model inference. `tests/container-smoke.sh IMAGE` exercises the actual built image without GPU or downloads. CI has read-only permissions, no login, no push and no production tags; container build is manual dispatch after offline tests. A public build may still consume account CI allowance; no remote workflow was dispatched here.

The R4 wrapper deliberately replaces the base `/start.sh` service fan-out with supervised Jupyter/ComfyUI. It retains NVIDIA entrypoint initialization but does not launch nginx, base pre-start hooks or SSH. Normal Jupyter terminals are supported and tested; SSH-dependent deployments are outside this candidate's supported interface. Jupyter's token remains authenticated, CORS/XSRF protections remain enabled, and token-bearing runtime files live outside the archive tree.
