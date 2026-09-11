#!/usr/bin/env bash
# Run with the absolute path to a freshly installed vasp-workflow command.
set -euo pipefail
workflow="${1:?Pass the installed vasp-workflow executable}"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/installed-workflow.XXXXXX")"
trap 'case "$test_root" in */installed-workflow.*) rm -rf -- "$test_root" ;; esac' EXIT
unset PYTHONPATH WORKFLOW_CONFIG WORKFLOW_ROOT WORKFLOW_PACKAGE WORKFLOW_CODE_DIR
mkdir -p "$test_root/mockbin" "$test_root/structures/nested"
cat > "$test_root/structures/nested/POSCAR" <<'EOF'
Installed package test
1.0
1 0 0
0 1 0
0 0 1
Si
1
Direct
0 0 0
EOF
cat > "$test_root/mockbin/vaspkit" <<'EOF'
#!/usr/bin/env bash
read -r task
case "$task" in
  103) printf 'ENMAX = 400.0; ENMIN = 250.0 eV\n' > POTCAR ;;
  102) read -r centering; read -r kpr; printf 'Gamma test\n0\nGamma\n2 2 2\n0 0 0\n' > KPOINTS ;;
  303) printf 'Path test\n10\nLine-mode\nReciprocal\n0 0 0 ! G\n0.5 0 0 ! X\n' > KPATH.in ;;
  *) exit 2 ;;
esac
EOF
cat > "$test_root/mockbin/sbatch" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$SUBMISSION_LOG"
printf '12345\n'
EOF
chmod +x "$test_root/mockbin/vaspkit" "$test_root/mockbin/sbatch"
export PATH="$test_root/mockbin:$PATH"
export SUBMISSION_LOG="$test_root/submissions"
cd "$test_root"
"$workflow" --version
"$workflow" --help
"$workflow" init 'case with spaces' --poscar structures/nested/POSCAR --profile local
cd 'case with spaces'
"$workflow" doctor prepare
"$workflow" doctor submit
"$workflow" prepare --no-relax
test -s 01_scf/INCAR
grep -Fx 'ENCUT = 600' 01_scf/INCAR
test ! -e 00_relax
"$workflow" submit --job-name 'installed-test'
test "$(wc -l < "$SUBMISSION_LOG")" -eq 3
grep -F -- '--dependency=afterok:12345' "$SUBMISSION_LOG"
"$workflow" status
! grep -F 'workflow.sh' 01_scf/job.sh
if "$workflow" --config "$test_root/missing.conf" prepare; then
  printf 'Missing configuration should fail.\n' >&2; exit 1
fi
if "$workflow" init . --poscar ../structures/nested/POSCAR; then
  printf 'Initialization should not overwrite a case.\n' >&2; exit 1
fi
"$workflow" postprocess --help
"$workflow" rank-bands --help
"$workflow" prepare-wannier --help
"$workflow" prepare-crpa --help
test ! -e 04_wann
test ! -e 05_crpa
"$workflow" --config "$PWD/workflow.conf" batch --mode prepare ../structures ../batch
test -s ../batch/nested/workflow.sh
test ! -e ../batch/nested/prepare_wannier.py
(cd ../batch/nested && bash workflow.sh status)
printf 'Installed package integration test passed.\n'
