"""Evidence records shared by checks and report writers."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class Issue:
    check_id: str
    severity: str
    finding_id: str
    subject_id: str
    record_id: str
    field: str
    expected: str
    observed: str
    message: str
    action: str


@dataclass
class Check:
    check_id: str
    title: str
    status: str = "NOT_RUN"
    records_checked: int = 0
    reason: str = ""


@dataclass
class Result:
    release_id: str
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    issues: list[Issue] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    inputs: list[dict] = field(default_factory=list)
    lineage: list[dict] = field(default_factory=list)
    changes: list[dict] = field(default_factory=list)
    limitations: list[str] = field(default_factory=lambda: [
        "A passed check establishes only the stated operational comparison, not medical correctness or regulatory approval.",
        "Missing inputs are reported as NOT_RUN; they are not evidence of completed review.",
        "Listing snapshots and optional PDF text checks do not establish visual layout, checkbox placement, or PI signature validity.",
        "Inputs and reports may contain sensitive information. Keep production data and reports out of public repositories.",
    ])

    def begin(self, check_id, title, available=True, reason=""):
        check = Check(check_id, title, "PASS" if available else "NOT_RUN", 0, reason)
        self.checks.append(check)
        return check

    def add(self, check, severity, message, action, row=None, field="", expected="", observed=""):
        row = row or {}
        self.issues.append(Issue(
            check.check_id, severity, str(row.get("finding_id", "")),
            str(row.get("subject_id", "")), str(row.get("ae_id", row.get("review_id", row.get("decision_id", "")))),
            field, str(expected), str(observed), message, action,
        ))
        if severity in {"ERROR", "WARNING"}:
            check.status = "FAIL" if severity == "ERROR" or check.status == "FAIL" else "WARN"

    def counts(self):
        return {level: sum(i.severity == level for i in self.issues) for level in ("ERROR", "WARNING", "INFO")}

    def as_dict(self):
        data = asdict(self)
        data["counts"] = self.counts()
        data["coverage_complete"] = all(c.status != "NOT_RUN" for c in self.checks)
        data["blocking_issues"] = self.counts()["ERROR"] > 0
        return data

