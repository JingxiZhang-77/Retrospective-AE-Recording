# Check catalog and interpretation

Each run has a check register. PASS means no warning/error was detected by that
specific check on the supplied inputs. WARN and FAIL preserve the affected rows.
NOT_RUN states what input or optional capability was missing.

| ID | Principal checks | Important boundary |
| --- | --- | --- |
| SOURCE | Finding key, subject, domain/test context, candidate booleans, source/rule version, configured test/category aliases | Does not derive candidates from a full EDC extract or perform grading |
| REVIEW | Coverage in both directions, duplicate/current replies, identity/context agreement, source version, reviewer/timestamp/status, response codes, authorized assessment precedence | Does not interpret clinical free text or authenticate a signature |
| DECISION | One decision/owner/route, authorization, current versions, pending/preliminary status, manual/existing EDC link, excluded-output survival, missing results, override reference, configured grade ceiling and exclusion flag | Presence of authorization text is documentary evidence, not independent proof of clinical authority |
| AE | AE/repeat identity, source linkage and displays, configured start derivation, term/grade/comment provenance, required values, placeholders, field lengths, formats, codes, defaults, management/no-action inconsistency | No clinical diagnosis, dose attribution, or grade is invented |
| LISTING | Missing/extra rows, all configured AE fields, source display fields, release ID | A listing snapshot alone does not prove the PDF rendering |
| XML_STRUCTURE | UTF-8 XML, no DTD/entity declarations, namespace/version, study/metadata/event/form/group IDs, one subject per file, repeat/transaction conventions, unique mapped items, Value versus IsNull | Not full XSD validation, vendor-interface acceptance, transmission, or processing-order proof |
| XML | Detail record population and each mapped value/null compared with the AE reference | Requires stable subject/repeat keys |
| ACTIVATION | Approved universe, one activation per subject, authorized Yes/No coverage, consistency with details and in-scope decisions | Does not infer No from absence of new detail rows or inspect an undeclared database population |
| EDC | Missing/extra records, field/null differences, configured representation differences, explicit manual/existing route exceptions | Manual/existing exceptions are linked by documented AE identity; independent medical field review remains necessary |
| CHANGE | Record/field differences from baseline | Registers changes but does not itself approve every source/review/clinical change |
| PACKAGE | ZIP member names, unsafe paths, duplicate/missing/extra entries, size limits, current member hashes | Integrity is checked against declared files, not an undeclared delivery universe |
| PDF_INDEX | Missing/extra/duplicate subjects and missing/oversized PDFs | Does not establish page layout or a signed listing |
| PDF_TEXT | Subject identifier and configured values present in extracted PDF text | Presence is not field-to-row association, visual equivalence, checkbox verification, or signature verification |
| COVERAGE | All configured required checks actually ran | Optional NOT_RUN checks remain visible even if not required for a particular milestone |

## Response and field rules

- `remains_ncs` with `is_ae=N`, or `not_ae` with `is_ae=Y`, triggers a conflict.
  An authorized `assessment_precedence` decision records an INFO item without
  changing the original reply. This is a configured project convention, not a
  general clinical rule.
- A nonempty reviewed comment is used verbatim. With applicable PI fields, a
  confirmed `remains_ncs`, symptoms `none`, and management `none` can support the
  configured standard sentence. A modified/initiated intervention cannot silently
  receive that sentence. Documented overrides are checked separately.
- The example PI term falls back to the program term only when the reviewed term
  is missing. Setting `pi_fields_required=false` expects blank PI fields rather
  than fabricated confirmation.
- Field length uses Python character count, including spaces. For targets using
  bytes, UTF-16 code units, or other limits, adapt and validate the metadata check.
- Null is not zero or No. Date, time, case, and value-code normalization are
  field-specific. Raw differences allowed by a configured rule appear as INFO.
- Grade ceilings are study-specific output-routing checks. They do not declare
  a finding clinically significant. A scoped grade override requires documented
  authorization and does not update the original source grade.

## Evaluation scenarios

The test suite exercises positive and negative paths, including one mutation per
configured AE field, conflicting ECG replies, actual management comments, missing
reviews, grade-ceiling flags, unknown results, manual entry, nulls, Yes/No
activation, metadata/repeat/null XML structure, stale archives, adapter failures,
input immutability, report escaping, and command-line gates. See
`tests/test_toolkit.py` and `docs/VALIDATION.md`.

