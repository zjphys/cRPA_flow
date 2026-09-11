#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
for test_file in tests/test_batch_workflow.sh tests/test_crpa_workflow.sh tests/test_wannier_workflow.sh tests/test_independent_jobs.sh; do
  printf '\nRunning %s\n' "$test_file"
  bash "$test_file"
done
