"""Public-documentation-informed simulation controls, using no participant data."""
from collections import Counter
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from finding_ae_review.config import load_config
from finding_ae_review.engine import Engine
from finding_ae_review.simulation import CASES, REFERENCES, generate_simulation, make_observations, run_simulation


class SimulationPopulationTests(unittest.TestCase):
    def test_exact_population_and_domain_counts(self):
        rows, subjects = make_observations()
        self.assertEqual((len(subjects), len(rows)), (20, 100))
        self.assertEqual(Counter(r["domain"] for r in rows), {"LAB": 40, "ECG": 20, "VS": 40})
        self.assertEqual(Counter(r["subject_id"] for r in rows), {s["subject_id"]: 5 for s in subjects})

    def test_same_seed_is_reproducible(self):
        self.assertEqual(make_observations(), make_observations())

    def test_other_seed_changes_values_not_identity(self):
        left, _ = make_observations(123)
        right, _ = make_observations(456)
        self.assertEqual([r["finding_id"] for r in left], [r["finding_id"] for r in right])
        self.assertNotEqual([r["result"] for r in left], [r["result"] for r in right])

    def test_references_and_identifiers_are_explicit(self):
        rows, subjects = make_observations()
        reference_ids = {r["reference_id"] for r in REFERENCES}
        self.assertEqual({r["reference_id"] for r in rows}, reference_ids)
        self.assertTrue(all(r["synthetic"] == "true" and r["subject_id"].startswith("SYN-") for r in rows))


class SimulationWorkflowTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / "reports" / ".simulation-tests"
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="case-", dir=parent)
        self.root = Path(self.temp.name)
        self.paths, self.summary = generate_simulation(self.root / "inputs")

    def tearDown(self):
        self.temp.cleanup()

    def test_source_observations_are_identical_across_phases(self):
        initial = (self.paths["01_initial"].parent / "findings.csv").read_bytes()
        resolved = (self.paths["02_resolved"].parent / "findings.csv").read_bytes()
        self.assertEqual(initial, resolved)
        self.assertEqual(self.summary["review_requests"], 65)
        self.assertEqual(self.summary["routes"], {"automated": 60, "excluded": 37, "manual": 2, "existing": 1})

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "optional PDF dependency")
    def test_all_injected_scenarios_are_detected(self):
        result = Engine(load_config(self.paths["01_initial"])).run()
        for cid, fid, check, _, _ in CASES:
            with self.subTest(case=cid):
                self.assertTrue(any(i.severity == "ERROR" and i.check_id == check and (not fid or i.finding_id == fid) for i in result.issues))

    @unittest.skipUnless(importlib.util.find_spec("pypdf"), "optional PDF dependency")
    def test_resolved_population_has_no_blocking_issues(self):
        result = Engine(load_config(self.paths["02_resolved"])).run()
        self.assertEqual(result.counts()["ERROR"], 0)
        self.assertEqual(result.counts()["WARNING"], 0)
        self.assertFalse(any(c.status == "NOT_RUN" for c in result.checks))
        self.assertEqual(len(result.lineage), 100)

    def test_xml_detail_and_activation_coverage(self):
        config = load_config(self.paths["02_resolved"])
        values, groups = [], 0
        for name in config["xml_files"]:
            root = ET.fromstring((config["_base"] / name).read_bytes())
            for group in root.findall(".//{*}ItemGroupData"):
                if group.get("ItemGroupOID") == "AE1YN_LOG_LINE":
                    self.assertNotIn("ItemGroupRepeatKey", group.attrib)
                    values.append(group[0].get("Value"))
                else:
                    groups += 1
                    self.assertEqual(len(group), 27)
        self.assertEqual(Counter(values), {"Y": 18, "N": 2})
        self.assertEqual(groups, 60)

    @unittest.skipUnless(importlib.util.find_spec("pypdf") and importlib.util.find_spec("openpyxl"), "optional report dependencies")
    def test_full_walkthrough_produces_reports_and_workbooks(self):
        result = run_simulation(self.root / "walkthrough", self.root / "reports")
        self.assertEqual(result["detected_scenarios"], 14)
        self.assertEqual(result["phases"]["02_resolved"]["counts"]["ERROR"], 0)
        for phase in ("01_initial", "02_resolved"):
            for name in ("report.html", "report.xlsx", "Simulation_Data.xlsx", "run.json"):
                self.assertTrue((self.root / "reports" / phase / name).is_file())


if __name__ == "__main__":
    unittest.main()
