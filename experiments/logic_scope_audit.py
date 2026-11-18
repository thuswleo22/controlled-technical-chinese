"""Audit scope diagnostics against all three-atom truth tables in a bounded language."""

import argparse
from collections import Counter
from itertools import product
import json
import sys

from profile_baseline import ROOT

sys.path.insert(0, str(ROOT / "src"))
from ctc_linter import check

ATOMS = ("甲有效", "乙有效", "丙有效")
OPERATORS = ("且", "或")


def operation(operator, left, right):
    if operator == "且":
        return left and right
    if operator == "或":
        return left or right
    if operator == "异或":
        return left != right
    raise ValueError(operator)


def ambiguous(atoms, left_op, right_op):
    for values in product((False, True), repeat=len(ATOMS)):
        assignment = dict(zip(ATOMS, values))
        a, b, c = (assignment[atom] for atom in atoms)
        left_tree = operation(right_op, operation(left_op, a, b), c)
        right_tree = operation(left_op, a, operation(right_op, b, c))
        if left_tree != right_tree:
            return True
    return False


def audit(operators=OPERATORS):
    groups = {shape: Counter() for shape in ("raw", "left", "right", "wrapped")}
    mismatches = []
    for atoms in product(ATOMS, repeat=3):
        a, b, c = atoms
        for left_op, right_op in product(operators, repeat=2):
            raw = f"{a}{left_op}{b}{right_op}{c}"
            ambiguous_raw = ambiguous(atoms, left_op, right_op)
            conditions = {
                "raw": (raw, ambiguous_raw),
                "left": (f"（{a}{left_op}{b}）{right_op}{c}", False),
                "right": (f"{a}{left_op}（{b}{right_op}{c}）", False),
                "wrapped": (f"{a}{left_op}{b}\n{right_op}{c}", ambiguous_raw),
            }
            for shape, (condition, gold) in conditions.items():
                diagnostic = any(row.rule_id == "RULE-LOG-01"
                                 for row in check(f"如果{condition}，执行检查。"))
                outcome = ("tp" if gold else "fp") if diagnostic else ("fn" if gold else "tn")
                groups[shape][outcome] += 1
                if diagnostic != gold:
                    mismatches.append({"shape": shape, "condition": condition,
                                       "gold_ambiguity": gold, "outcome": outcome})
    return {"counts": groups, "mismatches": mismatches}


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--xor", action="store_true")
    args = cli.parse_args()
    operators = OPERATORS + (("异或",) if args.xor else ())
    print(json.dumps(audit(operators), ensure_ascii=False, indent=2))
