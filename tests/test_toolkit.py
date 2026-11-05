"""Synthetic regression tests; no study data or network services are used."""
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import csv
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from finding_ae_review.cli import main
from finding_ae_review.config import InputError, load_config
from finding_ae_review.demo import make_example, write_csv
from finding_ae_review.engine import Engine
from finding_ae_review.io import file_hash
from finding_ae_review.report import safe_csv, write_reports
from finding_ae_review.values import equal, normalize


class ToolkitTests(unittest.TestCase):
    def setUp(self):
        work = ROOT / "reports" / ".tests"
        work.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="case-", dir=work)
        self.root = Path(self.temp.name)
        self.path = make_example(self.root / "input")
        self.config = load_config(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def engine(self):
        return Engine(self.config)

    def errors(self, result, check=None):
        return [i for i in result.issues if i.severity == "ERROR" and (not check or i.check_id == check)]

    def has(self, result, check, text=""):
        self.assertTrue(any(text in i.message for i in self.errors(result, check)), (check, text, [(i.check_id, i.message) for i in result.issues]))

    def xml_edit(self, name, transform):
        path = self.path.parent / "artifacts" / name
        root = ET.fromstring(path.read_bytes())
        transform(root)
        ET.register_namespace("", "http://www.cdisc.org/ns/odm/v1.3")
        path.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))

    def cli(self, *args):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            return main(list(args))

    def test_clean_fixture_has_no_errors_or_warnings(self):
        result = self.engine().run()
        self.assertEqual(result.counts()["ERROR"], 0)
        self.assertEqual(result.counts()["WARNING"], 0)
        self.assertEqual(len(result.lineage), 8)

    def test_problem_fixture_detects_multiple_handoffs(self):
        path = make_example(self.root / "problem", issues=True)
        result = Engine(load_config(path)).run()
        for check in ("REVIEW", "DECISION", "AE", "LISTING", "XML_STRUCTURE", "XML", "ACTIVATION", "EDC", "PACKAGE"):
            with self.subTest(check=check):
                self.has(result, check)

    def test_missing_review_is_not_confirmation(self):
        engine = self.engine()
        engine.data["reviews"].pop()
        engine.reviews.pop("F008")
        self.has(engine.run(), "REVIEW", "missing")

    def test_duplicate_finding_is_blocking(self):
        engine = self.engine()
        engine.findings["F001"].append(dict(engine.findings["F001"][0]))
        self.has(engine.run(), "SOURCE", "duplicated")

    def test_duplicate_review_is_not_silently_selected(self):
        engine = self.engine()
        engine.reviews["F001"].append(dict(engine.reviews["F001"][0]))
        self.has(engine.run(), "REVIEW", "Multiple")

    def test_review_orphan(self):
        engine = self.engine()
        engine.reviews["MISSING"] = [dict(engine.reviews["F001"][0], finding_id="MISSING")]
        self.has(engine.run(), "REVIEW", "no corresponding")

    def test_review_context_mismatch(self):
        engine = self.engine()
        engine.reviews["F001"][0]["subject_id"] = "DEMO-OTHER"
        self.has(engine.run(), "REVIEW", "identity/context")

    def test_review_version_is_stale(self):
        engine = self.engine()
        engine.reviews["F001"][0]["source_version"] = "OLD"
        self.has(engine.run(), "REVIEW", "source version")

    def test_unconfirmed_review(self):
        engine = self.engine()
        engine.reviews["F001"][0]["status"] = "pending"
        self.has(engine.run(), "REVIEW", "not documented as complete")

    def test_review_requires_reviewer(self):
        engine = self.engine()
        engine.reviews["F001"][0]["reviewer"] = ""
        self.has(engine.run(), "REVIEW", "not documented as complete")

    def test_review_requires_timestamp(self):
        engine = self.engine()
        engine.reviews["F001"][0]["reviewed_at"] = "not-a-date"
        self.has(engine.run(), "REVIEW", "not documented as complete")

    def test_unresolved_ecg_conflict(self):
        engine = self.engine()
        engine.decisions["F001"][0]["conflict_resolution"] = ""
        self.has(engine.run(), "REVIEW", "precedence")

    def test_authorized_conflict_retains_original_answers(self):
        engine = self.engine()
        before = deepcopy(engine.reviews["F001"][0])
        result = engine.run()
        self.assertFalse(self.errors(result, "REVIEW"))
        self.assertEqual(engine.reviews["F001"][0], before)
        self.assertTrue(any(i.check_id == "REVIEW" and i.severity == "INFO" for i in result.issues))

    def test_management_comment_is_not_invented(self):
        engine = self.engine()
        engine.reviews["F002"][0]["comment"] = ""
        self.has(engine.run(), "AE", "lacks a supported source")

    def test_no_action_conflict_is_a_warning_not_an_automatic_edit(self):
        engine = self.engine()
        row = next(r for r in engine.data["ae"] if r["finding_id"] == "F002")
        row["no_action"] = "1"
        result = engine.run()
        self.assertTrue(any(i.severity == "WARNING" and "No Action Taken" in i.message for i in result.issues))
        self.assertEqual(row["no_action"], "1")

    def test_comment_limit_includes_spaces(self):
        engine = self.engine()
        row = engine.data["ae"][0]
        row["comments"] = "a "*100 + "a"
        self.has(engine.run(), "AE", "including spaces")

    def test_exact_200_character_comment_is_not_truncated(self):
        engine = self.engine()
        row = next(r for r in engine.data["ae"] if r["finding_id"] == "F002")
        value = "a "*100
        engine.reviews["F002"][0]["comment"] = value
        row["comments"] = value
        engine.run()
        self.assertEqual(row["comments"], value)

    def test_pi_term_precedence(self):
        engine = self.engine()
        row = engine.data["ae"][0]
        row["pi_term"] = row["term"]
        self.has(engine.run(), "AE", "documented derivation")

    def test_missing_pi_term_falls_back_to_program_term(self):
        engine = self.engine()
        engine.reviews["F001"][0]["confirmed_term"] = ""
        engine.data["ae"][0]["pi_term"] = engine.data["ae"][0]["term"]
        result = engine.run()
        self.assertFalse(any(i.check_id == "AE" and i.field == "pi_term" for i in self.errors(result)))

    def test_unapplied_grade_override(self):
        engine = self.engine()
        row = next(r for r in engine.data["ae"] if r["finding_id"] == "F008")
        row["grade"] = "2"
        self.has(engine.run(), "AE", "documented derivation")

    def test_override_requires_reference(self):
        engine = self.engine()
        engine.decisions["F008"][0]["override_reference"] = ""
        self.has(engine.run(), "DECISION", "supporting decision reference")

    def test_manual_entry_requires_stored_record(self):
        engine = self.engine()
        engine.data["edc"] = [r for r in engine.data["edc"] if r["ae_id"] != "AE-F006"]
        self.has(engine.run(), "DECISION", "not been verified")

    def test_grade_ceiling_requires_inconsistent_flag(self):
        engine = self.engine()
        engine.findings["F006"][0]["consistency_flag"] = "Consistent"
        self.has(engine.run(), "DECISION", "exclusion flag")

    def test_automated_grade_ceiling_without_override(self):
        engine = self.engine()
        engine.decisions["F008"][0]["grade_override"] = ""
        self.has(engine.run(), "DECISION", "grade ceiling")

    def test_pending_is_not_completed(self):
        engine = self.engine()
        engine.decisions["F003"][0]["route"] = "pending"
        self.has(engine.run(), "DECISION", "remains pending")

    def test_preliminary_export_is_blocked_by_default(self):
        engine = self.engine()
        engine.decisions["F004"][0]["confirmation_status"] = "preliminary"
        self.has(engine.run(), "DECISION", "Preliminary")

    def test_explicit_preliminary_export_remains_a_warning(self):
        engine = self.engine()
        engine.config["allow_preliminary_output"] = True
        engine.decisions["F004"][0]["confirmation_status"] = "preliminary"
        self.assertTrue(any(i.check_id == "DECISION" and i.severity == "WARNING" for i in engine.run().issues))

    def test_placeholder_is_not_a_positive_result(self):
        engine = self.engine()
        engine.findings["F003"][0]["result"] = "See Below"
        self.has(engine.run(), "DECISION", "placeholder")

    def test_missing_unit_does_not_erase_trace(self):
        engine = self.engine()
        row = next(r for r in engine.data["ae"] if r["finding_id"] == "F003")
        self.assertEqual(row["source_unit"], "")
        self.assertEqual(row["source_result"], "Trace")
        listing = next(r for r in engine.data["listing"] if r["finding_id"] == "F003")
        listing["source_result"] = ""
        self.has(engine.run(), "LISTING", "Field differs")

    def test_source_display_changed(self):
        engine = self.engine()
        engine.data["ae"][0]["source_result"] = "Incorrect result"
        self.has(engine.run(), "AE", "source display")

    def test_source_specimen_changed_in_listing(self):
        engine = self.engine()
        engine.data["listing"][0]["source_specimen"] = "Wrong specimen"
        self.has(engine.run(), "LISTING", "Field differs")

    def test_source_alias_context(self):
        engine = self.engine()
        engine.findings["F004"][0]["canonical_test"] = "blood_rbc"
        self.has(engine.run(), "SOURCE", "test alias")

    def test_stale_decision(self):
        engine = self.engine()
        engine.decisions["F003"][0]["source_version"] = "OLD"
        self.has(engine.run(), "DECISION", "stale")

    def test_ongoing_not_inferred(self):
        engine = self.engine()
        engine.data["ae"][0]["ongoing"] = "1"
        self.has(engine.run(), "AE", "recording default")

    def test_start_date_matches_explicit_study_convention(self):
        engine = self.engine()
        engine.data["ae"][0]["start_date"] = "2026-01-11"
        self.has(engine.run(), "AE", "start timing")

    def test_duplicate_repeat_key(self):
        engine = self.engine()
        engine.data["ae"][1]["repeat_key"] = engine.data["ae"][0]["repeat_key"]
        self.has(engine.run(), "AE", "repeat key")

    def test_missing_listing_record(self):
        engine = self.engine()
        engine.data["listing"].pop()
        self.has(engine.run(), "LISTING", "missing")

    def test_extra_listing_record(self):
        engine = self.engine()
        engine.data["listing"].append(dict(engine.data["listing"][0], repeat_key="EXTRA"))
        self.has(engine.run(), "LISTING", "Extra")

    def test_all_27_fields_are_compared(self):
        for field in self.config["fields"]:
            with self.subTest(field=field["name"]):
                engine = self.engine()
                engine.data["edc"][0][field["name"]] = "UNEXPECTED"
                result = engine.run()
                self.assertTrue(any(i.check_id == "EDC" and i.field == field["name"] for i in self.errors(result)))

    def test_null_is_distinct_from_zero_and_no(self):
        self.assertFalse(equal("", "0", {}, self.config))
        self.assertFalse(equal("", "N", {}, self.config))
        self.assertFalse(equal("0", "N", {}, self.config))

    def test_date_representation_is_field_specific(self):
        meta = next(f for f in self.config["fields"] if f["name"] == "start_date")
        self.assertTrue(equal("2026-01-10", "10 JAN 2026", meta, self.config))
        self.assertFalse(equal("2026-01-10", "10 JAN 2026", {}, self.config))

    def test_invalid_date_not_silently_normalized(self):
        with self.assertRaises(ValueError):
            normalize("2026-02-30", {"type": "date", "formats": ["%Y-%m-%d"]}, self.config)

    def test_case_normalization_does_not_change_comments(self):
        self.assertTrue(equal("Term", "TERM", {"case_sensitive": False}, self.config))
        self.assertFalse(equal("Comment", "COMMENT", {"case_sensitive": True}, self.config))

    def test_xml_wrong_production_metadata(self):
        self.xml_edit("DEMO-001_02_details.xml", lambda r: r.find("{*}ClinicalData").set("StudyOID", "WRONG"))
        self.has(self.engine().run(), "XML_STRUCTURE", "target identifier")

    def test_xml_wrong_odm_version(self):
        self.xml_edit("DEMO-001_02_details.xml", lambda r: r.set("ODMVersion", "1.3.2"))
        self.has(self.engine().run(), "XML_STRUCTURE", "version")

    def test_xml_missing_null_item(self):
        def edit(root):
            group = root.find(".//{*}ItemGroupData")
            group.remove(next(i for i in group if i.get("ItemOID") == "AE1.AESTUNK"))
        self.xml_edit("DEMO-001_02_details.xml", edit)
        self.has(self.engine().run(), "XML_STRUCTURE", "omitted")

    def test_xml_duplicate_item(self):
        def edit(root):
            group = root.find(".//{*}ItemGroupData")
            group.append(deepcopy(list(group)[0]))
        self.xml_edit("DEMO-001_02_details.xml", edit)
        self.has(self.engine().run(), "XML_STRUCTURE", "Duplicate")

    def test_xml_null_and_value_are_mutually_exclusive(self):
        def edit(root):
            root.find(".//{*}ItemData").set("IsNull", "Yes")
        self.xml_edit("DEMO-001_02_details.xml", edit)
        self.has(self.engine().run(), "XML_STRUCTURE", "but not both")

    def test_xml_activation_repeat_key_is_rejected(self):
        self.xml_edit("DEMO-001_01_activation.xml", lambda r: r.find(".//{*}ItemGroupData").set("ItemGroupRepeatKey", "1"))
        self.has(self.engine().run(), "XML_STRUCTURE", "Activation contains")

    def test_xml_activation_transaction_type_is_rejected(self):
        self.xml_edit("DEMO-001_01_activation.xml", lambda r: r.find(".//{*}ItemGroupData").set("TransactionType", "Upsert"))
        self.has(self.engine().run(), "XML_STRUCTURE", "Activation contains")

    def test_xml_detail_requires_upsert(self):
        self.xml_edit("DEMO-001_02_details.xml", lambda r: r.find(".//{*}ItemGroupData").set("TransactionType", "Insert"))
        self.has(self.engine().run(), "XML_STRUCTURE", "transaction type")

    def test_xml_one_subject_per_file(self):
        def edit(root):
            clinical = root.find("{*}ClinicalData")
            clinical.append(deepcopy(list(clinical)[0]))
        self.xml_edit("DEMO-001_02_details.xml", edit)
        self.has(self.engine().run(), "XML_STRUCTURE", "exactly one subject")

    def test_xml_dtd_is_rejected(self):
        path = self.path.parent / "artifacts/DEMO-001_02_details.xml"
        path.write_text('<!DOCTYPE ODM [<!ENTITY x "unsafe">]><ODM/>', encoding="utf-8")
        self.has(self.engine().run(), "XML_STRUCTURE", "entity declarations")

    def test_xml_unknown_namespace(self):
        path = self.path.parent / "artifacts/DEMO-001_02_details.xml"
        path.write_text(path.read_text().replace("http://www.cdisc.org/ns/odm/v1.3", "urn:unexpected"), encoding="utf-8")
        self.has(self.engine().run(), "XML_STRUCTURE", "namespace")

    def test_no_activation_is_not_inferred_from_absence(self):
        engine = self.engine()
        next(s for s in engine.data["subjects"] if s["subject_id"] == "DEMO-005")["coverage_confirmed"] = "false"
        self.has(engine.run(), "ACTIVATION", "coverage/authorization")

    def test_no_activation_cannot_hide_retained_findings(self):
        engine = self.engine()
        next(s for s in engine.data["subjects"] if s["subject_id"] == "DEMO-001")["expected_ae"] = "N"
        self.has(engine.run(), "ACTIVATION", "conflicts")

    def test_missing_activation(self):
        engine = self.engine()
        engine.config["xml_files"] = [p for p in engine.config["xml_files"] if "DEMO-005" not in p]
        self.has(engine.run(), "ACTIVATION", "missing")

    def test_zip_stale_file(self):
        path = self.path.parent / "artifacts/DEMO-001.pdf"
        path.write_bytes(path.read_bytes()+b"\nchanged")
        self.has(self.engine().run(), "PACKAGE", "stale")

    def test_zip_extra_file(self):
        path = self.path.parent / "artifacts/delivery.zip"
        with ZipFile(path, "a") as archive:
            archive.writestr("unexpected.txt", "unexpected")
        self.has(self.engine().run(), "PACKAGE", "inventory")

    def test_zip_unsafe_path(self):
        path = self.path.parent / "artifacts/delivery.zip"
        with ZipFile(path, "a") as archive:
            archive.writestr("../unexpected.txt", "unexpected")
        self.has(self.engine().run(), "PACKAGE", "unsafe")

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "optional PDF dependency")
    def test_pdf_text_fixture(self):
        engine = self.engine()
        engine.config["pdf_text"] = True
        result = engine.run()
        self.assertFalse(self.errors(result, "PDF_TEXT"))

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "optional PDF dependency")
    def test_pdf_missing_qualitative_result(self):
        path = make_example(self.root / "problem", issues=True)
        engine = Engine(load_config(path))
        engine.config["pdf_text"] = True
        self.has(engine.run(), "PDF_TEXT", "absent")

    def test_missing_input_is_not_passed(self):
        self.config["tables"].pop("listing")
        result = self.engine().run()
        self.assertEqual(next(c for c in result.checks if c.check_id == "LISTING").status, "NOT_RUN")
        self.has(result, "COVERAGE")

    def test_baseline_change_register(self):
        result = self.engine().run()
        self.assertTrue(any(c["field"] == "grade" and c["before"] == "2" and c["after"] == "1" for c in result.changes))

    def test_report_html_escapes_untrusted_values(self):
        result = self.engine().run()
        result.issues[0].observed = '<script>alert("example")</script>'
        write_reports(result, self.root / "out", "test")
        html = (self.root / "out/report.html").read_text(encoding="utf-8")
        self.assertNotIn('<script>alert("example")', html)
        self.assertIn("&lt;script&gt;", html)

    def test_csv_formula_guard(self):
        for value in ("=1+1", "+SUM(A1)", "-1+1", "@SUM(A1)", "\t=1", " =1"):
            with self.subTest(value=value):
                self.assertTrue(safe_csv(value).startswith("'"))
        self.assertEqual(safe_csv("Trace"), "Trace")

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "optional Excel dependency")
    def test_excel_report_is_not_formula_executable(self):
        from openpyxl import load_workbook
        result = self.engine().run()
        result.issues[0].observed = "=1+1"
        write_reports(result, self.root / "out", "test", xlsx=True)
        book = load_workbook(self.root / "out/report.xlsx", data_only=False)
        self.assertEqual(book["Issues"].cell(2, 8).data_type, "s")
        self.assertEqual(book["Issues"].cell(2, 8).value, "=1+1")
        book.close()

    def test_inputs_are_unchanged(self):
        before = {p: file_hash(p) for p in self.path.parent.rglob("*") if p.is_file()}
        result = self.engine().run()
        write_reports(result, self.root / "out", "test")
        self.assertEqual(before, {p: file_hash(p) for p in before})

    def test_cli_clean_exit(self):
        self.assertEqual(self.cli("run", "--config", str(self.path), "--output", str(self.root / "out")), 0)
        self.assertTrue((self.root / "out/report.html").is_file())

    def test_cli_issue_exit(self):
        path = make_example(self.root / "problem", issues=True)
        self.assertEqual(self.cli("run", "--config", str(path), "--output", str(self.root / "out")), 1)

    def test_cli_explicit_never_gate(self):
        path = make_example(self.root / "problem", issues=True)
        self.assertEqual(self.cli("run", "--config", str(path), "--output", str(self.root / "out"), "--fail-on", "never"), 0)

    def test_cli_refuses_silent_report_overwrite(self):
        out = self.root / "out"
        self.assertEqual(self.cli("run", "--config", str(self.path), "--output", str(out)), 0)
        original = (out / "run.json").read_bytes()
        self.assertEqual(self.cli("run", "--config", str(self.path), "--output", str(out)), 2)
        self.assertEqual((out / "run.json").read_bytes(), original)

    def test_cli_refuses_input_output_overlap(self):
        self.assertEqual(self.cli("run", "--config", str(self.path), "--output", str(self.path.parent), "--overwrite"), 2)

    def test_invalid_config_writes_failure_evidence(self):
        path = self.root / "invalid.json"
        path.write_text("{}", encoding="utf-8")
        self.assertEqual(self.cli("run", "--config", str(path), "--output", str(self.root / "out")), 2)
        self.assertTrue((self.root / "out/report.html").is_file())

    def test_duplicate_csv_header_is_rejected(self):
        (self.path.parent / "findings.csv").write_text("finding_id,finding_id\nF1,F1\n", encoding="utf-8")
        with self.assertRaises(InputError):
            self.engine()

    def test_oversized_csv_cell_is_an_input_error(self):
        path = self.path.parent / "findings.csv"
        path.write_text("finding_id\n" + "X"*150000 + "\n", encoding="utf-8")
        with self.assertRaises(InputError):
            self.engine()

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "optional Excel dependency")
    def test_corrupt_xlsx_is_an_input_error(self):
        path = self.path.parent / "subjects.xlsx"
        path.write_bytes(b"not a workbook")
        self.config["tables"]["subjects"] = {"path": "subjects.xlsx", "sheet": "Subjects"}
        with self.assertRaises(InputError):
            self.engine()

    def test_duplicate_item_mapping_is_rejected(self):
        config = json.loads(self.path.read_text())
        config["fields"][1]["item_oid"] = config["fields"][0]["item_oid"]
        self.path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaises(InputError):
            load_config(self.path)

    def test_bad_null_token_is_rejected(self):
        config = json.loads(self.path.read_text())
        config["null_tokens"].append("0")
        self.path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaises(InputError):
            load_config(self.path)

    def test_explicit_no_cannot_be_a_null_token(self):
        config = json.loads(self.path.read_text())
        config["null_tokens"].append("No")
        self.path.write_text(json.dumps(config), encoding="utf-8")
        with self.assertRaises(InputError):
            load_config(self.path)

    def test_explicit_checked_value_is_not_null(self):
        self.assertFalse(equal("", "1", {}, self.config))

    def test_explicit_field_map_can_normalize_target_unchecked_representation(self):
        self.assertTrue(equal("", "0", {"value_map": {"0": ""}}, self.config))

    def test_unrecognized_response_code_is_reported(self):
        engine = self.engine()
        engine.data["ae"][0]["drug_action"] = "999"
        self.has(engine.run(), "AE", "Unrecognized coded value")

    def test_universe_includes_manual_only_source_subjects(self):
        engine = self.engine()
        engine.data["subjects"] = [r for r in engine.data["subjects"] if r["subject_id"] != "DEMO-003"]
        engine.config["xml_files"] = [p for p in engine.config["xml_files"] if "DEMO-003" not in p]
        self.has(engine.run(), "ACTIVATION", "universe entry")

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "optional Excel dependency")
    def test_public_workbook_theme_has_no_non_english_font_names(self):
        result = self.engine().run()
        write_reports(result, self.root / "out", "test", xlsx=True)
        with ZipFile(self.root / "out/report.xlsx") as package:
            theme = ET.fromstring(package.read("xl/theme/theme1.xml"))
            for element in theme.iter():
                self.assertTrue(element.get("typeface", "").isascii())

    def test_mapped_csv_columns(self):
        path = self.path.parent / "subjects.csv"
        content = path.read_text().replace("subject_id,", "Participant,")
        path.write_text(content, encoding="utf-8")
        self.config["tables"]["subjects"] = {"path": "subjects.csv", "columns": {"subject_id": "Participant"}}
        self.assertFalse(self.errors(self.engine().run(), "ACTIVATION"))

    @unittest.skipUnless(importlib.util.find_spec("openpyxl"), "optional Excel dependency")
    def test_xlsx_adapter_rejects_formula_cells(self):
        from openpyxl import Workbook
        book = Workbook()
        sheet = book.active
        sheet.title = "Subjects"
        sheet.append(["subject_id", "expected_ae", "coverage_confirmed", "authorized_by", "authorized_at"])
        sheet.append(["=1+1", "N", "true", "Example Reviewer", "2026-01-15T10:00:00Z"])
        book.save(self.path.parent / "subjects.xlsx")
        self.config["tables"]["subjects"] = {"path": "subjects.xlsx", "sheet": "Subjects"}
        with self.assertRaises(InputError):
            self.engine()


if __name__ == "__main__":
    unittest.main()

