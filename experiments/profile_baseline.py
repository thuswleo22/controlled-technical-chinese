"""Measure observed Chinese dependency and POS features with local UDPipe."""

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_SHA256 = "2138c2efe2426f8a48c767ad3a35629a565e0f0fd37d13c3a007903236c6736d"


@dataclass(frozen=True)
class Word:
    id: int
    text: str
    upos: str
    head: int
    relation: str


def read_conllu(text):
    for block in text.strip().split("\n\n"):
        words = []
        sentence = ""
        for line in block.splitlines():
            if line.startswith("# text = "):
                sentence = line[9:]
            elif not line.startswith("#") and line.split("\t", 1)[0].isdigit():
                fields = line.split("\t")
                words.append(Word(int(fields[0]), fields[1], fields[3], int(fields[6]), fields[7]))
        if words:
            yield sentence, words


def load_parser(model_path):
    from ufal.udpipe import Model, Pipeline, ProcessingError

    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if MODEL_SHA256 and digest != MODEL_SHA256:
        raise ValueError(f"Model SHA-256 mismatch: {digest}")
    model = Model.load(str(model_path))
    if model is None:
        raise ValueError(f"Cannot load model: {model_path}")
    def parse(text):
        # The native pipeline borrows the model pointer. Keep the model alive.
        pipeline = Pipeline(model, "tokenize", Pipeline.DEFAULT, Pipeline.DEFAULT, "conllu")
        error = ProcessingError()
        output = pipeline.process(text, error)
        if error.occurred():
            raise RuntimeError(error.message)
        return list(read_conllu(output))

    return parse, digest


def depth(word, by_id):
    visited = set()
    while word.head:
        if word.id in visited:
            raise ValueError("Cycle in dependency tree")
        visited.add(word.id)
        word = by_id[word.head]
    return len(visited)


def profile(documents, parser):
    positions = defaultdict(Counter)
    rows = []
    for item in documents:
        for text, words in parser(item["text"]):
            by_id = {word.id: word for word in words}
            content = [word for word in words if word.upos != "PUNCT"]
            for word in content:
                positions[word.text][word.upos] += 1
            rows.append({
                "genre": item["genre"],
                "source": item.get("source"),
                "line": item.get("line"),
                "text": text,
                "tokens": len(content),
                "characters": sum(not char.isspace() for char in text),
                "dependency_depth": max((depth(word, by_id) for word in content), default=0),
                "verbal_clause_proxy": sum(
                    word.upos == "VERB"
                    and word.relation.split(":")[0] in {"root", "conj", "advcl", "ccomp"}
                    for word in content
                ),
                "weak_verb_candidates": sum(word.text in {"进行", "开展", "实施"} for word in content),
            })
    average_fields = ("characters", "tokens", "dependency_depth", "verbal_clause_proxy")
    token_count = sum(row["tokens"] for row in rows)
    return {
        "rows": rows,
        "sentence_count": len(rows),
        "token_count": token_count,
        "means": {key: sum(row[key] for row in rows) / len(rows) if rows else None
                  for key in average_fields},
        "observed_multi_upos_token_fraction": sum(
            sum(tags.values()) for tags in positions.values() if len(tags) > 1
        ) / token_count if token_count else None,
        "weak_verb_candidates_per_1000_tokens": 1000 * sum(
            row["weak_verb_candidates"] for row in rows
        ) / token_count if token_count else None,
        "pos_frequencies": dict(sorted(positions.items())),
    }


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--model", type=Path, required=True)
    cli.add_argument("--corpus", type=Path, default=ROOT / "corpus/kubernetes_v134.json")
    args = cli.parse_args()
    parse, digest = load_parser(args.model)
    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    if isinstance(corpus, list):
        results = {"synthetic": profile(corpus, parse)}
    else:
        results = {}
        for split in dict.fromkeys(doc["split"] for doc in corpus["documents"]):
            paragraphs = [
                {"genre": doc["genre"], "source": doc["source"], **block}
                for doc in corpus["documents"] if doc["split"] == split
                for block in doc["paragraphs"]
            ]
            results[split] = profile(paragraphs, parse)
    print(json.dumps({"engine": "ufal.udpipe 1.3.1.1", "model_sha256": digest,
                      "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
