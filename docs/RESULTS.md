# R4 verification record

Candidate: R4.0.0-rc1. Draft PR: https://github.com/BmoreRavens522055/pawlished-pink-comfyui/pull/1

| Verification | Result | Evidence and scope |
|---|---|---|
| Live source versus supplied R2 | PASS | Ten archived source files match baseline `8f3a38d`; published R2 manifest shares inspected base layers |
| Original R3 suite reproduction | PASS (narrow) | 11 original tests; these do not establish runtime correctness |
| R4 local behavioral suite | PASS | 32 tests, 55.558 s, no skips; retained before interruption |
| Real local Jupyter | PASS | Login/token enforcement, upload/readback, terminals, forwarded Host and cross-origin rejection |
| Pinned ComfyUI CPU supervision | PASS | IMAGE/VIDEO/BOTH, services before model failure, SIGTERM, unexpected exit, detached init/retrieval; no inference |
| Native HF progress and local transfer | PASS | HF/Xet reporting distinguishes reconstruction vs wire bytes; 4 MiB local HTTP resume uses actual downloader |
| Real production weights | NOT RUN | No full HF transfers or inference; exact pins preserved |
| Graph sockets | PASS (static scope) | Actual pinned schemas; missing model choices fail; no supplied production shot/fallback JSON |
| Local Docker build | FAIL — environment capacity | 32 GB filesystem exhausted while fetching/extracting base; original failure log retained |
| First public CI offline gate | FAIL — test cleanup | Assertions passed; Jupyter teardown timeout with autodetected Julia process. Container correctly skipped |
| Corrected local Jupyter test | PASS | 4 tests after disabling unrelated language-server autodetection and bounding process-group cleanup |
| Corrected public CI offline gate | PASS | Run 38812402901: 29 passed, 3 CPU-ComfyUI tests skipped; no failures |
| Actual Docker build | PASS | Run 38812402901, tested source `9957fd50862c9edcec8eef9077d9cff5e0c5cbb5`; dependency checks passed |
| Actual image smoke tests | PASS | Missing-auth refusal; IMAGE/VIDEO/BOTH startup, authenticated upload/readback, graceful shutdown; no weights/GPU/inference |
| RunPod browser/proxy/storage/template | NOT RUN | No deployment or saved-template mutation authorized |
| Production native audio/MULTI | NOT RUN | Ordinary next authorized production evidence, not a separate paid canary |
| Owner-local output readback / shutdown | NOT RUN | Runbook requires real retrieved archive/media checks before owner shutdown |

Preserved development checkpoint `d8f4e4c`; subsequent local commits contain CI and Jupyter cleanup corrections. GitHub commit IDs differ because the connector created the same source trees through Git objects. Exact tree equivalence is checked independently.

No production label, provider billing cutoff, successful local retrieval, or deployable published R4 digest is implied by offline results. The only published image identity verified here is unchanged R2: `ghcr.io/bmoreravens522055/pawlished-pink-comfyui@sha256:463ce9b3c1e0cdf20674094a653d6fef59342cf3822209b2280518379bedd660` (historical, not production approval).

## Built image and retained evidence

Built image ID (config digest): `sha256:7caf863122addd1a4d917de2aae6a7fe50df29fc22fffeb0882898e3a675bfa5`. This is **not a published registry digest**. The temporary CI runner built and exercised the image; no image was pushed, exported as a retained image archive, or deployed. Publication requires a separately authorized build/publish step and exact resulting registry digest.

Successful run: https://github.com/BmoreRavens522055/pawlished-pink-comfyui/actions/runs/38812402901

Raw container logs/states and `image-inspect.json`: https://github.com/BmoreRavens522055/pawlished-pink-comfyui/actions/runs/38812402901/artifacts/12008903974 (GitHub retention until 2026-10-22). GitHub reports ZIP digest `eb95637cd6ce6039f9bab0d0d8e20c9be0e4f472d0d1573ba2e04be37ee4390d`.

Full CI job logs were retrieved through the connector and retained in the engineering package. The connector also retrieved the raw artifact to File Service, but copying that ZIP into this workspace was blocked by its network proxy (403 for the File Service host). No workaround bypassed the policy. Consequently raw artifact CRC and image-inspect JSON readback in this workspace are **NOT RUN**; use the attached CI artifact for those files. This retrieval limitation does not change the completed GitHub build/smoke results.

Final label: **CODE-CORRECTED / OFFLINE-TESTED / BUILT / CONTAINER-SMOKE-TESTED**. Not RunPod-runtime-tested, production-ready or approved. Remaining real-provider/episode checks are listed above and in `REVIEW-GATES.md`.
