# Changelog

## 1.0.0 — initial release candidate

- Fix Slurm spool-copy stage discovery and non-executing command help.
- Stop on child-shell setup, command and pipeline failures.
- Restore existing Wannier results if forced installation fails.
- Honor configured postprocessing VASPKIT with CLI override precedence.
- Validate complete text WANPROJ dimensions and transformation blocks.
- Regenerate registration drafts from release metadata with pending ownership
  facts and verifiable source, input, PDF and ZIP snapshots.

- Rename the command to `crpa-workflow`, the batch alias to `crpa-workflow-batch`,
  the Python package to `crpa_workflow`, and the distribution to `crpa-workflow`.

- Installable Python package with `crpa-workflow` and `crpa-workflow-batch` commands.
- Separate calculation directories from the installed software.
- Add non-overwriting case initialization, local/Slurm profiles and environment checks.
- Archive the original code, cluster configuration and retired root launchers; use the installed package commands.
- Batch cases use a launcher and configuration instead of duplicating source code.
- Move Python implementation and shell resources under `src/crpa_workflow`.
- Add installation, developer and registration documentation and a silicon example.
- Keep scientific algorithms unchanged; compare against baseline commit
  `13b6b6c1166b7417c9c748fd99207520db86adee`.

This is a candidate release. It has not yet been validated by a real VASP/Wannier/cRPA run.
