"""Portable, escaped evidence reports without external assets or services."""
import csv
from dataclasses import asdict
from html import escape
import json
from pathlib import Path

from . import __version__


def safe_csv(value):
    text = "" if value is None else str(value)
    # Prevent spreadsheet formula execution; JSON retains the original value.
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r")) else text


def csv_file(path, rows, headers):
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: safe_csv(row.get(key, "")) for key in headers})


def html_table(rows, headers, table_id=""):
    head = "".join("<th>" + escape(name.replace("_", " ").title()) + "</th>" for name in headers)
    body = []
    for row in rows:
        cells = "".join("<td>" + escape(str(row.get(name, ""))) + "</td>" for name in headers)
        body.append("<tr>" + cells + "</tr>")
    if not body:
        body = [f'<tr><td colspan="{len(headers)}">No entries.</td></tr>']
    return f'<div class="scroll"><table id="{escape(table_id)}"><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def write_reports(result, output, config_fingerprint, xlsx=False):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    payload = result.as_dict()
    payload.update(tool_version=__version__, configuration_sha256=config_fingerprint)
    issue_rows = [asdict(issue) for issue in result.issues]
    check_rows = [asdict(check) for check in result.checks]
    tables = {
        "issues": (issue_rows, ["check_id", "severity", "finding_id", "subject_id", "record_id", "field", "expected", "observed", "message", "action"]),
        "checks": (check_rows, ["check_id", "title", "status", "records_checked", "reason"]),
        "lineage": (result.lineage, ["finding_id", "subject_id", "test_name", "source_version", "review_id", "review_status", "decision_id", "route", "ae_id", "owner", "errors", "warnings"]),
        "changes": (result.changes, ["subject_id", "repeat_key", "field", "before", "after"]),
        "inputs": (result.inputs, ["role", "file", "sha256", "rows", "sheet"]),
    }
    for name, (rows, headers) in tables.items():
        csv_file(output / (name + ".csv"), rows, headers)
    (output / "run.json").write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    counts = result.counts()
    gaps = sum(c.status == "NOT_RUN" for c in result.checks)
    state = "BLOCKING ISSUES" if counts["ERROR"] else "COVERAGE GAPS" if gaps else "WARNINGS REQUIRE REVIEW" if counts["WARNING"] else "NO BLOCKING ISSUES IN THE CHECKED SCOPE"
    sections = ["<h2>Check coverage</h2>", html_table(check_rows, tables["checks"][1])]
    sections += ['<h2>Issue register</h2><label>Filter issues <input id="filter" type="search" placeholder="Finding, subject, field, severity, or text"></label>', html_table(issue_rows, tables["issues"][1], "issues")]
    for name in ("lineage", "changes", "inputs"):
        sections.extend(["<h2>" + name.title() + "</h2>", html_table(*tables[name])])
    sections.append("<h2>Interpretation and limitations</h2><ul>" + "".join("<li>" + escape(item) + "</li>" for item in result.limitations) + "</ul>")
    html = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Finding-to-AE review report</title><style>
body{{font:15px/1.5 system-ui,sans-serif;color:#172b40;background:#f4f7fa;margin:0;padding:28px}}
main{{max-width:1500px;margin:auto;background:white;padding:28px;border-radius:12px}}
h1,h2{{color:#173b59}}.state{{border-left:6px solid #b35d18;background:#fff3df;padding:14px}}
.metrics{{display:flex;gap:24px;flex-wrap:wrap;margin:20px 0}}.metric{{background:#edf3f8;padding:14px 20px}}
table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{text-align:left;vertical-align:top;border-bottom:1px solid #d6e0e8;padding:9px;white-space:pre-wrap;overflow-wrap:anywhere}}
th{{background:#edf3f8;position:sticky;top:0}}.scroll{{overflow:auto;max-height:650px;margin:12px 0 24px}}input{{padding:8px;width:min(500px,80%)}}small{{color:#526475}}
@media print{{body,main{{padding:0;background:white}}.scroll{{overflow:visible;max-height:none}}input{{display:none}}th{{position:static}}}}
</style></head><body><main><h1>Finding-to-AE Review Report</h1>
<p>Release: <strong>{escape(result.release_id)}</strong><br>Run started (UTC): {escape(result.started_at)}<br><small>Tool {__version__}; configuration SHA-256: {escape(config_fingerprint)}</small></p>
<div class="state">{state}. This report does not authorize clinical decisions, database changes, or release.</div>
<div class="metrics"><div class="metric">Errors: {counts['ERROR']}</div><div class="metric">Warnings: {counts['WARNING']}</div><div class="metric">Information: {counts['INFO']}</div><div class="metric">Not run: {gaps}</div></div>
{''.join(sections)}
</main><script>document.getElementById('filter').addEventListener('input',function(){{const q=this.value.toLowerCase();document.querySelectorAll('#issues tbody tr').forEach(function(r){{r.hidden=!r.textContent.toLowerCase().includes(q);}});}});</script></body></html>'''
    (output / "report.html").write_text(html, encoding="utf-8")
    if xlsx:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.writer.theme import theme_xml
        from xml.etree import ElementTree as ET
        book = Workbook()
        theme = ET.fromstring(theme_xml)
        for element in theme.iter():
            face = element.get("typeface")
            if face and not face.isascii():
                element.set("typeface", "Arial")
        book.loaded_theme = ET.tostring(theme, encoding="utf-8")
        book.properties.creator = "Finding-to-AE Review Toolkit"
        book.properties.lastModifiedBy = "Finding-to-AE Review Toolkit"
        sheet = book.active
        sheet.title = "Summary"
        for row in [("Release", result.release_id), ("Status", state), ("Tool version", __version__), ("Configuration SHA-256", config_fingerprint), *counts.items(), ("Not run", gaps)]:
            sheet.append(row)
        for name, (rows, headers) in tables.items():
            sheet = book.create_sheet(name.title())
            sheet.append(headers)
            for row in rows:
                for col, key in enumerate(headers, 1):
                    cell = sheet.cell(sheet.max_row + 1 if col == 1 else sheet.max_row, col)
                    cell.value = str(row.get(key, ""))
                    cell.data_type = "s"
        for sheet in book:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="173B59")
            for row in sheet:
                for cell in row:
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
            for col in sheet.columns:
                sheet.column_dimensions[col[0].column_letter].width = min(55, max(18, max(len(str(c.value or "")) for c in col[:30]) + 2))
        book.save(output / "report.xlsx")
    return payload

