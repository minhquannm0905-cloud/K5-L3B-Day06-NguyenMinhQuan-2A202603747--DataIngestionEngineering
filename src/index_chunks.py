import json
from pathlib import Path
from time import perf_counter

import psycopg
from dotenv import dotenv_values
from sentence_transformers import SentenceTransformer

from embeddings import MODEL_NAME


ROOT = Path(__file__).resolve().parents[1]

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS lab_chunks (
    chunk_id TEXT PRIMARY KEY,
    strategy TEXT NOT NULL CHECK (strategy IN ('A', 'B')),
    document_id TEXT NOT NULL,
    source TEXT NOT NULL,
    page_id TEXT NOT NULL,
    pdf_page INTEGER NOT NULL,
    printed_page INTEGER NOT NULL,
    chapter INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(384) NOT NULL
)
"""

INSERT_CHUNK = """
INSERT INTO lab_chunks (
    chunk_id, strategy, document_id, source, page_id,
    pdf_page, printed_page, chapter, content, embedding
)
VALUES (
    %(chunk_id)s, %(strategy)s, %(document_id)s, %(source)s, %(page_id)s,
    %(pdf_page)s, %(printed_page)s, %(chapter)s, %(text)s, %(embedding)s::vector
)
"""


def load_chunks(strategy):
    path = ROOT / "data" / "processed" / f"chunks_{strategy.lower()}.jsonl"
    with path.open(encoding="utf-8") as file:
        chunks = [json.loads(line) for line in file if line.strip()]
    if not chunks:
        raise ValueError(f"No chunks found in {path.name}")
    return chunks


def main():
    config = dotenv_values(ROOT / "starter" / ".env")
    database_url = config.get("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is missing from starter/.env")

    started = perf_counter()
    chunks = load_chunks("A") + load_chunks("B")
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    vectors = model.encode(
        [f"passage: {chunk['text']}" for chunk in chunks],
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    if vectors.shape != (len(chunks), 384):
        raise ValueError(f"Unexpected embedding shape: {vectors.shape}")

    for chunk, vector in zip(chunks, vectors, strict=True):
        chunk["embedding"] = json.dumps(vector.tolist(), allow_nan=False)

    document_ids = sorted({chunk["document_id"] for chunk in chunks})
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLE)
            cursor.execute(
                "DELETE FROM lab_chunks WHERE document_id = ANY(%s)",
                (document_ids,),
            )
            cursor.executemany(INSERT_CHUNK, chunks)
            cursor.execute(
                """
                SELECT strategy, COUNT(*)
                FROM lab_chunks
                WHERE document_id = ANY(%s)
                GROUP BY strategy
                ORDER BY strategy
                """,
                (document_ids,),
            )
            counts = cursor.fetchall()

    for strategy, count in counts:
        print(f"{strategy}: {count} chunks in pgvector")
    print(f"Total indexing time: {perf_counter() - started:.2f} s")


if __name__ == "__main__":
    main()