"""
Unified RAG Pipeline Orchestrator for CloudOps Intel.
Integrates Semantic Chunking, Embeddings, Hybrid BM25+Dense Retrieval, Augmentation, and Gemini Generation.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone, timedelta
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import select, desc

from RAG_System.config import rag_settings
from RAG_System.chunking.text_chunker import DocumentChunk, chunk_markdown_document
from RAG_System.chunking.telemetry_chunker import chunk_telemetry_signals
from RAG_System.embeddings.embedding_service import get_embedding_provider
from RAG_System.vector_store.store import PersistentVectorStore
from RAG_System.retrieval.retriever import HybridRetriever, RetrievedChunk
from RAG_System.augmentation.context_builder import ContextBuilder, AugmentedPrompt
from RAG_System.generation.gemini_generator import GeminiRAGGenerator, GenerationResult

from backend.app.models.host import Host
from backend.app.models.alert import Alert
from backend.app.models.security import SecurityEvent
from backend.app.models.cost import CostRecommendation

logger = logging.getLogger("rag_system.pipeline")


class RAGPipeline:
    """
    Main entry point for CloudOps Intel RAG operations.
    Manages knowledge indexing, signal aggregation, retrieval, and generative reasoning.
    """

    _instance = None

    def __init__(self):
        self.embedding_provider = get_embedding_provider()
        self.store = PersistentVectorStore()
        
        # Try loading persisted index from disk
        storage_dir = rag_settings.INDEX_STORAGE_DIR
        loaded = self.store.load(storage_dir)
        
        # Index runbooks if index is fresh or empty
        if not loaded or self.store.count() == 0:
            self.index_runbooks()

        self.retriever = HybridRetriever(store=self.store)
        self.context_builder = ContextBuilder()
        self.generator = GeminiRAGGenerator()

    @classmethod
    def get_instance(cls) -> "RAGPipeline":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def index_runbooks(self, runbooks_dir: Optional[Path] = None) -> int:
        """
        Indexes all markdown runbooks from the knowledge base directory.
        """
        kb_dir = runbooks_dir or rag_settings.KNOWLEDGE_BASE_DIR
        if not kb_dir.exists():
            logger.warning("Knowledge base directory %s does not exist.", kb_dir)
            return 0

        md_files = list(kb_dir.glob("*.md"))
        logger.info("Indexing %d runbooks from %s...", len(md_files), kb_dir)

        all_chunks: List[DocumentChunk] = []
        for md_path in md_files:
            try:
                content = md_path.read_text(encoding="utf-8")
                # Extract Title & ID from front lines if present
                title = md_path.stem.replace("_", " ").title()
                for line in content.splitlines()[:5]:
                    if line.startswith("# "):
                        title = line.lstrip("# ").strip()
                        break
                
                chunks = chunk_markdown_document(
                    markdown_text=content,
                    doc_id=md_path.stem,
                    title=title,
                    chunk_size=rag_settings.CHUNK_SIZE,
                    chunk_overlap=rag_settings.CHUNK_OVERLAP,
                    extra_metadata={"type": "runbook", "file_name": md_path.name},
                )
                all_chunks.extend(chunks)
            except Exception as e:
                logger.error("Failed to parse runbook %s: %s", md_path.name, e)

        if all_chunks:
            texts = [c.text for c in all_chunks]
            embeddings = self.embedding_provider.embed_documents(texts)
            self.store.add_chunks(all_chunks, embeddings)
            self.store.save(rag_settings.INDEX_STORAGE_DIR)
            logger.info("Successfully indexed %d chunks from %d runbooks.", len(all_chunks), len(md_files))

        return len(all_chunks)

    def query(
        self,
        db: Session,
        query: str,
        host_id: Optional[int] = None,
        environment: Optional[str] = None,
        time_window_minutes: int = 60,
    ) -> Dict[str, Any]:
        """
        Executes an end-to-end RAG incident investigation query.
        """
        # Sanitize query and time window edge cases
        cleaned_query = (query or "").strip()
        if not cleaned_query:
            cleaned_query = "Operational status and infrastructure incident triage overview."
        elif len(cleaned_query) > 2000:
            cleaned_query = cleaned_query[:2000]

        time_window_minutes = max(1, min(time_window_minutes, 10080))
        now = datetime.now(timezone.utc)
        since_ts = now - timedelta(minutes=time_window_minutes)

        # 1. Fetch live database records for signals
        host_stmt = select(Host)
        if host_id:
            host_stmt = host_stmt.where(Host.id == host_id)
        elif environment:
            host_stmt = host_stmt.where(Host.environment == environment)
        hosts = list(db.scalars(host_stmt.limit(10)).all())
        host_ids = [h.id for h in hosts] if hosts else []

        alert_stmt = select(Alert).order_by(desc(Alert.created_at)).limit(20)
        if host_ids:
            alert_stmt = alert_stmt.where(Alert.host_id.in_(host_ids))
        recent_alerts = list(db.scalars(alert_stmt).all())

        sec_stmt = select(SecurityEvent).order_by(desc(SecurityEvent.timestamp)).limit(20)
        if host_ids:
            sec_stmt = sec_stmt.where(SecurityEvent.host_id.in_(host_ids))
        recent_sec = list(db.scalars(sec_stmt).all())

        cost_stmt = select(CostRecommendation).order_by(desc(CostRecommendation.created_at)).limit(10)
        if host_ids:
            cost_stmt = cost_stmt.where(CostRecommendation.host_id.in_(host_ids))
        recent_cost = list(db.scalars(cost_stmt).all())

        # 2. Ingest dynamic telemetry signals into VectorStore for retrieval
        try:
            telemetry_chunks = chunk_telemetry_signals(
                alerts=recent_alerts,
                security_events=recent_sec,
                hosts=hosts,
                cost_recommendations=recent_cost,
            )
            if telemetry_chunks:
                existing_ids = set(self.store.chunk_ids)
                new_chunks = [c for c in telemetry_chunks if c.chunk_id not in existing_ids]
                if new_chunks:
                    texts = [c.text for c in new_chunks]
                    emb = self.embedding_provider.embed_documents(texts)
                    self.store.add_chunks(new_chunks, emb)
        except Exception as e:
            logger.warning("Could not index dynamic telemetry signals: %s", e)

        # 3. Retrieve relevant chunks using hybrid BM25 + Dense search
        retrieved_chunks = self.retriever.retrieve(
            query=cleaned_query,
            top_k=rag_settings.TOP_K,
        )

        # 4. Format live signals dict for augmentation
        live_signal_data = {
            "hosts": [{"id": h.id, "hostname": h.hostname, "environment": h.environment} for h in hosts],
            "alerts": [
                {
                    "id": a.id,
                    "host_id": a.host_id,
                    "hostname": a.host.hostname if a.host else f"Host-{a.host_id}",
                    "metric": a.metric,
                    "value": a.value,
                    "threshold": a.threshold,
                    "severity": a.severity,
                    "message": a.message,
                    "created_at": a.created_at,
                }
                for a in recent_alerts
            ],
            "security_events": [
                {
                    "id": s.id,
                    "host_id": s.host_id,
                    "hostname": s.host.hostname if s.host else "Perimeter",
                    "event_type": s.event_type,
                    "severity": s.severity,
                    "description": s.description,
                    "timestamp": s.timestamp,
                }
                for s in recent_sec
            ],
            "cost_recommendations": [
                {
                    "id": c.id,
                    "host_id": c.host_id,
                    "hostname": c.host.hostname if c.host else f"Host-{c.host_id}",
                    "recommendation_type": c.recommendation_type,
                    "savings": c.estimated_monthly_savings_usd,
                    "created_at": c.created_at,
                }
                for c in recent_cost
            ],
        }

        # 5. Augment Context
        augmented = self.context_builder.build_context(
            query=cleaned_query,
            retrieved_chunks=retrieved_chunks,
            live_signals=live_signal_data,
            time_window_minutes=time_window_minutes,
        )

        # 6. Generate with Gemini / Fallback
        gen_result: GenerationResult = self.generator.generate(augmented)

        # Build timeline events for the UI
        timeline_events = []
        for a in recent_alerts:
            timeline_events.append({
                "category": "Alert",
                "timestamp": a.created_at,
                "resource": a.host.hostname if a.host else f"Host-{a.host_id}",
                "detail": f"[{a.severity.upper()}] {a.message} ({a.metric}={a.value:.1f}, Threshold: {a.threshold:.1f})",
                "severity": a.severity,
            })
        for s in recent_sec:
            timeline_events.append({
                "category": "Security",
                "timestamp": s.timestamp,
                "resource": s.host.hostname if s.host else "Network Perimeter",
                "detail": f"[{s.severity.upper()}] {s.event_type}: {s.description}",
                "severity": s.severity,
            })
        for c in recent_cost:
            timeline_events.append({
                "category": "Cost",
                "timestamp": c.created_at,
                "resource": c.host.hostname if c.host else f"Host-{c.host_id}",
                "detail": f"Cost Optimization: {c.recommendation_type} (Potential savings: ${c.estimated_monthly_savings_usd:.2f}/mo)",
                "severity": "info",
            })
        timeline_events.sort(key=lambda x: x["timestamp"] or now, reverse=True)

        affected_hosts = list({e["resource"] for e in timeline_events}) or [
            h.hostname for h in hosts
        ] or ["Fleet-wide Infrastructure"]

        retrieved_data = [
            {
                "chunk_id": rc.chunk_id,
                "reference_id": rc.reference_id,
                "title": rc.title,
                "section": rc.section,
                "source_type": rc.source_type,
                "score": round(rc.score, 3),
                "content_preview": rc.content[:160] + "..." if len(rc.content) > 160 else rc.content,
            }
            for rc in retrieved_chunks
        ]

        structured_explanation = {
            "observation": gen_result.observation,
            "evidence_points": gen_result.evidence_points,
            "possible_root_cause": gen_result.possible_root_cause,
            "recommended_investigation": gen_result.recommended_investigation,
            "confidence_level": gen_result.confidence_level,
            "affected_resources": affected_hosts,
            "timeline_events": timeline_events[:15],
            "cited_data_sources": gen_result.citations,
            "retrieved_chunks": retrieved_data,
            "model_used": gen_result.model_used,
        }

        return {
            "query": query,
            "generated_at": now,
            "structured_explanation": structured_explanation,
            "raw_markdown_narrative": gen_result.markdown_narrative,
            "disclaimer": "AI model inferences are analytical suggestions grounded in telemetry and must be validated by operators before taking destructive remediation actions.",
        }
