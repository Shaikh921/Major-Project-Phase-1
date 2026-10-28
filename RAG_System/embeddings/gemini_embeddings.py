"""
Google Gemini Dense Vector Embeddings Provider (gemini-embedding-001).
Includes in-memory query cache, automatic input sanitization, and graceful fallback.
"""

import logging
from typing import List, Dict
from RAG_System.config import rag_settings
from RAG_System.embeddings.local_embeddings import LocalDenseEmbeddingProvider

logger = logging.getLogger("cloudops.rag.embeddings")


class GeminiEmbeddingProvider:
    """Generates dense semantic vector embeddings using Google Gemini gemini-embedding-001."""

    def __init__(self, api_key: str, model: str = "gemini-embedding-001"):
        self.api_key = api_key
        self.model = model
        self._query_cache: Dict[str, List[float]] = {}
        self._cache_limit: int = 500
        self._local_fallback = LocalDenseEmbeddingProvider(dimension=768)

        try:
            from google import genai
            from google.genai import types
            self.client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=10000),
            )
        except Exception as e:
            logger.warning("Could not initialize google.genai client: %s", e)
            self.client = None

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embeds a batch of document texts into 768-dim vectors with fallback."""
        if not texts:
            return []

        # Sanitize texts (truncate extremely long chunks)
        cleaned_texts = [(t[:2000] if len(t) > 2000 else t) for t in texts]

        if self.client is None:
            return self._local_fallback.embed_documents(cleaned_texts)

        embeddings = []
        batch_size = 20
        for i in range(0, len(cleaned_texts), batch_size):
            batch = cleaned_texts[i : i + batch_size]
            try:
                from google.genai import types
                response = self.client.models.embed_content(
                    model=self.model,
                    contents=batch,
                    config=types.EmbedContentConfig(output_dimensionality=768),
                )
                if hasattr(response, "embeddings") and response.embeddings:
                    for emb in response.embeddings:
                        embeddings.append(list(emb.values))
                elif hasattr(response, "embedding") and response.embedding:
                    embeddings.append(list(response.embedding.values))
                else:
                    raise ValueError("Unexpected embedding response structure from Gemini API")
            except Exception as e:
                logger.warning("Gemini embedding batch failed (%s); using deterministic local embedding.", e)
                fallback_batch = self._local_fallback.embed_documents(batch)
                embeddings.extend(fallback_batch)

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embeds a single search query with LRU memory caching."""
        if not text or not text.strip():
            return [0.0] * 768

        normalized = text.strip().lower()
        if normalized in self._query_cache:
            return self._query_cache[normalized]

        results = self.embed_documents([text])
        vec = results[0] if results else [0.0] * 768

        # Cache result
        if len(self._query_cache) >= self._cache_limit:
            keys_to_remove = list(self._query_cache.keys())[:100]
            for k in keys_to_remove:
                self._query_cache.pop(k, None)
        self._query_cache[normalized] = vec

        return vec
