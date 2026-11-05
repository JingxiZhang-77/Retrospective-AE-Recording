# Finding-to-AE Review Toolkit

Repository: [Retrospective-AE-Recording](https://github.com/JingxiZhang-77/Retrospective-AE-Recording)

A read-only Python toolkit for checking the links between source findings,
investigator reviews, recording decisions, AE workbooks, listings, ODM XML, and
stored EDC records. It produces an actionable issue register and a finding-level
evidence report rather than modifying clinical data.

**Status:** reference implementation, version 0.1.0. Demonstrated and regression
tested with fictional data. Not a validated production clinical system.

## Why this exists

Retrospective recording requires medical decisions and operational handoffs that
cannot simply be removed. This toolkit checks whether those handoffs are complete
and consistent: a received review is not automatically an interpretable decision;
an exclusion is not necessarily completed follow-up; a successful upload is not
proof that the intended values were stored.

The toolkit is independent of any sponsor's grading or reporting programs. It
does not implement CTCAE grading, diagnose an AE, replace investigator judgment,
or publish restricted study programs or records.

## Quick start

Python 3.11 or later is required. Run the retained 20-subject, 100-observation
walkthrough from this directory:

```console
python -m pip install -e ".[all]"
python -B scripts/run_public_reference_simulation.py
```

On Windows, `py -3` can replace `python`. Open
`reports/public_reference_simulation/Simulation_Overview.html` to compare the
initial issue report with the resolved report and inspect the data workbook.
No web server, account, or runtime network connection is required.

`01_initial` and `02_resolved` are both retained because they demonstrate detection
and rechecking, not duplicate histories. See
[the walkthrough](docs/PUBLIC_REFERENCE_SIMULATION.md) for the public references
and synthetic-data limitations.

To run the checker directly on a prepared snapshot:

```console
python run_review.py run --config examples/public_reference_simulation/02_resolved/study.json --output reports/my_review --pdf-text --xlsx
```

The source-tree entry point does not require package installation. CSV/XML core
checks use the standard library; Excel/PDF features need the optional extras.
After installation, `finding-ae-review` is also available.

### Run the regression suite

```console
python -m unittest discover -s tests -v
python scripts/check_repository.py
```

Optional Excel and PDF tests are skipped when their dependencies are absent.
The continuous-integration workflow installs both extras and runs the full suite
and the 20-subject walkthrough. Smaller test fixtures are generated temporarily;
older committed copies are not needed.

## Folder guide

| Folder | Purpose |
| --- | --- |
| `src/` | Program and report writers |
| `scripts/` | Simulation runner and release utilities |
| `examples/public_reference_simulation/` | Current synthetic inputs and artifacts |
| `reports/public_reference_simulation/` | Current overview and initial/resolved reports |
| `tests/` | Automated regression tests |
| `docs/` | Input, configuration, check, evaluation, and release instructions |
| `.github/` | Automated test workflow |

## Verification coverage

| Area | What is checked |
| --- | --- |
| Source population | Stable finding identifiers, required context, explicit candidate flags, rule version, and configured test aliases |
| PI review | Missing/extra links, conflicting replies, current source version, confirmation metadata, and authorized precedence |
| Recording decision | One route and responsible owner, authorization, manual/existing AE completion, preliminary status, exclusion flags, and scoped overrides |
| AE fields | All configured fields, term/comment provenance, grade overrides, source displays, timing conventions, defaults, formats, codes, and character limits |
| Listing snapshot | Missing/extra records and field-level agreement, including unitless qualitative results and specimen context |
| ODM XML | Environment identifiers, namespace/version, repeat keys, transaction structure, all mapped items, explicit nulls, and value agreement |
| Subject activation | Approved subject-universe coverage and explicit Yes/No decisions; No is never inferred only from absence of exported rows |
| EDC download | Record and value reconciliation with field-specific normalization; documented manual/existing recording routes |
| Change control | Record and field differences from the previous AE reference |
| PDF and delivery | Subject PDF inventory, optional text-presence checks, and ZIP inventory/member hashes |

See [the check catalog](docs/CHECK_CATALOG.md) for the exact limits of each check.

## Input contract

Inputs are explicit current snapshots, not arbitrary clinical workbooks that the
tool attempts to interpret. Prepare canonical CSV tables, or configure XLSX
sheets and column mappings. Preserve the original data separately and review the
adapter/mapping before use. Finding IDs must be created upstream; no fuzzy
clinical matching is performed.

The main tables are `findings`, `reviews`, `decisions`, `ae`, `listing`, `edc`, and
`subjects`. A previous AE reference and a PDF index support additional checks.
The configuration lists the target field metadata, XML files, and delivery ZIPs.

- [Data dictionary](docs/DATA_DICTIONARY.md)
- [Configuration and adapters](docs/CONFIGURATION.md)
- [20-subject public-reference synthetic walkthrough](docs/PUBLIC_REFERENCE_SIMULATION.md)

The included mappings, grade ceilings, defaults, and limits are **fictional example
settings**, not universal clinical or EDC conventions. Authorize a study-specific
profile before applying them to real data.

## Output and exit status

Every completed run writes:

- `report.html`: self-contained dashboard, check coverage, filterable issues,
  lineage, changes, input hashes, and limitations.
- `issues.csv`: record-level issues and proposed follow-up actions.
- `checks.csv`: executed, failed, warned, and not-run verification areas.
- `lineage.csv`: finding-to-review-to-decision-to-AE links and owners.
- `changes.csv`: record/field changes from the prior reference.
- `inputs.csv`: input filenames, row counts where applicable, and SHA-256 hashes.
- `run.json`: machine-readable evidence preserving original issue values.
- `report.xlsx`: optional editable evidence workbook with the same registers.

`ERROR` blocks the default command; `WARNING` requires review; `INFO` records a
documented interpretation, change, or configured representation difference.
Missing inputs produce `NOT_RUN`, never a silent pass. A required check that did
not run adds a blocking coverage issue.

| Exit code | Meaning |
| --- | --- |
| 0 | No issues met the selected command-line failure threshold |
| 1 | Issues met `--fail-on error` or `--fail-on warning` |
| 2 | Input, configuration, output, or dependency failure |

`--fail-on never` returns 0 even when findings are present; it is for inspecting
negative examples, not approval gating. Output directories must be new or empty.
`--overwrite` replaces named report files only; it does not delete other files.

## What a report cannot establish

- Clinical correctness, complete PI signatures, or formal validation approval.
- Completeness of findings that were never supplied to this checker.
- Whether a reviewer identity in a spreadsheet is an authenticated signature.
- Row-level visual equivalence from a listing snapshot or PDF text presence alone.
- Correct execution order or successful transmission of XML files.
- A valid target XSD or complete vendor-interface acceptance. This is a defined
  structural/value check, not a replacement for schema/UAT testing.
- A guarantee that every possible data issue has been detected.

The program never uploads data, edits source workbooks, changes PI answers,
truncates comments, or silently assigns a clinical diagnosis or grade.

## Privacy and publication

All committed examples are fictional. Do not add real participant data, PI
free-text replies, sponsor code, credentials, or production reports. Store such
files in a controlled location outside this repository. `private_data/` and
`reports/` are ignored as an additional safeguard, not an access-control system.

Run the [release checklist](docs/RELEASE_CHECKLIST.md) before publication. The
current `LICENSE` reserves rights pending owner approval; this repository must
not be described as open source unless an appropriate license is approved.
No remote repository is created or published by these scripts.

## Paper companion

The implemented checks operationalize the handoffs described in the companion
paper. They were developed after the retrospective project; the toolkit is not
represented as the system that performed the original study work. See
[evaluation](docs/VALIDATION.md).
The designated repository is linked above; `CITATION.cff` provides the software
citation metadata. Confirm publication approval, licensing, and the reviewed
remote version before citing it as a public release.

