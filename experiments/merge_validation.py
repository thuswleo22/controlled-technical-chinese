"""Verify adopted CTC constraints with independent cases and enumerated scalar sets."""

from collections import Counter, defaultdict
from fractions import Fraction
from itertools import product
import json
import sys

from profile_baseline import ROOT

sys.path.insert(0, str(ROOT / "src"))
from ctc_linter import check


def interval_cases():
    grid = [Fraction(index, 2) for index in range(-2, 9)]
    for lower, upper, lower_closed, upper_closed, reverse in product(
        range(4), range(4), (False, True), (False, True), (False, True)
    ):
        left = f"{'>=' if lower_closed else '>'}{lower}℃"
        right = f"{'<=' if upper_closed else '<'}{upper}℃"
        pieces = [right, left] if reverse else [left, right]
        members = [value for value in grid
                   if (value >= lower if lower_closed else value > lower)
                   and (value <= upper if upper_closed else value < upper)]
        yield {"text": "范围：温度" + "且".join(pieces) + "。", "expect": not members}


def main():
    cases = json.loads((ROOT / "corpus/merge_cases.json").read_text(encoding="utf-8"))
    counts = defaultdict(Counter)
    rows = []
    for case in cases:
        findings = [item for item in check(case["text"]) if item.rule_id == case["rule"]]
        prediction = bool(findings)
        key = ("tp" if case["expect"] else "fp") if prediction else ("fn" if case["expect"] else "tn")
        counts[case["rule"]][key] += 1
        rows.append({**case, "prediction": prediction, "diagnostic_lines": [item.line for item in findings]})
    failures = []
    total = 0
    for case in interval_cases():
        total += 1
        prediction = any(item.rule_id == "RULE-QNT-01" for item in check(case["text"]))
        if prediction != case["expect"]:
            failures.append({**case, "prediction": prediction})
    report = {
        "independent_cases": len(rows),
        "summary": {rule: {key: count[key] for key in ("tp", "tn", "fp", "fn")}
                    for rule, count in sorted(counts.items())},
        "enumerated_intervals": total,
        "interval_mismatches": failures,
        "rows": rows,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(bool(failures) or any(row["prediction"] != row["expect"] for row in rows))


if __name__ == "__main__":
    raise SystemExit(main())
