# Candidate validation record — 1.4.1

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
| Source export | Complete runtime listing and SHA-256 manifest generated; no pagination yet |
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
3. Confirm official registration identity, ownership, language and dates.
4. Add approved real screenshots/results and finalize pagination for registration.

The current manual is a draft and the package is a candidate, not a claim of
production or registration approval.

## Legacy-file cleanup

The ten former root scripts/configuration/document redirects were archived. Tests
now import the package directly, and source exports omit the retired launchers.
After cleanup, all 119 Python tests and all four Bash regression tests passed.
