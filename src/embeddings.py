import json
from pathlib import Path

from sentence_transformers import SentenceTransformer


MODEL_NAME = "intfloat/e5-small-v2"


def main():
    root = Path(__file__).resolve().parents[1]
    chunks_path = root / "data" / "processed" / "chunks_a.jsonl"

    with chunks_path.open(encoding="utf-8") as file:
        chunk = json.loads(next(file))

    model = SentenceTransformer(MODEL_NAME, device="cpu")
    vector = model.encode(
        f"passage: {chunk['text']}",
        normalize_embeddings=True,
    )

    print(f"Chunk: {chunk['chunk_id']}")
    print(f"Embedding shape: {vector.shape}")


if __name__ == "__main__":
    main()