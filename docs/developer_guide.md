# Developer guide

## Layout and responsibilities

| Location | Responsibility |
| --- | --- |
| `src/vasp_workflow/cli.py` | Installed command, initialization, runtime paths and subprocess dispatch |
| `src/vasp_workflow/resources/workflow.sh` | Stage preparation, synchronization, execution, Slurm dependencies and status |
| `src/vasp_workflow/resources/batch_workflow.sh` | Structure discovery, case naming and batch orchestration |
| `src/vasp_workflow/resources/defaults.conf` | Portable new-case configuration and INCAR/job templates |
| `src/vasp_workflow/prepare_wannier.py` | Wannier preparation and validation |
| `src/vasp_workflow/wannier_windows.py` | Adaptive energy-window selection |
| `src/vasp_workflow/rank_wannier_bands.py` | PROCAR/EIGENVAL parsing and band ranking |
| `src/vasp_workflow/prepare_crpa.py` | cRPA preparation and target-state validation |
| `src/vasp_workflow/postprocess.py` | Projected band/DOS plots |
| `archive/legacy-files-1.4.zip` | Preserved original sources and retired root files; excluded from distributions |
| `tests/` | Scientific unit tests and mocked workflow integration tests |
| `docs/` | Maintained user, developer and registration documents |

Use the installed command or `PYTHONPATH=src python -m vasp_workflow` from the
repository root. Tests import the package directly. The old root launchers and
cluster configuration have been archived; they are no longer active entry points.
Installed modules use the current calculation directory by default.

Keep scientific changes separate from structural changes. Extract shared parsers
only after comparing their validation and error behavior. Shell fallback templates
remain embedded to preserve standalone backend behavior; the new-case configuration
overrides them intentionally, as the original research configuration did.

## Development and checks

```bash
python -m pip install -e '.[plot]'
python -B -m unittest discover -s tests -v
bash tests/run_shell_tests.sh
python -m pip wheel . --no-deps -w dist
```

The shell tests mock external executables. The tests covering standalone jobs and
dispatch copy the maintained shell backend into isolated cases. The batch test
exercises the package command-line interface and ensures it does not duplicate Python
source files. `tests/test_installed_workflow.sh` tests the installed package in a
separate directory; pass its installation's `vasp-workflow` executable as argument.

## Versioning and release procedure

Update the package version in `pyproject.toml`, the source fallback in `__init__.py`,
the changelog and document titles together. Preserve the Git commit used for release.
The current restructuring baseline is `13b6b6c1166b7417c9c748fd99207520db86adee`.

Build a wheel and install it in a fresh environment. Run help, initialization,
doctor, mocked preparation/submission, batch and plotting checks from outside the
source directory. Compare representative generated inputs and job files against
the baseline with identical configuration. Then run a representative real case
through the supported production stages on the intended cluster before declaring
the release production-validated.

Initialized cases record the version and initial configuration hash in
`.workflow-release.json`. Batch cases record `.workflow-version`. These record
creation, not later upgrades or every configuration edit. Preserve the actual
configuration, input files and job scripts with results.
