import argparse
import json
import re
import unicodedata

import psycopg
from dotenv import dotenv_values
from sentence_transformers import SentenceTransformer

from embeddings import MODEL_NAME
from retrieval import ROOT, retrieve


def evidence_key(text):
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"(?<=\w)-[ \t]*\r?\n[ \t]*(?=\w)", "", text)
    text = text.replace("\u00ad", "").replace("\u2212", "-")
    text = text.translate(str.maketrans("\u201c\u201d", '""'))
    return "".join(text.split())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    split = parser.parse_args().split

    questions_path = ROOT / "benchmark" / "questions.json"
    questions = json.loads(questions_path.read_text(encoding="utf-8-sig"))
    selected = [item for item in questions if item["split"] == split]

    minimum = {"dev": 15, "test": 5}[split]
    if len(selected) < minimum or any(
        not evidence_key(item["evidence"]) for item in selected
    ):
        raise ValueError(f"Expected at least {minimum} {split} questions with evidence")

    database_url = dotenv_values(ROOT / "starter" / ".env").get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is missing from starter/.env")

    model = SentenceTransformer(MODEL_NAME, device="cpu")
    vectors = model.encode(
        [f"query: {item['question']}" for item in selected],
        normalize_embeddings=True,
    )

    traces = []
    with psycopg.connect(database_url) as connection:
        for item, vector in zip(selected, vectors, strict=True):
            query_vector = json.dumps(vector.tolist(), allow_nan=False)
            gold = evidence_key(item["evidence"])

            for strategy in ("A", "B", "C"):
                rows = retrieve(
                    connection,
                    query_vector,
                    strategy,
                    item["document_id"],
                    item.get("filters", {}),
                )
                if len(rows) != 3:
                    raise RuntimeError(
                        f"{item['id']} / {strategy}: expected 3 chunks, got {len(rows)}"
                    )

                for rank, row in enumerate(rows, start=1):
                    row["rank"] = rank
                    row["evidence_hit"] = (
                        row["document_id"] == item["document_id"]
                        and row["printed_page"] == item["printed_page"]
                        and gold in evidence_key(row["content"])
                    )

                traces.append({
                    "question": item,
                    "strategy": strategy,
                    "hit_at_1": rows[0]["evidence_hit"],
                    "hit_at_3": any(row["evidence_hit"] for row in rows),
                    "results": rows,
                })

    output = ROOT / "results" / f"{split}_trace.jsonl"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        for trace in traces:
            file.write(json.dumps(trace, ensure_ascii=False) + "\n")

    for strategy in ("A", "B", "C"):
        runs = [trace for trace in traces if trace["strategy"] == strategy]
        hit_1 = sum(trace["hit_at_1"] for trace in runs)
        hit_3 = sum(trace["hit_at_3"] for trace in runs)
        print(
            f"{strategy}: Hit@1 = {hit_1}/{len(runs)} | "
            f"Evidence Hit@3 = {hit_3}/{len(runs)}"
        )

    print(f"Saved {len(traces)} runs to {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()