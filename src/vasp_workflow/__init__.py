"""VASP workflow tooling. External simulation software is configured separately."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("vasp-scf-crpa-workflow")
except PackageNotFoundError:
    __version__ = "1.4.1"
