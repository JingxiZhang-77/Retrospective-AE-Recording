# Configuration, adapters, and operating procedure

Use `examples/public_reference_simulation/02_resolved/study.json` and its CSV
headers as the working fictional profile and input examples. Copy them into a
controlled location and replace the data and approved mappings before adapting
the tool. Never use fictional target identifiers or defaults in a real upload.

## Explicit table mappings

```json
{
  "tables": {
    "subjects": {
      "path": "approved_subjects.xlsx",
      "sheet": "Subjects",
      "columns": {
        "subject_id": "Participant",
        "expected_ae": "Approved AE indicator",
        "coverage_confirmed": "Coverage complete",
        "authorized_by": "Reviewer",
        "authorized_at": "Approval timestamp"
      }
    }
  }
}
```

`columns` maps canonical names to source headers, not the reverse. Duplicate or
missing mapped headers are rejected. All paths resolve from the configuration
directory unless absolute paths are explicitly supplied. Reports record file
basenames and hashes, not complete local directory paths.

Each role currently reads one current CSV or one specified XLSX sheet. If source
data are split across subjects, batches, or sheets, prepare a controlled canonical
snapshot upstream. Preserve the original file/sheet/row references in that
adapter's evidence; the toolkit does not supply a study-specific batch adapter.
No input workbook is resaved. Formulas are rejected so their cached values cannot
silently become the review reference.

## Field metadata

Each field needs a canonical `name` and unique target `item_oid`:

```json
{
  "name": "start_date",
  "item_oid": "AE1.AESTDAT",
  "type": "date",
  "formats": ["%Y-%m-%d", "%d %b %Y"],
  "required": true
}
```

Supported types are text, date, time, and number. Optional `allowed_values`,
`max_length`, `case_sensitive`, and `value_map` define explicit target rules.
Example `value_map`: `{"Grade 1 (Mild)": "1"}`. Values are compared under that
mapping, but the source is not rewritten. Confirm mappings and raw code meanings
with the target database metadata.

The example has 27 fields; `expected_field_count` makes the expected count
explicit for another profile. `source_field_map` separately connects rendered
source context to finding columns. These are not additional AE target items.

## Scope, review, and decisions

Provide upstream `in_scope` and `review_required` flags. The checker verifies
their representation and downstream handling; it does not recreate every rule
that selected the population. Keep those rules and their approval separately.

`rule_version`, source/review versions, owner, reason, authorization, and override
reference preserve decision lineage. Changed source or review versions should
trigger a documented impact assessment and a refreshed decision snapshot.

`ae_defaults` verifies agreed recording conventions. Do not use a default to
guess a medical fact. `start_from_assessment=true` checks a study's explicit
assessment-based timing convention, not the actual onset of every AE.

`automated_grade_ceilings` and `require_inconsistent_flag` are optional,
study-specific checks. Omit them if the target study has no such convention.
`allow_preliminary_output` defaults to false; enabling it retains a warning.

## ODM and subject activation

Specify the approved namespace/version, StudyOID, MetaDataVersionOID, event,
form/group/item identifiers, and repeat/transaction conventions. The initial
profile supports non-repeating Yes/No activation and repeating detail records,
each in a separate subject transaction. A different vendor structure requires
reviewed adaptation and tests; it must not be declared equivalent without them.

Every detail group must contain each mapped ItemData once. Empty values use
`IsNull="Yes"` rather than missing rows or an empty Value. Activation must not
contain ItemGroupRepeatKey or the configured prohibited transaction attributes.

The `subjects` table is an approved universe with an explicit expected Yes/No
decision. A subject without detail transactions may have an already recorded
manual/existing target AE. Do not generate No merely by subtracting a detail
subject list from the study roster.

## Listing, PDF, and package evidence

Supply the current listing snapshot and PDF index. `--pdf-text` enables additional
text-presence checks; `pdf_fields` selects fields. They are intentionally not
advertised as exact row-level PDF reconciliation. Perform controlled visual and
signature checks outside this tool.

Each `packages` entry declares a ZIP and expected members, for example:

```json
{"path": "delivery.zip", "members": [{"name": "subject.pdf", "path": "subject.pdf"}]}
```

ZIP members are read, never extracted. Changed member bytes, missing files, extras,
duplicate names, unsafe paths, and oversized entries are reported.

## Run and review

1. Approve the candidate population, profile, adapters, and reference snapshots.
2. Run in a controlled location with a new report directory.
3. Review coverage first. Missing input is not a pass.
4. Assign issue owners and resolve issues in authorized upstream records.
5. Rerun against the revised snapshots and inspect the change register.
6. Perform the remaining clinical, visual, signature, interface, and release checks.
7. Retain input versions, configuration, hashes, reports, and approval evidence
   under the organization's retention and access policies.

Use `--fail-on warning` for a stricter automated gate. A zero exit code is not a
clinical approval or release authorization.

