import csv
import datetime
import json
import re
import unicodedata
from pathlib import Path
from typing import Iterable
from urllib import request


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LIST_FILE = ROOT / "docs" / "stripe_sources.md"
RAW_DIR = ROOT / "docs" / "raw"
REQ_DIR = ROOT / "docs" / "requirements"
TRACEABILITY_MATRIX_FILE = ROOT / "docs" / "traceability_matrix.csv"
SCOPE_CORE_FILE = REQ_DIR / "traceability_scope_core.csv"


def extract_source_urls(markdown_text: str) -> list[str]:
    urls = []
    for line in markdown_text.splitlines():
        line = line.strip()
        if line.startswith("- http://") or line.startswith("- https://"):
            urls.append(line[2:].strip())
    return urls


def to_markdown_url(url: str) -> str:
    return url if url.endswith(".md") else f"{url}.md"


def fetch_markdown(url: str) -> str:
    with request.urlopen(url, timeout=40) as resp:
        body = resp.read()
    return body.decode("utf-8", errors="replace")


def slugify_url(url: str) -> str:
    cleaned = re.sub(r"^https?://", "", url)
    cleaned = cleaned.replace("/", "_")
    cleaned = cleaned.replace("?", "_")
    cleaned = cleaned.replace("&", "_")
    cleaned = cleaned.replace("=", "_")
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned[:120]


def strip_markdown_noise(markdown_text: str) -> str:
    text = markdown_text
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`[^`]+`", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]+\]\([^)]*\)", " ", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"\|.*\|", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def split_sentences(text: str) -> Iterable[str]:
    rough = re.split(r"(?<=[.!?])\s+", text)
    for sentence in rough:
        s = normalize_ascii(sentence.strip())
        if len(s) < 30:
            continue
        if len(s.split()) < 6:
            continue
        if _is_noise_sentence(s):
            continue
        yield s


def normalize_ascii(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", errors="ignore").decode("ascii")
    return re.sub(r"\s+", " ", ascii_text).strip()


def _is_noise_sentence(sentence: str) -> bool:
    lower = sentence.lower()
    if "related guide" in lower:
        return True
    if lower.startswith("endpoints "):
        return True
    if sentence.count("-") > 6:
        return True
    if "copy for llm" in lower:
        return True
    if lower.startswith("was this page helpful"):
        return True
    if lower.startswith("more "):
        return True
    return False


def classify_sentence(url: str, sentence: str) -> str:
    url_l = url.lower()
    s = sentence.lower()
    if "/create" in url_l or "create" in s:
        return "create"
    if "/confirm" in url_l or "confirm" in s:
        return "confirm"
    if "/cancel" in url_l or "cancel" in s:
        return "cancel"
    if "/capture" in url_l or "capture" in s:
        return "capture"
    if "/refund" in url_l or "refund" in s:
        return "refund"
    if "idempot" in s:
        return "idempotency"
    if "error" in s:
        return "errors"
    if "status" in s:
        return "status"
    return "general"


def is_core_scope_sentence(sentence: str) -> bool:
    lower = sentence.lower()
    if lower.startswith("- "):
        return False
    if lower.startswith("parameters "):
        return False
    if "(optional)" in lower or "(enum" in lower or "(object" in lower:
        return False
    if "line item data" in lower:
        return False
    if len(sentence) > 260:
        return False

    signal_terms = [
        "must",
        "should",
        "cannot",
        "can ",
        "create",
        "confirm",
        "cancel",
        "capture",
        "refund",
        "status",
        "returns",
        "required",
        "idempotent",
        "error",
        "succeeded",
        "requires_",
        "paymentintent",
    ]
    return any(term in lower for term in signal_terms)


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    REQ_DIR.mkdir(parents=True, exist_ok=True)

    if not SOURCE_LIST_FILE.exists():
        raise FileNotFoundError(f"Missing source list: {SOURCE_LIST_FILE}")

    source_urls = extract_source_urls(SOURCE_LIST_FILE.read_text(encoding="utf-8"))
    if not source_urls:
        raise RuntimeError("No source URLs found in docs/stripe_sources.md")

    rows = []
    summary_docs = []
    doc_index = 1
    sentence_counter = 1

    for source_url in source_urls:
        markdown_url = to_markdown_url(source_url)
        markdown_text = fetch_markdown(markdown_url)
        slug = slugify_url(source_url)
        raw_path = RAW_DIR / f"{doc_index:02d}_{slug}.md"
        raw_path.write_text(markdown_text, encoding="utf-8")

        normalized_text = strip_markdown_noise(markdown_text)
        doc_sentences = list(split_sentences(normalized_text))

        doc_id = f"DOC{doc_index:03d}"
        for sentence in doc_sentences:
            sentence_id = f"REQ{sentence_counter:05d}"
            rows.append(
                {
                    "doc_id": doc_id,
                    "source_url": source_url,
                    "markdown_url": markdown_url,
                    "sentence_id": sentence_id,
                    "sentence": sentence,
                    "category": classify_sentence(source_url, sentence),
                    "planned_test_ids": "",
                }
            )
            sentence_counter += 1

        summary_docs.append(
            {
                "doc_id": doc_id,
                "source_url": source_url,
                "markdown_url": markdown_url,
                "raw_markdown_file": str(raw_path.relative_to(ROOT)).replace("\\", "/"),
                "sentence_count": len(doc_sentences),
            }
        )
        doc_index += 1

    csv_path = REQ_DIR / "traceability_seed.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "doc_id",
                "source_url",
                "markdown_url",
                "sentence_id",
                "sentence",
                "category",
                "planned_test_ids",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    with TRACEABILITY_MATRIX_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "doc_id",
                "source_url",
                "markdown_url",
                "sentence_id",
                "sentence",
                "category",
                "planned_test_ids",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    scope_rows = [row for row in rows if is_core_scope_sentence(row["sentence"])]
    with SCOPE_CORE_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "doc_id",
                "source_url",
                "markdown_url",
                "sentence_id",
                "sentence",
                "category",
                "planned_test_ids",
            ],
        )
        writer.writeheader()
        writer.writerows(scope_rows)

    summary = {
        "generated_at_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "source_count": len(source_urls),
        "requirement_sentence_count": len(rows),
        "documents": summary_docs,
        "output_files": [
            str(csv_path.relative_to(ROOT)).replace("\\", "/"),
            str(TRACEABILITY_MATRIX_FILE.relative_to(ROOT)).replace("\\", "/"),
            str(SCOPE_CORE_FILE.relative_to(ROOT)).replace("\\", "/"),
        ],
        "core_scope_sentence_count": len(scope_rows),
    }
    summary_path = REQ_DIR / "ingestion_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"Wrote {len(rows)} requirement sentences to {csv_path}")
    print(f"Wrote summary to {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
