"""Hosted sentence embeddings. No model weights or ML runtime are loaded locally."""

from time import perf_counter
from urllib.parse import quote

import httpx
import numpy as np

from . import telemetry
from .config import settings


class EmbeddingUnavailable(RuntimeError):
    """Safe, actionable embedding service or index error for the client."""


class Embeddings:
    @property
    def endpoint(self):
        return settings.hf_embedding_url or (
            "https://router.huggingface.co/hf-inference/models/"
            + quote(settings.embedding_model, safe="/")
        )

    @property
    def signature(self):
        # Changing the model, endpoint or text processing requires reindexing.
        # Never include the token in index metadata or cache keys.
        return {
            "provider": "huggingface",
            "model": settings.embedding_model,
            "endpoint": self.endpoint,
            "dimensions": settings.embedding_dimensions,
            "query_prefix": settings.embedding_query_prefix,
            "normalize": True,
            "truncate": True,
        }

    def encode(self, texts, *, query=False):
        if not settings.hf_token:
            raise EmbeddingUnavailable(
                "Configure HF_TOKEN in backend/.env to enable course search and indexing."
            )
        if not texts:
            raise ValueError("Provide at least one text to embed.")
        inputs = (
            [settings.embedding_query_prefix + t for t in texts] if query else texts
        )
        started, failed = perf_counter(), True
        try:
            with httpx.Client(timeout=settings.embedding_timeout_seconds) as client:
                response = client.post(
                    self.endpoint,
                    headers={"Authorization": "Bearer " + settings.hf_token},
                    json={"inputs": inputs, "normalize": True, "truncate": True},
                )
                response.raise_for_status()
                vectors = np.asarray(response.json(), dtype="float32")
            if vectors.shape != (len(texts), settings.embedding_dimensions):
                raise ValueError("Unexpected sentence embedding dimensions.")
            if not np.isfinite(vectors).all():
                raise ValueError("Non-finite embedding values.")
            norms = np.linalg.norm(vectors, axis=1, keepdims=True)
            if not np.isfinite(norms).all() or (norms <= 0).any():
                raise ValueError("Invalid embedding norms.")
            vectors = np.ascontiguousarray(vectors / norms, dtype="float32")
            failed = False
            return vectors
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status in (401, 403):
                detail = "Hugging Face rejected access. Check HF_TOKEN and its Inference Providers permission."
            elif status in (402, 429):
                detail = "Hugging Face embedding quota or rate limit was reached. Check your account credits and retry later."
            else:
                detail = "Hugging Face embeddings are unavailable. Check the configured model or endpoint and retry."
            raise EmbeddingUnavailable(detail) from exc
        except httpx.HTTPError as exc:
            raise EmbeddingUnavailable(
                "Hugging Face embeddings timed out or could not be reached. Please retry."
            ) from exc
        except (ValueError, TypeError, OverflowError) as exc:
            raise EmbeddingUnavailable(
                "Hugging Face returned invalid embeddings. Check the model, dimensions and feature-extraction endpoint."
            ) from exc
        finally:
            telemetry.record(
                "embeddings",
                "huggingface",
                (perf_counter() - started) * 1000,
                error=failed,
                text_count=len(texts),
            )
