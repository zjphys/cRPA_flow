#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="$(mktemp -d "${TMPDIR:-/tmp}/version1-batch-test.XXXXXX")"
trap 'case "$TEST_DIR" in */version1-batch-test.*) rm -rf -- "$TEST_DIR" ;; esac' EXIT

mkdir -p "$TEST_DIR/structures/nested_case" "$TEST_DIR/mockbin"
cat > "$TEST_DIR/structures/POSCAR_flat.vasp" <<'EOF'
Batch test
1.0
1 0 0
0 1 0
0 0 1
Si
1
Direct
0 0 0
EOF
cp "$TEST_DIR/structures/POSCAR_flat.vasp" "$TEST_DIR/structures/nested_case/POSCAR"

cat > "$TEST_DIR/mockbin/vaspkit" <<'EOF'
#!/usr/bin/env bash
read -r task
case "$task" in
  103) printf 'ENMAX = 500.0; ENMIN = 300.0 eV\n' > POTCAR ;;
  102)
    read -r centering
    read -r kpr
    [[ "$centering" == 2 ]] || exit 3
    printf 'Mock Gamma KPR %s\n0\nGamma\n4 4 4\n0 0 0\n' "$kpr" > KPOINTS
    ;;
  303)
    cat > KPATH.in <<'KPATH'
Mock path
20
Line-mode
Reciprocal
0 0 0 ! G
0.5 0 0 ! X
KPATH
    ;;
  *) exit 2 ;;
esac
EOF
chmod +x "$TEST_DIR/mockbin/vaspkit"

cp "$SOURCE_DIR/src/vasp_workflow/resources/defaults.conf" "$TEST_DIR/workflow.conf"
printf '\nSBATCH_NODES=4\n' >> "$TEST_DIR/workflow.conf"
PYTHONPATH="$SOURCE_DIR/src${PYTHONPATH:+:$PYTHONPATH}" \
PATH="$TEST_DIR/mockbin:$PATH" \
  python3 -m vasp_workflow --config "$TEST_DIR/workflow.conf" batch --mode prepare --no-relax \
  "$TEST_DIR/structures" "$TEST_DIR/calculations"

test -s "$TEST_DIR/calculations/flat/01_scf/INCAR"
test -s "$TEST_DIR/calculations/flat/01_scf/KPOINTS"
test -s "$TEST_DIR/calculations/flat/02_dos/KPOINTS"
test -s "$TEST_DIR/calculations/flat/01_scf/job.sh"
test -s "$TEST_DIR/calculations/flat/02_dos/job.sh"
test ! -e "$TEST_DIR/calculations/flat/prepare_wannier.py"
test ! -e "$TEST_DIR/calculations/flat/wannier_windows.py"
test ! -e "$TEST_DIR/calculations/flat/prepare_crpa.py"
test -s "$TEST_DIR/calculations/nested_case/03_band/KPOINTS"
grep -Fx 'KPAR = 4' "$TEST_DIR/calculations/flat/01_scf/INCAR"
grep -Fx 'Mock Gamma KPR 0.02' "$TEST_DIR/calculations/flat/01_scf/KPOINTS"
grep -Fx 'Mock Gamma KPR 0.02' "$TEST_DIR/calculations/flat/02_dos/KPOINTS"
! grep -Eq '^[[:space:]]*(KSPACING|KGAMMA)[[:space:]]*=' "$TEST_DIR/calculations/flat/01_scf/INCAR"
test -f "$TEST_DIR/calculations/flat/.batch-workflow-case"
! grep -F 'workflow.sh' "$TEST_DIR/calculations/flat/01_scf/job.sh"
! grep -F '../00_relax/CONTCAR' "$TEST_DIR/calculations/flat/01_scf/job.sh"
grep -F '../01_scf/CHGCAR' "$TEST_DIR/calculations/flat/02_dos/job.sh"

(cd "$TEST_DIR/calculations/flat" && bash workflow.sh status)
test -s "$TEST_DIR/calculations/flat/.workflow-version"
printf 'batch functional test passed\n'
