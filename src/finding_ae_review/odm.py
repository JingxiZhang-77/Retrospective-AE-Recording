"""Inspect declared ODM transactions; never upload or rewrite them."""
from xml.etree import ElementTree as ET

from .io import file_hash, resolve


def local(tag):
    return tag.rsplit("}", 1)[-1]


def children(element, name):
    return [e for e in element if local(e.tag) == name]


def read_odm(config, result):
    files = config.get("xml_files")
    check = result.begin("XML_STRUCTURE", "ODM hierarchy, identifiers, fields, and null representation", bool(files), "No XML files declared." if not files else "")
    if not files:
        return None, None
    metadata = config.get("odm", {})
    required = ("study_oid", "metadata_version_oid", "form_oid", "item_group_oid", "activation_form_oid", "activation_group_oid", "activation_item_oid")
    absent = [key for key in required if not metadata.get(key)]
    if absent:
        result.add(check, "ERROR", "ODM target metadata are incomplete.", "Supply approved target metadata.", observed=", ".join(absent))
        return [], []
    fields = {item["item_oid"]: item["name"] for item in config["fields"]}
    details, activations = [], []
    seen_paths = set()
    for declared in files:
        path = resolve(config, declared)
        if path in seen_paths:
            result.add(check, "ERROR", "The same XML file is declared more than once.", "Remove duplicate manifest entries.", observed=path.name)
            continue
        seen_paths.add(path)
        if not path.is_file():
            result.add(check, "ERROR", "Declared XML file is missing.", "Supply the intended transaction file.", observed=path.name)
            continue
        if path.stat().st_size > config.get("max_input_bytes", 50_000_000):
            result.add(check, "ERROR", "XML file exceeds the configured size limit.", "Review input size before processing.", observed=path.name)
            continue
        payload = path.read_bytes()
        result.inputs.append({"role": "xml", "file": path.name, "sha256": file_hash(path)})
        # This reader intentionally accepts UTF-8 XML only, simplifying entity safeguards.
        try:
            xml_text = payload.decode("utf-8-sig")
        except UnicodeError:
            result.add(check, "ERROR", "XML is not UTF-8 encoded.", "Export UTF-8 XML for this reader.", observed=path.name)
            continue
        if "<!DOCTYPE" in xml_text.upper() or "<!ENTITY" in xml_text.upper():
            result.add(check, "ERROR", "DTD or entity declarations are not accepted.", "Provide plain clinical ODM without entity declarations.", observed=path.name)
            continue
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            result.add(check, "ERROR", "XML is not well formed.", "Correct the XML before comparison.", observed=f"{path.name}: {exc}")
            continue
        check.records_checked += 1
        if local(root.tag) != "ODM" or root.get("ODMVersion") not in metadata.get("versions", ["1.3"]):
            result.add(check, "ERROR", "Unexpected ODM root or version.", "Use the approved target ODM version.", observed=str(root.attrib))
        if not root.tag.startswith("{") or root.tag.split("}")[0][1:] != metadata.get("namespace", "http://www.cdisc.org/ns/odm/v1.3"):
            result.add(check, "ERROR", "Unexpected ODM namespace.", "Use the approved namespace.", observed=root.tag)
        clinical = children(root, "ClinicalData")
        subjects = [s for c in clinical for s in children(c, "SubjectData")]
        if metadata.get("one_subject_per_file", True) and len(subjects) != 1:
            result.add(check, "ERROR", "Transaction does not contain exactly one subject.", "Separate subjects as required by the interface.", observed=len(subjects))
        if not clinical:
            result.add(check, "ERROR", "No ClinicalData element was found.", "Check the transaction hierarchy.", observed=path.name)
        for cdata in clinical:
            for attr, key in (("StudyOID", "study_oid"), ("MetaDataVersionOID", "metadata_version_oid")):
                if cdata.get(attr) != metadata[key]:
                    result.add(check, "ERROR", "Unexpected target identifier.", "Use approved environment metadata.", field=attr, expected=metadata[key], observed=cdata.get(attr))
            for subject in children(cdata, "SubjectData"):
                subject_id = subject.get("SubjectKey", "")
                events = children(subject, "StudyEventData")
                if not subject_id or not events:
                    result.add(check, "ERROR", "Subject key or event hierarchy is missing.", "Provide complete subject/event identifiers.", row={"subject_id": subject_id})
                for event in events:
                    if event.get("StudyEventOID") != metadata.get("event_oid", "COM") or event.get("StudyEventRepeatKey") != metadata.get("event_repeat_key", "1"):
                        result.add(check, "ERROR", "Unexpected study event or repeat key.", "Check target event metadata.", row={"subject_id": subject_id}, observed=str(event.attrib))
                    for form in children(event, "FormData"):
                        form_oid = form.get("FormOID")
                        if form_oid not in {metadata["form_oid"], metadata["activation_form_oid"]}:
                            result.add(check, "ERROR", "Unexpected form in the declared upload set.", "Restrict the reviewed transfer to configured forms.", row={"subject_id": subject_id}, observed=form_oid)
                            continue
                        if form.get("FormRepeatKey") != metadata.get("form_repeat_key", "1"):
                            result.add(check, "ERROR", "Unexpected form repeat key.", "Use the configured form repeat key.", row={"subject_id": subject_id}, observed=str(form.attrib))
                        groups = children(form, "ItemGroupData")
                        if not groups:
                            result.add(check, "ERROR", "Form has no item group.", "Provide the configured item group.", row={"subject_id": subject_id})
                        for group in groups:
                            activation = form_oid == metadata["activation_form_oid"]
                            expected_group = metadata["activation_group_oid"] if activation else metadata["item_group_oid"]
                            row = {"subject_id": subject_id, "repeat_key": group.get("ItemGroupRepeatKey", ""), "_file": path.name}
                            if group.get("ItemGroupOID") != expected_group:
                                result.add(check, "ERROR", "Unexpected item group.", "Check form/group mapping.", row=row, expected=expected_group, observed=group.get("ItemGroupOID"))
                            if activation:
                                if "ItemGroupRepeatKey" in group.attrib or any("TransactionType" in e.attrib for e in (subject, event, form, group)):
                                    result.add(check, "ERROR", "Activation contains an item-group repeat key or transaction type.", "Use the approved non-repeating activation structure.", row=row)
                            elif not row["repeat_key"] or group.get("TransactionType") != metadata.get("transaction_type", "Upsert"):
                                result.add(check, "ERROR", "Detail repeat key or transaction type is incorrect.", "Use a stable repeat key and configured transaction type.", row=row, observed=str(group.attrib))
                            items = children(group, "ItemData")
                            seen = set()
                            allowed = {metadata["activation_item_oid"]: "activation"} if activation else fields
                            for item in items:
                                oid = item.get("ItemOID", "")
                                if oid in seen or oid not in allowed:
                                    result.add(check, "ERROR", "Duplicate or unknown ItemOID.", "Provide every expected item exactly once.", row=row, observed=oid)
                                    continue
                                seen.add(oid)
                                has_value, has_null = "Value" in item.attrib, "IsNull" in item.attrib
                                if has_value == has_null or (has_null and item.get("IsNull") != "Yes") or (has_value and item.get("Value") == ""):
                                    result.add(check, "ERROR", "Item must contain a nonempty Value or IsNull=Yes, but not both.", "Represent blanks explicitly without erasing No or zero.", row=row, field=oid, observed=str(item.attrib))
                                row[allowed[oid]] = item.get("Value", "") if has_value else ""
                            absent_items = set(allowed) - seen
                            if absent_items:
                                result.add(check, "ERROR", "Expected items are omitted, including possible null fields.", "Include every configured field.", row=row, observed=", ".join(sorted(absent_items)))
                            (activations if activation else details).append(row)
    return details, activations

