"""Read declared inputs without modifying them or executing workbook formulas."""
import csv
from datetime import date, datetime
import hashlib
from pathlib import Path
from zipfile import BadZipFile

from .config import InputError


def file_hash(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve(config, value):
    path = Path(value)
    return path.resolve() if path.is_absolute() else (config["_base"] / path).resolve()


def cell(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def read_table(config, role, result):
    spec = config["tables"].get(role)
    if spec is None:
        return None
    if isinstance(spec, str):
        spec = {"path": spec}
    if not isinstance(spec, dict) or not spec.get("path"):
        raise InputError(f"Invalid table specification: {role}")
    path = resolve(config, spec["path"])
    if not path.is_file():
        raise InputError(f"Input does not exist for {role}: {path.name}")
    if path.stat().st_size > config.get("max_input_bytes", 50_000_000):
        raise InputError(f"Input exceeds size limit: {path.name}")
    rows = []
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            try:
                values = list(reader)
            except csv.Error as exc:
                raise InputError(f"CSV cannot be parsed for {role}: {exc}") from exc
    elif path.suffix.lower() == ".xlsx":
        try:
            from openpyxl import load_workbook
            from openpyxl.utils.exceptions import InvalidFileException
        except ImportError as exc:
            raise InputError("XLSX input requires the optional excel dependency.") from exc
        try:
            book = load_workbook(path, read_only=True, data_only=False)
        except (BadZipFile, InvalidFileException, KeyError) as exc:
            raise InputError(f"XLSX input cannot be opened for {role}: {type(exc).__name__}") from exc
        try:
            if not spec.get("sheet"):
                raise InputError(f"XLSX input requires an explicit sheet: {role}")
            if spec["sheet"] not in book.sheetnames:
                raise InputError(f"Missing sheet for {role}: {spec['sheet']}")
            sheet = book[spec["sheet"]]
            values = []
            for row in sheet.iter_rows():
                if any(item.data_type == "f" for item in row):
                    raise InputError(f"Formula cells are not accepted in canonical inputs: {role}")
                values.append([cell(item.value) for item in row])
        finally:
            book.close()
    else:
        raise InputError(f"Unsupported table format: {path.suffix}")
    if not values:
        raise InputError(f"Input requires a header row: {role}")
    headers = [cell(v).strip() for v in values[0]]
    if any(not h for h in headers) or len(headers) != len(set(headers)):
        raise InputError(f"Blank or duplicate input headers: {role}")
    mapping = spec.get("columns", {})  # canonical name -> source column name
    if not isinstance(mapping, dict) or any(v not in headers for v in mapping.values()):
        raise InputError(f"Invalid or missing mapped source column: {role}")
    inverse = {v: k for k, v in mapping.items()}
    canonical_headers = [inverse.get(h, h) for h in headers]
    if len(set(canonical_headers)) != len(canonical_headers):
        raise InputError(f"Column mapping produces duplicate canonical names: {role}")
    for index, values_row in enumerate(values[1:], 2):
        if not any(cell(v).strip() for v in values_row):
            continue
        if len(values_row) != len(headers):
            raise InputError(f"Incorrect number of cells: {role}, row {index}")
        row = dict(zip(canonical_headers, map(cell, values_row)))
        row["_row"] = str(index)
        rows.append(row)
    result.inputs.append({"role": role, "file": path.name, "sha256": file_hash(path), "rows": len(rows), "sheet": spec.get("sheet", ""), "columns": canonical_headers})
    return rows


def true(value):
    return str(value).strip().casefold() in {"true", "yes", "y", "1"}

