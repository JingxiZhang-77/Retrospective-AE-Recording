"""Deterministic, entirely fictional fixtures for demonstration and regression tests."""
import csv
from copy import deepcopy
import json
from pathlib import Path
from textwrap import wrap
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from .config import example_fields


STAMP = "2026-01-15T10:00:00+00:00"
COMMENT = "Asymptomatic and no medical intervention needed"
FINDING_COLUMNS = ["finding_id", "subject_id", "visit", "assessment_datetime", "domain", "test_name", "specimen", "category", "canonical_test", "result", "unit", "lower_limit", "upper_limit", "clinical_significance", "review_required", "in_scope", "source_term", "source_grade", "source_version", "rule_version", "consistency_flag"]
REVIEW_COLUMNS = ["review_id", "finding_id", "subject_id", "visit", "assessment_datetime", "test_name", "specimen", "assessment", "is_ae", "symptoms", "management", "confirmed_term", "comment", "status", "reviewer", "reviewed_at", "source_version", "review_version"]
DECISION_COLUMNS = ["decision_id", "finding_id", "route", "ae_id", "owner", "reason", "authorized_by", "authorized_at", "source_version", "review_version", "rule_version", "pi_fields_required", "confirmation_status", "conflict_resolution", "term_override", "grade_override", "comment_override", "pi_term_override", "override_reference"]
AE_EXTRA = ["ae_id", "finding_id", "subject_id", "repeat_key", "source_result", "source_unit", "source_test", "source_specimen", "source_category", "source_assessment_datetime", "release_id"]


def write_csv(path, rows, headers):
    with Path(path).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def example_ae(source, key, repeat, pi_term="", comments=""):
    row = {field["name"]: "" for field in example_fields()}
    row.update({
        "ae_id": key, "finding_id": source["finding_id"], "subject_id": source["subject_id"],
        "repeat_key": str(repeat), "source_result": source["result"], "source_unit": source["unit"], "release_id": "DEMO-R2",
        "source_test": source["test_name"], "source_specimen": source["specimen"], "source_category": source["category"], "source_assessment_datetime": source["assessment_datetime"],
        "term": source["source_term"], "grade": source["source_grade"], "start_date": "2026-01-10", "start_time": "09:00",
        "local_related": "N", "last_related": "N", "wound_related": "N", "opioid_related": "N", "serious": "N", "discontinued": "N",
        "stop_indeterminate": "1", "relatedness": "6", "drug_action": "1", "no_action": "1", "outcome": "7", "pi_term": pi_term, "comments": comments,
    })
    return row


def pdf_bytes(lines):
    """Minimal text PDF fixture, not a production clinical reporting engine."""
    escaped = []
    for line in lines:
        for part in wrap(str(line), width=100, break_long_words=False) or [""]:
            escaped.append(part.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)"))
    pages = [escaped[i:i+65] for i in range(0, len(escaped), 65)] or [[]]
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"", b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for page in pages:
        number = len(objects) + 1
        content_number = number + 1
        kids.append(f"{number} 0 R")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_number} 0 R >>".encode("ascii"))
        stream = ("BT /F1 8 Tf 10 TL 40 755 Td\n" + "\n".join(f"({line}) Tj T*" for line in page) + "\nET").encode("ascii")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream")
    objects[1] = f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(kids)}] >>".encode("ascii")
    output, offsets = bytearray(b"%PDF-1.4\n"), [0]
    for index, value in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii") + value + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return bytes(output)


def xml_document(subject, fields, rows=None, activation=None):
    root = ET.Element("ODM", {"xmlns": "http://www.cdisc.org/ns/odm/v1.3", "ODMVersion": "1.3", "FileType": "Transactional", "FileOID": "DEMO-" + subject, "CreationDateTime": STAMP})
    clinical = ET.SubElement(root, "ClinicalData", {"StudyOID": "DEMO-STUDY(Prod)", "MetaDataVersionOID": "DEMO-MDV-1"})
    person = ET.SubElement(clinical, "SubjectData", {"SubjectKey": subject})
    event = ET.SubElement(person, "StudyEventData", {"StudyEventOID": "COM", "StudyEventRepeatKey": "1"})
    form = ET.SubElement(event, "FormData", {"FormOID": "AE1YN" if activation is not None else "AE1", "FormRepeatKey": "1"})
    if activation is not None:
        group = ET.SubElement(form, "ItemGroupData", {"ItemGroupOID": "AE1YN_LOG_LINE"})
        ET.SubElement(group, "ItemData", {"ItemOID": "AE1YN.AE1YN", "Value": activation})
    else:
        for row in rows or []:
            group = ET.SubElement(form, "ItemGroupData", {"ItemGroupOID": "AE1_LOG_LINE", "ItemGroupRepeatKey": row["repeat_key"], "TransactionType": "Upsert"})
            for field in fields:
                attrs = {"ItemOID": field["item_oid"]}
                attrs.update({"Value": row[field["name"]]} if row[field["name"]] else {"IsNull": "Yes"})
                ET.SubElement(group, "ItemData", attrs)
    ET.indent(root)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def make_example(destination, issues=False):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    artifacts = destination / "artifacts"
    artifacts.mkdir(exist_ok=True)
    specifications = [
        ("F001", "DEMO-001", "ECG", "T wave abnormality", "", "", "T wave abnormality", "1", "automated", True),
        ("F002", "DEMO-001", "LAB", "Potassium", "3.2", "mmol/L", "Potassium decreased", "1", "automated", True),
        ("F003", "DEMO-002", "LAB", "Occult blood", "Trace", "", "Urinary occult blood positive", "1", "automated", True),
        ("F004", "DEMO-002", "LAB", "Erythrocytes", "6-10", "/HPF", "Hematuria", "1", "automated", True),
        ("F005", "DEMO-003", "LAB", "Protein", "See Below", "", "Protein abnormal", "1", "excluded", False),
        ("F006", "DEMO-003", "VS", "Oxygen saturation", "87", "%", "Oxygen saturation decreased", "3", "manual", False),
        ("F007", "DEMO-004", "LAB", "Glucose", "110", "mg/dL", "Glucose increased", "1", "excluded", False),
        ("F008", "DEMO-004", "LAB", "Lymphocytes", "4.5", "K/uL", "Lymphocyte count increased", "2", "automated", True),
    ]
    findings, reviews, decisions, aes = [], [], [], []
    repeat = {}
    for fid, subject, domain, test, result, unit, term, grade, route, needs_review in specifications:
        finding = {key: "" for key in FINDING_COLUMNS}
        finding.update(finding_id=fid, subject_id=subject, visit="POSTDOSE" if fid != "F007" else "SCREENING", assessment_datetime="2026-01-10 09:00:00", domain=domain, test_name=test, result=result or "Abnormal interpretation", unit=unit, source_term=term, source_grade=grade, in_scope="false" if fid == "F007" else "true", review_required=str(needs_review).lower(), source_version="S1", rule_version="RULES-1", clinical_significance="NCS")
        finding["category"] = "URINALYSIS" if fid in {"F003", "F004", "F005"} else "OTHER"
        finding["specimen"] = "URINE" if finding["category"] == "URINALYSIS" else ""
        finding["canonical_test"] = "urine_rbc" if fid == "F004" else test.casefold()
        finding["consistency_flag"] = "Inconsistent" if fid == "F006" else "Consistent"
        findings.append(finding)
        reply = None
        if needs_review:
            reply = {key: "" for key in REVIEW_COLUMNS}
            reply.update({key: finding[key] for key in ("finding_id", "subject_id", "visit", "assessment_datetime", "test_name", "specimen", "source_version")})
            reply.update(review_id="R-"+fid, assessment="remains_ncs", is_ae="N" if fid == "F001" else "Y", symptoms="none", management="modified" if fid == "F002" else "none", confirmed_term="Cardiac disorders - Other, specify: reviewed nonspecific finding" if fid == "F001" else term, comment="No symptoms were reported. The existing medication schedule was adjusted following investigator review." if fid == "F002" else "", status="confirmed", reviewer="Example Investigator", reviewed_at=STAMP, review_version="R1")
            reviews.append(reply)
        decision = {key: "" for key in DECISION_COLUMNS}
        decision.update(decision_id="D-"+fid, finding_id=fid, route=route, owner="Example DM", reason="Reviewed recording decision" if route == "automated" else "Missing result" if fid == "F005" else "Outside recording scope" if fid == "F007" else "Separate manual recording verified", authorized_by="Example Medical Reviewer", authorized_at=STAMP, source_version="S1", review_version="R1" if needs_review else "", rule_version="RULES-1", pi_fields_required=str(needs_review).lower(), confirmation_status="confirmed")
        if fid == "F001":
            decision["conflict_resolution"] = "assessment_precedence"
        if fid == "F008":
            decision.update(grade_override="1", override_reference="DEMO-OVERRIDE-1")
        if route in {"automated", "manual"}:
            decision["ae_id"] = "AE-"+fid
        decisions.append(decision)
        if route == "automated":
            repeat[subject] = repeat.get(subject, 0) + 1
            ae = example_ae(finding, decision["ae_id"], repeat[subject], reply["confirmed_term"], reply["comment"] or COMMENT)
            if fid == "F008":
                ae["grade"] = "1"
            if fid == "F002":
                ae.update(no_action="", conmed="1")
            aes.append(ae)
    listing, edc, baseline = deepcopy(aes), deepcopy(aes), deepcopy(aes)
    for row in baseline:
        row["release_id"] = "DEMO-R1"
        if row["finding_id"] == "F008":
            row["grade"] = "2"
    manual_source = next(f for f in findings if f["finding_id"] == "F006")
    edc.append(example_ae(manual_source, "AE-F006", "99"))
    subjects = [{"subject_id": f"DEMO-{n:03d}", "expected_ae": "N" if n == 5 else "Y", "coverage_confirmed": "true", "authorized_by": "Example Medical Reviewer", "authorized_at": STAMP} for n in range(1, 6)]
    fields = example_fields()
    for item in fields:
        if item["name"] in {"term", "grade", "start_date"}:
            item["required"] = True
    config = {
        "release_id": "DEMO-R2", "rule_version": "RULES-1", "expected_field_count": 27,
        "tables": {role: role+".csv" for role in ("findings", "reviews", "decisions", "ae", "listing", "edc", "subjects", "baseline_ae", "pdf_index")},
        "fields": fields, "null_tokens": [""], "result_placeholders": ["See Below", "See Report", "Pending"],
        "standard_comment": COMMENT,
        "ae_defaults": {"ongoing": "", "end_date": "", "end_time": "", "stop_indeterminate": "1", "relatedness": "6", "outcome": "7"},
        "source_field_map": {"source_result": "result", "source_unit": "unit", "source_test": "test_name", "source_specimen": "specimen", "source_category": "category", "source_assessment_datetime": "assessment_datetime"},
        "start_from_assessment": True,
        "automated_grade_ceilings": {"LAB": "2", "ECG": "2", "VS": "3"}, "require_inconsistent_flag": True,
        "test_aliases": [{"aliases": ["RBC", "Erythrocytes", "Erythrocyte"], "category": "URINALYSIS", "canonical_test": "urine_rbc"}],
        "required_checks": ["SOURCE", "REVIEW", "DECISION", "AE", "LISTING", "XML_STRUCTURE", "XML", "ACTIVATION", "EDC", "CHANGE", "PACKAGE", "PDF_INDEX"],
        "odm": {"versions": ["1.3"], "namespace": "http://www.cdisc.org/ns/odm/v1.3", "study_oid": "DEMO-STUDY(Prod)", "metadata_version_oid": "DEMO-MDV-1", "event_oid": "COM", "form_oid": "AE1", "item_group_oid": "AE1_LOG_LINE", "activation_form_oid": "AE1YN", "activation_group_oid": "AE1YN_LOG_LINE", "activation_item_oid": "AE1YN.AE1YN", "transaction_type": "Upsert", "one_subject_per_file": True},
        "xml_files": [], "packages": [], "pdf_text": False,
    }
    pdf_index, package_members = [], []
    for person in subjects:
        subject = person["subject_id"]
        activation_name = f"artifacts/{subject}_01_activation.xml"
        (destination / activation_name).write_bytes(xml_document(subject, fields, activation=person["expected_ae"]))
        config["xml_files"].append(activation_name)
        package_members.append({"name": Path(activation_name).name, "path": activation_name})
        rows = [row for row in aes if row["subject_id"] == subject]
        if rows:
            detail_name = f"artifacts/{subject}_02_details.xml"
            (destination / detail_name).write_bytes(xml_document(subject, fields, rows))
            config["xml_files"].append(detail_name)
            package_members.append({"name": Path(detail_name).name, "path": detail_name})
            pdf_name = f"artifacts/{subject}.pdf"
            lines = ["Fictional review fixture - not for clinical use", "Subject: "+subject]
            for row in rows:
                lines += ["Record: "+row["ae_id"]] + [name+": "+row.get(name, "") for name in [*[f["name"] for f in fields], "source_result", "source_unit"]]
            (destination / pdf_name).write_bytes(pdf_bytes(lines))
            pdf_index.append({"subject_id": subject, "path": pdf_name})
            package_members.append({"name": Path(pdf_name).name, "path": pdf_name})
    package_name = "artifacts/delivery.zip"
    with ZipFile(destination / package_name, "w", ZIP_DEFLATED) as archive:
        for entry in package_members:
            archive.write(destination / entry["path"], entry["name"])
    config["packages"].append({"path": package_name, "members": package_members})
    if issues:
        reviews[:] = [r for r in reviews if r["finding_id"] != "F004"]
        next(d for d in decisions if d["finding_id"] == "F001")["conflict_resolution"] = ""
        next(r for r in reviews if r["finding_id"] == "F002")["comment"] = ""
        next(a for a in aes if a["finding_id"] == "F002").update(comments=COMMENT, no_action="1")
        next(a for a in aes if a["finding_id"] == "F003")["comments"] = "X"*201
        next(a for a in aes if a["finding_id"] == "F008")["grade"] = "2"
        next(f for f in findings if f["finding_id"] == "F003")["result"] = "See Below"
        next(a for a in listing if a["finding_id"] == "F004")["source_result"] = ""
        edc[:] = [r for r in edc if r["finding_id"] != "F006"]
        next(a for a in edc if a["finding_id"] == "F003")["pi_term"] = "Unconfirmed infection term"
        next(d for d in decisions if d["finding_id"] == "F008")["source_version"] = "S0"
        next(f for f in findings if f["finding_id"] == "F006")["consistency_flag"] = "Consistent"
        xml_path = artifacts / "DEMO-001_02_details.xml"
        payload = xml_path.read_text(encoding="utf-8")
        payload = payload.replace('      <ItemData ItemOID="AE1.AESTUNK" IsNull="Yes" />\n', '', 1)
        # The replacement is checked rather than assuming indentation.
        import re
        payload = re.sub(r'\s*<ItemData ItemOID="AE1.AESTUNK" IsNull="Yes"\s*/>', '', payload, count=1)
        xml_path.write_text(payload, encoding="utf-8")
        activation_path = artifacts / "DEMO-005_01_activation.xml"
        activation_path.write_bytes(xml_document("DEMO-005", fields, activation="Y"))
        pdf_name = artifacts / "DEMO-002.pdf"
        pdf_name.write_bytes(pdf_bytes(["Fictional incomplete report", "Subject: DEMO-002", "Urinary occult blood positive", "Hematuria"]))
    ae_headers = AE_EXTRA + [f["name"] for f in fields]
    for role, rows, headers in (("findings", findings, FINDING_COLUMNS), ("reviews", reviews, REVIEW_COLUMNS), ("decisions", decisions, DECISION_COLUMNS), ("ae", aes, ae_headers), ("listing", listing, ae_headers), ("edc", edc, ae_headers), ("baseline_ae", baseline, ae_headers), ("subjects", subjects, ["subject_id", "expected_ae", "coverage_confirmed", "authorized_by", "authorized_at"]), ("pdf_index", pdf_index, ["subject_id", "path"])):
        write_csv(destination / (role+".csv"), rows, headers)
    (destination / "study.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    return destination / "study.json"

