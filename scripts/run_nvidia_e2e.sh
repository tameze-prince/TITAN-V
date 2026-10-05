#!/usr/bin/env bash
set -euo pipefail

: "\${TITAN_NVIDIA_API_KEY:?Set TITAN_NVIDIA_API_KEY to a newly generated NVIDIA API key}"

export TITAN_E2E_REAL=1
export TITAN_MODEL_PROVIDER=nvidia
export TITAN_E2E_KEEP_WORKSPACE=1

run_id="$(date +%Y%m%d-%H%M%S)"
export TITAN_E2E_WORKSPACE_ROOT=".titan/e2e-workspaces/\${run_id}"

mkdir -p .titan/logs "\${TITAN_E2E_WORKSPACE_ROOT}"
log_file=".titan/logs/nvidia-e2e-\${run_id}.log"

echo "TITAN NVIDIA E2E"
echo "workspace: \${TITAN_E2E_WORKSPACE_ROOT}"
echo "log: \${log_file}"

pytest -q tests/e2e/test_real_project_execution.py -vv 2>&1 | tee "\${log_file}"

echo
echo "Evidence workspace:"
find "\${TITAN_E2E_WORKSPACE_ROOT}" -maxdepth 5 -type f -print
