"""
Embeddings package for dense vector generation.
"""

from RAG_System.embeddings.embedding_service import get_embedding_provider, EmbeddingProvider

__all__ = ["get_embedding_provider", "EmbeddingProvider"]
