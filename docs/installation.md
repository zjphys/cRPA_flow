# Installation and first use — 1.4.1

## Supported environment

Run calculations from Linux with Bash 4 or newer and Python 3.10 or newer.
Slurm is required only for submission. Windows users should install and run the
workflow inside WSL or connect to a Linux cluster. Native Windows calculation
execution is not supported. Python analysis functions can also be imported on Windows.

Install VASP and VASPKIT separately, and configure the pseudopotential library.
Wannier/cRPA stages require the corresponding capabilities in your VASP build;
check your build with the cluster administrator. The workflow installer does not
install these simulation programs or pseudopotentials.

No administrator privileges are needed to install this package in your account.
The Python installation must provide `venv` and either `ensurepip` or an existing
pip with `--python` support for the convenience installer.

## Install from a source release

Extract the complete source release. From its directory:

```bash
bash install.sh "$HOME/.local/share/vasp-workflow/1.4.1"
source "$HOME/.local/share/vasp-workflow/1.4.1/bin/activate"
vasp-workflow --version
```

The installer refuses to reuse an existing destination. Use a new versioned
directory when upgrading so existing batch launchers keep their original runtime.

Alternatively, in an existing Python environment with pip:

```bash
python -m pip install '.[plot]'
```

The `plot` extra installs NumPy and Matplotlib. Omit it for preparation-only use.
Neither path changes your shell startup files. Activate the environment in each
new shell, or call the installed command by its full path.

## Offline installation

On an internet-connected Linux machine matching the cluster's Python version and
CPU architecture, prepare all wheels, including the build dependency:

```bash
python -m pip wheel '.[plot]' 'setuptools>=68' -w wheelhouse
```

Transfer `wheelhouse` to the cluster. In a Python environment that already has pip:

```bash
python -m pip install --no-index --find-links wheelhouse 'vasp-scf-crpa-workflow[plot]==1.4.1'
```

For source installation with `install.sh`, the matching wheelhouse can instead be
selected using `PIP_NO_INDEX=1` and `PIP_FIND_LINKS=/absolute/path/wheelhouse`.

## Initialize a calculation

Run this from the source release to use the supplied structure:

```bash
vasp-workflow init "$HOME/calculations/silicon" \
  --poscar examples/silicon/POSCAR --profile slurm
cd "$HOME/calculations/silicon"
```

Edit `workflow.conf`: set the partition, account if required, resource counts,
execution setup and VASP command. Slurm initialization uses `srun vasp_std` and
one node/task as portable starting values. These resources are not recommendations
for a converged production calculation. Use `--profile local` for a direct
`vasp_std` command, or replace it with the appropriate MPI command for your system.

```bash
vasp-workflow doctor prepare
vasp-workflow prepare --no-relax
vasp-workflow doctor submit
vasp-workflow submit --job-name silicon
vasp-workflow status
```

`doctor` checks dependencies available in the current shell. It does not execute
environment setup, VASP, VASPKIT, or a Slurm job, and cannot certify a compute-node
environment or pseudopotential installation. Load preparation tools in the current
shell; use `EXECUTION_SETUP` for setup captured in execution commands and jobs.

## Existing calculations and configuration

Use `vasp-workflow --root /path/to/existing/case status` without copying software.
Global options go before the command; stage-specific options go after it.

Configuration selection is explicit `--config FILE`, then `WORKFLOW_CONFIG`, then
the calculation's `workflow.conf`. An explicit file replaces the case file.
Variables absent from that file fall back to the shell backend's historical
defaults. Configuration assignments override same-named environment values.
The `init` command copies `--config FILE` verbatim when provided; otherwise it uses
the supplied portable defaults and requested profile. It does not use
`WORKFLOW_CONFIG` for initialization.

`workflow.conf` is Bash code, supporting command maps, setup and templates; use
configuration from a trusted source. The original cluster's `workflow.conf` is preserved inside
`archive/legacy-files-1.4.zip` and is not installed in wheels.

Existing generated `job.sh` files stay self-contained. Regenerating them adopts
the current configuration; already generated files retain their captured commands.
Do not regenerate running calculations. Review `--force` carefully because it
rewrites workflow-owned input files and job scripts.

## Common installation issues

| Problem | Action |
| --- | --- |
| `venv` or `ensurepip` unavailable | Use the cluster's Python environment with pip, or request its Python venv component. |
| Command not found | Activate the installation environment or use the full executable path. |
| NumPy or Matplotlib unavailable | Install the `plot` extra in the environment selected by `PYTHON_BIN`. |
| VASPKIT unavailable during preparation | Load its module or configure `VASPKIT_BIN` as an absolute executable path. |
| Old batch launcher points at a removed install | Activate the desired release and use `vasp-workflow --root CASE`; retain old installs for reproducibility. |
