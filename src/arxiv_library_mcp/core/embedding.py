"""Text chunking utilities for embedding indexing."""

from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 512, overlap: int = 64) -> list[str]:
    """Split text into overlapping chunks by word count.

    Tries to split on paragraph boundaries first, falling back to word boundaries.
    """
    if not text or not text.strip():
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current_words: list[str] = []

    for para in paragraphs:
        words = para.split()
        for word in words:
            current_words.append(word)
            if len(current_words) >= chunk_size:
                chunks.append(" ".join(current_words))
                # Keep overlap words for context continuity
                current_words = current_words[-overlap:]

    # Flush remaining words if they form a meaningful chunk
    if current_words:
        chunks.append(" ".join(current_words))

    return chunks
