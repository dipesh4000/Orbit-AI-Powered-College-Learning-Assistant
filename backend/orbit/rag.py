import hashlib
import json
from threading import RLock
import numpy as np
from .config import ROOT, settings
from .cache import TTLCache

INSUFFICIENT = "Insufficient information in the available course materials."


class Retriever:
    def __init__(self):
        self.model = None
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
            return
        import faiss
        from sentence_transformers import SentenceTransformer

        folder = ROOT / "data" / "rag"
        manifest = json.loads((folder / "chunks.json").read_text(encoding="utf-8"))
        if manifest["model"] != settings.embedding_model:
            raise RuntimeError("Embedding model changed; rebuild the course index.")
        self.model = SentenceTransformer(
            settings.embedding_model,
            cache_folder=str(ROOT / "data" / "models"),
            local_files_only=True,
        )
        self.index = faiss.read_index(str(folder / "index.faiss"))
        self.chunks = manifest["chunks"]
        self.catalog = manifest["catalog"]
        self.version = manifest["version"]

    def search(self, query, course_id=None, top_k=5):
        self.load()

        def retrieve():
            vector = np.asarray(
                self.model.encode([query], normalize_embeddings=True), dtype="float32"
            )
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
            (query, course_id, top_k, self.version), retrieve
        )
        return result

    def topics(self, course_id):
        # Listing topics does not require loading the embedding model into memory.
        manifest = json.loads(
            (ROOT / "data/rag/chunks.json").read_text(encoding="utf-8")
        )
        return sorted(
            {c["topic"] for c in manifest["chunks"] if course_id in c["course_ids"]}
        )


def build_index():
    import faiss
    from sentence_transformers import SentenceTransformer
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
    model = SentenceTransformer(
        settings.embedding_model, cache_folder=str(ROOT / "data" / "models")
    )
    vectors = np.asarray(
        model.encode(
            [c["source"] + ". " + c["text"] for c in chunks], normalize_embeddings=True
        ),
        dtype="float32",
    )
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    folder = ROOT / "data" / "rag"
    folder.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(folder / "index.faiss"))
    (folder / "chunks.json").write_text(
        json.dumps(
            {
                "model": settings.embedding_model,
                "version": hashlib.sha256(content.encode()).hexdigest(),
                "chunks": chunks,
                "catalog": catalog,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"Indexed {len(chunks)} demo course chunks; {sum(bool([c for c in chunks if k in c['course_ids']]) for k in catalog)} courses have material."
    )


if __name__ == "__main__":
    build_index()
