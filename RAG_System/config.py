"""
Configuration parameters for CloudOps Intel RAG System.
"""

import os
from pathlib import Path
from backend.app.core.config import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent

class RAGSettings:
    # Directory paths
    BASE_DIR: Path = Path(__file__).resolve().parent
    KNOWLEDGE_BASE_DIR: Path = BASE_DIR / "knowledge_base" / "runbooks"
    INDEX_STORAGE_DIR: Path = PROJECT_ROOT / "data" / "rag_index"

    # Models
    GEMINI_API_KEY: str = (settings.gemini_api_key or "").strip().strip("\"'")
    GEMINI_GENERATION_MODEL: str = settings.default_llm_model or "gemini-2.5-flash"
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"

    # Chunking
    CHUNK_SIZE: int = 400  # Words per chunk
    CHUNK_OVERLAP: int = 60  # Overlapping words between chunks

    # Retrieval
    TOP_K: int = 5  # Number of chunks to retrieve
    HYBRID_ALPHA: float = 0.65  # Weight for dense similarity (1.0 = pure dense, 0.0 = pure BM25)
    SIMILARITY_THRESHOLD: float = 0.25  # Minimum cosine similarity to accept

    # Fallback
    IS_PLACEHOLDER_KEY: bool = (
        not GEMINI_API_KEY
        or "PLACEHOLDER" in GEMINI_API_KEY
        or GEMINI_API_KEY.startswith("replace-")
    )

    def refresh_key(self):
        """Reloads the key if changed in environment or .env."""
        from backend.app.core.config import settings
        raw_key = (settings.gemini_api_key or "").strip().strip("\"'")
        self.GEMINI_API_KEY = raw_key
        self.IS_PLACEHOLDER_KEY = (
            not self.GEMINI_API_KEY
            or "PLACEHOLDER" in self.GEMINI_API_KEY
            or self.GEMINI_API_KEY.startswith("replace-")
        )

rag_settings = RAGSettings()
