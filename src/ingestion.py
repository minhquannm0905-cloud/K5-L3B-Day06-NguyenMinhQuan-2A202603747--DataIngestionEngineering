import json
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader


def normalize_text(text):
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00ad", "")
    text = re.sub(r"(?<=\w)-[ \t]*\r?\n[ \t]*(?=\w)", "", text)
    return "\n".join(" ".join(line.split()) for line in text.splitlines()).strip()


def get_chapter(printed_page):
    for chapter, first, last in ((3, 31, 44), (4, 45, 56), (5, 57, 73)):
        if first <= printed_page <= last:
            return chapter
    raise ValueError(f"No chapter mapping for printed page {printed_page}")


def main():
    root = Path(__file__).resolve().parents[1]
    manifest_path = root / "data" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    reader = PdfReader(root / manifest["local_path"])

    records = []
    for page in manifest["pages"]:
        if not page.get("included", True):
            continue

        number = page["printed_page"]
        text = normalize_text(reader.pages[page["pdf_page"] - 1].extract_text() or "")
        if not text:
            raise ValueError(f"No text extracted from printed page {number}")

        records.append({
            "page_id": page["page_id"],
            "document_id": manifest["source_id"],
            "source": manifest["source_path_or_url"],
            "pdf_page": page["pdf_page"],
            "printed_page": number,
            "chapter": get_chapter(number),
            "text": text,
        })

    output_path = root / "data" / "processed" / "pages.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )
    print(f"Saved {len(records)} pages to {output_path.relative_to(root)}")


if __name__ == "__main__":
    main()