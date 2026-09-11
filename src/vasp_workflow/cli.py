"""Installed interface: software location and calculation location are independent."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from . import __version__

RESOURCES = Path(__file__).resolve().parent / "resources"
COMMANDS = (
    "init", "doctor", "batch", "prepare", "run", "submit", "execute", "status",
    "postprocess", "rank-bands", "prepare-wannier", "run-wannier",
    "submit-wannier", "prepare-crpa", "run-crpa", "submit-crpa",
)


def runtime_environment(root: Path, config: Path | None) -> dict[str, str]:
    env = os.environ.copy()
    env["WORKFLOW_ROOT"] = str(root)
    env["WORKFLOW_CODE_DIR"] = str(RESOURCES)
    env["WORKFLOW_PACKAGE"] = "1"
    env.setdefault("PYTHON_BIN", sys.executable)
    # Also makes generated case launchers usable from an uninstalled source tree.
    package_parent = str(RESOURCES.parent.parent)
    env["PYTHONPATH"] = package_parent + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    if config is not None:
        env["WORKFLOW_CONFIG"] = str(config)
    elif env.get("WORKFLOW_CONFIG"):
        env["WORKFLOW_CONFIG"] = str(Path(env["WORKFLOW_CONFIG"]).expanduser().resolve())
    return env


def initialize(argv: list[str], root: Path, config: Path | None) -> int:
    parser = argparse.ArgumentParser(prog="vasp-workflow init", description="Create a case without overwriting existing inputs.")
    parser.add_argument("directory", nargs="?", type=Path, default=root)
    parser.add_argument("--poscar", type=Path)
    parser.add_argument("--profile", choices=("local", "slurm"), default="slurm")
    args = parser.parse_args(argv)
    destination = args.directory.expanduser().resolve()
    for name in ("workflow.conf", ".workflow-release.json", "POSCAR" if args.poscar else "workflow.conf"):
        if (destination / name).exists():
            raise ValueError(f"Refusing to overwrite {destination / name}; use a new case directory.")
    if args.poscar is not None and not args.poscar.is_file():
        raise ValueError(f"POSCAR input does not exist: {args.poscar}")
    content = (config or RESOURCES / "defaults.conf").read_text(encoding="utf-8")
    if config is None and args.profile == "slurm":
        content += '\n# Slurm profile: set partition/account/resources above for your cluster.\n'
        content += "STAGE_COMMANDS[default]='srun vasp_std'\n"
    destination.mkdir(parents=True, exist_ok=True)
    if args.poscar is not None:
        shutil.copyfile(args.poscar, destination / "POSCAR")
    (destination / "workflow.conf").write_text(content, encoding="utf-8", newline="\n")
    metadata = {
        "software": "VASP SCF-to-cRPA Workflow", "version": __version__,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "profile": "custom" if config else args.profile,
        "config_sha256": hashlib.sha256(content.encode()).hexdigest(),
    }
    (destination / ".workflow-release.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Initialized {destination}\nEdit workflow.conf, then run vasp-workflow --root {shlex.quote(str(destination))} doctor prepare")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="VASP SCF-to-cRPA Workflow. Put global options before COMMAND.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="calculation directory (default: current directory)")
    parser.add_argument("--config", type=Path, help="explicit configuration file; replaces case workflow.conf")
    parser.add_argument("command", nargs="?", choices=COMMANDS)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    try:
        root = args.root.expanduser().resolve()
        config = args.config.expanduser().resolve() if args.config else None
        if config is not None and not config.is_file():
            raise ValueError(f"Configuration file does not exist: {config}")
        if args.command == "init":
            return initialize(args.arguments, root, config)
        if args.command in ("prepare-wannier", "prepare-crpa", "postprocess"):
            if any(arg == "--root" or arg.startswith("--root=") for arg in args.arguments):
                raise ValueError("Put --root DIR before the command so preparation and job generation use the same case.")
        if not root.is_dir():
            raise ValueError(f"Calculation directory does not exist: {root}")
        env = runtime_environment(root, config)
        if args.command == "rank-bands":
            return subprocess.call([sys.executable, "-m", "vasp_workflow.rank_wannier_bands", *args.arguments], cwd=root, env=env)
        bash = shutil.which("bash")
        if bash is None or os.name == "nt":
            raise ValueError("Run workflow commands in Linux/Bash (on Windows, install and run inside WSL).")
        if args.command == "batch":
            selected = config or Path(env.get("WORKFLOW_CONFIG", str(root / "workflow.conf")))
            if not selected.is_file() and not any(arg in ("--help", "-h") for arg in args.arguments):
                raise ValueError("Batch processing needs a configuration: initialize a case or use --config FILE before batch.")
            env["WORKFLOW_BATCH_CONFIG"] = str(selected)
            return subprocess.call([bash, str(RESOURCES / "batch_workflow.sh"), *args.arguments], cwd=root, env=env)
        return subprocess.call([bash, str(RESOURCES / "workflow.sh"), args.command, *args.arguments], cwd=root, env=env)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def batch_main() -> int:
    """Alias; global options are supported by vasp-workflow ... batch."""
    return main(["batch", *sys.argv[1:]])
