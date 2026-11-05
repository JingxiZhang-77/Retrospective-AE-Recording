"""Public-documentation-informed synthetic workflow, independent of study data."""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html import escape
import json
from pathlib import Path
import random
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from .config import example_fields, load_config
from .demo import AE_EXTRA, DECISION_COLUMNS, FINDING_COLUMNS, REVIEW_COLUMNS, pdf_bytes, write_csv
from .engine import Engine
from .io import file_hash
from .report import html_table, write_reports


SEED = 20261105
STAMP = "2027-02-20T12:00:00+00:00"
STANDARD_COMMENT = "No associated symptoms or additional intervention were reported in this simulated assessment."
MANAGEMENT_COMMENT = "The fictional reviewer documented a change in the monitoring schedule; no associated symptoms were reported."
REFERENCES = [
    {"reference_id": "NHANES-CBC", "title": "NHANES 2017-2018 Complete Blood Count with 5-Part Differential", "version": "2017-2018 (CBC_J)", "url": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/CBC_J.htm", "fields": "Hemoglobin (LBXHGB, g/dL); WBC (LBXWBCSI, 1000 cells/uL); platelets (LBXPLTSI, 1000 cells/uL)", "use": "Variable names and units only; no participant rows sampled."},
    {"reference_id": "NHANES-GLU", "title": "NHANES 2017-2018 Plasma Fasting Glucose", "version": "2017-2018 (GLU_J)", "url": "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/GLU_J.htm", "fields": "Fasting glucose (LBXGLU, mg/dL)", "use": "Variable type and units only; no population distribution fitted."},
    {"reference_id": "PTBXL-PLUS", "title": "PTB-XL+, a comprehensive electrocardiographic feature dataset", "version": "1.0.1", "url": "https://physionet.org/content/ptb-xl-plus/1.0.1/", "doi": "10.13026/g6h6-7g88", "fields": "ECG intervals in ms; record-level feature tables and diagnostic-statement context", "use": "Tabular ECG structure and units only; no ECG records or waveforms copied."},
    {"reference_id": "BIDMC", "title": "BIDMC PPG and Respiration Dataset", "version": "1.0.0", "url": "https://physionet.org/content/bidmc/1.0.0/", "doi": "10.13026/C2208R", "fields": "Heart rate (beats/min); respiratory rate (breaths/min); oxygen saturation (%)", "use": "Numeric vital-sign field definitions only; no waveform/numeric patient rows copied."},
]


def profile():
    fields = example_fields()
    for field in fields:
        if field["name"] in {"term", "grade", "start_date"}:
            field["required"] = True
    return {
        "release_id": "SIM-R2", "rule_version": "SIM-RULES-1", "expected_field_count": 27,
        "tables": {role: role + ".csv" for role in ("findings", "reviews", "decisions", "ae", "listing", "edc", "subjects", "baseline_ae", "pdf_index")},
        "fields": fields, "null_tokens": [""], "result_placeholders": ["Not available", "Pending"],
        "standard_comment": STANDARD_COMMENT,
        "source_field_map": {"source_result": "result", "source_unit": "unit", "source_test": "test_name", "source_specimen": "specimen", "source_category": "category", "source_assessment_datetime": "assessment_datetime"},
        "ae_defaults": {"ongoing": "", "end_date": "", "end_time": "", "stop_indeterminate": "1", "relatedness": "6", "outcome": "7"},
        "start_from_assessment": True,
        "required_checks": ["SOURCE", "REVIEW", "DECISION", "AE", "LISTING", "XML_STRUCTURE", "XML", "ACTIVATION", "EDC", "CHANGE", "PACKAGE", "PDF_INDEX", "PDF_TEXT"],
        "odm": {"versions": ["1.3"], "namespace": "http://www.cdisc.org/ns/odm/v1.3", "study_oid": "SYNTHETIC-WORKFLOW(Training)", "metadata_version_oid": "SIM-METADATA-1", "event_oid": "COM", "form_oid": "AE1", "item_group_oid": "AE1_LOG_LINE", "activation_form_oid": "AE1YN", "activation_group_oid": "AE1YN_LOG_LINE", "activation_item_oid": "AE1YN.AE1YN", "transaction_type": "Upsert", "one_subject_per_file": True},
        "xml_files": [], "packages": [], "pdf_text": True,
        "pdf_fields": ["term", "pi_term", "comments", "source_result", "source_unit", "source_test"],
    }


def make_observations(seed=SEED):
    rng = random.Random(seed)
    rows, subjects = [], []
    for n in range(1, 21):
        subject = f"SYN-{n:03d}"
        person = {"subject_id": subject, "age": str(rng.randint(25, 74)), "sex": "F" if n % 2 else "M", "synthetic": "true"}
        subjects.append(person)
        for slot in range(1, 6):
            fid = f"OBS-{(n-1)*5+slot:04d}"
            when = datetime(2027, 1, 10, 9) + timedelta(days=n*2, minutes=(slot-1)*10)
            domain = "LAB" if slot <= 2 else "ECG" if slot == 3 else "VS"
            abnormal = n <= 18 and ((n % 4 != 0) if slot == 1 else (n % 3 != 0) if slot == 2 else (n % 5 != 0) if slot == 3 else (n % 3 != 1) if slot == 4 else (n % 4 != 2))
            unit, lower, upper, specimen, category = "", "", "", "", domain
            reference = "BIDMC"
            if slot == 1:
                reference, specimen, category = "NHANES-CBC", "BLOOD", "HEMATOLOGY"
                option = (n-1) % 3
                if option == 0:
                    test, unit, lower, upper = "Hemoglobin", "g/dL", "13", "17"
                    result = f"{rng.uniform(10.1, 12.4) if abnormal else rng.uniform(13.5, 16.5):.1f}"
                elif option == 1:
                    test, unit, lower, upper = "White blood cell count", "1000 cells/uL", "4", "11"
                    result = f"{rng.uniform(11.5, 15.0) if abnormal else rng.uniform(5.0, 9.0):.1f}"
                else:
                    test, unit, lower, upper = "Platelet count", "1000 cells/uL", "150", "400"
                    result = str(rng.randint(110, 145) if abnormal else rng.randint(180, 350))
            elif slot == 2:
                reference, specimen, category = "NHANES-GLU", "PLASMA", "CHEMISTRY"
                test, unit, lower, upper = "Fasting glucose", "mg/dL", "70", "100"
                result = str(rng.randint(110, 150) if abnormal else rng.randint(80, 98))
            elif slot == 3:
                reference = "PTBXL-PLUS"
                if n % 3 == 0:
                    test = "ECG interpretation"
                    result = "Nonspecific ST-T pattern" if abnormal else "Normal synthetic interpretation"
                elif n % 2:
                    test, unit, lower, upper = "PR interval", "ms", "120", "200"
                    result = str(rng.randint(210, 230) if abnormal else rng.randint(130, 180))
                else:
                    test, unit, lower, upper = "QT interval", "ms", "350", "440"
                    result = str(rng.randint(460, 490) if abnormal else rng.randint(360, 420))
            elif slot == 4:
                test, unit, lower, upper = "Heart rate", "beats/min", "60", "100"
                result = str(rng.randint(105, 118) if abnormal else rng.randint(65, 90))
            else:
                test, unit, lower, upper = "Oxygen saturation", "%", "95", "100"
                result = str(rng.randint(92, 94) if abnormal else rng.randint(96, 99))
            # The bands and flags below are deliberately designed test controls,
            # not clinical reference intervals, diagnoses, or CTCAE derivations.
            missing = fid == "OBS-0067"
            if missing:
                result, abnormal = "Not available", True
            row = {key: "" for key in FINDING_COLUMNS}
            row.update(finding_id=fid, subject_id=subject, visit="FOLLOWUP", assessment_datetime=when.isoformat(sep=" "), domain=domain, test_name=test, specimen=specimen, category=category, canonical_test=test.lower().replace(" ", "_"), result=result, unit=unit, lower_limit=lower, upper_limit=upper, clinical_significance="Synthetic assessment pending" if abnormal else "Within demonstration band", review_required=str(abnormal and not missing).lower(), in_scope=str(abnormal).lower(), source_term=test + " finding", source_grade="" if missing or not abnormal else "2" if fid == "OBS-0008" else "1", source_version="SIM-S1", rule_version="SIM-RULES-1", consistency_flag="Not applicable in this simulation")
            row.update(reference_id=reference, synthetic="true", simulation_band_status="missing" if missing else "outside_demo_band" if abnormal else "within_demo_band", age=person["age"], sex=person["sex"])
            rows.append(row)
    assert len(rows) == 100 and len(subjects) == 20
    assert Counter(r["domain"] for r in rows) == {"LAB": 40, "ECG": 20, "VS": 40}
    return rows, subjects


def assemble(source, decision, reply, repeat_key, release_id):
    row = {field["name"]: "" for field in example_fields()}
    timestamp = datetime.fromisoformat(source["assessment_datetime"])
    row.update(ae_id=decision["ae_id"], finding_id=source["finding_id"], subject_id=source["subject_id"], repeat_key=str(repeat_key), release_id=release_id, term=decision["term_override"] or source["source_term"], grade=decision["grade_override"] or source["source_grade"], start_date=timestamp.date().isoformat(), start_time=timestamp.strftime("%H:%M"), local_related="N", last_related="N", wound_related="N", opioid_related="N", serious="N", discontinued="N", stop_indeterminate="1", relatedness="6", drug_action="1", outcome="7", no_action="1")
    for target, origin in profile()["source_field_map"].items():
        row[target] = source[origin]
    if decision["pi_fields_required"] == "true":
        row.update(pi_term=reply["confirmed_term"] or row["term"], comments=reply["comment"] or STANDARD_COMMENT)
    if reply.get("management") == "modified":
        row.update(no_action="", other_action="1", other_action_specify="Simulated monitoring schedule adjustment")
    return row


def resolved_tables(seed=SEED):
    observations, people = make_observations(seed)
    reviews, decisions, aes, manual = [], [], [], []
    repeats = Counter()
    for source in observations:
        fid = source["finding_id"]
        active = source["in_scope"] == "true"
        route = "automated" if active else "excluded"
        if fid == "OBS-0067" or fid in {"OBS-0033", "OBS-0053"}:
            route = "excluded"
        if fid in {"OBS-0021", "OBS-0046"}:
            route = "manual"
        if fid == "OBS-0038":
            route = "existing"
        reply = {}
        if source["review_required"] == "true":
            reply = {key: "" for key in REVIEW_COLUMNS}
            reply.update({key: source[key] for key in ("finding_id", "subject_id", "visit", "assessment_datetime", "test_name", "specimen", "source_version")})
            reply.update(review_id="SIM-REVIEW-"+fid, assessment="not_ae" if route == "excluded" else "remains_ncs", is_ae="N" if route == "excluded" or fid == "OBS-0018" else "Y", symptoms="none", management="modified" if fid == "OBS-0007" else "none", confirmed_term="Other specified ECG finding: simulated nonspecific ST-T pattern" if fid == "OBS-0028" else source["source_term"], comment=MANAGEMENT_COMMENT if fid == "OBS-0007" else "Fictional reviewer determined that the observation did not require AE recording." if route == "excluded" else "", status="confirmed", reviewer="Simulated Investigator", reviewed_at=STAMP, source_version="SIM-S1", review_version="SIM-REVIEW-R2")
            reviews.append(reply)
        decision = {key: "" for key in DECISION_COLUMNS}
        decision.update(decision_id="SIM-DECISION-"+fid, finding_id=fid, route=route, ae_id="SIM-AE-"+fid if route in {"automated", "manual", "existing"} else "", owner="Simulated Data Manager", reason="Scripted recording decision for demonstration" if active else "Within demonstration band; no candidate AE recording", authorized_by="Simulated Medical Reviewer", authorized_at=STAMP, source_version="SIM-S1", review_version=reply.get("review_version", ""), rule_version="SIM-RULES-1", pi_fields_required=str(route == "automated").lower(), confirmation_status="confirmed")
        if fid == "OBS-0067":
            decision["reason"] = "Missing observation; exclude from simulated AE output"
        if fid == "OBS-0018":
            decision.update(conflict_resolution="assessment_precedence", reason="Scripted authorization resolves the conflicting assessment/checkbox selection")
        if fid == "OBS-0008":
            decision.update(grade_override="1", override_reference="SIMULATED-OVERRIDE-001")
        decisions.append(decision)
        if route in {"automated", "manual", "existing"}:
            repeats[source["subject_id"]] += 1
            ae = assemble(source, decision, reply, repeats[source["subject_id"]], "SIM-R2")
            (aes if route == "automated" else manual).append(ae)
    edc = deepcopy(aes) + manual
    for index, row in enumerate(edc):
        if index % 7 == 0:
            row["start_date"] = datetime.strptime(row["start_date"], "%Y-%m-%d").strftime("%d %b %Y").upper()
        if index % 11 == 0:
            row["term"] = row["term"].upper()
    subjects = [{"subject_id": p["subject_id"], "expected_ae": "Y" if any(a["subject_id"] == p["subject_id"] for a in edc) else "N", "coverage_confirmed": "true", "authorized_by": "Simulated Medical Reviewer", "authorized_at": STAMP} for p in people]
    return {"findings": observations, "reviews": reviews, "decisions": decisions, "ae": aes, "listing": deepcopy(aes), "edc": edc, "subjects": subjects}, people


CASES = [
    ("SIM-C01", "OBS-0003", "REVIEW", "Required mock review omitted", "Supply the scripted confirmed reply and refresh the decision"),
    ("SIM-C02", "OBS-0018", "REVIEW", "Conflicting assessment/checkbox without authorization", "Document the scripted precedence instruction"),
    ("SIM-C03", "OBS-0007", "AE", "Modified management with unsupported no-intervention comment", "Use the scripted reviewer comment and reconcile action fields"),
    ("SIM-C04", "OBS-0008", "AE", "Authorized grade override not carried into AE data", "Apply the documented synthetic override across outputs"),
    ("SIM-C05", "OBS-0028", "AE", "Reviewed term not carried into field 26", "Transfer the scripted confirmed term"),
    ("SIM-C06", "OBS-0017", "AE", "Comment exceeds the target length", "Use the scripted reviewer-approved replacement"),
    ("SIM-C07", "OBS-0013", "LISTING", "Unitless ECG interpretation missing from listing/PDF", "Restore the complete qualitative source result"),
    ("SIM-C08", "OBS-0021", "DECISION", "Manual recording lacks stored-record evidence", "Restore the linked simulated EDC record"),
    ("SIM-C09", "OBS-0043", "EDC", "Expected stored AE is missing", "Reconcile the local fictional download"),
    ("SIM-C10", "", "EDC", "Undocumented extra stored AE", "Remove the deliberately injected extra record"),
    ("SIM-C11", "", "XML_STRUCTURE", "Null ItemData omitted", "Include the expected item with IsNull=Yes"),
    ("SIM-C12", "", "XML_STRUCTURE", "Wrong target study metadata", "Use the declared fictional training target"),
    ("SIM-C13", "", "ACTIVATION", "No-AE subject incorrectly activated Yes", "Use the approved synthetic subject decision"),
    ("SIM-C14", "", "PACKAGE", "ZIP contains an older report version", "Rebuild from the checked current files"),
]


def initial_tables(resolved):
    data = deepcopy(resolved)
    data["reviews"] = [r for r in data["reviews"] if r["finding_id"] != "OBS-0003"]
    for reply in data["reviews"]:
        reply["review_version"] = "SIM-REVIEW-R1"
        if reply["finding_id"] == "OBS-0007":
            reply["comment"] = ""
    for decision in data["decisions"]:
        if decision["review_version"]:
            decision["review_version"] = "SIM-REVIEW-R1"
        if decision["finding_id"] == "OBS-0018":
            decision.update(conflict_resolution="", authorized_by="", authorized_at="")
        if decision["finding_id"] == "OBS-0003":
            decision["route"] = "pending"
    for role in ("ae", "listing", "edc"):
        for row in data[role]:
            row["release_id"] = "SIM-R1"
    for row in data["ae"]:
        fid = row["finding_id"]
        if fid == "OBS-0007":
            row.update(comments=STANDARD_COMMENT, no_action="1", other_action="", other_action_specify="")
        elif fid == "OBS-0008":
            row["grade"] = "2"
        elif fid == "OBS-0028":
            row["pi_term"] = row["term"]
        elif fid == "OBS-0017":
            row["comments"] = "Synthetic overlength comment: " + "X"*180
    for row in data["listing"]:
        if row["finding_id"] == "OBS-0013":
            row["source_result"] = ""
    data["edc"] = [row for row in data["edc"] if row["finding_id"] not in {"OBS-0021", "OBS-0043"}]
    extra = deepcopy(data["edc"][0])
    extra.update(ae_id="SIM-EXTRA-AE", repeat_key="999", finding_id="SIM-EXTRA-FINDING")
    data["edc"].append(extra)
    return data


def odm_bytes(subject, config, rows=None, activation=None):
    target = config["odm"]
    root = ET.Element("ODM", {"xmlns": target["namespace"], "ODMVersion": "1.3", "FileType": "Transactional", "FileOID": "SYNTHETIC-"+subject, "CreationDateTime": STAMP})
    clinical = ET.SubElement(root, "ClinicalData", {"StudyOID": target["study_oid"], "MetaDataVersionOID": target["metadata_version_oid"]})
    person = ET.SubElement(clinical, "SubjectData", {"SubjectKey": subject})
    event = ET.SubElement(person, "StudyEventData", {"StudyEventOID": "COM", "StudyEventRepeatKey": "1"})
    form = ET.SubElement(event, "FormData", {"FormOID": target["activation_form_oid"] if activation is not None else target["form_oid"], "FormRepeatKey": "1"})
    if activation is not None:
        group = ET.SubElement(form, "ItemGroupData", {"ItemGroupOID": target["activation_group_oid"]})
        ET.SubElement(group, "ItemData", {"ItemOID": target["activation_item_oid"], "Value": activation})
    else:
        for row in rows:
            group = ET.SubElement(form, "ItemGroupData", {"ItemGroupOID": target["item_group_oid"], "ItemGroupRepeatKey": row["repeat_key"], "TransactionType": "Upsert"})
            for field in config["fields"]:
                attrs = {"ItemOID": field["item_oid"]}
                attrs.update({"Value": row[field["name"]]} if row[field["name"]] else {"IsNull": "Yes"})
                ET.SubElement(group, "ItemData", attrs)
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def write_phase(directory, data, baseline, initial=False):
    directory.mkdir(parents=True, exist_ok=True)
    artifacts = directory / "artifacts"
    artifacts.mkdir(exist_ok=True)
    config = profile()
    config["release_id"] = "SIM-R1" if initial else "SIM-R2"
    data["baseline_ae"] = deepcopy(baseline)
    members, index = [], []
    for person in data["subjects"]:
        subject = person["subject_id"]
        activation_file = f"artifacts/{subject}_01_activation.xml"
        (directory / activation_file).write_bytes(odm_bytes(subject, config, activation=person["expected_ae"]))
        config["xml_files"].append(activation_file)
        members.append({"name": Path(activation_file).name, "path": activation_file})
        rows = [r for r in data["ae"] if r["subject_id"] == subject]
        if not rows:
            continue
        detail_file = f"artifacts/{subject}_02_details.xml"
        (directory / detail_file).write_bytes(odm_bytes(subject, config, rows=rows))
        config["xml_files"].append(detail_file)
        members.append({"name": Path(detail_file).name, "path": detail_file})
        pdf_file = f"artifacts/{subject}.pdf"
        lines = ["FICTIONAL WORKFLOW DEMONSTRATION - NOT FOR CLINICAL USE", "Subject: "+subject]
        for row in [r for r in data["listing"] if r["subject_id"] == subject]:
            lines += ["Record: "+row["ae_id"]] + [key+": "+row.get(key, "") for key in [*[f["name"] for f in config["fields"]], *config["source_field_map"]]]
        (directory / pdf_file).write_bytes(pdf_bytes(lines))
        index.append({"subject_id": subject, "path": pdf_file})
        members.append({"name": Path(pdf_file).name, "path": pdf_file})
    archive_file = "artifacts/delivery.zip"
    with ZipFile(directory / archive_file, "w", ZIP_DEFLATED) as archive:
        for item in members:
            archive.write(directory / item["path"], item["name"])
    config["packages"].append({"path": archive_file, "members": members})
    if initial:
        # Introduce explicit negative controls after building the package.
        path = artifacts / "SYN-001_02_details.xml"
        root = ET.fromstring(path.read_bytes())
        group = root.find(".//{*}ItemGroupData")
        group.remove(next(item for item in group if item.get("ItemOID") == "AE1.AESTUNK"))
        path.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
        path = artifacts / "SYN-002_02_details.xml"
        root = ET.fromstring(path.read_bytes())
        root.find("{*}ClinicalData").set("StudyOID", "SYNTHETIC-WORKFLOW(IncorrectTarget)")
        path.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))
        (artifacts / "SYN-020_01_activation.xml").write_bytes(odm_bytes("SYN-020", config, activation="Y"))
        (artifacts / "SYN-003.pdf").write_bytes(pdf_bytes(["FICTIONAL INCOMPLETE REPORT", "Subject: SYN-003"]))
    data["pdf_index"] = index
    columns = {
        "findings": FINDING_COLUMNS + ["reference_id", "synthetic", "simulation_band_status", "age", "sex"],
        "reviews": REVIEW_COLUMNS, "decisions": DECISION_COLUMNS,
        "subjects": ["subject_id", "expected_ae", "coverage_confirmed", "authorized_by", "authorized_at"],
        "pdf_index": ["subject_id", "path"],
    }
    for role in ("ae", "listing", "edc", "baseline_ae"):
        columns[role] = AE_EXTRA + [f["name"] for f in config["fields"]]
    for role, rows in data.items():
        write_csv(directory / (role+".csv"), rows, columns[role])
    path = directory / "study.json"
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return path


def generate_simulation(directory, seed=SEED):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    resolved, people = resolved_tables(seed)
    initial = initial_tables(resolved)
    paths = {
        "01_initial": write_phase(directory / "01_initial", initial, initial["ae"], True),
        "02_resolved": write_phase(directory / "02_resolved", resolved, initial["ae"]),
    }
    raw = deepcopy(resolved["findings"])
    write_csv(directory / "source_observations.csv", raw, list(raw[0]))
    write_csv(directory / "synthetic_subjects.csv", people, list(people[0]))
    write_csv(directory / "scenario_cases.csv", [dict(zip(("case_id", "finding_id", "expected_check", "initial_problem", "scripted_resolution"), row)) for row in CASES], ["case_id", "finding_id", "expected_check", "initial_problem", "scripted_resolution"])
    references = {"accessed": "2026-11-05", "method": "Public data documentation informed field names, units, and table structure only. No participant data were downloaded, sampled, linked, or fitted. Values, demonstration bands, severity codes, reviews, decisions, and target metadata are independently fictional.", "seed": seed, "references": REFERENCES}
    (directory / "references.json").write_text(json.dumps(references, indent=2) + "\n", encoding="utf-8")
    summary = {
        "seed": seed, "subjects": len(people), "observations": len(raw), "domains": dict(Counter(r["domain"] for r in raw)),
        "review_requests": sum(r["review_required"] == "true" for r in raw),
        "in_scope_observations": sum(r["in_scope"] == "true" for r in raw),
        "routes": dict(Counter(r["route"] for r in resolved["decisions"])),
        "retained_ae": len(resolved["ae"]), "edc_ae": len(resolved["edc"]),
        "activation": dict(Counter(r["expected_ae"] for r in resolved["subjects"])),
        "cases": len(CASES), "fictional": True,
    }
    (directory / "simulation_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return paths, summary


def save_data_workbook(destination, tables, people, references):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.writer.theme import theme_xml
    book = Workbook()
    book.remove(book.active)
    theme = ET.fromstring(theme_xml)
    for item in theme.iter():
        if not item.get("typeface", "").isascii():
            item.set("typeface", "Arial")
    book.loaded_theme = ET.tostring(theme, encoding="utf-8")
    book.properties.creator = book.properties.lastModifiedBy = "Finding-to-AE Review Toolkit"
    all_tables = {"Subjects": people, "Public_References": references}
    all_tables.update({key.title(): value for key, value in tables.items() if key != "pdf_index"})
    for name, rows in all_tables.items():
        sheet = book.create_sheet(name[:31])
        headers = list(rows[0]) if rows else ["No rows"]
        sheet.append(headers)
        for row in rows:
            sheet.append([str(row.get(key, "")) for key in headers])
            for cell in sheet[sheet.max_row]:
                cell.data_type = "s"
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.fill = PatternFill("solid", fgColor="173B59")
            cell.font = Font(bold=True, color="FFFFFF")
        for row in sheet:
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(48, max(18, len(str(column[0].value))+4))
    book.save(destination)


def run_simulation(inputs, output, seed=SEED):
    inputs, output = Path(inputs), Path(output)
    paths, summary = generate_simulation(inputs, seed)
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for phase, path in paths.items():
        engine = Engine(load_config(path))
        result = engine.run()
        result.limitations.insert(0, "Entirely fictional demonstration: no public participant rows or private study data were used. Investigator reviews and authorizations are scripted, not real clinical assessments.")
        write_reports(result, output / phase, file_hash(path), xlsx=True)
        save_data_workbook(output / phase / "Simulation_Data.xlsx", engine.data, [{"subject_id": row["subject_id"], "expected_ae": row["expected_ae"], "synthetic": "true"} for row in engine.data["subjects"]], REFERENCES)
        results[phase] = result
    first, final = results["01_initial"], results["02_resolved"]
    assert first.counts()["ERROR"] > 0
    assert final.counts()["ERROR"] == final.counts()["WARNING"] == 0, final.counts()
    assert all(check.status != "NOT_RUN" for check in final.checks)
    detection = []
    for cid, fid, check, problem, resolution in CASES:
        found = [issue for issue in first.issues if issue.check_id == check and issue.severity == "ERROR" and (not fid or issue.finding_id == fid)]
        assert found, (cid, check, fid)
        detection.append({"case_id": cid, "finding_id": fid, "check": check, "problem": problem, "detected": "Yes", "scripted_resolution": resolution, "final_blocking_issues": "0"})
    write_csv(output / "scenario_detection.csv", detection, list(detection[0]))
    summary["phases"] = {key: {"counts": value.counts(), "coverage_complete": all(c.status != "NOT_RUN" for c in value.checks)} for key, value in results.items()}
    summary["detected_scenarios"] = len(detection)
    (output / "simulation_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    sections = ["<h1>Public-reference Synthetic Workflow</h1>", "<p><strong>20 fictional subjects; 100 observations; no private study data.</strong> Public sources informed field structure and units only. Values, medical reviews, authorizations, reference bands, and severity codes are scripted test controls, not clinical evidence or CTCAE grading.</p>"]
    sections.append("<p>LAB: 40; ECG: 20; vital signs: 40. Scripted review requests: 65. Final automated AEs: 60; manual entries: 2; existing AE links: 1; exclusions: 37. Activation: 18 Yes and 2 No.</p>")
    sections.append("<h2>Workflow</h2><p>Generate observations → identify demonstration candidates → request scripted review → assign recording routes → assemble AE fields → generate PDF/XML and a local EDC snapshot → run verification → apply scripted resolutions → repeat verification.</p>")
    rows = [{"phase": key, **result.counts(), "checks_run": sum(c.status != "NOT_RUN" for c in result.checks)} for key, result in results.items()]
    sections.extend(["<h2>Before and after</h2>", html_table(rows, ["phase", "ERROR", "WARNING", "INFO", "checks_run"]), '<p><a href="01_initial/report.html">Initial issue report</a> | <a href="02_resolved/report.html">Resolved verification report</a> | <a href="02_resolved/Simulation_Data.xlsx">Resolved simulation workbook</a></p>', "<h2>Scenario checks</h2>", html_table(detection, list(detection[0])), "<h2>Reference sources</h2>"])
    for reference in REFERENCES:
        sections.append('<p><a href="'+escape(reference["url"], quote=True)+'">'+escape(reference["title"])+"</a><br>"+escape(reference["use"])+"</p>")
    sections.append("<p>The public datasets are different populations and were not linked. No waveform realism, medical validity, real investigator confirmation, live upload, or clinical validation is claimed.</p>")
    document = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Synthetic workflow overview</title><style>body{font:15px/1.5 system-ui,sans-serif;margin:32px;color:#172b40}h1,h2{color:#173b59}table{border-collapse:collapse;width:100%}th,td{border-bottom:1px solid #cad7e2;padding:9px;text-align:left;vertical-align:top}th{background:#edf3f8}.scroll{overflow:auto}a{color:#17528a}</style></head><body>'+"".join(sections)+"</body></html>"
    (output / "Simulation_Overview.html").write_text(document, encoding="utf-8")
    return summary

