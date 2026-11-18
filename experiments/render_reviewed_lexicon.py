"""Build the specification's trial lexicon from independently reviewed records."""

import argparse
import json
from pathlib import Path

from audit_candidate_lexicon import FIELDS, ROOT, load_candidates

BEGIN = "<!-- BEGIN REVIEWED LEXICON -->"
END = "<!-- END REVIEWED LEXICON -->"
HEADER = "| 词条 | 限定词性 | 唯一核准释义 | 非核准别名（限本义） | 合规例句 | 违规例句 |"
LABELS = {
    "ADJ": "形容词", "ADV": "副词", "AUX": "助动词", "CCONJ": "并列连词",
    "NOUN": "名词", "SCONJ": "从属连词", "VERB": "动词", "PHRASE": "固定短语",
    "DET": "限定词", "NUM": "数词", "PART": "助词",
}


def judgments(path, words):
    rows = json.loads(path.read_text(encoding="utf-8"))
    result = {row["word"]: row["status"] for row in rows}
    if len(result) != len(rows) or result.keys() != words:
        raise ValueError(f"{path.name}: review does not cover the required entries")
    if not set(result.values()) <= {"accept", "revise"}:
        raise ValueError(f"{path.name}: unknown status")
    return result


def reviewed_records(entries):
    original = json.loads((ROOT / "results/lexicon_candidate_audit_before_review.json")
                          .read_text(encoding="utf-8"))
    original_rows = {row["word"]: row for row in original["rows"]}
    accepted = []
    pending = []
    for area in ("data", "operations", "states"):
        group = [item for item in entries if item["file"] == f"lexicon_{area}.tsv"]
        initial = judgments(ROOT / f"corpus/lexicon_{area}_review.json",
                            {item["word"] for item in group})
        revised_words = {word for word, status in initial.items() if status == "revise"}
        revised = judgments(ROOT / f"corpus/lexicon_{area}_rereview.json", revised_words)
        for item in group:
            word = item["word"]
            changed = any(item[key] != original_rows[word][key] for key in FIELDS)
            if changed != (word in revised_words):
                raise ValueError(f"Changes for {word} do not match the revision set")
            status = revised.get(word, initial[word])
            (accepted if status == "accept" else pending).append(item)
    return accepted, pending


def table(entries):
    lines = [BEGIN, HEADER, "| --- | --- | --- | --- | --- | --- |"]
    for entry in entries:
        row = dict(entry)
        row["upos"] = LABELS[row["upos"]]
        row["alias"] = row["alias"] or "暂无"
        fields = [row[key].replace("|", r"\|") for key in FIELDS]
        lines.append("| " + " | ".join(fields) + " |")
    lines.append(END)
    return "\n".join(lines)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--check", action="store_true")
    args = cli.parse_args()
    path = ROOT / "docs/CTC-Specification.md"
    entries, pending = reviewed_records(load_candidates())
    rendered = table(entries)
    original = path.read_text(encoding="utf-8")
    start = original.index(BEGIN)
    end = original.index(END, start) + len(END)
    updated = original[:start] + rendered + original[end:]
    if args.check:
        if original != updated:
            raise SystemExit("Specification lexicon differs from the reviewed TSV entries")
    else:
        path.write_text(updated, encoding="utf-8")
    print(f"Reviewed trial lexicon: {len(entries)} accepted, {len(pending)} pending")


if __name__ == "__main__":
    main()
