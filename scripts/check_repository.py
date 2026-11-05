"""Limited public-release content checks, not a complete disclosure review."""
from pathlib import Path
import os
import re
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SKIP = {".git", "__pycache__", "reports", "private_data", ".venv", "venv", "dist", "build"}
CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
REAL_SUBJECT = re.compile(r"\b0[1-4]-\d{5}\b")
PRIVATE_PATH = re.compile(r"[A-Za-z]:[\\/]Users[\\/]", re.I)
STUDY_IDENTIFIER = re.compile(r"\bTLC\d{5,}\b", re.I)


def release_files():
    for directory, subdirs, names in os.walk(ROOT):
        subdirs[:] = sorted(name for name in subdirs if name not in SKIP and not name.endswith(".egg-info"))
        for name in sorted(names):
            path = Path(directory) / name
            if not path.is_symlink():
                yield path


def main():
    issues = []
    paths = list(release_files())
    for path in paths:
        relative = path.relative_to(ROOT).as_posix()
        if CJK.search(relative):
            issues.append(relative + ": non-English filename")
        if path.suffix.lower() in {".pdf", ".zip"}:
            if path.suffix.lower() == ".zip":
                with ZipFile(path) as archive:
                    for name in archive.namelist():
                        if CJK.search(name) or PRIVATE_PATH.search(name):
                            issues.append(relative + ": nonportable archive member")
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeError:
            issues.append(relative + ": unexpected non-text release file")
            continue
        for label, pattern in (("non-English text", CJK), ("participant-style identifier", REAL_SUBJECT), ("private local path", PRIVATE_PATH), ("production study identifier", STUDY_IDENTIFIER)):
            if pattern.search(text):
                issues.append(relative + ": " + label)
    for name in ("README.md", "LICENSE", "CITATION.cff", "pyproject.toml", "run_review.py", "tests/test_toolkit.py", "docs/RELEASE_CHECKLIST.md"):
        if not (ROOT / name).is_file():
            issues.append("Missing required release file: " + name)
    if issues:
        print("Release checks need attention:")
        print("\n".join(issues))
        return 1
    print(f"Limited release checks passed for {len(paths)} files. Owner privacy, permissions, and license review are still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

