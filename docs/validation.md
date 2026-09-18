# Candidate validation record — 1.1.0

## Empty-array compatibility fix — 2026-09-18

- Reproduced `options[@]: unbound variable` with the unpatched backend using
  an isolated Bash 4.3.30 runtime; the new cRPA regression test fails before the fix.
- After the fix, all 22 submission tests pass on Bash 4.3.30 and Bash 5.2.21.
  They cover empty submit/query options, exact argument boundaries, active-job
  reuse, accounting queries and explicit resubmission.
- All four Shell integration suites pass on Bash 4.3.30, including explicit
  Wannier `--kpr` overrides. Scheduler calls are mocked; no real jobs were submitted.
- To exercise an older Bash, put its `bin` directory first in `PATH` when running
  `python -B -m unittest discover -s tests -p test_submission_safety.py` and
  `bash tests/run_shell_tests.sh`. This selects it for child Bash invocations too.

## Submission reliability checks — 2026-09-18

- Full Python suite: 142 tests passed on Ubuntu 24.04 / Python 3.12, including
  21 new Linux/Bash regression tests in `test_submission_safety.py`.
- Four existing Shell integration suites passed with mocked VASPKIT/Slurm.
- Built and installed the wheel in a separate Linux environment; installed CLI
  integration passed outside the repository, including paths containing spaces.
- Verified login-profile isolation, failed header setup, header directive order,
  whole-pipeline preflight, partial retry, active-job guards, completed/failed job
  handling, explicit resubmission, accounting outages, ambiguous scheduler results,
  cluster propagation, per-case submission locking and incomplete batch recovery.
- Slurm was simulated; no real scheduler submissions or VASP calculations were run.

The records below describe earlier validation runs.

Validated on 2026-09-11. This record concerns source organization, packaging and
mocked execution. No actual VASP, Wannier or cRPA calculation was run during this work.

## Baseline preservation

Baseline Git commit: `13b6b6c1166b7417c9c748fd99207520db86adee`.

- All 115 original Python tests passed before restructuring and after the move.
- All four original shell integration tests passed before restructuring.
- The five scientific Python modules match baseline text exactly after accounting
  for relative package imports and installed modules' current-directory CLI defaults.
- The original `workflow.conf`, now in the legacy archive, is byte-identical to the baseline configuration.

## Candidate checks

| Check | Result and scope |
| --- | --- |
| Python suite | 119 tests passed: 115 original tests and 4 initialization tests |
| Shell suite | Batch, Wannier dispatch, cRPA preparation and independent job tests passed |
| Wheel build/install | Universal Python wheel built and installed into an isolated Linux environment |
| Installed commands | Help, version, init, doctor, preparation, mocked Slurm dependencies, status and batch passed outside the source directory |
| Path handling | Calculation directory with spaces passed; software and data directories were separate |
| Non-overwrite behavior | Reinitialization and missing explicit configuration failed as intended |
| Help side effects | Wannier/cRPA help did not create stage directories |
| Plotting | Installed command produced a PNG from synthetic PBAND/PDOS fixtures; figure inspected |
| Source distribution | Built and extracted; excludes original cluster configuration and bytecode |
| Convenience installer | Installed from the extracted source distribution into a new environment, including plotting dependencies |
| Document links | All local Markdown links resolve |
| Whitespace | `git diff --check` passed |

Python unit-test environment: Windows, Python 3.13.5, NumPy 2.1.3 and
Matplotlib 3.10.0. Linux package/integration environment: Ubuntu 24.04 under WSL,
Python 3.12.3 and Bash 5.2.21. Installed plotting dependencies: NumPy 2.5.3 and
Matplotlib 3.11.1. Other supported Python/dependency combinations were not exercised.

The original shell tests use the maintained backend with mock tools. The batch
regression now uses portable fixture configuration reproducing the original
four-node scientific settings, so distributed tests do not require the private
cluster configuration. Installed integration checks use mock VASPKIT and Slurm,
not actual simulation executables or a scheduler service.

## Remaining release decisions

1. Confirm intended users, supported clusters and simulation build versions.
2. Complete a representative production calculation and inspect its physical results.

The current manual is a draft and the package is a candidate; production
validation remains subject to the checks above.

## Legacy-file cleanup

The ten former root scripts/configuration/document redirects were archived. Tests
now import the package directly, and source exports omit the retired launchers.
After cleanup, all 119 Python tests and all four Bash regression tests passed.

## Command rename — 2026-09-12

The command and distribution are now `crpa-workflow`, the batch alias is
`crpa-workflow-batch`, and the Python package is `crpa_workflow`. All 119 Python
tests and four Bash regression tests passed after the rename. The renamed wheel
was installed into the isolated Linux test environment; version/help, both entry
points, initialization, mocked preparation/submission, and generated batch
launchers passed the installed integration test. The five scientific module
contents and legacy ZIP remain byte-identical to the preceding commit.

## Review defect remediation — 2026-09-12

The six reproduced defects in the review were corrected. Earlier statements
about unchanged module contents describe the preceding restructuring snapshots;
this remediation changes execution, recovery and restart-input validation.

- 121 Python tests passed, including complete/truncated/contradictory WANPROJ
  payloads, multiple k-points, both spin modes and failed forced Wannier install.
- All four shell integration scripts passed in WSL, including a copied Slurm
  spool script, unowned submission directory rejection, help/unknown options,
  setup/command/pipeline failure propagation and postprocessing configuration.
- A freshly built wheel was explicitly reinstalled (same-version pip skips are
  not accepted as validation). Installed integration passed outside the checkout,
  including help for all 16 public commands and the batch alias.

No actual scheduler submission or VASP/Wannier/cRPA scientific calculation was
performed. Existing generated jobs must be regenerated to use the fixed backend.
