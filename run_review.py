"""Source-tree entry point; no installation is required for CSV/XML checks."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from finding_ae_review.cli import main

if __name__ == "__main__":
    raise SystemExit(main())

