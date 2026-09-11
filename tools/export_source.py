"""Export complete first-party source for review before final registration layout."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    files = [root / "install.sh"]
    files += sorted(path for path in (root / "src/vasp_workflow").rglob("*")
                    if path.is_file() and path.suffix in (".py", ".sh", ".conf"))
    listing = []
    manifest = []
    for path in files:
        data = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        relative = path.relative_to(root).as_posix()
        manifest.append({"path": relative, "lines": len(data.splitlines()),
                         "sha256_lf_utf8": hashlib.sha256(data.encode("utf-8")).hexdigest()})
        listing.append(f"===== {relative} =====\n{data.rstrip()}\n")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "source_listing.txt").write_text("\n".join(listing), encoding="utf-8", newline="\n")
    (args.output / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(files)} source files; {sum(item['lines'] for item in manifest)} lines before layout.")


if __name__ == "__main__":
    main()
