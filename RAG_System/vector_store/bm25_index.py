"""
Pure Python Okapi BM25 Lexical Index for Sparse Keyword Retrieval.
Optimized for precise infrastructure tokens (Hostnames, IPs, Metric names, Alert types).
"""

import math
import re
from typing import List, Dict, Any, Tuple


class BM25Index:
    """Okapi BM25 implementation with sub-millisecond sparse text retrieval."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avg_doc_len = 0.0
        self.doc_lengths: List[int] = []
        self.doc_ids: List[str] = []
        self.doc_token_freqs: List[Dict[str, int]] = []
        self.doc_freqs: Dict[str, int] = {}
        self.idf: Dict[str, float] = {}

    def _tokenize(self, text: str) -> List[str]:
        # Keeps letters, digits, underscores, dashes, and periods (e.g. IPs or hostnames)
        tokens = re.findall(r"[a-zA-Z0-9_\-\.]+", text.lower())
        return [t for t in tokens if len(t) > 1]

    def index_documents(self, doc_ids: List[str], texts: List[str]):
        """Builds inverted index and IDF weights for a document collection."""
        self.doc_ids = doc_ids
        self.corpus_size = len(texts)
        self.doc_lengths = []
        self.doc_token_freqs = []
        self.doc_freqs = {}
        total_len = 0

        for text in texts:
            tokens = self._tokenize(text)
            doc_len = len(tokens)
            self.doc_lengths.append(doc_len)
            total_len += doc_len

            freqs: Dict[str, int] = {}
            for t in tokens:
                freqs[t] = freqs.get(t, 0) + 1
            self.doc_token_freqs.append(freqs)

            for t in freqs.keys():
                self.doc_freqs[t] = self.doc_freqs.get(t, 0) + 1

        self.avg_doc_len = (total_len / self.corpus_size) if self.corpus_size > 0 else 1.0

        # Precompute IDF for all terms
        self.idf = {}
        for term, freq in self.doc_freqs.items():
            # Standard Lucene/Okapi smoothed IDF
            self.idf[term] = math.log(1.0 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Scores documents against query using BM25 formula. Returns list of (doc_index, score)."""
        if not self.corpus_size:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores = [0.0] * self.corpus_size

        for term in query_tokens:
            if term not in self.idf:
                continue
            term_idf = self.idf[term]

            for doc_idx in range(self.corpus_size):
                tf = self.doc_token_freqs[doc_idx].get(term, 0)
                if tf == 0:
                    continue

                doc_len = self.doc_lengths[doc_idx]
                numerator = tf * (self.k1 + 1.0)
                denominator = tf + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
                scores[doc_idx] += term_idf * (numerator / denominator)

        # Sort top-k by score descending
        scored_pairs = [(i, s) for i, s in enumerate(scores) if s > 0]
        scored_pairs.sort(key=lambda x: x[1], reverse=True)
        return scored_pairs[:top_k]
