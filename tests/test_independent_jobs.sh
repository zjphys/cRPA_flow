#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="$(mktemp -d "${TMPDIR:-/tmp}/version1-independent-jobs-test.XXXXXX")"
trap 'case "$TEST_DIR" in */version1-independent-jobs-test.*) rm -rf -- "$TEST_DIR" ;; esac' EXIT

CASE_DIR="$TEST_DIR/case"
mkdir -p "$CASE_DIR" "$TEST_DIR/mockbin"
cp "$SOURCE_DIR/src/crpa_workflow/resources/workflow.sh" "$CASE_DIR/workflow.sh"
chmod +x "$CASE_DIR/workflow.sh"
cat > "$CASE_DIR/POSCAR" <<'EOF'
Independent job test
1.0
1 0 0
0 1 0
0 0 1
Si
1
Direct
0 0 0
EOF

cat > "$TEST_DIR/mockbin/vaspkit" <<'EOF'
#!/usr/bin/env bash
read -r task
case "$task" in
  103) printf 'ENMAX = 400.0; ENMIN = 250.0 eV\n' > POTCAR ;;
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

cat > "$TEST_DIR/mock_sbatch" <<'EOF'
#!/usr/bin/env bash
printf '%s|%s\n' "$PWD" "$*" >> "$(dirname "$0")/submit-calls"
printf '12345\n'
EOF
chmod +x "$TEST_DIR/mock_sbatch"

cat > "$CASE_DIR/workflow.conf" <<EOF
VASPKIT_BIN="$TEST_DIR/mockbin/vaspkit"
SUBMIT_COMMAND="../mock_sbatch"
RUN_RELAX=yes
EXECUTION_SETUP='export SETUP_VALUE=ready'
declare -A STAGE_COMMANDS=(
  [default]='printf "%s|%s|%s\n" "\$PWD" "\${SLURM_NTASKS:-missing}" "\${SETUP_VALUE:-unset}" > executed'
)
EOF

(
  cd "$CASE_DIR"
  ./workflow.sh prepare
  ./workflow.sh submit
)

for stage in 00_relax 01_scf 02_dos 03_band; do
  job="$CASE_DIR/$stage/job.sh"
  test -x "$job"
  ! grep -F 'workflow.sh' "$job"
  ! grep -F "$CASE_DIR" "$job"
done
grep -F '../00_relax/CONTCAR' "$CASE_DIR/01_scf/job.sh"
grep -F '../01_scf/POSCAR' "$CASE_DIR/02_dos/job.sh"
grep -F '../01_scf/CHGCAR' "$CASE_DIR/03_band/job.sh"

grep -Fx "$CASE_DIR/00_relax|--parsable job.sh" "$TEST_DIR/submit-calls"
grep -Fx "$CASE_DIR/01_scf|--parsable --dependency=afterok:12345 job.sh" "$TEST_DIR/submit-calls"
grep -Fx "$CASE_DIR/02_dos|--parsable --dependency=afterok:12345 job.sh" "$TEST_DIR/submit-calls"
grep -Fx "$CASE_DIR/03_band|--parsable --dependency=afterok:12345 job.sh" "$TEST_DIR/submit-calls"

: > "$TEST_DIR/submit-calls"
(
  cd "$CASE_DIR"
  ./workflow.sh submit --job-name Pu
)
grep -Fx "$CASE_DIR/00_relax|--parsable --job-name=Pu-relax job.sh" "$TEST_DIR/submit-calls"
grep -Fx "$CASE_DIR/01_scf|--parsable --job-name=Pu-scf --dependency=afterok:12345 job.sh" "$TEST_DIR/submit-calls"
grep -Fx "$CASE_DIR/02_dos|--parsable --job-name=Pu-dos --dependency=afterok:12345 job.sh" "$TEST_DIR/submit-calls"
grep -Fx "$CASE_DIR/03_band|--parsable --job-name=Pu-band --dependency=afterok:12345 job.sh" "$TEST_DIR/submit-calls"

: > "$TEST_DIR/submit-calls"
(
  cd "$CASE_DIR"
  ./workflow.sh submit --job-name=Am
)
grep -Fx "$CASE_DIR/01_scf|--parsable --job-name=Am-scf --dependency=afterok:12345 job.sh" "$TEST_DIR/submit-calls"

for invalid_args in "--job-name" "--job-name=" "--unknown"; do
  : > "$TEST_DIR/submit-calls"
  if (cd "$CASE_DIR" && ./workflow.sh submit $invalid_args); then
    printf 'invalid submit arguments unexpectedly succeeded: %s\n' "$invalid_args" >&2
    exit 1
  fi
  test ! -s "$TEST_DIR/submit-calls"
done

(
  cd "$TEST_DIR"
  SLURM_NTASKS=8 bash "$CASE_DIR/00_relax/job.sh"
)
grep -Fx "$CASE_DIR/00_relax|8|ready" "$CASE_DIR/00_relax/executed"

printf 'relaxed POSCAR\n' > "$CASE_DIR/00_relax/CONTCAR"
printf 'stale POSCAR\n' > "$CASE_DIR/01_scf/POSCAR"
(
  cd "$TEST_DIR"
  bash "$CASE_DIR/01_scf/job.sh"
)
cmp "$CASE_DIR/00_relax/CONTCAR" "$CASE_DIR/01_scf/POSCAR"

printf 'completed SCF POSCAR\n' > "$CASE_DIR/01_scf/POSCAR"
printf 'completed SCF CHGCAR\n' > "$CASE_DIR/01_scf/CHGCAR"
for stage in 02_dos 03_band; do
  printf 'stale POSCAR\n' > "$CASE_DIR/$stage/POSCAR"
  printf 'stale CHGCAR\n' > "$CASE_DIR/$stage/CHGCAR"
  (
    cd "$TEST_DIR"
    bash "$CASE_DIR/$stage/job.sh"
  )
  cmp "$CASE_DIR/01_scf/POSCAR" "$CASE_DIR/$stage/POSCAR"
  cmp "$CASE_DIR/01_scf/CHGCAR" "$CASE_DIR/$stage/CHGCAR"
done

NO_RELAX_DIR="$TEST_DIR/no-relax-case"
mkdir -p "$NO_RELAX_DIR"
cp "$CASE_DIR/workflow.sh" "$NO_RELAX_DIR/workflow.sh"
cp "$CASE_DIR/POSCAR" "$NO_RELAX_DIR/POSCAR"
chmod +x "$NO_RELAX_DIR/workflow.sh"
cat > "$NO_RELAX_DIR/workflow.conf" <<EOF
VASPKIT_BIN="$TEST_DIR/mockbin/vaspkit"
RUN_RELAX=no
GENERATE_BANDS=no
declare -A STAGE_COMMANDS=(
  [default]='printf "%s\n" "\$PWD" > executed'
)
EOF
(
  cd "$NO_RELAX_DIR"
  ./workflow.sh prepare --no-relax
)
test ! -e "$NO_RELAX_DIR/00_relax"
! grep -F '../00_relax/CONTCAR' "$NO_RELAX_DIR/01_scf/job.sh"
(
  cd "$TEST_DIR"
  bash "$NO_RELAX_DIR/01_scf/job.sh"
)
grep -Fx "$NO_RELAX_DIR/01_scf" "$NO_RELAX_DIR/01_scf/executed"

# Slurm executes a spool copy, with submission from the stage directory.
mkdir -p "$TEST_DIR/spool"
cp "$NO_RELAX_DIR/01_scf/job.sh" "$TEST_DIR/spool/slurm_script"
(cd "$TEST_DIR" && SLURM_JOB_ID=42 SLURM_SUBMIT_DIR="$NO_RELAX_DIR/01_scf" bash "$TEST_DIR/spool/slurm_script")
grep -Fx "$NO_RELAX_DIR/01_scf" "$NO_RELAX_DIR/01_scf/executed"
if SLURM_JOB_ID=42 SLURM_SUBMIT_DIR="$TEST_DIR/spool" bash "$TEST_DIR/spool/slurm_script"; then
  echo 'Unowned Slurm directory unexpectedly accepted' >&2; exit 1
fi

# Help and extra arguments must never invoke a simulation or submission.
cat >> "$NO_RELAX_DIR/workflow.conf" <<'EOF'
STAGE_COMMANDS[default]='touch should-not-run'
EOF
for command in doctor prepare run submit execute status run-wannier submit-wannier run-crpa submit-crpa; do
  (cd "$NO_RELAX_DIR" && ./workflow.sh "$command" --help >/dev/null)
  if (cd "$NO_RELAX_DIR" && ./workflow.sh "$command" --unknown >/dev/null 2>&1); then
    echo "Unknown argument accepted: $command" >&2; exit 1
  fi
done
test -z "$(find "$NO_RELAX_DIR" -name should-not-run -print)"

# Setup failures and failed pipelines stop both direct and generated jobs.
for failure in setup pipeline command; do
  case "$failure" in
    setup) printf "\nEXECUTION_SETUP='false'\nSTAGE_COMMANDS[default]='touch should-not-run'\n" >> "$NO_RELAX_DIR/workflow.conf" ;;
    pipeline) printf "\nEXECUTION_SETUP=''\nSTAGE_COMMANDS[default]='false | cat; touch should-not-run'\n" >> "$NO_RELAX_DIR/workflow.conf" ;;
    command) printf "\nSTAGE_COMMANDS[default]='false; touch should-not-run'\n" >> "$NO_RELAX_DIR/workflow.conf" ;;
  esac
  (cd "$NO_RELAX_DIR" && ./workflow.sh prepare --force --no-relax >/dev/null)
  if (cd "$NO_RELAX_DIR" && ./workflow.sh execute 01_scf); then
    echo "Direct execution ignored $failure failure" >&2; exit 1
  fi
  if bash "$NO_RELAX_DIR/01_scf/job.sh"; then
    echo "Generated job ignored $failure failure" >&2; exit 1
  fi
  test ! -e "$NO_RELAX_DIR/01_scf/should-not-run"
done

# Configuration is explicitly forwarded; an explicit CLI override wins.
cat > "$NO_RELAX_DIR/postprocess.py" <<'PY'
import argparse
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument('--root')
p.add_argument('--vaspkit')
a = p.parse_args()
Path(a.root, 'selected-vaspkit').write_text(a.vaspkit)
PY
(cd "$NO_RELAX_DIR" && ./workflow.sh postprocess)
grep -Fx "$TEST_DIR/mockbin/vaspkit" "$NO_RELAX_DIR/selected-vaspkit"
(cd "$NO_RELAX_DIR" && ./workflow.sh postprocess --vaspkit /explicit/vaspkit)
grep -Fx /explicit/vaspkit "$NO_RELAX_DIR/selected-vaspkit"

printf '\nSTAGE_COMMANDS[default]="exit 99"\n' >> "$CASE_DIR/workflow.conf"
mv "$CASE_DIR/workflow.sh" "$CASE_DIR/workflow.sh.saved"
mv "$CASE_DIR/workflow.conf" "$CASE_DIR/workflow.conf.saved"
RELOCATED="$TEST_DIR/relocated-case"
mv "$CASE_DIR" "$RELOCATED"
(
  cd "$TEST_DIR"
  SLURM_NTASKS=16 bash "$RELOCATED/03_band/job.sh"
)
grep -Fx "$RELOCATED/03_band|16|ready" "$RELOCATED/03_band/executed"
cmp "$RELOCATED/01_scf/POSCAR" "$RELOCATED/03_band/POSCAR"
cmp "$RELOCATED/01_scf/CHGCAR" "$RELOCATED/03_band/CHGCAR"

printf 'independent job scripts functional test passed\n'
