"""Read-only checks from source findings through review and stored AE values."""
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation

from . import __version__
from .config import InputError
from .io import read_table, true
from .model import Result
from .odm import read_odm
from .values import equal, normalize, null


ROLES = ("findings", "reviews", "decisions", "ae", "listing", "edc", "subjects", "baseline_ae", "pdf_index")
MIN_COLUMNS = {
    "findings": {"finding_id", "subject_id", "domain", "test_name", "result", "in_scope", "review_required", "source_version", "rule_version"},
    "reviews": {"review_id", "finding_id", "assessment", "is_ae", "symptoms", "management", "confirmed_term", "comment", "status", "reviewer", "reviewed_at", "source_version", "review_version"},
    "decisions": {"decision_id", "finding_id", "route", "ae_id", "owner", "reason", "authorized_by", "authorized_at", "source_version", "review_version", "rule_version", "pi_fields_required"},
    "subjects": {"subject_id", "expected_ae", "coverage_confirmed", "authorized_by", "authorized_at"},
    "pdf_index": {"subject_id", "path"},
}


def grouped(rows, key):
    result = defaultdict(list)
    for row in rows or []:
        result[key(row)].append(row)
    return result


def record_key(row):
    return row.get("subject_id", ""), row.get("repeat_key", "")


def ae_key(row):
    return row.get("subject_id", ""), row.get("ae_id", "")


def timestamp(value):
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return bool(value)
    except (ValueError, AttributeError):
        return False


class Engine:
    def __init__(self, config):
        self.config = config
        self.result = Result(config["release_id"])
        self.data = {}
        for role in ROLES:
            rows = read_table(config, role, self.result)
            self.data[role] = rows
            if rows is not None:
                columns = next(item["columns"] for item in self.result.inputs if item["role"] == role)
                needed = MIN_COLUMNS.get(role, set())
                if role == "findings":
                    needed = needed | set(config.get("source_field_map", {}).values())
                if role in {"ae", "listing", "edc", "baseline_ae"}:
                    needed = {"subject_id", "repeat_key"} | {f["name"] for f in config["fields"]}
                    if role in {"ae", "baseline_ae", "listing"}:
                        needed |= {"ae_id", "finding_id", "source_result", "source_unit", "release_id"}
                        needed |= set(config.get("source_field_map", {}))
                missing = needed - set(columns)
                if missing:
                    raise InputError(f"Missing canonical columns in {role}: {', '.join(sorted(missing))}")
        self.findings = grouped(self.data["findings"], lambda r: r.get("finding_id", ""))
        self.reviews = grouped(self.data["reviews"], lambda r: r.get("finding_id", ""))
        self.decisions = grouped(self.data["decisions"], lambda r: r.get("finding_id", ""))
        self.aes = grouped(self.data["ae"], ae_key)
        self.fields = {f["name"]: f for f in config["fields"]}

    def check(self, check_id, title, *roles):
        missing = [r for r in roles if self.data[r] is None]
        return self.result.begin(check_id, title, not missing, "Missing input: " + ", ".join(missing) if missing else "")

    def one(self, mapping, key):
        rows = mapping.get(key, [])
        return rows[0] if len(rows) == 1 else {}

    def authorized(self, row):
        return bool(row.get("authorized_by") and timestamp(row.get("authorized_at", "")) and row.get("reason"))

    def source(self):
        check = self.check("SOURCE", "Source identity, context, and candidate integrity", "findings")
        if check.status == "NOT_RUN":
            return
        for fid, rows in self.findings.items():
            row = rows[0]
            check.records_checked += 1
            if not fid or not row.get("subject_id") or len(rows) != 1:
                self.result.add(check, "ERROR", "Finding identity is missing or duplicated.", "Resolve identity before linking review or AE data.", row)
            for flag in ("in_scope", "review_required"):
                if row.get(flag, "").strip().lower() not in {"true", "false", "yes", "no", "y", "n", "1", "0"}:
                    self.result.add(check, "ERROR", "Candidate flag is not explicit.", "Provide an explicit true/false flag.", row, flag, observed=row.get(flag))
            if not row.get("test_name") or not row.get("domain") or not row.get("source_version"):
                self.result.add(check, "ERROR", "Source context or version is incomplete.", "Supply test, domain, and source version.", row)
            if row.get("rule_version") != self.config["rule_version"]:
                self.result.add(check, "ERROR", "Finding was prepared under another rule version.", "Review affected findings against the active rules.", row, "rule_version", self.config["rule_version"], row.get("rule_version"))
            aliases = self.config.get("test_aliases", [])
            for rule in aliases:
                if row.get("test_name", "").casefold() in [v.casefold() for v in rule["aliases"]] and row.get("category") == rule.get("category"):
                    if row.get("canonical_test") != rule["canonical_test"]:
                        self.result.add(check, "ERROR", "Context-specific test alias is not mapped consistently.", "Review the approved test/category mapping; do not infer specimen from the label alone.", row, "canonical_test", rule["canonical_test"], row.get("canonical_test"))

    def review(self):
        check = self.check("REVIEW", "Review coverage, linkage, completion, and response interpretation", "findings", "reviews", "decisions")
        if check.status == "NOT_RUN":
            return
        for fid, rows in self.reviews.items():
            if len(rows) > 1:
                self.result.add(check, "ERROR", "Multiple review rows have the same finding identifier.", "Provide a resolved current snapshot; do not silently choose a reply.", rows[0])
            if fid not in self.findings:
                self.result.add(check, "ERROR", "Review has no corresponding source finding.", "Resolve the unmatched review entry.", rows[0])
        for key, rows in grouped(self.data["reviews"], lambda r: r.get("review_id", "")).items():
            if not key or len(rows) != 1:
                self.result.add(check, "ERROR", "Review identifier is missing or duplicated.", "Assign unique review identifiers.", rows[0])
        for fid, source_rows in self.findings.items():
            source = source_rows[0]
            if not true(source.get("in_scope")):
                continue
            check.records_checked += 1
            reply = self.one(self.reviews, fid)
            decision = self.one(self.decisions, fid)
            if true(source.get("review_required")) and not reply:
                self.result.add(check, "ERROR", "Required PI review is missing or ambiguous.", "Obtain or match the required assessment; do not assume confirmation.", source)
            if not reply:
                continue
            for key in ("subject_id", "visit", "assessment_datetime", "test_name", "specimen"):
                if reply.get(key) and source.get(key) and reply[key] != source[key]:
                    self.result.add(check, "ERROR", "Linked reply disagrees with the source identity/context.", "Verify the finding-to-reply link.", source, key, source[key], reply[key])
            if reply.get("source_version") != source.get("source_version"):
                self.result.add(check, "ERROR", "Review refers to a different source version.", "Assess the impact of the source change and reconfirm as needed.", source, "source_version", source.get("source_version"), reply.get("source_version"))
            if reply.get("status") != "confirmed" or not reply.get("reviewer") or not timestamp(reply.get("reviewed_at", "")) or not reply.get("review_version"):
                self.result.add(check, "ERROR", "Review is not documented as complete.", "Complete reviewer, timestamp, and confirmation status.", source)
            assessment, is_ae = reply.get("assessment"), reply.get("is_ae")
            conflict = (assessment == "remains_ncs" and is_ae == "N") or (assessment == "not_ae" and is_ae == "Y")
            if conflict:
                resolved = decision.get("conflict_resolution") == "assessment_precedence" and self.authorized(decision)
                self.result.add(check, "INFO" if resolved else "ERROR", "PI assessment and AE checkbox require explicit precedence.", "Retain the original answers and document an authorized interpretation.", source, "assessment / is_ae", expected="Authorized precedence", observed=f"{assessment} / {is_ae}")
            if assessment not in {"remains_ncs", "not_ae", "cs"} or is_ae not in {"Y", "N", ""}:
                self.result.add(check, "ERROR", "Review response uses an unrecognized controlled value.", "Map responses explicitly before checking.", source)
            if reply.get("symptoms") not in {"none", "present", "unknown"} or reply.get("management") not in {"none", "modified", "initiated", "unknown"}:
                self.result.add(check, "ERROR", "Symptoms or management response is not interpretable.", "Map the structured answers explicitly; do not infer a clinical answer.", source)

    def disposition(self):
        check = self.check("DECISION", "Recording routes, authorization, and manual completion", "findings", "decisions", "ae", "edc")
        if check.status == "NOT_RUN":
            return
        exported = grouped(self.data["ae"], lambda r: r.get("finding_id", ""))
        edc_ids = grouped(self.data["edc"], ae_key)
        for fid, rows in self.decisions.items():
            if fid not in self.findings or len(rows) > 1:
                self.result.add(check, "ERROR", "Decision is orphaned or duplicated.", "Provide one authorized current disposition per finding.", rows[0])
        for key, rows in grouped(self.data["decisions"], lambda r: r.get("decision_id", "")).items():
            if not key or len(rows) != 1:
                self.result.add(check, "ERROR", "Decision identifier is missing or duplicated.", "Assign unique decision identifiers.", rows[0])
        for fid, sources in self.findings.items():
            row = sources[0]
            check.records_checked += 1
            decision = self.one(self.decisions, fid)
            reply = self.one(self.reviews, fid)
            if not decision:
                self.result.add(check, "ERROR", "Finding has no unambiguous recording disposition.", "Assign an owner and document the recording route.", row)
                continue
            route = decision.get("route")
            if route not in {"automated", "manual", "existing", "excluded", "pending"}:
                self.result.add(check, "ERROR", "Unknown recording route.", "Use an approved disposition value.", row, observed=route)
            if not decision.get("owner") or not self.authorized(decision):
                self.result.add(check, "ERROR", "Disposition lacks owner, reason, or authorization.", "Complete the decision evidence.", row)
            for version in ("source_version", "rule_version"):
                expected = row.get(version)
                if decision.get(version) != expected:
                    self.result.add(check, "ERROR", "Decision is stale relative to its source/rules.", "Review and document the effect of the change.", row, version, expected, decision.get(version))
            if reply and decision.get("review_version") != reply.get("review_version"):
                self.result.add(check, "ERROR", "Decision does not reference the current review version.", "Reapply and verify the reviewed decision.", row)
            if decision.get("confirmation_status", "confirmed") != "confirmed" and exported.get(fid):
                self.result.add(check, "WARNING" if self.config.get("allow_preliminary_output", False) else "ERROR", "Preliminary assessment is present in the reporting population.", "Obtain final confirmation or explicitly authorize a preliminary release.", row)
            if route == "pending":
                self.result.add(check, "ERROR", "Finding remains pending.", "Resolve the outstanding recording decision before release.", row)
            if route in {"manual", "existing"}:
                target = (row.get("subject_id"), decision.get("ae_id", ""))
                if not target[1] or len(edc_ids.get(target, [])) != 1:
                    self.result.add(check, "ERROR", "Manual/existing recording has not been verified in the EDC snapshot.", "Link the decision to one verified stored AE record.", row)
                elif edc_ids[target][0].get("finding_id") and edc_ids[target][0]["finding_id"] != fid:
                    self.result.add(check, "ERROR", "Manual/existing AE points to a different finding.", "Verify the linked stored record rather than matching an identifier alone.", row)
            if route != "automated" and exported.get(fid):
                self.result.add(check, "ERROR", "Non-automated finding survived in the automated output.", "Verify filters and the intended recording route.", row, expected=route, observed="automated AE row")
            if route == "automated":
                linked = self.aes.get((row.get("subject_id"), decision.get("ae_id", "")), [])
                if len(linked) != 1:
                    self.result.add(check, "ERROR", "Automated decision does not link to exactly one AE.", "Resolve the missing or duplicated AE link.", row)
                if not true(row.get("in_scope")):
                    self.result.add(check, "ERROR", "Out-of-scope finding entered automated output.", "Apply the approved scope decision.", row)
                if row.get("result", "").strip().casefold() in {v.casefold() for v in self.config["result_placeholders"]} or null(row.get("result"), self.config):
                    self.result.add(check, "ERROR", "Missing/placeholder result entered automated output.", "Verify the source result and apply the study-specific missing-result route.", row, "result", observed=row.get("result"))
            if reply.get("assessment") == "not_ae" and route == "automated" and not decision.get("conflict_resolution"):
                self.result.add(check, "ERROR", "A non-AE assessment was retained without an explicit resolution.", "Verify the disposition against the PI assessment.", row)
            for name in ("term_override", "grade_override", "comment_override", "pi_term_override"):
                if decision.get(name) and not decision.get("override_reference"):
                    self.result.add(check, "ERROR", "An override has no supporting decision reference.", "Record the scoped authorization; do not silently overwrite derived values.", row, name, observed=decision[name])
            ceiling = self.config.get("automated_grade_ceilings", {}).get(row.get("domain"))
            if ceiling is not None:
                try:
                    source_grade = Decimal(str(normalize(row.get("source_grade", ""), self.fields.get("grade", {}), self.config)))
                    effective_grade = Decimal(str(normalize(decision.get("grade_override") or row.get("source_grade", ""), self.fields.get("grade", {}), self.config)))
                    if route == "automated" and effective_grade >= Decimal(str(ceiling)):
                        self.result.add(check, "ERROR", "Automated AE meets the configured manual-recording grade ceiling.", "Verify the route or supply an authorized scoped grade override.", row)
                    if route in {"manual", "excluded"} and source_grade >= Decimal(str(ceiling)) and self.config.get("require_inconsistent_flag", False) and row.get("consistency_flag") != "Inconsistent":
                        self.result.add(check, "ERROR", "Grade-ceiling finding lacks the required exclusion flag.", "Verify the post-review flag and downstream removal.", row, "consistency_flag", "Inconsistent", row.get("consistency_flag", ""))
                except (InvalidOperation, ValueError):
                    self.result.add(check, "ERROR", "Grade cannot be evaluated against the configured ceiling.", "Provide an explicit grade mapping for the supplied label.", row)

    def expected_pi(self, source, reply, decision):
        if not true(decision.get("pi_fields_required")):
            return "", ""
        term = decision.get("pi_term_override") or reply.get("confirmed_term") or decision.get("term_override") or source.get("source_term", "")
        comment = decision.get("comment_override") or reply.get("comment", "")
        supported = reply.get("assessment") == "remains_ncs" and reply.get("symptoms") == "none" and reply.get("management") == "none" and reply.get("status") == "confirmed"
        if not comment and supported:
            comment = self.config["standard_comment"]
        return term, comment

    def ae(self):
        check = self.check("AE", "AE identity, field rules, reviewed terms, grades, and comments", "findings", "reviews", "decisions", "ae")
        if check.status == "NOT_RUN":
            return
        repeat_keys = grouped(self.data["ae"], record_key)
        for key, rows in self.aes.items():
            if not all(key) or len(rows) != 1:
                self.result.add(check, "ERROR", "AE identifier is blank or duplicated within subject.", "Resolve AE identity.", rows[0])
        for key, rows in repeat_keys.items():
            if not all(key) or len(rows) != 1:
                self.result.add(check, "ERROR", "AE repeat key is blank or duplicated within subject.", "Use stable, unique target repeat keys.", rows[0])
        for row in self.data["ae"]:
            check.records_checked += 1
            source = self.one(self.findings, row.get("finding_id"))
            reply = self.one(self.reviews, row.get("finding_id"))
            decision = self.one(self.decisions, row.get("finding_id"))
            if not source or not decision:
                self.result.add(check, "ERROR", "AE has no unambiguous source/decision link.", "Resolve lineage before release.", row)
                continue
            if row.get("subject_id") != source.get("subject_id"):
                self.result.add(check, "ERROR", "AE subject does not match the linked finding.", "Correct the record linkage.", row)
            for target, origin in self.config["source_field_map"].items():
                if row.get(target, "") != source.get(origin, ""):
                    self.result.add(check, "ERROR", "AE source display differs from its linked finding.", "Carry the intended result, unit, and source context into the output.", row, target, source.get(origin, ""), row.get(target, ""))
            if self.config.get("start_from_assessment", False):
                try:
                    assessment = datetime.fromisoformat(source.get("assessment_datetime", ""))
                    for field, expected_time in (("start_date", assessment.date().isoformat()), ("start_time", assessment.time().isoformat())):
                        if not equal(expected_time, row.get(field, ""), self.fields.get(field, {}), self.config):
                            self.result.add(check, "ERROR", "AE start timing differs from the configured assessment-based convention.", "Verify the source timestamp and approved timing rule.", row, field, expected_time, row.get(field, ""))
                except ValueError:
                    self.result.add(check, "ERROR", "Assessment timestamp cannot support the configured start-date/time derivation.", "Verify source timing; do not invent an onset time.", row)
            expected = {"term": decision.get("term_override") or source.get("source_term", ""), "grade": decision.get("grade_override") or source.get("source_grade", "")}
            expected["pi_term"], expected["comments"] = self.expected_pi(source, reply, decision)
            for field, value in expected.items():
                if field in self.fields and not equal(value, row.get(field, ""), self.fields[field], self.config):
                    self.result.add(check, "ERROR", "AE value does not match its documented derivation/review.", "Reconcile the field with the authorized source decision.", row, field, value, row.get(field, ""))
            if true(decision.get("pi_fields_required")) and not expected["comments"]:
                self.result.add(check, "ERROR", "Required medical comment lacks a supported source.", "Obtain the PI comment or an applicable authorized instruction.", row, "comments")
            for name, item in self.fields.items():
                value = row.get(name, "")
                if value in {"BLANK", "PENDING", "PENDING PI COMMENT", "--", "\u2014", "\u2014\u2014"} and not null(value, self.config):
                    self.result.add(check, "ERROR", "Display/review placeholder remains in AE data.", "Represent an authorized blank or supply the reviewed value.", row, name, observed=value)
                if item.get("required") and null(value, self.config):
                    self.result.add(check, "ERROR", "Required AE field is blank.", "Complete the field under approved instructions.", row, name)
                if item.get("max_length") and len(value) > item["max_length"]:
                    self.result.add(check, "ERROR", "Text exceeds the target field length, including spaces.", "Obtain approved shorter text; do not truncate automatically.", row, name, item["max_length"], len(value))
                try:
                    normalized = normalize(value, item, self.config)
                    if normalized is not None and item.get("allowed_values") and normalized not in item["allowed_values"]:
                        raise ValueError("Unrecognized coded value")
                except ValueError as exc:
                    self.result.add(check, "ERROR", str(exc), "Verify the field-specific format or code mapping.", row, name, observed=value)
            for name, expected_value in self.config.get("ae_defaults", {}).items():
                if not equal(expected_value, row.get(name, ""), self.fields.get(name, {}), self.config):
                    self.result.add(check, "ERROR", "AE field differs from the configured recording default.", "Verify the study convention and any authorized exception.", row, name, expected_value, row.get(name, ""))
            if reply.get("management") in {"modified", "initiated"} and row.get("no_action") == "1":
                self.result.add(check, "WARNING", "No Action Taken is selected despite reported management/intervention.", "Request an authorized recording decision; do not change the medical answer automatically.", row, "no_action")
            if row.get("release_id") != self.config["release_id"]:
                self.result.add(check, "ERROR", "AE row belongs to another release.", "Use the approved current load reference.", row)

    def compare(self, check_id, title, role, expected, observed, extra_fields=(), allow_extra=None):
        check = self.result.begin(check_id, title, expected is not None and observed is not None, "Required comparison input is missing." if expected is None or observed is None else "")
        if check.status == "NOT_RUN":
            return
        left, right = grouped(expected, record_key), grouped(observed, record_key)
        for key, rows in right.items():
            if not all(key) or len(rows) != 1:
                self.result.add(check, "ERROR", f"{role} key is blank or duplicated.", "Resolve record identity before value comparison.", rows[0])
        for key in sorted(set(left) | set(right)):
            check.records_checked += 1
            if key not in left:
                if not allow_extra or key not in allow_extra:
                    self.result.add(check, "ERROR", f"Extra record in {role}.", "Reconcile the unexpected record.", right[key][0])
                continue
            if key not in right:
                self.result.add(check, "ERROR", f"Expected record is missing from {role}.", "Restore or explain the missing record.", left[key][0])
                continue
            if len(left[key]) != 1 or len(right[key]) != 1:
                continue
            reference, actual = left[key][0], right[key][0]
            for name in [*self.fields, *extra_fields]:
                metadata = self.fields.get(name, {})
                a, b = reference.get(name, ""), actual.get(name, "")
                if not equal(a, b, metadata, self.config):
                    self.result.add(check, "ERROR", f"Field differs between AE reference and {role}.", "Reconcile clinical values and null states using the approved mapping.", reference, name, a, b)
                elif a != b:
                    self.result.add(check, "INFO", f"Configured representation difference in {role}.", "Retain the documented field-specific comparison rule.", reference, name, a, b)

    def snapshots(self):
        self.compare("LISTING", "Listing snapshot population, AE fields, and qualitative/numeric source displays", "listing snapshot", self.data["ae"], self.data["listing"], (*self.config["source_field_map"], "release_id"))
        manual_targets = {
            (self.one(self.findings, fid).get("subject_id"), decisions[0].get("ae_id"))
            for fid, decisions in self.decisions.items()
            if len(decisions) == 1 and decisions[0].get("route") in {"manual", "existing"}
        }
        allowed = {record_key(row) for row in self.data["edc"] or [] if ae_key(row) in manual_targets}
        self.compare("EDC", "Stored EDC records, field values, nulls, and documented manual/existing routes", "EDC download", self.data["ae"], self.data["edc"], allow_extra=allowed)

    def xml(self):
        details, activations = read_odm(self.config, self.result)
        self.compare("XML", "XML detail population and all mapped field values", "XML detail", self.data["ae"], details)
        check = self.check("ACTIVATION", "Subject-universe activation coverage and authorized Yes/No decisions", "subjects", "findings", "decisions", "ae")
        if activations is None:
            check.status, check.reason = "NOT_RUN", "No XML transactions declared."
            return
        if check.status == "NOT_RUN":
            return
        subjects = grouped(self.data["subjects"], lambda r: r.get("subject_id", ""))
        actual = grouped(activations, lambda r: r.get("subject_id", ""))
        detail_subjects = {r["subject_id"] for r in details}
        source_subjects = {r["subject_id"] for r in self.data["findings"] if true(r.get("in_scope"))}
        for sid in set(subjects) | set(actual) | detail_subjects | source_subjects:
            check.records_checked += 1
            row = self.one(subjects, sid)
            if not sid or not row:
                self.result.add(check, "ERROR", "Subject universe entry is missing or duplicated.", "Use an approved complete subject list.", {"subject_id": sid})
                continue
            if len(actual.get(sid, [])) != 1:
                self.result.add(check, "ERROR", "Activation is missing or duplicated.", "Provide exactly one activation record per approved subject.", row)
            expected = row.get("expected_ae")
            if expected not in {"Y", "N"} or not true(row.get("coverage_confirmed")) or not row.get("authorized_by") or not timestamp(row.get("authorized_at", "")):
                self.result.add(check, "ERROR", "Activation decision lacks complete coverage/authorization evidence.", "Do not infer No merely because a subject has no exported AE rows.", row)
            if actual.get(sid) and actual[sid][0].get("activation") != expected:
                self.result.add(check, "ERROR", "Activation value differs from the approved subject decision.", "Reconcile Yes/No against the approved universe.", row, "activation", expected, actual[sid][0].get("activation"))
            if sid in detail_subjects and expected != "Y":
                self.result.add(check, "ERROR", "Subject with detail records is not marked Yes.", "Resolve the inconsistent activation decision.", row)
            if expected == "N":
                pending = [f for f in self.data["findings"] if f.get("subject_id") == sid and true(f.get("in_scope")) and (not self.one(self.decisions, f.get("finding_id")) or self.one(self.decisions, f.get("finding_id"))["route"] in {"automated", "manual", "existing", "pending"})]
                if pending:
                    self.result.add(check, "ERROR", "No activation conflicts with retained/manual/unresolved findings.", "Complete the subject-level recording decision before assigning No.", row)

    def changes(self):
        check = self.check("CHANGE", "Field-level differences from the prior AE reference", "baseline_ae", "ae")
        if check.status == "NOT_RUN":
            return
        before, after = grouped(self.data["baseline_ae"], record_key), grouped(self.data["ae"], record_key)
        for key in sorted(set(before) | set(after)):
            check.records_checked += 1
            if len(before.get(key, [])) > 1 or len(after.get(key, [])) > 1:
                self.result.add(check, "ERROR", "Baseline/current repeat key is ambiguous.", "Resolve the release identities before comparing changes.", (after.get(key) or before[key])[0])
                continue
            a, b = self.one(before, key), self.one(after, key)
            if not a or not b:
                self.result.changes.append({"subject_id": key[0], "repeat_key": key[1], "field": "record", "before": "present" if a else "", "after": "present" if b else ""})
            else:
                for name in [*self.fields, "source_result", "source_unit"]:
                    if a.get(name, "") != b.get(name, ""):
                        self.result.changes.append({"subject_id": key[0], "repeat_key": key[1], "field": name, "before": a.get(name, ""), "after": b.get(name, "")})
        if self.result.changes:
            self.result.add(check, "INFO", "Changes from the prior AE reference were recorded.", "Review the change register and affected downstream outputs.", observed=len(self.result.changes))

    def lineage(self):
        for fid, rows in self.findings.items():
            source = rows[0]
            review = self.one(self.reviews, fid)
            decision = self.one(self.decisions, fid)
            issues = [i for i in self.result.issues if i.finding_id == fid]
            self.result.lineage.append({
                "finding_id": fid, "subject_id": source.get("subject_id", ""), "test_name": source.get("test_name", ""),
                "source_version": source.get("source_version", ""), "review_id": review.get("review_id", ""),
                "review_status": review.get("status", "not_received"), "decision_id": decision.get("decision_id", ""),
                "route": decision.get("route", "unassigned"), "ae_id": decision.get("ae_id", ""),
                "owner": decision.get("owner", ""), "errors": sum(i.severity == "ERROR" for i in issues),
                "warnings": sum(i.severity == "WARNING" for i in issues),
            })

    def run(self):
        self.source()
        self.review()
        self.disposition()
        self.ae()
        self.snapshots()
        self.xml()
        self.changes()
        from .artifacts import check_packages, check_pdf
        check_packages(self.config, self.result)
        check_pdf(self.config, self.result, self.data)
        required = self.result.begin("COVERAGE", "Required verification areas were executed")
        completed = {c.check_id: c for c in self.result.checks}
        for key in self.config["required_checks"]:
            required.records_checked += 1
            if key not in completed or completed[key].status == "NOT_RUN":
                self.result.add(required, "ERROR", "A required verification area was not run.", "Supply the required input or approve a documented scope change.", field=key)
        self.lineage()
        return self.result
