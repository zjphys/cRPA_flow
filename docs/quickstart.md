# Workflow Quick Operation Guide

This guide covers every public command in `crpa-workflow` and all calculation
stages. Run installed commands from the calculation directory. Global `--root` and `--config` options go before the command.

## 1. Setup

Required user input:

```text
POSCAR
```

Use a VASP 5-style POSCAR with element symbols on line 6. Provide an existing
`POTCAR`, or configure VASPKIT so the workflow can generate one. Review
`workflow.conf` before running, especially the VASP command, modules, Slurm
resources, pseudopotential setup, and INCAR templates.

Show the built-in help:

```bash
crpa-workflow --help
```

## 2. Stages

| Stage | Purpose | Main prerequisite |
|---|---|---|
| `00_relax` | Structural relaxation | `POSCAR`, `POTCAR` |
| `01_scf` | Self-consistent calculation | Relaxed `CONTCAR`, or input `POSCAR` |
| `02_dos` | DOS calculation | Completed `01_scf/CHGCAR` |
| `03_band` | Band structure | Completed `01_scf/CHGCAR`, generated `KPATH.in` |
| `04_wann` | Wannier construction | Completed SCF and DOS data; band inspection optional |
| `05_crpa` | cRPA calculation | Completed `04_wann` and selected Wannier states |

`02_dos` and `03_band` are independent children of `01_scf`. Wannier and cRPA
are deliberately prepared and launched separately.

## 3. Prepare and Run Stages 00–03

Generate the relaxation, SCF, DOS, and band inputs:

```bash
crpa-workflow prepare
```

Skip relaxation when the supplied POSCAR is already the desired structure:

```bash
crpa-workflow prepare --no-relax
```

Refresh workflow-owned stage directories after changing configuration:

```bash
crpa-workflow prepare --force
```

Run all prepared base stages sequentially in the current shell:

```bash
crpa-workflow run
```

Submit the base Slurm pipeline. SCF depends on relaxation when enabled; DOS and
bands both depend on SCF:

```bash
crpa-workflow submit
# Optional shared prefix: Pu-relax, Pu-scf, Pu-dos, Pu-band
crpa-workflow submit --job-name Pu
```

Both `--job-name Pu` and `--job-name=Pu` are accepted. Without this option,
the job names embedded in the generated `job.sh` files remain in effect.

Every generated `job.sh` is self-contained and may instead be submitted from
its own stage directory, for example:

```bash
cd 01_scf
sbatch job.sh
```

Submit downstream stages separately only after their prerequisite outputs
exist, or add the appropriate Slurm dependency yourself. The job synchronizes
required sibling-stage inputs, changes into its own directory, and runs the
command and setup captured when it was generated. Regenerate stage inputs and
jobs after changing `workflow.conf`.

Run exactly one prepared stage directly, mainly for debugging:

```bash
crpa-workflow execute 00_relax
crpa-workflow execute 01_scf
crpa-workflow execute 02_dos
crpa-workflow execute 03_band
crpa-workflow execute 04_wann
crpa-workflow execute 05_crpa
```

Check whether every registered stage is prepared, started, or finished:

```bash
crpa-workflow status
```

## 4. Plot Bands and DOS

After `02_dos` and `03_band` finish, plot all available element projections:

```bash
crpa-workflow postprocess --emin -3 --emax 4 --title "My material"
```

Plot selected elements and write PNG, PDF, and SVG files:

```bash
crpa-workflow postprocess \
  --elements Mn Sb \
  --format png --format pdf --format svg \
  --output mn_sb_band_dos
```

Plot orbital components for one element:

```bash
crpa-workflow postprocess \
  --orbital-element Mn \
  --orbitals dxy dyz dz2 dxz dx2-y2 \
  --emin -5 --emax 5
```

Reuse existing `PBAND_*.dat` and `PDOS_*.dat` without running VASPKIT again.
Spin-polarized `_UP.dat`/`_DW.dat` pairs are detected automatically:

```bash
crpa-workflow postprocess --reuse-data --dpi 300 --dos-max 20
```

After `04_wann` finishes, optionally overlay its interpolated bands on the
projected DFT band panel while keeping the same DOS panel:

```bash
crpa-workflow postprocess --wannier-bands --emin -3 --emax 4
```

The overlay reads `04_wann/INCAR` to determine `ISPIN`. It uses
`wannier90_band.dat` for `ISPIN=1`, or both `wannier90.1_band.dat` and
`wannier90.2_band.dat` for `ISPIN=2`. Raw Wannier energies are shifted by the
final `E-fermi` value in `04_wann/OUTCAR`; both Wannier spin channels are dashed. Use `--reuse-data` as well when the existing PBAND/PDOS files should
not be regenerated.

Other useful plotting controls are `--marker-scale`, `--vaspkit`, and repeated
`--format` options. The defaults are PNG and PDF output.

## 5. Prepare and Run Stage 04: Wannier

Choose positionally paired element/orbital projections and the number of
Wannier functions. Adaptive selection is the default: search for the requested
orbital subspace from `E_F - 20` to `E_F + 20` eV using the last finite SCF
OUTCAR Fermi value. It scores exact pairs (`Mn:d`, `Sb:p`) at each SCF k-point,
without requiring a contiguous band-index block. The ranking CSV remains a
separate report; it does not define the adaptive windows.

```bash
crpa-workflow prepare-wannier \
  --elements Mn Sb \
  --orbitals d p
```

Without `--num-bands`, `NUM_WANN` is inferred from `01_scf/POSCAR`: each
paired element count is multiplied by `s=1`, `p=3`, `d=5`, or `f=7` and the
results are summed. Wannier ranking accepts only these aggregate shells because
the SCF stage uses `LORBIT=10`; component names such as `dxy` are rejected. Use
`--num-bands N` to override the inferred count.

Ranking is read directly from `01_scf/PROCAR`, not from the symmetry-line band
path. For every band and spin channel, the requested ion/shell projections are
summed over the complete irreducible SCF mesh using the `weight =` value written
by VASP, then normalized by the total k-point weight. Adaptive selection uses
each SCF state's own energy; `02_dos/EIGENVAL` supplies independent state-count
checks and the CSV energy extrema. A missing or empty SCF PROCAR
is a hard error; rerun or restart the SCF projection output before preparation.

The Gamma-centered Wannier mesh uses `KPR_WANN` from `workflow.conf`
(default `0.04`). Pass `--kpr VALUE` to override it for one preparation.

Example with every optional preparation control:

```bash
crpa-workflow prepare-wannier \
  --elements Mn Sb \
  --orbitals d p \
  --num-bands 22 \
  --kpr 0.04 \
  --frozen-margin 0.1 \
  --window-method adaptive \
  --search-energy-range -20 20 \
  --outer-coverage 0.8 \
  --frozen-character-min 0.70 \
  --vaspkit vaspkit \
  --force
```

Run or submit only the prepared Wannier stage:

```bash
crpa-workflow run-wannier
crpa-workflow submit-wannier --job-name Pu  # Pu-wann
```

Inspect `04_wann/OUTCAR`, the Wannier90 output, interpolated bands, and
`wannier_band_ranking.csv` before choosing cRPA target states. Before running,
inspect `04_wann/wannier_window_diagnostics.json` for selected absolute and
relative windows, coverage, limiting counts, and warnings.

The outer window combines the weighted 10th–90th percentile intervals of every
nonzero pair/k-point/spin distribution within the bounded search region.
`--outer-coverage C` sets the percentile probabilities to `(1-C)/2` and `(1+C)/2`.
The combined span is rounded outward to the 0.25 eV
grid, and expanded as needed to fit at least `NUM_WANN` states at every SCF/DOS
k-point. Diagnostics record the percentile span and whether counts forced
expansion. Inclusive endpoints and expansion can retain more than the requested
fraction; the outer window can still reach a search boundary.
There is no separate target interval. Bands outside that region
cannot move the windows. A frozen interval is selected inside the outer and
must pass the PAW character threshold, fit `NUM_WANN` on both
SCF/DOS meshes, and contain states in each spin channel. When no frozen
candidate passes, preparation explicitly writes an outer-only calculation.
PAW character is a heuristic, not a radial-shell label or a proof of
interpolation accuracy; the generated Wannier mesh remains unverified.

`--search-energy-range` replaces the former target-range and padding options.
The default search bounds are −20 to +20 eV relative to `E_F`; final windows are free to be narrower
or asymmetric, and neither window must contain `E_F`. Search bounds only need
finite `MIN < MAX`, so `--search-energy-range 2 8` is also valid. The inner
window is no longer restricted to ±2 eV.

Use `--window-method legacy` to retain the previous cross-product ranking,
largest contiguous run and guarded frozen-window formulas. Both modes now
reject outer windows with fewer than `NUM_WANN` states at any supplied
SCF/DOS k-point. Other adaptive thresholds apply only to adaptive mode.

## 6. Prepare and Run Stage 05: cRPA

After Wannier finishes, omit `--target-states` to select every state from `1`
through `NUM_WANN`:

```bash
crpa-workflow prepare-crpa
```

To select a subset, one-based inclusive ranges and individual indices may be
mixed:

```bash
crpa-workflow prepare-crpa --target-states 1-5 8 10-12
```

Override all optional cRPA preparation values when required:

```bash
crpa-workflow prepare-crpa \
  --target-states 1-10 \
  --nbandsgw 160 \
  --encutgw 350 \
  --kpar 4 \
  --force
```

`NBANDSGW` defaults to the effective completed-Wannier `NBANDS`, `ENCUTGW`
defaults to two-thirds of `ENCUT`, and `KPAR` comes from `CRPA_KPAR` in
`workflow.conf`. For spin-polarized calculations, add `ISPIN` and `MAGMOM`
manually to `INCAR_CRPA_TEMPLATE`; preparation checks the effective `ISPIN`
against the spin-channel count stored in `WANPROJ`.

Run or submit only the prepared cRPA stage:

```bash
crpa-workflow run-crpa
crpa-workflow submit-crpa --job-name Pu  # Pu-crpa
```

## 7. Complete Example

Local sequential workflow:

```bash
crpa-workflow prepare --no-relax
crpa-workflow run
crpa-workflow postprocess --elements Mn Sb --emin -4 --emax 4
crpa-workflow prepare-wannier \
  --elements Mn Sb --orbitals d p
crpa-workflow run-wannier
crpa-workflow prepare-crpa
crpa-workflow run-crpa
crpa-workflow status
```

Slurm workflow:

```bash
crpa-workflow prepare --no-relax
crpa-workflow submit --job-name Pu
# Wait for SCF, DOS, and band jobs to finish.
crpa-workflow prepare-wannier \
  --elements Mn Sb --orbitals d p
crpa-workflow submit-wannier --job-name Pu
# Wait for the Wannier job and inspect its results.
crpa-workflow prepare-crpa
crpa-workflow submit-crpa --job-name Pu
crpa-workflow status
```

`submit-wannier` and `submit-crpa` do not automatically add dependencies to
earlier jobs; invoke them only after their prerequisite calculations finish.
Their generated jobs may also be submitted directly with `cd 04_wann && sbatch
job.sh` or `cd 05_crpa && sbatch job.sh`.


### Execution and restart validation (2026-09-12)

Submit generated jobs from their stage directory (`cd STAGE && sbatch job.sh`).
Slurm jobs resolve their stage using `SLURM_SUBMIT_DIR` and require the workflow
ownership marker; direct Bash execution resolves the script location. Regenerate
existing job scripts after updating the package to obtain these fixes.

Help for execution commands performs no calculation, and unexpected arguments
are rejected. Runtime setup and custom commands use `set -euo pipefail` in the
child login shell. A failed setup, simple command or pipeline stops the job;
custom shell code that explicitly handles failures remains responsible for its
own exit semantics. `postprocess` uses configured `VASPKIT_BIN`, with an explicit
`--vaspkit` argument taking precedence.

Failed forced Wannier installation restores the previous stage. If filesystem
errors also prevent rollback, the previous tree remains in the preparation
temporary directory (`previous-04_wann`) for recovery; do not remove it before
recovering data. Successful force replacement still discards old Wannier results.

cRPA preparation supports the documented whitespace-separated text WANPROJ
format, not the HDF5 representation. It checks dimensions against INCAR/effective
OUTCAR NBANDS (and OUTCAR NKPTS when present), the k-point table, all spin/k-point
blocks, complete band/orbital index coverage and finite matrix entries. It does
not prove matrix orthonormality, physical compatibility or scientific convergence.
Format reference: https://vasp.at/wiki/WANPROJ .
