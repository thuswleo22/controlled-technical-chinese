"""Validate candidate dictionary records and track parser-attested contexts."""

import argparse
from collections import Counter
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ("word", "upos", "sense", "alias", "positive", "negative")
UPOS = {"VERB", "ADJ", "AUX", "ADV", "NOUN", "CCONJ", "SCONJ", "DET", "NUM", "PART", "PHRASE"}


def load_candidates():
    records = []
    for path in sorted((ROOT / "corpus").glob("lexicon_*.tsv")):
        with path.open(encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file, delimiter="\t")
            if tuple(reader.fieldnames or ()) != FIELDS:
                raise ValueError(f"{path.name}: invalid columns")
            for line, row in enumerate(reader, 2):
                if (set(row) != set(FIELDS) or any(value is None for value in row.values())
                        or any(not row[key] for key in FIELDS if key != "alias")):
                    raise ValueError(f"{path.name}:{line}: row must contain six fields")
                if row["upos"] not in UPOS or row["word"] not in row["positive"]:
                    raise ValueError(f"{path.name}:{line}: invalid UPOS or positive example")
                if row["positive"] == row["negative"]:
                    raise ValueError(f"{path.name}:{line}: examples must differ")
                records.append({**row, "file": path.name, "line": line})
    words = Counter(row["word"] for row in records)
    aliases = Counter(row["alias"] for row in records if row["alias"])
    if any(count != 1 for count in words.values()):
        raise ValueError("Multiple entries use the same word")
    if words.keys() & aliases.keys() or any(count != 1 for count in aliases.values()):
        raise ValueError("An alias conflicts with a word or another alias")
    return records


def counts_for(entry, corpus):
    word = entry["word"]
    return corpus["pos_frequencies"].get(word, {})


def audit(records, baselines):
    rows = []
    totals = {label: Counter() for label in baselines}
    for entry in records:
        observations = {}
        for label, corpus in baselines.items():
            tags = counts_for(entry, corpus)
            occurrences = sum(tags.values())
            in_scope_pos = tags.get(entry["upos"], 0)
            totals[label]["attested_as_single_token"] += bool(occurrences)
            totals[label]["target_upos_attested"] += bool(in_scope_pos)
            totals[label]["other_upos_attested"] += in_scope_pos != occurrences
            observations[label] = tags
        rows.append({**entry, "observed_upos_counts": observations})
    return {
        "candidate_count": len(rows), "alias_count": sum(bool(row["alias"]) for row in rows),
        "candidate_upos": dict(sorted(Counter(row["upos"] for row in rows).items())),
        "coverage": totals, "rows": rows,
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--kubernetes", type=Path, help="Kubernetes profile JSON")
    cli.add_argument("--mdn", type=Path, help="MDN profile JSON")
    args = cli.parse_args()
    records = load_candidates()
    baselines = {}
    if args.kubernetes is not None:
        kubernetes = json.loads(args.kubernetes.read_text(encoding="utf-8"))["results"]
        baselines.update(kubernetes_development=kubernetes["development"],
                         kubernetes_holdout=kubernetes["holdout"])
    if args.mdn is not None:
        mdn = json.loads(args.mdn.read_text(encoding="utf-8"))["results"]
        baselines["mdn"] = mdn["external"]
    print(json.dumps(audit(records, baselines), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
