# Software copyright registration preparation

This is a preparation note, not a completed application. The current code and
manual form a reviewable candidate release. The applicant must confirm the
registration jurisdiction and institution-specific requirements before final export.

## Proposed software identity

Working name: crpa-workflow. Candidate technical version: 1.0.0.
The final Chinese/English registration name, copyright holder(s), authors,
development/completion dates and registration version remain to be confirmed.
Do not infer ownership from the developer names or select an open-source license
without the rights holder's decision.

## Reference formats

For a Chinese registration, the official rules describe source-program and
document identification materials, normally the first and last 30 consecutive
pages of each. If the complete material has fewer than 60 pages, submit it in
full. Except for specified circumstances, source pages require at least 50 lines
and document pages at least 30 lines. See the
[National Copyright Administration rules, Articles 9–12](https://www.ncac.gov.cn/xxfb/flfg/bmgz/202410/t20241015_869486.html).

The [Shanghai Software Center guidance](https://www.sscenter.sh.cn/SoftwareCopyrightAgency/index.html)
provides practical advice on software-name/version headers and page numbering.
The [public ZZU application/template repository](https://github.com/George551556/zzu-SCA)
contains an operation-manual template as a layout reference. Its informal process
advice is not a substitute for the official rules or the applicant's university
instructions. No template text has been copied into this manual.

## Source materials

The maintained source is under `src/crpa_workflow`, with `install.sh` at the root.
Legacy files are archived and excluded from the active source export. `tools/export_source.py` creates a deterministic, complete text listing
and a per-file hash manifest from the current source. It excludes caches, test
fixtures, generated calculations, third-party packages and the original cluster's
local configuration. It includes the distributed default configuration.

```bash
python tools/export_source.py artifacts/registration
```

This text is an intermediate review artifact, not a paginated filing. Freeze the
approved Git revision and software identity before producing final source and
manual PDFs. Format genuine source in a consistent file order, applying the
required page selection to the complete listing. Do not add filler code to reach
an assumed minimum program length.

## Manual materials

The draft is `docs/user_manual.md`, supported by installation, quick-command and
physics-reference documents. Its example commands correspond to the packaged
command-line interface. Use actual terminal captures and plots when preparing the
final illustrated manual. Mock test output must remain labeled as mock output.

The Chinese manual is [docs/user_manual_zh.md](user_manual_zh.md). It includes
installation, configuration, operation examples, commands, files and troubleshooting,
with pending registration details explicitly marked for applicant confirmation.

Outstanding applicant inputs:

- Official identity, ownership, dates, language and institutional template.
- Confirmation of the stable source version and the supported simulation builds.
- A completed example authorized for inclusion, with actual results and screenshots.
- Final production verification on the intended cluster and approval of the manual.

Keep the software name/version consistent across application, source listing,
manual and captured outputs. Source and manual export should follow the approved
release; changing scientific behavior afterwards requires renewed verification.

## Rebuilding the preparation packet

Confirmed registration facts belong in `docs/registration_details.json`. Null or
false entries remain visibly pending; the builder does not infer ownership or
signature status. See `docs/component_provenance.md` for the evidence inventory.

Use a separate developer Python 3.11+ environment with
`python -m pip install -r tools/requirements-registration.txt`. This is separate
from the Linux workflow's Python 3.10+ runtime. The default PDF fonts are Windows
SimSun, SimHei and Consolas. On another OS, set `REGISTRATION_CN_FONT`,
`REGISTRATION_BOLD_FONT` and `REGISTRATION_CODE_FONT` to licensed local font files
with the required Chinese/code glyphs, and visually recheck all output pages.

Run `python tools/build_registration_materials.py`, then
`python tools/verify_registration_materials.py --build-zip`. The second command
validates all four required PDFs, exact source body text, document text, geometry,
source/input snapshots and release identity before building the ZIP. Inspect the
rendered pages in `artifacts/copyright_application_qa`. Subsequent checks use
`python tools/verify_registration_materials.py --no-render` without changing the
packet. The ZIP hash receipt is stored beside the ZIP; each file has an internal
hash record. Actual source, manuals, tooling, tests and Git working-tree state are
recorded because a HEAD revision alone does not identify an uncommitted snapshot.

These technical checks do not certify ownership or replace applicant confirmation,
actual signatures, the official application form or the filing system's current
requirements. A real scientific run remains outside this mock-tested release.
