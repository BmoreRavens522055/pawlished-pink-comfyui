# Independent evidence and decisions — 2026-10-15

Live GitHub HEAD independently retrieved through GitHub connector and `git ls-remote`: `8f3a38d0ace7f81f7896e07d3746fa9bb9e2aa65`. Clean existing checkout matches that commit. Engineering branch: `codex/r4-offline-candidate`. Supplied R2/R3 archives and documents were unpacked separately under `/workspace/r4-evidence`; no historical source was changed.

| Issue | Classification and primary evidence | R4 disposition |
|---|---|---|
| ComfyUI waits behind model downloads | Confirmed source cause: R2 shell executes sync before final exec | Start ComfyUI/Jupyter before model sync; distinguish service and model states |
| Historical Jupyter failed to start | Observed report; exact cause unknown, original service logs absent | Deterministic supervised JupyterLab, prelaunch auth checks, redacted logs, authenticated API checks |
| Actual base launch | Inspected registry config/layer, not inferred from current upstream | Pin amd64 base digest; retain NVIDIA entrypoint; avoid base fan-out |
| Base failure path | Actual `/start.sh` has `set -e`, runs nginx before Jupyter, and backgrounds Jupyter without verifying it | These can explain failures but do not establish the lost pod's cause |
| Base origin policy | Actual launcher passes `--ServerApp.allow_origin=*` | Explicit same-origin Jupyter config; no unauthenticated shortcut |
| Cross-site 403 | Pinned ComfyUI middleware explicitly rejects `Sec-Fetch-Site: cross-site`, including document GET | Preserve security; direct-address navigation is supported operator path. R3 patch not adopted |
| Nonpersistent outputs | R2 launch has no explicit persistent data directory flags; no actual data loss proven | Explicit `/workspace/ComfyUI/{input,output,user,temp}` flags; save mount evidence, require template declaration without pretending it proves storage lifecycle |
| R3 auth ordering | Confirmed archived shell starts base before auth preflight | Auth validation before any service; executable prevention tests |
| R3 readiness | Login redirect/HTTP response was insufficient proof | Unauthenticated contents denied plus authenticated contents/terminals; offline login/upload/terminal tests; external browser still unknown |
| R3 readiness wall time | Repeated long requests amplify timeout | Monotonic 120-second startup budget, bounded 2-second local calls; at most current probe calls add a few seconds |
| Existing files with auto-download disabled | R3 always blocks | Always validate selected existing weights first; missing files fail without network when disabled |
| Prior `-9` | Observed process exit, OOM hypothesis only | Cgroup/host available-memory admission, default one worker, no high-performance Xet; record actual exit without causal invention |
| Progress | R2 has only total network RX; accepted old monitor estimated per-file percent from that RX | Native HF reconstruction bytes and separate Xet transfer callback; percent never derives from wire totals |
| File validation | Historical byte counts do not prove tensor openability or inference | Exact size plus safetensors metadata opening, no giant tensor allocation/full-weight SHA loop |
| ZIP intake | R2/R3 lack complete safe intake | CRC-checked transactional single-root extraction; no traversal/links/duplicates/conflict overwrite; required directories filled |
| Download lifetime | R2 lacks bounded stall/deadline and worker cleanup | Separate worker processes, explicit deadlines, status/exit reporting, termination and resumable staging |
| Mutable publication | R2 workflow writes `:r2`, R3 writes `:r3` after weak checks | Candidate CI has no package-write permission/push path; release publication is a separate reviewed action |
| Retrieval | No historical complete archive/local readback evidence | Prepared snapshot includes outputs/workflows/history/logs with pod-side CRC; local media/CRC verification remains an owner action |

Base digest: `runpod/pytorch@sha256:4d1721e62b56d345c83b4fd6090664be6daf9312caab5b2e76f23d8231941851` (linux/amd64). Config: NVIDIA entrypoint + CMD `/start.sh`. The actual launcher was extracted from layer `sha256:4eab779129b12baf6aa7f280a550d23f7d824cff44a965c419b5c13e728ad01e`. Evidence directory contains manifests/config and extracted launcher. This is direct registry evidence; it cannot reconstruct deleted pod environment or service logs.

ComfyUI pin remains `6b747c0428c343e1417219641db93a4fb7cb69ae`; VHS remains `4d907bee61e92c2e65af3bd6383a4e4d356126d1`. Seven model names, byte counts and HF repository revisions remain unchanged in `models.json`. The current user request expressly includes Qwen IMAGE/BOTH; older Technical references retire Qwen Image. R4 preserves the requested technical profiles without promoting a retired creative workflow. That scope distinction must accompany any production routing decision.

Governing references read: RunPod Production Reference lifecycle/intake/model/retrieval sections; Technical OS cloud execution, graph provenance, model acquisition and hub boundaries; Technical Runtime exact versions/paths and assumed primary; Technical Model MiniMax multireference/native physical sound. No creative prompt, canon, approval, conditioning intent or actual episode file was changed. No supplied approved shot graph exists in this engineering bundle; schema compatibility can be inspected, but a production graph or proven fallback cannot be reconstructed from node availability alone.
