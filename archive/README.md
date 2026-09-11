# Legacy files

`legacy-files-1.4.zip` is a verified backup containing:

- `original-version1.4/`: the original tracked sources, documentation, configuration
  and tests from commit `13b6b6c1166b7417c9c748fd99207520db86adee` (27 files).
  Generated Python bytecode is excluded.
- `retired-root-files/`: exact copies of the ten top-level files removed during
  cleanup: seven compatibility scripts, `workflow.conf` and two documentation
  redirects. These launchers depend on the reorganized package and are not a
  standalone copy of the original program.
- `manifest.json`: original Git revision, file sizes and SHA-256 hashes.

To recover the original program, extract `original-version1.4/` into a separate
directory. It includes the original cluster-specific configuration; review it
before running on another system. No simulation executable or pseudopotential
library is included.

To recover a retired root file, extract it from `retired-root-files/` into the
repository root intentionally. Normal operation uses the installed `vasp-workflow`
command and does not need these files.

This archive is a local backup and is excluded from wheel/source distributions
and registration source exports.
