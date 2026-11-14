import json
from pathlib import Path

import psycopg
from dotenv import dotenv_values
from psycopg.rows import dict_row
from sentence_transformers import SentenceTransformer

from embeddings import MODEL_NAME


ROOT = Path(__file__).resolve().parents[1]


def retrieve(connection, query_vector, strategy, document_id, filters):
    indexed_strategy = "B" if strategy == "C" else strategy
    chapter = filters.get("chapter") if strategy == "C" else None

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute(
            """
            SELECT chunk_id, document_id, source, printed_page, chapter, content,
                   embedding <=> %(query_vector)s::vector AS distance
            FROM lab_chunks
            WHERE strategy = %(strategy)s
              AND document_id = %(document_id)s
              AND (%(chapter)s::integer IS NULL OR chapter = %(chapter)s::integer)
            ORDER BY distance, chunk_id
            LIMIT 3
            """,
            {
                "query_vector": query_vector,
                "strategy": indexed_strategy,
                "document_id": document_id,
                "chapter": chapter,
            },
        )
        return cursor.fetchall()


def main():
    questions_path = ROOT / "benchmark" / "questions.json"
    questions = json.loads(questions_path.read_text(encoding="utf-8-sig"))
    question = next(item for item in questions if item["id"] == "q02")

    database_url = dotenv_values(ROOT / "starter" / ".env").get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is missing from starter/.env")

    model = SentenceTransformer(MODEL_NAME, device="cpu")
    vector = model.encode(
        f"query: {question['question']}",
        normalize_embeddings=True,
    )
    query_vector = json.dumps(vector.tolist(), allow_nan=False)

    print(question["question"])
    with psycopg.connect(database_url) as connection:
        for strategy in ("A", "B", "C"):
            print(f"\nStrategy {strategy}")
            rows = retrieve(
                connection,
                query_vector,
                strategy,
                question["document_id"],
                question.get("filters", {}),
            )
            for rank, row in enumerate(rows, start=1):
                print(
                    f"{rank}. {row['chunk_id']} | page {row['printed_page']} "
                    f"| chapter {row['chapter']} | distance {row['distance']:.4f}"
                )
                print(row["content"])


if __name__ == "__main__":
    main()