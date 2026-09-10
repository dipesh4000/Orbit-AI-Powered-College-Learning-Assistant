import argparse
import hashlib
import json
import os
import tempfile
from threading import RLock

import numpy as np

from .cache import TTLCache
from .config import ROOT, settings
from .embeddings import Embeddings, EmbeddingUnavailable

INSUFFICIENT = "Insufficient information in the available course materials."
REINDEX = "Course index is outdated or incompatible. Run uv run python -m orbit.rag --from-existing from backend/ and restart the server."


def read_manifest():
    return json.loads((ROOT / "data/rag/chunks.json").read_text(encoding="utf-8"))


def index_ready():
    """Check compatibility without loading FAISS or making a paid API call."""
    try:
        manifest = read_manifest()
        return (
            manifest.get("embedding") == Embeddings().signature
            and manifest.get("index_sha256")
            == hashlib.sha256((ROOT / "data/rag/index.faiss").read_bytes()).hexdigest()
        )
    except (OSError, ValueError, AttributeError):
        return False


class Retriever:
    def __init__(self):
        self.embeddings = Embeddings()
        self.index = None
        self.chunks = []
        self.catalog = {}
        self.cache = TTLCache(ttl=300)
        self.version = ""
        self.lock = RLock()

    def load(self):
        with self.lock:
            self._load()

    def _load(self):
        if self.index is not None:
            if self.embedding_signature != self.embeddings.signature:
                raise EmbeddingUnavailable(REINDEX)
            return
        import faiss

        folder = ROOT / "data" / "rag"
        manifest = read_manifest()
        if manifest.get("embedding") != self.embeddings.signature:
            raise EmbeddingUnavailable(REINDEX)
        if (
            manifest.get("index_sha256")
            != hashlib.sha256((folder / "index.faiss").read_bytes()).hexdigest()
        ):
            raise EmbeddingUnavailable(REINDEX)
        index = faiss.read_index(str(folder / "index.faiss"))
        if index.d != settings.embedding_dimensions or index.ntotal != len(
            manifest["chunks"]
        ):
            raise EmbeddingUnavailable(REINDEX)
        self.chunks = manifest["chunks"]
        self.catalog = manifest["catalog"]
        self.version = manifest["version"]
        self.embedding_signature = manifest["embedding"]
        self.index = index

    def practice_sources(self, topic, course_id, top_k=5):
        # The picker supplies a catalog topic: retrieve its passages directly.
        # Known topics do not need an embedding API call just to create a quiz.
        manifest = json.loads(
            (ROOT / "data/rag/chunks.json").read_text(encoding="utf-8")
        )
        matches = [
            c
            for c in manifest["chunks"]
            if course_id in c["course_ids"]
            and c["topic"].strip().casefold() == topic.strip().casefold()
        ]
        return matches[:top_k] if matches else self.search(topic, course_id, top_k)

    def search(self, query, course_id=None, top_k=5):
        self.load()

        def retrieve():
            vector = self.embeddings.encode([query], query=True)
            scores, indices = self.index.search(vector, len(self.chunks))
            results = []
            for score, index in zip(scores[0], indices[0]):
                chunk = self.chunks[int(index)]
                if course_id and course_id not in chunk["course_ids"]:
                    continue
                if float(score) < settings.rag_threshold:
                    continue
                results.append({**chunk, "similarity": round(float(score), 4)})
                if len(results) == top_k:
                    break
            return results

        result, _ = self.cache.get_or_load(
            (query, course_id, top_k, self.version, settings.rag_threshold), retrieve
        )
        return result

    def topics(self, course_id):
        # Listing topics does not require an embedding API call.
        manifest = json.loads(
            (ROOT / "data/rag/chunks.json").read_text(encoding="utf-8")
        )
        return sorted(
            {c["topic"] for c in manifest["chunks"] if course_id in c["course_ids"]}
        )


def build_index(*, from_existing=False):
    import faiss

    if from_existing:
        manifest = read_manifest()
        chunks, catalog = manifest["chunks"], manifest["catalog"]
    else:
        chunks, catalog = source_chunks()
    if not chunks:
        raise ValueError("No course material to index.")
    embeddings = Embeddings()
    # Batch indexing; every batch must succeed before any existing artifact is replaced.
    vectors = np.concatenate(
        [
            embeddings.encode(
                [c["source"] + ". " + c["text"] for c in chunks[start : start + 32]]
            )
            for start in range(0, len(chunks), 32)
        ]
    )
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    manifest = {
        "model": settings.embedding_model,
        "embedding": embeddings.signature,
        "chunks": chunks,
        "catalog": catalog,
    }
    manifest["version"] = hashlib.sha256(
        json.dumps(manifest, sort_keys=True).encode()
    ).hexdigest()
    folder = ROOT / "data" / "rag"
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder) as staging:
        index_path = os.path.join(staging, "index.faiss")
        faiss.write_index(index, index_path)
        with open(index_path, "rb") as handle:
            manifest["index_sha256"] = hashlib.sha256(handle.read()).hexdigest()
        manifest_path = os.path.join(staging, "chunks.json")
        with open(manifest_path, "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)
        # The manifest checksum detects an interrupted update between these replacements.
        os.replace(index_path, folder / "index.faiss")
        os.replace(manifest_path, folder / "chunks.json")
    print(
        f"Indexed {len(chunks)} course chunks via Hugging Face ({settings.embedding_model}). Restart the backend."
    )


def source_chunks():

    from .ingest import rows

    catalog = {
        r["course_id"]: {"title": r["course_title"], "subject": r["course_sub_domain"]}
        for r in rows(settings.dataset_dir / "valid_uuid_engagement.csv")
    }
    content = (ROOT / "materials" / "demo_courses.json").read_text(encoding="utf-8")
    chunks = []
    for doc in json.loads(content):
        words = doc["text"].split()
        for offset in range(0, len(words), 150):
            chunks.append(
                {
                    "id": f"{doc['id']}-{offset}",
                    "source": doc["title"],
                    "topic": doc["topic"],
                    "text": " ".join(words[offset : offset + 180]),
                    "demo_material": True,
                    "course_ids": [
                        key
                        for key, value in catalog.items()
                        if value["subject"] in doc["subjects"]
                    ],
                }
            )
    return chunks, catalog


def check_retrieval():
    """Small live migration check, including unsupported questions. Consumes API quota."""
    retriever = Retriever()
    checks = [
        ("Explain database normalization", "sql-normalization-0"),
        ("What is a Python tuple?", "python-functions-0"),
        ("What is the secret campus parking policy?", None),
        ("How do I bake a chocolate cake?", None),
    ]
    failed = False
    for query, expected in checks:
        results = retriever.search(query)
        actual = results[0]["id"] if results else None
        passed = actual == expected
        failed |= not passed
        print(
            json.dumps(
                {
                    "query": query,
                    "expected": expected,
                    "actual": actual,
                    "score": results[0]["similarity"] if results else None,
                    "passed": passed,
                }
            )
        )
    if failed:
        raise EmbeddingUnavailable(
            "Retrieval checks failed. Review the model and RAG_THRESHOLD before deploying."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Build or validate the hosted embedding index."
    )
    options = parser.add_mutually_exclusive_group()
    options.add_argument(
        "--from-existing",
        action="store_true",
        help="Re-embed existing chunks without needing source CSVs.",
    )
    options.add_argument(
        "--check",
        action="store_true",
        help="Run live retrieval checks using the current index.",
    )
    args = parser.parse_args()
    try:
        if args.check:
            check_retrieval()
        else:
            build_index(from_existing=args.from_existing)
    except (EmbeddingUnavailable, FileNotFoundError) as exc:
        parser.exit(1, str(exc) + "\n")
