"""
Unit Tests for CloudOps Intel RAG System.
Validates Chunking, Embeddings, BM25 Indexing, Hybrid Search, and Pipeline Generation.
"""

import pytest
from RAG_System.chunking.text_chunker import chunk_markdown_document, DocumentChunk
from RAG_System.chunking.telemetry_chunker import chunk_telemetry_signals
from RAG_System.vector_store.bm25_index import BM25Index
from RAG_System.vector_store.store import PersistentVectorStore
from RAG_System.embeddings.embedding_service import get_embedding_provider
from RAG_System.pipeline import RAGPipeline
from tests.test_alert_engine import create_test_db


def test_markdown_chunker():
    markdown = """# SRE Runbook: High CPU Saturation
## 1. Symptom Profile
Host CPU utilization sustained above 85% for more than 5 minutes.
## 2. Remediation Steps
1. Identify top 5 CPU processes.
2. Gracefully signal rogue worker processes.
"""
    chunks = chunk_markdown_document(
        markdown_text=markdown,
        doc_id="test_runbook",
        title="High CPU Saturation",
        chunk_size=50,
        chunk_overlap=10,
    )
    assert len(chunks) >= 2
    sections = [c.section for c in chunks]
    assert any("Symptom Profile" in s for s in sections)
    assert any("Remediation Steps" in s for s in sections)


def test_bm25_lexical_index():
    index = BM25Index()
    docs = [
        "SRE Runbook: High CPU Saturation & Process Starvation with PID kill commands.",
        "SRE Runbook: Memory Leak & Out-of-Memory (OOM) Degradation with swap buffers.",
        "SRE Runbook: Storage Exhaustion & SQLite WAL Checkpoint Truncate commands.",
    ]
    doc_ids = ["doc_cpu", "doc_mem", "doc_disk"]
    index.index_documents(doc_ids, docs)

    # Search for CPU
    results_cpu = index.search("CPU saturation PID", top_k=2)
    assert len(results_cpu) > 0
    top_doc_idx = results_cpu[0][0]
    assert doc_ids[top_doc_idx] == "doc_cpu"

    # Search for WAL
    results_wal = index.search("sqlite WAL truncate checkpoint", top_k=2)
    assert len(results_wal) > 0
    top_doc_idx = results_wal[0][0]
    assert doc_ids[top_doc_idx] == "doc_disk"


def test_hybrid_vector_store():
    store = PersistentVectorStore()
    embedding_provider = get_embedding_provider()

    chunks = [
        DocumentChunk(
            chunk_id="chunk_1",
            doc_id="doc_cpu",
            title="CPU Runbook",
            section="Remediation",
            text="Kill rogue processes consuming high CPU utilization using kill -9 or Stop-Process.",
            metadata={"type": "runbook", "ref": "RUNBOOK-CPU-001"},
        ),
        DocumentChunk(
            chunk_id="chunk_2",
            doc_id="doc_mem",
            title="Memory Runbook",
            section="Remediation",
            text="Cycle worker processes when kernel OOM killer triggers on container restarts.",
            metadata={"type": "runbook", "ref": "RUNBOOK-MEM-002"},
        ),
    ]

    embeddings = embedding_provider.embed_documents([c.text for c in chunks])
    store.add_chunks(chunks, embeddings)
    assert store.count() == 2

    query = "How to kill high CPU processes?"
    query_vector = embedding_provider.embed_query(query)
    results = store.hybrid_search(query=query, query_vector=query_vector, top_k=1, alpha=0.65)

    assert len(results) == 1
    top_chunk, score = results[0]
    assert top_chunk.chunk_id == "chunk_1"
    assert score > 0.0


def test_rag_pipeline_end_to_end():
    db = create_test_db()
    pipeline = RAGPipeline.get_instance()

    result = pipeline.query(
        db=db,
        query="What is the procedure for high CPU saturation?",
        time_window_minutes=60,
    )

    assert result["query"] == "What is the procedure for high CPU saturation?"
    assert "structured_explanation" in result
    struct = result["structured_explanation"]
    assert len(struct["evidence_points"]) > 0
    assert len(struct["cited_data_sources"]) > 0
    assert struct["confidence_level"] in ["High", "Medium", "Low"]
    assert len(struct["retrieved_chunks"]) > 0
    assert struct["model_used"] is not None

    db.close()
