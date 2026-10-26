"""
Unified Embedding Service Factory with Dynamic Fallback Handling.
"""

import logging
from typing import List, Protocol
from RAG_System.config import rag_settings
from RAG_System.embeddings.local_embeddings import LocalDenseEmbeddingProvider

logger = logging.getLogger("cloudops.rag.embeddings")


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        ...

    def embed_query(self, text: str) -> List[float]:
        ...


def get_embedding_provider() -> EmbeddingProvider:
    """
    Returns GeminiEmbeddingProvider if a valid API key is present.
    Gracefully returns LocalDenseEmbeddingProvider when running with placeholder keys or offline.
    """
    rag_settings.refresh_key()
    api_key = rag_settings.GEMINI_API_KEY

    if api_key and not rag_settings.IS_PLACEHOLDER_KEY:
        try:
            from RAG_System.embeddings.gemini_embeddings import GeminiEmbeddingProvider
            logger.info("Initializing Gemini text-embedding-004 provider.")
            return GeminiEmbeddingProvider(api_key=api_key, model=rag_settings.GEMINI_EMBEDDING_MODEL)
        except Exception as e:
            logger.warning(f"Failed to initialize Gemini Embedding Provider ({e}); falling back to local vectorizer.")

    logger.info("Using local deterministic dense vectorizer (offline/fallback mode).")
    return LocalDenseEmbeddingProvider(dimension=768)
