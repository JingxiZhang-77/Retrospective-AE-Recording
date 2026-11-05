"""Generate and check 20 fictional subjects with exactly 100 observations."""
from pathlib import Path
import sys
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from finding_ae_review.simulation import run_simulation

if __name__ == "__main__":
    result = run_simulation(ROOT / "examples/public_reference_simulation", ROOT / "reports/public_reference_simulation")
    print(json.dumps(result, indent=2))
    print("Overview:", ROOT / "reports/public_reference_simulation/Simulation_Overview.html")
