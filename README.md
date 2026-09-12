# crpa-workflow

Version **1.0.0 — candidate release**. Linux command-line software for preparing,
running and analyzing VASP relaxation, SCF, DOS, bands, Wannier and cRPA workflows.

The main command is `crpa-workflow`; the batch alias is `crpa-workflow-batch`.
See the [migration instructions](docs/installation.md#command-name-migration) if
you installed the earlier command name.

## Install

Requires Linux, Bash 4+, Python 3.10+ with venv/pip, and separately configured
VASP/VASPKIT. Slurm is optional for direct execution. The installer includes the
NumPy/Matplotlib plotting dependencies.

```bash
bash install.sh "$HOME/.local/share/crpa-workflow/1.0.0"
source "$HOME/.local/share/crpa-workflow/1.0.0/bin/activate"
crpa-workflow --version
```

Or install in an existing Python environment: `python -m pip install '.[plot]'`.
See [installation and offline setup](docs/installation.md).

## Start a calculation

From the source release directory:

```bash
crpa-workflow init silicon --poscar examples/silicon/POSCAR --profile slurm
cd silicon
# Edit workflow.conf: cluster resources, environment and scientific settings.
crpa-workflow doctor prepare
crpa-workflow prepare --no-relax
crpa-workflow doctor submit
crpa-workflow submit --job-name silicon
crpa-workflow status
```

Use `--profile local` and `run` for direct execution with an appropriate command.
The example structure demonstrates input format; it is not a converged reference.
Wannier and cRPA preparation/submission are separate steps after prerequisite
results have been inspected. See the [user manual](docs/user_manual.md).

## Installed code and calculation data

The installed `crpa-workflow` operates in the current directory. To select another
case, use `crpa-workflow --root /path/to/case COMMAND`. Global `--root` and
`--config` options go before the command. Commands and options are listed by
`crpa-workflow --help` and the [quick guide](docs/quickstart.md).

Batch preparation uses one installation and creates a launcher in each case:

```bash
crpa-workflow --config /path/to/workflow.conf batch --mode prepare structures calculations
```

Batch defaults to submission; use `--mode prepare` to review inputs first.

## Source organization

Maintained Python modules, the Bash backend and portable defaults are in
`src/crpa_workflow/`. Use the installed `crpa-workflow` command, or run
`PYTHONPATH=src python -m crpa_workflow --help` from a source checkout.
Existing generated `job.sh` files remain self-contained and usable.

Original sources, the old cluster configuration and retired root launchers are
preserved in [archive/legacy-files-1.4.zip](archive/legacy-files-1.4.zip).
See [archive notes](archive/README.md) for contents and restoration.
The archive is kept locally and excluded from software distributions.
Scientific algorithms are preserved from Git baseline
`13b6b6c1166b7417c9c748fd99207520db86adee`.

## Documentation

- [User manual](docs/user_manual.md): functions, commands, files and troubleshooting.
- [中文版用户手册](docs/user_manual_zh.md)：安装配置、操作流程、命令说明与常见问题。
- [Installation](docs/installation.md): dependencies, configuration and upgrades.
- [Quick guide](docs/quickstart.md): detailed operation examples.
- [Physics reference](docs/physics_reference.md): methods and scientific checks.
- [Developer guide](docs/developer_guide.md): architecture, compatibility and testing.
- [Registration preparation](docs/registration.md): source/manual export and required applicant details.
- [Changelog](CHANGELOG.md): release changes.
- [Validation record](docs/validation.md): checks and remaining production verification.

## Verification

```bash
python -B -m unittest discover -s tests -v
bash tests/run_shell_tests.sh
```

External calculation programs are mocked in workflow tests. A representative real
VASP/Wannier/cRPA run on the intended cluster is still required before treating
this candidate as production-validated. Successful job completion alone does not
establish physical convergence or Wannier interpolation quality.
