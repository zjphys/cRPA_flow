# Changelog

## 1.4.1 — packaging and documentation draft

- Installable Python package with `vasp-workflow` and `vasp-workflow-batch` commands.
- Separate calculation directories from the installed software.
- Add non-overwriting case initialization, local/Slurm profiles and environment checks.
- Archive the original code, cluster configuration and retired root launchers; use the installed package commands.
- Batch cases use a launcher and configuration instead of duplicating source code.
- Move Python implementation and shell resources under `src/vasp_workflow`.
- Add installation, developer and registration documentation and a silicon example.
- Keep scientific algorithms unchanged; compare against baseline commit
  `13b6b6c1166b7417c9c748fd99207520db86adee`.

This is a candidate release. It has not yet been validated by a real VASP/Wannier/cRPA run.
