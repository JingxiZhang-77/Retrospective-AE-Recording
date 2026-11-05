"""Explicit metadata; example codes are not universal clinical conventions."""
import json
from pathlib import Path


class InputError(ValueError):
    pass


# Generic 27-field example. A target study must approve its own mappings.
FIELD_NAMES = (
    ("term", "AETERM"), ("local_related", "AELOCREL"), ("last_related", "POTLAST"),
    ("wound_related", "WHARAE"), ("opioid_related", "ORAE"), ("start_date", "AESTDAT"),
    ("start_time", "AESTTIM"), ("start_time_unknown", "AESTUNK"), ("ongoing", "AEONGO"),
    ("end_date", "AEENDAT"), ("end_time", "AEENTIM"), ("end_time_unknown", "AEENUNK"),
    ("stop_indeterminate", "AEDTDET"), ("grade", "AETOXGR"), ("serious", "AESER"),
    ("relatedness", "AEREL"), ("drug_action", "AEACN"), ("no_action", "AENONE"),
    ("conmed", "AECONMED"), ("procedure", "AECONTHP"), ("other_action", "AEACNOTH"),
    ("other_action_specify", "AEACNOTHSP"), ("outcome", "AEOUT1"), ("sequelae", "SEQUELAE"),
    ("discontinued", "AEDIS"), ("pi_term", "AETERMPI"), ("comments", "COMMENTS"),
)


def example_fields():
    fields = []
    yn = {"local_related", "last_related", "wound_related", "opioid_related", "serious", "discontinued"}
    checkbox = {"start_time_unknown", "ongoing", "end_time_unknown", "stop_indeterminate", "end_time_unknown", "no_action", "conmed", "procedure", "other_action"}
    for name, oid in FIELD_NAMES:
        item = {"name": name, "item_oid": "AE1." + oid, "type": "text", "case_sensitive": True}
        if name in yn:
            item["allowed_values"] = ["Y", "N"]
        if name in checkbox:
            item["allowed_values"] = ["1"]
        if name in {"start_date", "end_date"}:
            item.update(type="date", formats=["%Y-%m-%d", "%d %b %Y"])
        if name in {"start_time", "end_time"}:
            item.update(type="time", formats=["%H:%M", "%H:%M:%S"])
        if name == "grade":
            item["allowed_values"] = [str(n) for n in range(6)]
        if name == "relatedness":
            item["allowed_values"] = [str(n) for n in range(1, 7)]
        if name == "drug_action":
            item["allowed_values"] = [str(n) for n in range(1, 6)]
        if name == "outcome":
            item["allowed_values"] = [str(n) for n in range(1, 8)]
        if name in {"term", "pi_term"}:
            item.update(max_length=200, case_sensitive=False)
        if name == "comments":
            item["max_length"] = 200
        fields.append(item)
    return fields


def load_config(path):
    path = Path(path).resolve()
    try:
        config = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputError(f"Cannot read configuration: {exc}") from exc
    if not isinstance(config, dict):
        raise InputError("Configuration must be a JSON object.")
    for key in ("release_id", "rule_version", "tables", "fields"):
        if not config.get(key):
            raise InputError(f"Configuration requires {key}.")
    if not isinstance(config["tables"], dict) or not isinstance(config["fields"], list):
        raise InputError("tables must be an object and fields must be an array.")
    fields = config["fields"]
    names, oids = [], []
    for item in fields:
        if not isinstance(item, dict) or not item.get("name") or not item.get("item_oid"):
            raise InputError("Each field needs name and item_oid.")
        if item.get("type", "text") not in {"text", "date", "time", "number"}:
            raise InputError(f"Unsupported field type: {item['name']}")
        if item.get("type") in {"date", "time"} and not item.get("formats"):
            raise InputError(f"Date/time field requires explicit formats: {item['name']}")
        names.append(item["name"])
        oids.append(item["item_oid"])
    if len(set(names)) != len(names) or len(set(oids)) != len(oids):
        raise InputError("Field names and target item identifiers must be unique.")
    if len(fields) != config.get("expected_field_count", 27):
        raise InputError("Field count does not match expected_field_count.")
    config.setdefault("null_tokens", [""])
    if {str(t).strip().casefold() for t in config["null_tokens"]} & {"0", "1", "n", "no", "y", "yes", "false", "true"}:
        raise InputError("Null tokens must not erase zero or an explicit No response.")
    default_names = set(config.get("ae_defaults", {}))
    if not default_names <= set(names):
        raise InputError("An AE default names an unmapped field.")
    if not set(config.get("required_checks", [])) <= {"SOURCE", "REVIEW", "DECISION", "AE", "LISTING", "XML_STRUCTURE", "XML", "ACTIVATION", "EDC", "CHANGE", "PACKAGE", "PDF_INDEX", "PDF_TEXT"}:
        raise InputError("required_checks contains an unknown check identifier.")
    if any(not isinstance(item.get("max_length", 1), int) or item.get("max_length", 1) < 1 for item in fields):
        raise InputError("Field length limits must be positive integers.")
    config.setdefault("source_field_map", {"source_result": "result", "source_unit": "unit"})
    config.setdefault("result_placeholders", ["See Below", "See Report", "Pending"])
    config.setdefault("standard_comment", "Asymptomatic and no medical intervention needed")
    config.setdefault("required_checks", ["SOURCE", "REVIEW", "DECISION", "AE", "LISTING", "XML", "EDC"])
    config["_base"] = path.parent
    config["_path"] = path
    return config

