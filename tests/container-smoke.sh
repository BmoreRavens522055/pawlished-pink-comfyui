#!/usr/bin/env bash
set -Eeuo pipefail
IMAGE=${1:?candidate image required}
mkdir -p container-evidence
NAME=pp-r4-smoke-$$
cleanup() {
  docker logs "$NAME" > "container-evidence/${MODE:-auth}-stdout.log" 2>&1 || true
  docker cp "$NAME":/workspace/PP_RunPod_Setup "container-evidence/${MODE:-auth}-state" || true
  docker rm -f "$NAME" >/dev/null 2>&1 || true
}
trap cleanup EXIT
# Missing authentication must exit before any child service starts.
docker run --name "$NAME" -e PP_STORAGE_REVIEWED=1 "$IMAGE" && exit 1
cleanup
# Synthetic credential only. Never deploy, download weights or queue inference.
for MODE in image video both; do
  docker run -d --name "$NAME" -e JUPYTER_PASSWORD=synthetic-ci-token -e PP_STORAGE_REVIEWED=1 -e PP_AUTO_DOWNLOAD_MODELS=0 -e PP_CPU_SMOKE=1 -e PP_MODE="$MODE" "$IMAGE"
  for i in $(seq 1 150); do
    phase=$(docker exec "$NAME" python3 -c 'import json;print(json.load(open("/workspace/PP_RunPod_Setup/startup_state.json"))["phase"])' 2>/dev/null || true)
    if [[ "$phase" == ACTION_REQUIRED ]]; then break; fi
    if [[ "$phase" == FAILED ]]; then exit 1; fi
    sleep 1
  done
  [[ "$phase" == ACTION_REQUIRED ]]
  docker exec "$NAME" python3 /opt/pp/ppctl.py monitor --once > "container-evidence/$MODE-monitor.txt"
  docker exec -i "$NAME" /opt/pp-jupyter/bin/python - <<'PY'
import json,urllib.request,urllib.error
url='http://127.0.0.1:8888/api/contents'
try:
    urllib.request.urlopen(url)
except urllib.error.HTTPError as e:
    assert e.code in (401,403)
else:
    raise AssertionError('unauthenticated API exposed')
headers={'Authorization':'token synthetic-ci-token','Content-Type':'application/json'}
data=json.dumps({'type':'file','format':'text','content':'container-upload-readback'}).encode()
assert urllib.request.urlopen(urllib.request.Request(url+'/smoke.txt',headers=headers,data=data,method='PUT')).status==201
with urllib.request.urlopen(urllib.request.Request(url+'/smoke.txt',headers=headers)) as r:
    assert json.load(r)['content']=='container-upload-readback'
PY
  docker stop -t 20 "$NAME"
  [[ $(docker inspect -f '{{.State.ExitCode}}' "$NAME") == 0 ]]
  cleanup
done
trap - EXIT
