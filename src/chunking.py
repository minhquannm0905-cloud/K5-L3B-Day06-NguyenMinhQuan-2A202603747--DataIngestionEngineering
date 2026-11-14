import json
from pathlib import Path
import re

CHUNK_SIZE = 500
OVERLAP = 50


def fixed_chunks(text):
    start = 0
    while start < len(text):
        end = min(start + CHUNK_SIZE, len(text))
        chunk = text[start:end].strip()
        if chunk:
            yield chunk

        if end == len(text):
            break
        start = end - OVERLAP

HEADING = re.compile(r"^[345]\.\d+(?:\.\d+)*\s+\S")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def section_chunks(text):
    section_lines = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        if HEADING.match(line) and section_lines:
            yield from pack_sentences(" ".join(section_lines))
            section_lines = []

        section_lines.append(line)

    if section_lines:
        yield from pack_sentences(" ".join(section_lines))


def pack_sentences(text):
    current = ""

    for sentence in SENTENCE_END.split(text):
        if len(sentence) > CHUNK_SIZE:
            if current:
                yield current
                current = ""
            yield from fixed_chunks(sentence)
            continue

        candidate = f"{current} {sentence}".strip()
        if len(candidate) > CHUNK_SIZE:
            yield current
            current = sentence
        else:
            current = candidate

    if current:
        yield current

def main():
    root = Path(__file__).resolve().parents[1]
    processed = root / "data" / "processed"

    with (processed / "pages.jsonl").open(encoding="utf-8") as source:
        pages = [json.loads(line) for line in source if line.strip()]

    for strategy, split_text in (("A", fixed_chunks), ("B", section_chunks)):
        output_path = processed / f"chunks_{strategy.lower()}.jsonl"
        count = 0

        with output_path.open("w", encoding="utf-8") as output:
            for page in pages:
                metadata = {key: value for key, value in page.items() if key != "text"}
                text = page["text"]
                if strategy == "A":
                    text = " ".join(text.split())

                for index, chunk in enumerate(split_text(text), start=1):
                    record = {
                        **metadata,
                        "chunk_id": f"{strategy.lower()}-{page['page_id']}-{index:03d}",
                        "strategy": strategy,
                        "text": chunk,
                    }
                    output.write(json.dumps(record, ensure_ascii=False) + "\n")
                    count += 1

        print(f"Saved {count} chunks to {output_path.relative_to(root)}")


if __name__ == "__main__":
    main()