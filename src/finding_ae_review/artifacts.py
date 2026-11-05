"""Read-only PDF inventory/text and delivery-package consistency checks."""
from collections import Counter, defaultdict
import hashlib
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from .io import file_hash, resolve


def check_packages(config, result):
    packages = config.get("packages", [])
    check = result.begin("PACKAGE", "Delivery ZIP inventory and member hashes", bool(packages), "No delivery packages declared." if not packages else "")
    for spec in packages:
        path = resolve(config, spec["path"])
        if not path.is_file():
            result.add(check, "ERROR", "Delivery ZIP is missing.", "Supply the current delivery archive.", observed=path.name)
            continue
        result.inputs.append({"role": "package", "file": path.name, "sha256": file_hash(path)})
        expected = {entry["name"]: resolve(config, entry["path"]) for entry in spec["members"]}
        if len(expected) != len(spec["members"]):
            result.add(check, "ERROR", "Package manifest contains duplicate member names.", "Make member names unique.")
        try:
            with ZipFile(path) as archive:
                entries = [entry for entry in archive.infolist() if not entry.is_dir()]
                names = [entry.filename for entry in entries]
                for name, count in Counter(names).items():
                    if count > 1:
                        result.add(check, "ERROR", "ZIP contains duplicate names.", "Rebuild the package from approved files.", observed=name)
                    part = PurePosixPath(name.replace("\\", "/"))
                    if part.is_absolute() or ".." in part.parts or ":" in name:
                        result.add(check, "ERROR", "ZIP contains an unsafe member path.", "Use portable relative member names.", observed=name)
                for name in set(names) ^ set(expected):
                    result.add(check, "ERROR", "ZIP member inventory differs from the release manifest.", "Remove stale extras or restore missing members.", expected="present" if name in expected else "absent", observed=name)
                for entry in entries:
                    check.records_checked += 1
                    if entry.filename not in expected:
                        continue
                    source = expected[entry.filename]
                    if not source.is_file():
                        result.add(check, "ERROR", "Manifest reference file is missing.", "Supply the current unpackaged reference.", observed=source.name)
                        continue
                    if entry.file_size > config.get("max_input_bytes", 50_000_000):
                        result.add(check, "ERROR", "ZIP member exceeds the size limit.", "Review the archive before processing.", observed=entry.filename)
                        continue
                    digest = hashlib.sha256()
                    with archive.open(entry) as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                    if digest.hexdigest() != file_hash(source):
                        result.add(check, "ERROR", "ZIP contains a stale or changed file.", "Rebuild the package from the verified current outputs.", observed=entry.filename)
        except (BadZipFile, OSError, RuntimeError) as exc:
            result.add(check, "ERROR", "ZIP cannot be verified.", "Recreate or unlock the archive.", observed=str(exc))


def check_pdf(config, result, data):
    index = data["pdf_index"]
    ae = data["ae"]
    inventory = result.begin("PDF_INDEX", "PDF inventory by retained subject", index is not None and ae is not None, "PDF index or AE reference is missing." if index is None or ae is None else "")
    text_check = result.begin("PDF_TEXT", "Configured text values are present in subject PDFs", config.get("pdf_text", False) and index is not None and ae is not None, "Optional PDF text inspection is disabled or inputs are missing.")
    if inventory.status == "NOT_RUN":
        return
    by_subject = defaultdict(list)
    for row in index:
        by_subject[row.get("subject_id", "")].append(row)
    expected = {row["subject_id"] for row in ae}
    for subject in set(by_subject) | expected:
        inventory.records_checked += 1
        rows = by_subject.get(subject, [])
        if subject not in expected or len(rows) != 1:
            result.add(inventory, "ERROR", "PDF subject inventory is extra, missing, or duplicated.", "Generate one declared PDF per retained subject.", {"subject_id": subject})
    reader = None
    if text_check.status != "NOT_RUN":
        try:
            from pypdf import PdfReader
            reader = PdfReader
        except ImportError:
            text_check.status, text_check.reason = "NOT_RUN", "Optional PDF dependency is not installed."
    normalize = lambda value: " ".join(str(value).split()).casefold()
    for row in index:
        path = resolve(config, row["path"])
        if not path.is_file():
            result.add(inventory, "ERROR", "Subject PDF is missing.", "Supply the current PDF.", row, observed=path.name)
            if reader:
                result.add(text_check, "ERROR", "PDF text cannot be checked because the PDF is missing.", "Supply the PDF.", row)
            continue
        result.inputs.append({"role": "pdf", "file": path.name, "sha256": file_hash(path)})
        if path.stat().st_size > config.get("max_input_bytes", 50_000_000):
            result.add(inventory, "ERROR", "PDF exceeds the input-size limit.", "Review the PDF before processing.", row)
            continue
        if not reader:
            continue
        try:
            book = reader(path)
            text = normalize("\n".join(page.extract_text() or "" for page in book.pages))
        except Exception as exc:
            result.add(text_check, "ERROR", "PDF text could not be extracted.", "Provide a readable PDF or perform documented visual verification.", row, observed=type(exc).__name__)
            continue
        text_check.records_checked += 1
        if normalize(row["subject_id"]) not in text:
            result.add(text_check, "ERROR", "Expected subject identifier is absent from PDF text.", "Verify report-to-subject assignment.", row)
        for event in [e for e in ae if e["subject_id"] == row["subject_id"]]:
            for name in config.get("pdf_fields", ["term", "pi_term", "comments", "source_result", "source_unit"]):
                value = event.get(name, "")
                if value and normalize(value) not in text:
                    result.add(text_check, "ERROR", "Configured value is absent from the extracted subject PDF text.", "Check rendered content, including unitless qualitative results. Text presence alone is not a row-level visual comparison.", event, name, value, "not found")

