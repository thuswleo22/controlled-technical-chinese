"""Measure ambiguity and semantic preservation on frozen synthetic pairs."""

import argparse
from itertools import product
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from logic import OPERATOR, TOKEN, parse, truth_table


def evaluate(cases):
    rows = []
    for case in cases:
        atoms = list(dict.fromkeys(token for token in TOKEN.findall(case["raw"])
                                   if token not in OPERATOR | set("（）()")))
        assignments = {
            atom: sum(value << index for index, value in enumerate(values))
            for atom, values in zip(atoms, zip(*product((0, 1), repeat=len(atoms))))
        }
        gold = sum(int(value) << index for index, value in enumerate(case["gold_truth"]))
        for variant in ("raw", "edited"):
            trees = parse(case[variant])
            candidates = {truth_table(tree, assignments) for tree in trees}
            rows.append({
                "id": case["id"],
                "genre": case["genre"],
                "variant": variant,
                "parse_trees": len(trees),
                "interpretations": len(candidates),
                "gold_found": gold in candidates,
                "unique_correct": candidates == {gold},
                "candidate_precision": (gold in candidates) / len(candidates) if candidates else 0,
                "codepoints": len(case[variant]),
            })
    return rows


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--cases", type=Path, default=ROOT / "corpus/logic_pilot.json")
    args = cli.parse_args()
    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    rows = evaluate(cases)
    summary = {}
    for variant in ("raw", "edited"):
        group = [row for row in rows if row["variant"] == variant]
        correct = sum(row["gold_found"] for row in group)
        predictions = sum(row["interpretations"] for row in group)
        summary[variant] = {
            "cases": len(group),
            "unique": sum(row["interpretations"] == 1 for row in group),
            "unique_correct": sum(row["unique_correct"] for row in group),
            "logic_precision": correct / predictions,
            "logic_recall": correct / len(group),
            "codepoints": sum(row["codepoints"] for row in group),
        }
    print(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
