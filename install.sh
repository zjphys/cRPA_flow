#!/usr/bin/env bash
# Install into a user-owned virtual environment; no root access is needed.
set -euo pipefail
source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == --help ]]; then
  printf 'Usage: bash install.sh [VENV_DIRECTORY]\nEnvironment: PYTHON_BIN, PIP_NO_INDEX, PIP_FIND_LINKS\n'
  exit 0
fi
(( $# <= 1 )) || { printf 'ERROR: expected at most one installation directory.\n' >&2; exit 2; }
venv_dir="${1:-$HOME/.local/share/crpa-workflow/venv}"
if [[ -e "$venv_dir" ]]; then
  printf 'ERROR: destination already exists; choose a new directory: %s\n' "$venv_dir" >&2
  exit 1
fi
if "${PYTHON_BIN:-python3}" -c 'import venv, ensurepip' 2>/dev/null; then
  "${PYTHON_BIN:-python3}" -m venv "$venv_dir"
  "$venv_dir/bin/python" -m pip install "$source_dir[plot]"
elif "${PYTHON_BIN:-python3}" -m pip --help 2>/dev/null | grep -q -- --python; then
  # Some clusters provide pip but omit the standard ensurepip module.
  "${PYTHON_BIN:-python3}" -m venv --without-pip "$venv_dir"
  "${PYTHON_BIN:-python3}" -m pip --python "$venv_dir/bin/python" install pip "$source_dir[plot]"
else
  printf 'ERROR: this Python needs venv and either ensurepip or pip with --python support. Use a cluster Python environment with pip.\n' >&2
  exit 1
fi
"$venv_dir/bin/crpa-workflow" --version
printf '\nActivate with: source %q/bin/activate\n' "$venv_dir"
