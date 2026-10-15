#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
exec python3 /opt/pp/pp_runtime.py
