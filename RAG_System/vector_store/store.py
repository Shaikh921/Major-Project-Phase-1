"""
Persistent Hybrid Vector Store with Dense Cosine Matrix & Sparse BM25 Integration.
Persists embedding matrices and chunk metadata to disk at data/rag_index/.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np

from RAG_System.chunking.text_chunker import DocumentChunk
from RAG_System.vector_store.bm25_index import BM25Index

logger = logging.getLogger("cloudops.rag.vectorstore")


class PersistentVectorStore:
    """
    High-performance hybrid vector store supporting dense embedding vector search,
    sparse BM25 lexical keyword matching, metadata filtering, and disk persistence.
    """

    def __init__(self):
        self.chunks: List[DocumentChunk] = []
        self.chunk_ids: List[str] = []
        self.embeddings_matrix: Optional[np.ndarray] = None
        self.bm25 = BM25Index()

    def count(self) -> int:
        return len(self.chunks)

    def add_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]):
        """Adds new chunks and their corresponding embeddings into the index."""
        if not chunks:
            return

        # Deduplicate against existing chunk_ids
        existing_ids = set(self.chunk_ids)
        new_chunks = []
        new_embeddings = []

        for ch, emb in zip(chunks, embeddings):
            if ch.chunk_id in existing_ids:
                # Replace existing
                idx = self.chunk_ids.index(ch.chunk_id)
                self.chunks[idx] = ch
                if self.embeddings_matrix is not None:
                    self.embeddings_matrix[idx] = np.array(emb, dtype=np.float32)
            else:
                new_chunks.append(ch)
                new_embeddings.append(emb)
                existing_ids.add(ch.chunk_id)

        if new_chunks:
            self.chunks.extend(new_chunks)
            self.chunk_ids.extend([c.chunk_id for c in new_chunks])

            new_mat = np.array(new_embeddings, dtype=np.float32)
            # Ensure vectors are unit-normalized
            norms = np.linalg.norm(new_mat, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            new_mat = new_mat / norms

            if self.embeddings_matrix is None:
                self.embeddings_matrix = new_mat
            else:
                self.embeddings_matrix = np.vstack([self.embeddings_matrix, new_mat])

        # Re-index BM25 lexical search
        texts = [c.text for c in self.chunks]
        self.bm25.index_documents(self.chunk_ids, texts)
        logger.info(f"VectorStore currently holds {len(self.chunks)} active chunks.")

    def dense_search(
        self,
        query_vector: List[float],
        top_k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[DocumentChunk, float]]:
        """Dense semantic search using cosine similarity dot product."""
        if self.embeddings_matrix is None or len(self.chunks) == 0:
            return []

        q = np.array(query_vector, dtype=np.float32)
        norm = np.linalg.norm(q)
        if norm > 0:
            q = q / norm

        # Compute dot product against all document vectors
        similarities = np.dot(self.embeddings_matrix, q)

        results = []
        for idx, score in enumerate(similarities):
            chunk = self.chunks[idx]
            if self._matches_filter(chunk, metadata_filter):
                results.append((chunk, float(score)))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def bm25_search(
        self,
        query: str,
        top_k: int = 10,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[DocumentChunk, float]]:
        """Sparse lexical BM25 keyword search."""
        raw_results = self.bm25.search(query, top_k=top_k * 2)
        results = []
        for doc_idx, score in raw_results:
            chunk = self.chunks[doc_idx]
            if self._matches_filter(chunk, metadata_filter):
                results.append((chunk, score))
                if len(results) >= top_k:
                    break
        return results

    def hybrid_search(
        self,
        query: str,
        query_vector: List[float],
        top_k: int = 5,
        alpha: float = 0.65,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Executes Reciprocal Rank Fusion (RRF) & normalized score interpolation between
        dense semantic similarity and sparse BM25 keyword matching.
        """
        dense_results = self.dense_search(query_vector, top_k=top_k * 2, metadata_filter=metadata_filter)
        bm25_results = self.bm25_search(query, top_k=top_k * 2, metadata_filter=metadata_filter)

        # Normalize dense scores [0, 1]
        dense_scores = {chunk.chunk_id: score for chunk, score in dense_results}
        bm25_raw_scores = {chunk.chunk_id: score for chunk, score in bm25_results}

        max_bm25 = max(bm25_raw_scores.values()) if bm25_raw_scores else 1.0
        if max_bm25 == 0:
            max_bm25 = 1.0

        combined_scores: Dict[str, Tuple[DocumentChunk, float]] = {}

        # 1. Process dense candidates
        for chunk, dense_score in dense_results:
            cid = chunk.chunk_id
            norm_dense = max(0.0, min(1.0, (dense_score + 1.0) / 2.0))  # Map [-1, 1] to [0, 1]
            norm_bm25 = (bm25_raw_scores.get(cid, 0.0) / max_bm25)

            hybrid_score = (alpha * norm_dense) + ((1.0 - alpha) * norm_bm25)
            combined_scores[cid] = (chunk, hybrid_score)

        # 2. Process remaining BM25 candidates
        for chunk, raw_bm25 in bm25_results:
            cid = chunk.chunk_id
            if cid not in combined_scores:
                norm_bm25 = (raw_bm25 / max_bm25)
                dense_score = dense_scores.get(cid, 0.0)
                norm_dense = max(0.0, min(1.0, (dense_score + 1.0) / 2.0))
                hybrid_score = (alpha * norm_dense) + ((1.0 - alpha) * norm_bm25)
                combined_scores[cid] = (chunk, hybrid_score)

        sorted_results = sorted(combined_scores.values(), key=lambda x: x[1], reverse=True)
        return sorted_results[:top_k]

    def _matches_filter(self, chunk: DocumentChunk, metadata_filter: Optional[Dict[str, Any]]) -> bool:
        if not metadata_filter:
            return True
        for key, val in metadata_filter.items():
            if val is None:
                continue
            chunk_val = chunk.metadata.get(key)
            if chunk_val != val:
                return False
        return True

    def save(self, storage_dir: Path):
        """Persists vector store chunks and embeddings matrix to disk."""
        storage_dir.mkdir(parents=True, exist_ok=True)
        meta_path = storage_dir / "chunks.json"
        matrix_path = storage_dir / "embeddings.npy"

        chunks_data = [c.to_dict() for c in self.chunks]
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(chunks_data, f, indent=2)

        if self.embeddings_matrix is not None:
            np.save(matrix_path, self.embeddings_matrix)

        logger.info(f"Persisted {len(self.chunks)} chunks to {storage_dir}")

    def load(self, storage_dir: Path) -> bool:
        """Loads vector store chunks and embeddings matrix from disk."""
        meta_path = storage_dir / "chunks.json"
        matrix_path = storage_dir / "embeddings.npy"

        if not meta_path.exists() or not matrix_path.exists():
            return False

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                chunks_data = json.load(f)

            self.chunks = [DocumentChunk.from_dict(d) for d in chunks_data]
            self.chunk_ids = [c.chunk_id for c in self.chunks]
            self.embeddings_matrix = np.load(matrix_path)

            texts = [c.text for c in self.chunks]
            self.bm25.index_documents(self.chunk_ids, texts)
            logger.info(f"Loaded {len(self.chunks)} chunks from {storage_dir}")
            return True
        except Exception as e:
            logger.error(f"Failed to load vector store from {storage_dir}: {e}")
            return False
