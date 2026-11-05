# Canonical input dictionary

All tables have a header row. CSV is UTF-8, with an optional UTF-8 BOM. XLSX input
requires an explicit sheet name; formula cells are rejected rather than using
potentially stale cached results. Text is not silently truncated or stripped.
Missing means an empty cell unless additional null tokens have been explicitly
approved in the configuration. `0`, `N`, and null must remain distinguishable.

Input preparation is a controlled adapter step. This tool does not guess which
sheet contains the final response or perform fuzzy clinical matching.

## findings

| Column | Meaning |
| --- | --- |
| `finding_id` | Required stable, unique source-finding key |
| `subject_id` | Required participant key; fictional in public examples |
| `domain`, `test_name` | Required domain and original test/finding label |
| `visit`, `assessment_datetime` | Assessment context; ISO date/time when an assessment-based start convention is configured |
| `specimen`, `category`, `canonical_test` | Original specimen/category and approved context-specific test mapping |
| `result`, `unit` | Original observation for the intended display; an empty unit must not suppress a qualitative result |
| `lower_limit`, `upper_limit` | Available reference context; not used to perform CTCAE grading |
| `clinical_significance` | Original clinical classification, retained as context |
| `in_scope`, `review_required` | Required explicit boolean flags supplied by approved candidate/referral rules |
| `source_term`, `source_grade` | Derived upstream values; not computed here |
| `source_version`, `rule_version` | Required current source and selection/grading profile references |
| `consistency_flag` | Original routing flag; checked if configured for grade-ceiling exclusions |

Boolean flags accept true/false, yes/no, y/n, or 1/0 without case sensitivity.
No result placeholder is treated as a positive, negative, or measured value.

## reviews

Required columns are `review_id`, `finding_id`, `assessment`, `is_ae`, `symptoms`,
`management`, `confirmed_term`, `comment`, `status`, `reviewer`, `reviewed_at`,
`source_version`, and `review_version`. Include subject, visit, timing, test, and
specimen columns when available; these are cross-checked against the linked source.

| Column | Controlled values or interpretation |
| --- | --- |
| `assessment` | `remains_ncs`, `not_ae`, `cs` |
| `is_ae` | `Y`, `N`, or empty when not answered/applicable |
| `symptoms` | `none`, `present`, `unknown` |
| `management` | `none`, `modified`, `initiated`, `unknown` |
| `status` | `confirmed` is required for documented completion |
| `reviewed_at` | ISO timestamp; a documented timestamp is not authentication of a signature |
| `confirmed_term`, `comment` | Reviewed text, preserved verbatim |

A complete current snapshot has one review per finding. Missing review is not
silently converted into an asymptomatic/no-intervention assessment.

## decisions

| Column | Meaning |
| --- | --- |
| `decision_id`, `finding_id` | Required unique decision identity and source link |
| `route` | `automated`, `manual`, `existing`, `excluded`, or `pending` |
| `ae_id` | AE reference for automated/manual/existing routes |
| `owner`, `reason` | Required responsible role/person and decision basis |
| `authorized_by`, `authorized_at` | Required authorization record and ISO timestamp |
| `source_version`, `review_version`, `rule_version` | Required source/review/rule references; review version may be empty only if there is no linked review |
| `pi_fields_required` | Required explicit indication of whether the confirmed-term/comment fields apply |
| `confirmation_status` | `confirmed` or `preliminary`; omitted defaults to confirmed, so adapters should always provide it explicitly |
| `conflict_resolution` | `assessment_precedence` only with documented authorization; otherwise leave empty |
| `term_override`, `grade_override`, `comment_override`, `pi_term_override` | Optional scoped final values |
| `override_reference` | Required supporting reference if any override is supplied |

The toolkit verifies documented authorization metadata, not the authority of a
person or authenticity of an electronic signature. A manual route is complete
only when its linked AE is found once in the EDC snapshot. This identity check
does not independently validate every medical field of a manual AE without an
approved field-level reference.

## ae, listing, edc, baseline_ae

All snapshots contain `subject_id`, `repeat_key`, and the configured AE fields.
`ae`, `listing`, and `baseline_ae` also require `ae_id`, `finding_id`,
`source_result`, `source_unit`, `release_id`, and the configured source display
columns. The example additionally preserves source test, specimen, category,
and assessment timestamp. These source displays are not extra target AE items.

`listing` is a machine-readable record of the values intended/rendered by the
reporting workflow. It must be prepared independently enough to support its
stated comparison. Copying an AE table and calling it a listing is not evidence
that the actual PDF displayed those values. PDF text inspection is an additional,
limited check, not a substitute for visual inspection or signatures.

`edc` is the actual target download, mapped to the configured AE fields and stable
target repeat keys. Do not map system date variables instead of the entered
clinical date. `baseline_ae` is a prior approved/reference snapshot for change
review; it is not used to authorize a current change.

### Example 27-field profile

The target identifiers below are fictional configuration examples, not an
endorsed Rave database specification. Real identifiers/codes must be confirmed.

| No. | Canonical field | Example target item |
| --- | --- | --- |
| 1 | `term` | `AE1.AETERM` |
| 2 | `local_related` | `AE1.AELOCREL` |
| 3 | `last_related` | `AE1.POTLAST` |
| 4 | `wound_related` | `AE1.WHARAE` |
| 5 | `opioid_related` | `AE1.ORAE` |
| 6 | `start_date` | `AE1.AESTDAT` |
| 7 | `start_time` | `AE1.AESTTIM` |
| 8 | `start_time_unknown` | `AE1.AESTUNK` |
| 9 | `ongoing` | `AE1.AEONGO` |
| 10 | `end_date` | `AE1.AEENDAT` |
| 11 | `end_time` | `AE1.AEENTIM` |
| 12 | `end_time_unknown` | `AE1.AEENUNK` |
| 13 | `stop_indeterminate` | `AE1.AEDTDET` |
| 14 | `grade` | `AE1.AETOXGR` |
| 15 | `serious` | `AE1.AESER` |
| 16 | `relatedness` | `AE1.AEREL` |
| 17 | `drug_action` | `AE1.AEACN` |
| 18 | `no_action` | `AE1.AENONE` |
| 19 | `conmed` | `AE1.AECONMED` |
| 20 | `procedure` | `AE1.AECONTHP` |
| 21 | `other_action` | `AE1.AEACNOTH` |
| 22 | `other_action_specify` | `AE1.AEACNOTHSP` |
| 23 | `outcome` | `AE1.AEOUT1` |
| 24 | `sequelae` | `AE1.SEQUELAE` |
| 25 | `discontinued` | `AE1.AEDIS` |
| 26 | `pi_term` | `AE1.AETERMPI` |
| 27 | `comments` | `AE1.COMMENTS` |

## subjects

Required columns: `subject_id`, `expected_ae` (`Y` or `N`), `coverage_confirmed`,
`authorized_by`, and `authorized_at`. This is the approved target-form subject
universe, not a list inferred from surviving AE rows. Manual/existing target AEs
can justify Yes even when no new detail transaction is present. No requires
completed coverage and cannot hide a retained or unresolved in-scope finding.

## pdf_index

Required columns: `subject_id`, `path`. Relative paths resolve from the
configuration directory. One declared PDF is expected per retained subject.
The checker reads no undeclared subject PDFs.

