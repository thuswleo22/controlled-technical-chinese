"""Reproduce the public CTC checks and compare their committed reports."""

import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from logic import parse, truth_table

REPORTS = (
    ("specification_audit.json", "check_specification.py"),
    ("logic_pilot.json", "logic_pilot.py"),
    ("xor_pilot.json", "logic_pilot.py", "--cases", "corpus/xor_pilot.json"),
    ("logic_scope_audit.json", "logic_scope_audit.py"),
    ("logic_scope_xor_audit.json", "logic_scope_audit.py", "--xor"),
    ("merge_validation.json", "merge_validation.py"),
    ("lexicon_operation_checks.json", "verify_lexicon_operations.py"),
)


def verify_examples():
    expected = {
        "before.md": ["RULE-LOG-01", "RULE-REF-01", "RULE-REF-02"],
        "after.md": [],
        "wrong-grouping.md": [],
    }
    for name, codes in expected.items():
        path = ROOT / "examples" / name
        process = subprocess.run(
            [sys.executable, "src/ctc_linter.py", str(path), "--json"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
        )
        diagnostics = json.loads(process.stdout)
        if process.returncode != int(bool(codes)) or [row["rule_id"] for row in diagnostics] != codes:
            raise RuntimeError(f"Unexpected linter result for {name}")

    # The ticket must be valid even if the operator has permission.
    expired_ticket = {"值班员有权导出日志": 1, "审计员批准": 0, "工单有效": 0}
    for name, expected_decision in (("after.md", 0), ("wrong-grouping.md", 1)):
        prose = (ROOT / "examples" / name).read_text(encoding="utf-8")
        condition = re.search(r"^如果(.+)，导出故障日志。$", prose, re.MULTILINE)
        if condition is None:
            raise RuntimeError(f"Missing export condition in {name}")
        trees = parse(condition[1])
        if len(trees) != 1 or {truth_table(tree, expired_ticket) for tree in trees} != {expected_decision}:
            raise RuntimeError(f"Unexpected authorization decision for {name}")
    print("Verified the example diagnostics and the semantic counterexample.")


def main():
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                   cwd=ROOT, check=True)
    for report_name, program, *args in REPORTS:
        report = json.loads((ROOT / "results" / report_name).read_text(encoding="utf-8"))
        output = subprocess.check_output(
            [sys.executable, str(ROOT / "experiments" / program), *args],
            cwd=ROOT, text=True, encoding="utf-8",
        )
        if json.loads(output) != report:
            raise RuntimeError(f"Recomputed report differs: {report_name}")
        print(f"Reproduced {report_name}")
    subprocess.run([sys.executable, "src/ctc_linter.py", "docs/CTC-Specification.md",
                    "--bootstrap-check"], cwd=ROOT, check=True)
    verify_examples()


if __name__ == "__main__":
    main()
