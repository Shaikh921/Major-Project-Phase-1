"""
Semantic Markdown & Text Chunker with Header Tracking & Sliding Window Overlap.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class DocumentChunk:
    chunk_id: str
    doc_id: str
    title: str
    section: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_id": self.chunk_id,
            "doc_id": self.doc_id,
            "title": self.title,
            "section": self.section,
            "text": self.text,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentChunk":
        return cls(
            chunk_id=data["chunk_id"],
            doc_id=data["doc_id"],
            title=data.get("title", ""),
            section=data.get("section", ""),
            text=data["text"],
            metadata=data.get("metadata", {}),
        )


def chunk_markdown_document(
    markdown_text: str,
    doc_id: str,
    title: str,
    chunk_size: int = 350,
    chunk_overlap: int = 50,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> List[DocumentChunk]:
    """
    Splits markdown documentation into semantic chunks by headers,
    applying sliding-window overlap when sections exceed chunk_size words.
    """
    extra_metadata = extra_metadata or {}
    chunks: List[DocumentChunk] = []

    # Regex to identify H1, H2, H3 headers
    header_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
    matches = list(header_pattern.finditer(markdown_text))

    if not matches:
        # No headers found; perform standard sliding window on full text
        return _sliding_window_chunks(
            text=markdown_text,
            doc_id=doc_id,
            title=title,
            section="General",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            extra_metadata=extra_metadata,
        )

    # Process section by section
    for i, match in enumerate(matches):
        section_title = match.group(2).strip()
        start_pos = match.start()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(markdown_text)

        section_text = markdown_text[start_pos:end_pos].strip()
        if not section_text:
            continue

        words = section_text.split()
        if len(words) <= chunk_size:
            chunk_id = f"{doc_id}_sec_{i}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=doc_id,
                    title=title,
                    section=section_title,
                    text=section_text,
                    metadata={
                        **extra_metadata,
                        "source": doc_id,
                        "title": title,
                        "section": section_title,
                        "word_count": len(words),
                        "type": "runbook",
                    },
                )
            )
        else:
            # Section is large; apply sliding window within section
            sub_chunks = _sliding_window_chunks(
                text=section_text,
                doc_id=doc_id,
                title=title,
                section=section_title,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                prefix=f"sec_{i}",
                extra_metadata=extra_metadata,
            )
            chunks.extend(sub_chunks)

    return chunks


def _sliding_window_chunks(
    text: str,
    doc_id: str,
    title: str,
    section: str,
    chunk_size: int,
    chunk_overlap: int,
    prefix: str = "win",
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> List[DocumentChunk]:
    """Splits a single block of text into overlapping word windows."""
    extra_metadata = extra_metadata or {}
    words = text.split()
    chunks: List[DocumentChunk] = []

    if not words:
        return chunks

    step = max(1, chunk_size - chunk_overlap)
    sub_idx = 0
    for start in range(0, len(words), step):
        end = min(len(words), start + chunk_size)
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)

        chunk_id = f"{doc_id}_{prefix}_{sub_idx}"
        chunks.append(
            DocumentChunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                title=title,
                section=section,
                text=f"### {title} - {section}\n\n{chunk_text}",
                metadata={
                    **extra_metadata,
                    "source": doc_id,
                    "title": title,
                    "section": section,
                    "word_count": len(chunk_words),
                    "type": "runbook",
                },
            )
        )
        sub_idx += 1
        if end >= len(words):
            break

    return chunks
