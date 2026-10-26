"""
Google Gemini Dense Vector Embeddings Provider (text-embedding-004).
"""

import logging
from typing import List
from RAG_System.config import rag_settings

logger = logging.getLogger("cloudops.rag.embeddings")


class GeminiEmbeddingProvider:
    """Generates dense semantic vector embeddings using Google Gemini text-embedding-004."""

    def __init__(self, api_key: str, model: str = "text-embedding-004"):
        self.api_key = api_key
        self.model = model
        from google import genai
        self.client = genai.Client(api_key=api_key)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Embeds a batch of document texts into 768-dim vectors."""
        if not texts:
            return []

        embeddings = []
        # Batch in chunks of 20 to avoid payload limits
        batch_size = 20
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
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
                logger.error(f"Gemini embedding batch failed: {e}")
                raise e

        return embeddings

    def embed_query(self, text: str) -> List[float]:
        """Embeds a single search query."""
        results = self.embed_documents([text])
        if results:
            return results[0]
        return [0.0] * 768
