# VASP SCF-to-cRPA Workflow

This project automates a VASP workflow from structural relaxation and
self-consistent-field (SCF) calculations through density of states (DOS), band
structure, Wannier construction, and constrained random-phase approximation
(cRPA). It supports direct execution and Slurm submission, includes projected
band/DOS plotting, and can prepare multiple structures in batch.

## 1. Summary and usage

The workflow creates and manages the following calculation stages:

| Stage | Calculation |
| --- | --- |
| `00_relax` | Optional structural relaxation |
| `01_scf` | Self-consistent calculation |
| `02_dos` | Density of states |
| `03_band` | Band structure |
| `04_wann` | Wannier construction |
| `05_crpa` | cRPA calculation |

### Requirements

- Bash and standard Unix command-line utilities
- VASP
- VASPKIT configured with an appropriate licensed pseudopotential library
- Wannier90 for the Wannier stage
- Slurm for job submission (not required for direct local execution)
- Python 3, NumPy, and Matplotlib for post-processing

### Setup

Place a VASP 5-style `POSCAR` in the project directory. The element symbols
must be present on line 6. You may also provide an existing `POTCAR`; otherwise,
the workflow asks VASPKIT to generate it. Review `workflow.conf` before running,
especially the VASP command, environment setup, Slurm resources,
pseudopotential settings, and INCAR templates.

Show the available commands:

```bash
./workflow.sh --help
```

### Basic workflow

Prepare the relaxation, SCF, DOS, and band stages:

```bash
./workflow.sh prepare
```

If the input structure is already relaxed:

```bash
./workflow.sh prepare --no-relax
```

Run the prepared stages directly:

```bash
./workflow.sh run
```

Alternatively, submit an `afterok`-linked Slurm pipeline:

```bash
./workflow.sh submit --job-name my-system
```

Inspect the calculation state at any time:

```bash
./workflow.sh status
```

After the DOS and band calculations finish, create projected band and DOS
plots:

```bash
./workflow.sh postprocess --elements Mn Sb --emin -4 --emax 4
```

Prepare and run the Wannier stage after the required SCF, DOS, and band outputs
are available:

```bash
./workflow.sh prepare-wannier --elements Mn Sb --orbitals d p
./workflow.sh run-wannier
```

Wannier preparation now defaults to Fermi-centred adaptive selection. It uses
exact element-shell pairs (`Mn:d`, `Sb:p`) and searches from `E_F - 15` to
`E_F + 20` eV. For a different search range, for example:

```bash
./workflow.sh prepare-wannier --elements Mn Sb --orbitals d p \
  --search-energy-range -6 8
```

The outer window retains at least 98% of each pair's weight within the bounded
search region at each SCF k-point and spin, contains `E_F`, and contains at least
`NUM_WANN` states on both supplied SCF/DOS meshes. The narrowest passing
interval is selected; there is no separate target interval or minimum ±2 eV
span. A frozen interval is selected inside the outer window and must contain `E_F`,
pass the default 0.70 PAW target-character threshold, and fit `NUM_WANN`.
If no interval passes, preparation writes an outer-only calculation. Inspect
`04_wann/wannier_window_diagnostics.json` before running. These are heuristic
proposals; the actual Wannier mesh, radial-shell identity and interpolation
accuracy are not validated by preparation.

Use `--window-method legacy` for the previous scores and window formulas.
Both modes now reject an outer window with too few states. Adaptive mode
requires a finite `E-fermi` entry in `01_scf/OUTCAR`. See the operation manual
for all thresholds and diagnostics.

`--search-energy-range` replaces the former `--target-energy-range` and
`--outer-search-padding` options. Those options are no longer accepted.

After inspecting the completed Wannier calculation, prepare and run cRPA:

```bash
./workflow.sh prepare-crpa --target-states 1-5 8 10-12
./workflow.sh run-crpa
```

Use `submit-wannier` and `submit-crpa` instead of the corresponding `run`
commands on Slurm systems. These downstream submissions do not automatically
depend on earlier jobs, so submit them only after their prerequisites finish.
The automatically selected orbitals, energy windows, target states, and cutoff
parameters must still be checked for physical validity and convergence.

## 2. Script overview

| File | Purpose |
| --- | --- |
| `workflow.sh` | Main command-line entry point. Prepares, runs, submits, executes, and reports the status of all calculation stages; it also dispatches plotting, Wannier, and cRPA preparation. |
| `batch_workflow.sh` | Discovers flat or nested POSCAR inputs, creates one calculation directory per structure, copies the workflow files, and optionally prepares, runs, or submits every case. |
| `postprocess.py` | Generates element- or orbital-projected band and DOS figures from VASPKIT data. It supports spin-polarized data, multiple output formats, reusable projection data, and optional Wannier-band overlays. |
| `rank_wannier_bands.py` | Ranks bands using k-point-weighted aggregate shell projections from the full SCF `PROCAR`, combines them with DOS-mesh energy extrema, and can write a machine-readable CSV report. |
| `prepare_wannier.py` | Builds the `04_wann` stage from completed SCF and DOS outputs, infers or accepts `NUM_WANN`, determines energy windows, generates the Gamma-centered mesh, and writes Wannier inputs. |
| `wannier_windows.py` | Standard-library helper implementing bounded Fermi-centred window selection and SCF/DOS state-count diagnostics; copy it alongside `prepare_wannier.py`. |
| `prepare_crpa.py` | Builds the `05_crpa` stage from completed Wannier outputs, validates selected target-state indices, applies cRPA defaults or overrides, and copies the required restart files. |
| `workflow.conf` | Central configuration for executables, environment setup, Slurm resources, k-point resolution, calculation defaults, and stage-specific INCAR and job templates. |

Each shell script supports `--help`, and each Python utility can be inspected
with:

```bash
python SCRIPT_NAME.py --help
```

## 3. Workflow quick guide

See [WORKFLOW_QUICK_GUIDE.md](WORKFLOW_QUICK_GUIDE.md) for the complete
command-by-command guide, stage prerequisites, plotting options, Wannier and
cRPA examples, and full local and Slurm workflows.

For the underlying calculation process, configuration details, quality gates,
and troubleshooting notes, see [OPERATION_MANUAL.md](OPERATION_MANUAL.md).
