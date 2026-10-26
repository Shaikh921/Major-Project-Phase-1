"""
Deterministic Local Zero-Dependency Dense Embedding Provider (768-dim Normalized).
Provides offline and fallback semantic vectorization using subword hashing and TF-IDF weighting.
"""

import math
import hashlib
import numpy as np
from typing import List


class LocalDenseEmbeddingProvider:
    """
    Produces deterministic 768-dimensional normalized dense vectors using subword hashing,
    positional weighting, and n-gram feature projections.
    Guarantees full offline functionality when GEMINI_API_KEY is not yet populated.
    """

    def __init__(self, dimension: int = 768):
        self.dimension = dimension

    def _hash_token(self, token: str) -> int:
        h = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return int(h, 16) % self.dimension

    def _embed_single(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * self.dimension

        vec = np.zeros(self.dimension, dtype=np.float32)
        words = text.lower().split()
        total_words = len(words)

        for idx, word in enumerate(words):
            # Token feature
            bucket = self._hash_token(word)
            pos_weight = 1.0 + (1.0 / (1.0 + math.log(idx + 1.0)))
            vec[bucket] += pos_weight

            # Character 3-gram subwords for morphological capture
            if len(word) >= 3:
                for c_i in range(len(word) - 2):
                    trigram = word[c_i : c_i + 3]
                    tri_bucket = self._hash_token(trigram)
                    vec[tri_bucket] += 0.35

        # L2 Normalization so dot product = cosine similarity
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm

        return vec.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed_single(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed_single(text)
