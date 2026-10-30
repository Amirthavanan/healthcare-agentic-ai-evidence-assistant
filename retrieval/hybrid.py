import argparse
import hashlib
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from pypdf import PdfReader
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("healthcare_agentic_ai.retrieval")

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "sources"
REGISTRY_PATH = SOURCE_DIR / "registry.json"
INDEX_DIR = ROOT / "data" / "faiss_index"

MODEL_NAME = os.getenv(
    "EMBEDDING_MODEL",
    "pritamdeka/S-PubMedBert-MS-MARCO",
)

DEFAULT_SPARSE_WEIGHT = float(os.getenv("SPARSE_WEIGHT", "0.35"))
DEFAULT_DENSE_WEIGHT = float(os.getenv("DENSE_WEIGHT", "0.65"))

# Ingestion configuration constants
MAX_CHUNK_CHARS = 2000
CHUNK_OVERLAP_CHARS = 300
MIN_PDF_EXTRACTABLE_CHARS = 50


def clean_text(text: str) -> str:
    """Normalize ligatures, unicode noise, and remove repetitive OCR print artifacts."""
    if not text:
        return ""
    # Normalize common Unicode typographic ligatures
    text = (
        text.replace("ﬂ", "fl")
        .replace("ﬁ", "fi")
        .replace("ﬀ", "ff")
        .replace("ﬃ", "ffi")
        .replace("ﬄ", "ffl")
    )
    # Normalize quotes, dashes, and angle symbols
    text = (
        text.replace("»", "-")
        .replace("«", "-")
        .replace("—", "-")
        .replace("–", "-")
        .replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("‘", "'")
    )
    # Remove obvious OCR scan/print headers (e.g. timestamp lines) and URL footers
    cleaned_lines = []
    for line in text.splitlines():
        line_str = line.strip()
        if re.search(r"^\d{1,2}/\d{1,2}/\d{2,4}\.?\s+\d{1,2}:\d{2}\s+(?:AM|PM)", line_str, re.IGNORECASE):
            continue
        if re.search(r"^(?:https?|hllps|mzps|naps):[/\\]+", line_str, re.IGNORECASE):
            continue
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    # Normalize repeated whitespace and line breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list[str]:
    """Split long pages into semantically cohesive subchunks with overlap."""
    text = clean_text(text)
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]

    # Split by paragraphs or list items
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks = []
    current = ""
    for p in paragraphs:
        if not current:
            current = p
        elif len(current) + len(p) + 2 <= max_chars:
            current += "\n\n" + p
        else:
            chunks.append(current)
            overlap_prefix = current[-overlap:] if len(current) > overlap else current
            current = overlap_prefix + "\n\n" + p

    if current and (not chunks or current != chunks[-1]):
        chunks.append(current)

    return chunks


def _tokens(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric words for BM25."""
    return re.findall(r"[a-z0-9]+", text.lower())


def _load_source(path: Path) -> list[dict[str, Any]]:
    """Extract searchable text and section/page metadata from PDF, OCR text, or section files."""
    if not path.is_file():
        raise FileNotFoundError(f"Source file does not exist: {path}")

    # 1. PDF extraction
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        chunks = []
        total_extracted_chars = 0

        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            total_extracted_chars += len(text)
            if not text:
                continue

            subchunks = chunk_text(text, max_chars=MAX_CHUNK_CHARS, overlap=CHUNK_OVERLAP_CHARS)
            for part_idx, chunk_text_content in enumerate(subchunks, start=1):
                sec = f"Page {page_number}" if len(subchunks) == 1 else f"Page {page_number} (Part {part_idx})"
                chunks.append({
                    "section": sec,
                    "page": page_number,
                    "text": chunk_text_content,
                })

        if total_extracted_chars < MIN_PDF_EXTRACTABLE_CHARS:
            logger.warning(
                "PDF %s yielded only %d extractable characters. "
                "Document may be scanned or require OCR.",
                path.name,
                total_extracted_chars,
            )
        return chunks

    # 2. Text files (UTF-8 / UTF-8 with BOM)
    raw = path.read_text(encoding="utf-8-sig").strip()
    if not raw:
        logger.warning("Source text file is empty: %s", path.name)
        return []

    # Check for OCR page markers: "--- Page N ---"
    if re.search(r"(?m)^--- Page \d+ ---\s*$", raw):
        sections = re.split(r"(?m)^--- Page (\d+) ---\s*$", raw)
        chunks = []
        for i in range(1, len(sections), 2):
            page_number = int(sections[i])
            page_text = sections[i + 1].strip()
            if not page_text:
                continue
            subchunks = chunk_text(page_text, max_chars=MAX_CHUNK_CHARS, overlap=CHUNK_OVERLAP_CHARS)
            for part_idx, chunk_text_content in enumerate(subchunks, start=1):
                sec = f"Page {page_number}" if len(subchunks) == 1 else f"Page {page_number} (Part {part_idx})"
                chunks.append({
                    "section": sec,
                    "page": page_number,
                    "text": chunk_text_content,
                })
        return chunks

    # Check for legacy "SECTION: " markers
    if "SECTION:" in raw:
        sections = re.split(r"(?=SECTION: )", raw)
        chunks = []
        for section in sections:
            section = section.strip()
            if not section:
                continue
            heading, separator, body = section.partition("\n")
            text = clean_text(body if separator else heading)
            if text:
                chunks.append({
                    "section": heading.removeprefix("SECTION: ").strip(),
                    "page": None,
                    "text": text,
                })
        return chunks

    # Plain text without explicit markers
    subchunks = chunk_text(raw, max_chars=MAX_CHUNK_CHARS, overlap=CHUNK_OVERLAP_CHARS)
    return [{"section": f"Section {i}", "page": None, "text": chunk_t} for i, chunk_t in enumerate(subchunks, start=1)]


class HybridRetriever:
    """Hybrid retrieval engine combining BM25 sparse matching and FAISS dense vector search."""

    def __init__(
        self,
        sparse_weight: float | None = None,
        dense_weight: float | None = None,
        force_rebuild: bool = False,
    ):
        sp_w = DEFAULT_SPARSE_WEIGHT if sparse_weight is None else sparse_weight
        de_w = DEFAULT_DENSE_WEIGHT if dense_weight is None else dense_weight

        if sp_w < 0 or de_w < 0:
            raise ValueError("Sparse and dense weights must be non-negative.")

        total_weight = sp_w + de_w
        if total_weight <= 0:
            raise ValueError("At least one retrieval weight must be positive.")

        self.sparse_weight = sp_w / total_weight
        self.dense_weight = de_w / total_weight

        self.chunks: list[dict[str, Any]] = []
        self.bm25: BM25Okapi | None = None
        self.model: SentenceTransformer | None = None
        self.index: faiss.IndexFlatIP | None = None

        self._initialize(force_rebuild=force_rebuild)

    def _initialize(self, force_rebuild: bool = False) -> None:
        """Load registered sources, construct BM25 keyword index, and load/build FAISS vector index."""
        if not REGISTRY_PATH.is_file():
            raise FileNotFoundError(f"Registry file not found: {REGISTRY_PATH}")

        try:
            registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse registry.json: {exc}") from exc

        if not isinstance(registry, list):
            raise ValueError("registry.json must contain a list of source objects.")

        source_root = SOURCE_DIR.resolve()
        seen_ids = set()
        loaded_chunks = []

        for item in registry:
            if not isinstance(item, dict):
                raise ValueError("Every registry item must be an object.")
            file_name = item.get("file")
            source_id = item.get("id")

            if not file_name or not source_id:
                raise ValueError("Registry items must specify both 'id' and 'file'.")

            if source_id in seen_ids:
                raise ValueError(f"Duplicate source ID in registry: {source_id}")
            seen_ids.add(source_id)

            path = (SOURCE_DIR / file_name).resolve()
            if not path.is_relative_to(source_root):
                raise ValueError(f"Source file escapes sources directory: {path}")

            if not path.is_file():
                raise FileNotFoundError(f"Registered source file not found: {path}")

            source_chunks = _load_source(path)
            if not source_chunks:
                logger.warning("No searchable text extracted from source: %s", file_name)

            for part in source_chunks:
                loaded_chunks.append({
                    "id": source_id,
                    "source_id": source_id,
                    "title": item.get("title", source_id),
                    "publisher": item.get("publisher", "World Health Organization"),
                    "version": item.get("version", "2021"),
                    "effective_date": item.get("effective_date", "2021-01-01"),
                    "review_status": item.get("review_status", "approved"),
                    "description": item.get("description", ""),
                    "source_file": file_name,
                    "file": file_name,
                    "section": part["section"],
                    "page": part.get("page"),
                    "text": part["text"],
                })

        if not loaded_chunks:
            raise ValueError("No searchable text loaded. Check registry, file paths, and documents.")

        self.chunks = loaded_chunks
        print(f"Loaded {len(self.chunks)} text chunks across {len(registry)} sources.")

        # Build BM25 index over normalized token streams
        tokenized_corpus = [_tokens(chunk["text"]) for chunk in self.chunks]
        self.bm25 = BM25Okapi(tokenized_corpus)

        # Compute index cache signature based on model name, chunk metadata, and text content
        signature_payload = {
            "model": MODEL_NAME,
            "chunk_count": len(self.chunks),
            "chunks": [
                {
                    "source_id": c["source_id"],
                    "section": c["section"],
                    "page": c["page"],
                    "text_hash": hashlib.sha256(c["text"].encode("utf-8")).hexdigest(),
                }
                for c in self.chunks
            ],
        }
        signature = hashlib.sha256(
            json.dumps(signature_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        ).hexdigest()

        INDEX_DIR.mkdir(parents=True, exist_ok=True)
        index_path = INDEX_DIR / "index.faiss"
        chunks_path = INDEX_DIR / "chunks.json"
        manifest_path = INDEX_DIR / "manifest.json"

        cached = False
        if not force_rebuild and index_path.is_file() and chunks_path.is_file() and manifest_path.is_file():
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if manifest.get("signature") == signature:
                    cached_chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
                    cached_index = faiss.read_index(str(index_path))

                    if (
                        isinstance(cached_chunks, list)
                        and len(cached_chunks) == len(self.chunks)
                        and cached_index.ntotal == len(self.chunks)
                    ):
                        self.chunks = cached_chunks
                        self.index = cached_index
                        cached = True
            except (OSError, ValueError, RuntimeError) as exc:
                logger.warning("Failed to load existing FAISS cache, will rebuild: %s", exc)
                cached = False

        self.model = SentenceTransformer(MODEL_NAME)

        if not cached:
            print("Building FAISS index from source documents...")
            embeddings = self.model.encode(
                [chunk["text"] for chunk in self.chunks],
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            embeddings = np.asarray(embeddings, dtype=np.float32)

            new_index = faiss.IndexFlatIP(embeddings.shape[1])
            new_index.add(embeddings)

            # Atomic file writing using temporary files to guarantee cache consistency
            temp_index = INDEX_DIR / "index.faiss.tmp"
            temp_chunks = INDEX_DIR / "chunks.json.tmp"
            temp_manifest = INDEX_DIR / "manifest.json.tmp"

            faiss.write_index(new_index, str(temp_index))
            temp_chunks.write_text(json.dumps(self.chunks, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_manifest.write_text(json.dumps({"signature": signature, "model": MODEL_NAME, "chunks": len(self.chunks)}, indent=2), encoding="utf-8")

            temp_index.replace(index_path)
            temp_chunks.replace(chunks_path)
            temp_manifest.replace(manifest_path)

            self.index = new_index
            print(f"FAISS index built and saved ({self.index.ntotal} vectors).")
        else:
            print("Loaded existing FAISS index from cache.")

    def rebuild_index(self) -> None:
        """Force rebuild and persist the FAISS index cache."""
        self._initialize(force_rebuild=True)

    @staticmethod
    def _normalize(scores: list[float] | np.ndarray) -> list[float]:
        """Normalize scores to [0.0, 1.0] relative to max score."""
        scores_list = [float(s) for s in scores]
        maximum = max(scores_list, default=0.0)
        if maximum <= 0:
            return [0.0] * len(scores_list)
        return [score / maximum for score in scores_list]

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Retrieve the top_k most relevant chunks using hybrid sparse-dense ranking."""
        if not isinstance(query, str) or not query.strip():
            return []
        if top_k < 1:
            return []
        if not 0.0 <= min_score <= 1.0:
            raise ValueError("min_score must be between 0.0 and 1.0.")

        clean_query = clean_text(query)
        tokens = _tokens(clean_query)
        if not tokens:
            return []

        # 1. Sparse BM25 keyword score
        sparse_scores = self.bm25.get_scores(tokens)

        # 2. Dense semantic vector similarity
        query_embedding = self.model.encode(
            [clean_query],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        query_embedding = np.asarray(query_embedding, dtype=np.float32)

        similarities, indices = self.index.search(query_embedding, len(self.chunks))

        dense_scores = np.zeros(len(self.chunks), dtype=np.float32)
        for score, index in zip(similarities[0], indices[0]):
            if index >= 0:
                dense_scores[index] = max(0.0, float(score))

        # 3. Hybrid combination with normalization
        sparse_norm = self._normalize(sparse_scores)
        dense_norm = self._normalize(dense_scores)

        results = []
        for i, chunk in enumerate(self.chunks):
            combined_score = (
                self.sparse_weight * sparse_norm[i]
                + self.dense_weight * dense_norm[i]
            )

            if combined_score <= 0.0 or combined_score < min_score:
                continue

            results.append({
                **chunk,
                "score": round(float(combined_score), 4),
                "sparse_score": round(float(sparse_norm[i]), 4),
                "dense_score": round(float(dense_norm[i]), 4),
                "excerpt": chunk["text"][:1200],
            })

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]


# Singleton instance for direct imports
retriever = HybridRetriever()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = argparse.ArgumentParser(description="Healthcare Hybrid Retrieval Engine CLI")
    parser.add_argument("--query", "-q", type=str, help="Search query")
    parser.add_argument("--top-k", "-k", type=int, default=5, help="Number of results")
    parser.add_argument("--rebuild", action="store_true", help="Force rebuild the FAISS index cache")
    args = parser.parse_args()

    if args.rebuild:
        print("Rebuilding retrieval index cache...")
        retriever.rebuild_index()
        print("Done.")
    elif args.query:
        print(f"\nSearching for: {args.query}")
        search_results = retriever.search(args.query, top_k=args.top_k)
        for rank, res in enumerate(search_results, start=1):
            print(f"\n{rank}. {res['source_id']} | {res.get('section')} | Score: {res['score']} (dense={res.get('dense_score')}, sparse={res.get('sparse_score')})")
            print(f"Title: {res.get('title')}")
            print(f"Excerpt: {res['excerpt'][:300]}...")
    else:
        print("Loaded retriever successfully with cached index.")
