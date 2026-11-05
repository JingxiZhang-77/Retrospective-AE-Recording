"""Command-line interface with explicit failure and incomplete-coverage handling."""
import argparse
from pathlib import Path
import sys

from . import __version__
from .config import InputError, load_config
from .engine import Engine
from .io import file_hash, resolve
from .model import Result
from .report import write_reports


def main(argv=None):
    parser = argparse.ArgumentParser(description="Review finding-to-AE lineage and reporting/EDC consistency. Inputs are read-only.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Run configured checks and write evidence reports")
    run.add_argument("--config", required=True, type=Path)
    run.add_argument("--output", required=True, type=Path)
    run.add_argument("--xlsx", action="store_true", help="Also write an Excel report (optional dependency)")
    run.add_argument("--pdf-text", action="store_true", help="Also inspect configured subject PDF text")
    run.add_argument("--fail-on", choices=("error", "warning", "never"), default="error")
    run.add_argument("--overwrite", action="store_true", help="Replace only named report files in an existing report directory")
    args = parser.parse_args(argv)
    output = args.output.resolve()
    result = None
    fingerprint = "unavailable"
    try:
        if args.xlsx:
            try:
                import openpyxl
            except ImportError as exc:
                raise InputError("--xlsx requires the optional excel dependency.") from exc
        if output.exists() and (not output.is_dir() or (any(output.iterdir()) and not args.overwrite)):
            raise InputError("Output must be a new/empty directory, or use --overwrite for named report files.")
        config = load_config(args.config)
        fingerprint = file_hash(args.config)
        if args.pdf_text:
            config["pdf_text"] = True
        protected = [args.config.resolve()]
        for spec in config["tables"].values():
            protected.append(resolve(config, spec if isinstance(spec, str) else spec["path"]))
        protected.extend(resolve(config, value) for value in config.get("xml_files", []))
        protected.extend(resolve(config, spec["path"]) for spec in config.get("packages", []))
        if any(p == output or output in p.parents for p in protected):
            raise InputError("Output directory must not contain any configured input file.")
        engine = Engine(config)
        for item in engine.data.get("pdf_index") or []:
            protected.append(resolve(config, item["path"]))
        for package in config.get("packages", []):
            protected.extend(resolve(config, item["path"]) for item in package["members"])
        if any(p == output or output in p.parents for p in protected):
            raise InputError("Output directory must not contain a declared PDF or package reference file.")
        result = engine.run()
        payload = write_reports(result, output, fingerprint, args.xlsx)
        counts = result.counts()
        print(f"Release {result.release_id}: {counts['ERROR']} error(s), {counts['WARNING']} warning(s), {counts['INFO']} information item(s).")
        print(f"Check coverage: {sum(c.status != 'NOT_RUN' for c in result.checks)}/{len(result.checks)} areas executed.")
        print(f"Report: {output / 'report.html'}")
        if not payload["coverage_complete"]:
            print("Some checks were NOT_RUN; inspect the check register.")
        if args.fail_on == "never":
            return 0
        return int(counts["ERROR"] > 0 or (args.fail_on == "warning" and counts["WARNING"] > 0))
    except (InputError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Input/configuration failure: {exc}", file=sys.stderr)
        # Never replace existing evidence during a failed invocation.
        if not output.exists() or (output.is_dir() and not any(output.iterdir())):
            failure = result or Result("unconfigured")
            check = failure.begin("INPUT", "Input and configuration validation")
            failure.add(check, "ERROR", str(exc), "Correct the input/configuration and rerun. No clinical data were changed.")
            try:
                write_reports(failure, output, fingerprint)
            except OSError:
                pass
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
