"""Enumerate Boolean interpretations for short conditions with explicit grouping."""

from functools import lru_cache
import re

TOKEN = re.compile(r"异或|[且或（）()]|(?:(?!异或)[^且或（）()\s])+")
OPERATOR = {"且", "或", "异或"}


def parse(text):
    tokens = tuple(TOKEN.findall(text))

    @lru_cache(maxsize=None)
    def read(start, stop):
        if stop - start == 1 and tokens[start] not in OPERATOR | set("（）()"):
            return frozenset({tokens[start]})
        answers = set()
        if (tokens[start:start + 1], tokens[stop - 1:stop]) in {
            (("（",), ("）",)), (("(",), (")",))
        }:
            answers.update(read(start + 1, stop - 1))
        depth = 0
        for index in range(start, stop):
            token = tokens[index]
            if token in "（(":
                depth += 1
            elif token in "）)":
                depth -= 1
            elif depth == 0 and token in OPERATOR and start < index < stop - 1:
                for left in read(start, index):
                    for right in read(index + 1, stop):
                        answers.add((token, left, right))
        return frozenset(answers)

    return read(0, len(tokens)) if tokens else frozenset()


def truth_table(tree, assignments):
    if isinstance(tree, str):
        return assignments[tree]
    operator, left, right = tree
    lhs = truth_table(left, assignments)
    rhs = truth_table(right, assignments)
    if operator == "且":
        return lhs & rhs
    if operator == "或":
        return lhs | rhs
    if operator == "异或":
        return lhs ^ rhs
    raise ValueError(f"Unknown Boolean operator: {operator}")
