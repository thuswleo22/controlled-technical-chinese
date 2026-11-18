"""Run the linter on each specification example and the full document."""

import json
import re
import sys

from audit_candidate_lexicon import ROOT, load_candidates
from render_reviewed_lexicon import BEGIN, END, reviewed_records, table

sys.path.insert(0, str(ROOT / "src"))
from ctc_linter import check

RULE_SECTION = re.compile(
    r"^### (RULE-[A-Z]+-[0-9]+) [^\n]+\n(.*?)(?=^#{1,3} |\Z)", re.MULTILINE | re.DOTALL
)
EXAMPLE = re.compile(r"^```text\n(.*?)^```$", re.MULTILINE | re.DOTALL)
CATEGORIES = {"LEX", "REF", "LOG", "MOD", "QNT", "DOC"}


def main():
    path = ROOT / "docs/CTC-Specification.md"
    document = path.read_text(encoding="utf-8")
    rows = []
    seen = set()
    for section in RULE_SECTION.finditer(document):
        rule, body = section.groups()
        if rule in seen:
            raise ValueError(f"Duplicate rule: {rule}")
        seen.add(rule)
        bad, good = EXAMPLE.findall(body)
        bad_codes = {item.rule_id for item in check(bad)}
        good_codes = {item.rule_id for item in check(good)}
        rows.append({"rule": rule, "bad_example_codes": sorted(bad_codes),
                     "good_example_codes": sorted(good_codes),
                     "automated": bool(rule in bad_codes and not good_codes)})
    if {rule.split("-")[1] for rule in seen} != CATEGORIES:
        raise ValueError("Specification must cover all six rule categories")
    automated = sum(row["automated"] for row in rows)
    approved, pending = reviewed_records(load_candidates())
    start = document.index(BEGIN)
    end = document.index(END, start) + len(END)
    if document[start:end] != table(approved):
        raise ValueError("Specification dictionary differs from approved records")
    self_diagnostics = list(check(document))
    report = {
        "rule_count": len(rows), "automated_rules": automated,
        "automated_rule_fraction": automated / len(rows),
        "approved_lexicon_entries": len(approved), "pending_lexicon_entries": len(pending),
        "specification_diagnostics": len(self_diagnostics), "rules": rows,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return int(automated * 5 < len(rows) * 4 or not 150 <= len(approved) <= 300
               or bool(pending) or bool(self_diagnostics))


if __name__ == "__main__":
    raise SystemExit(main())
