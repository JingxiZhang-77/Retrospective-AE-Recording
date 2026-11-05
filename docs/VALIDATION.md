# Evaluation and production qualification

## Evidence supplied with this repository

The automated regression suite uses only deterministic fictional fixtures. It
contains positive controls, negative mutations, input/adapter failures, report
safety tests, and command-line acceptance gates. One parameterized test mutates
each of the 27 configured EDC fields. Source inputs are hashed before/after a run
to test immutability.

Run:

```console
python -m unittest discover -s tests -v
python scripts/run_public_reference_simulation.py
```

The first command reports the actual test count and skips, if any. Its small
positive/negative fixtures are generated in temporary test folders; committed
copies are not needed. Tests are not clinical validation, an approved formal run
of record, or evidence of sponsor acceptance.

The second command runs an independent 20-subject/100-observation walkthrough,
with explicit public-documentation references, before/after reports, and
scenario-level detection assertions. It uses no participant rows from the public
datasets and no private study inputs. Its investigator decisions and resolutions
are fictional controls, not observed clinical review.
It writes the current initial/resolved reports under
`reports/public_reference_simulation/` and asserts detection of all injected
scenarios and the absence of errors/warnings after scripted resolution.

## Reproducibility

The example generator uses fixed fictional identifiers, dates, and clinical
comments. It creates canonical tables, explicit-null ODM transactions, text PDFs,
and a declared delivery ZIP. Reports include input SHA-256 hashes, the
configuration hash, tool version, check status, and run timestamp. Timestamps and
ZIP metadata may vary between executions; operational results and test
assertions, not byte-identical run reports, define the demonstration acceptance.

## Requirements-to-test coverage

| Requirement | Representative tests |
| --- | --- |
| Missing, duplicate, and unmatched review | `test_missing_review_is_not_confirmation`, `test_duplicate_review_is_not_silently_selected`, `test_review_orphan` |
| Original conflicting answers retained | `test_authorized_conflict_retains_original_answers`, `test_unresolved_ecg_conflict` |
| No unsupported standard comment | `test_management_comment_is_not_invented`, `test_comment_limit_includes_spaces` |
| Scoped term/grade decisions | `test_pi_term_precedence`, `test_missing_pi_term_falls_back_to_program_term`, `test_unapplied_grade_override` |
| Correct manual routing and flags | `test_manual_entry_requires_stored_record`, `test_grade_ceiling_requires_inconsistent_flag` |
| Preliminary/pending states remain visible | `test_pending_is_not_completed`, `test_preliminary_export_is_blocked_by_default` |
| Qualitative result and specimen display | `test_missing_unit_does_not_erase_trace`, `test_source_specimen_changed_in_listing` |
| All target fields, dates, nulls, and codes | `test_all_27_fields_are_compared`, `test_null_is_distinct_from_zero_and_no`, `test_date_representation_is_field_specific` |
| Correct XML metadata and structure | XML version/metadata/null/repeat/duplicate/entity test group |
| Authorized subject-level No | `test_no_activation_is_not_inferred_from_absence`, `test_no_activation_cannot_hide_retained_findings` |
| Current package | `test_zip_stale_file`, `test_zip_extra_file`, `test_zip_unsafe_path` |
| No unsafe report rendering | `test_report_html_escapes_untrusted_values`, `test_csv_formula_guard`, `test_excel_report_is_not_formula_executable` |
| Read-only operation and explicit gates | `test_inputs_are_unchanged`, CLI gate/overwrite/overlap tests |

## Before production use

1. Establish an approved intended use and requirements specification.
2. Approve study-specific candidate rules, mappings, field codes, routing,
   defaults, comment constraints, and null/format conventions.
3. Qualify the adapters and stable-key derivations using representative real
   source structures in a controlled environment.
4. Independently review implementation and risk-based test coverage.
5. Add study/vendor-specific negative controls, including partial dates,
   repeated visits, many-to-one event links, mixed manual/automated routes,
   reading-level findings, and target code conventions.
6. Verify the actual target XML against the approved schema and interface in UAT.
7. Establish authenticated review/signature, access, change, incident, retention,
   and release procedures outside this reference implementation.
8. Obtain the required approvals before a formal validation run of record and
   before production deployment.

No measured reduction in work, regulatory acceptance, clinical correctness, or
prevention of future remediation is claimed by the synthetic evaluation.

