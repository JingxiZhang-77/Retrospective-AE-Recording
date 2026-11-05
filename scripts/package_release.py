"""Prepare a local source archive; never create or publish a remote repository."""
import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from finding_ae_review import __version__
from check_repository import main as check_repository, release_files


def main():
    if check_repository():
        return 1
    destination = ROOT / "dist"
    destination.mkdir(exist_ok=True)
    archive = destination / f"finding-ae-review-{__version__}.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as output:
        for path in release_files():
            output.write(path, "finding-ae-review/" + path.relative_to(ROOT).as_posix())
    print(archive)
    print("SHA-256:", hashlib.sha256(archive.read_bytes()).hexdigest())
    print("Local package prepared. Publication permissions and license approval remain required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

