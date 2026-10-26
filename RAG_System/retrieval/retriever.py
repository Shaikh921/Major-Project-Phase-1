"""
Hybrid Retriever combining Dense Vector and BM25 lexical results with metadata filtering.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from RAG_System.vector_store.store import PersistentVectorStore
from RAG_System.chunking.text_chunker import DocumentChunk
from RAG_System.embeddings.embedding_service import get_embedding_provider
from RAG_System.config import rag_settings


@dataclass
class RetrievedChunk:
    chunk_id: str
    content: str
    source_type: str
    reference_id: str
    title: str
    section: str
    metadata: Dict[str, Any]
    score: float

    def to_citation(self) -> str:
        """Returns clean markdown citation label."""
        return f"[{self.reference_id}] {self.title} (Relevance: {self.score:.2f})"


class HybridRetriever:
    """
    Retrieves grounded context documents for incoming incident queries
    by querying PersistentVectorStore using hybrid BM25 + dense search.
    """

    def __init__(self, store: Optional[PersistentVectorStore] = None):
        self.store = store or PersistentVectorStore()
        self.embedding_provider = get_embedding_provider()

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        source_type: Optional[str] = None,
        metadata_filter: Optional[Dict[str, Any]] = None,
    ) -> List[RetrievedChunk]:
        """
        Executes hybrid retrieval and converts DocumentChunk matches to RetrievedChunk.
        """
        k = top_k or rag_settings.TOP_K
        query_vector = self.embedding_provider.embed_query(query)

        filter_dict = dict(metadata_filter) if metadata_filter else {}
        if source_type:
            filter_dict["type"] = source_type

        matches = self.store.hybrid_search(
            query=query,
            query_vector=query_vector,
            top_k=k,
            alpha=rag_settings.HYBRID_ALPHA,
            metadata_filter=filter_dict if filter_dict else None,
        )

        retrieved: List[RetrievedChunk] = []
        for chunk, score in matches:
            ref_id = chunk.metadata.get("reference_id") or chunk.metadata.get("id") or chunk.doc_id
            s_type = chunk.metadata.get("type") or chunk.metadata.get("source_type") or "runbook"
            retrieved.append(
                RetrievedChunk(
                    chunk_id=chunk.chunk_id,
                    content=chunk.text,
                    source_type=str(s_type),
                    reference_id=str(ref_id),
                    title=chunk.title,
                    section=chunk.section,
                    metadata=chunk.metadata,
                    score=float(score),
                )
            )

        return retrieved
