"""Duplicate and variant paper detection using multi-signal scoring."""

from __future__ import annotations

import re

from arxiv_library_mcp.db.models import DuplicatePair, Paper


def _title_words(title: str) -> set[str]:
    """Normalize a title into a set of lowercase words, stripping punctuation."""
    return set(re.findall(r"[a-z0-9]+", title.lower()))


def _author_names(paper: Paper) -> set[str]:
    """Get normalized last names from a paper's author list."""
    names = set()
    for a in paper.authors:
        parts = a.name.strip().split()
        if parts:
            names.add(parts[-1].lower())
    return names


def _arxiv_base_id(arxiv_id: str | None) -> str | None:
    """Strip version suffix: '2301.07041v2' -> '2301.07041'."""
    if not arxiv_id:
        return None
    m = re.match(r"^(.+?)(?:v\d+)?$", arxiv_id)
    return m.group(1) if m else arxiv_id


def detect_duplicates(
    papers: list[Paper],
    threshold: float = 0.85,
    embeddings: dict[str, list[float]] | None = None,
) -> list[DuplicatePair]:
    """Find potential duplicate/variant pairs among a list of papers.

    Scoring signals (weighted):
    - Title word overlap (Jaccard): weight 0.4
    - Author last name overlap (Jaccard): weight 0.3
    - arXiv version match (same base ID): weight 0.3
    - DOI match: automatic 1.0
    - Embedding cosine similarity: used as tiebreaker when available

    Args:
        papers: Papers to compare
        threshold: Minimum combined score to flag as duplicate (0.0-1.0)
        embeddings: Optional dict of paper_id -> embedding vector for cosine boost
    """
    pairs: list[DuplicatePair] = []
    seen: set[tuple[str, str]] = set()

    for i, a in enumerate(papers):
        for j in range(i + 1, len(papers)):
            b = papers[j]
            pair_key = (min(a.id, b.id), max(a.id, b.id))
            if pair_key in seen:
                continue

            score, reason = _score_pair(a, b, embeddings)
            if score >= threshold:
                seen.add(pair_key)
                pairs.append(DuplicatePair(
                    paper_a_id=a.id,
                    paper_b_id=b.id,
                    confidence=round(score, 3),
                    reason=reason,
                ))

    pairs.sort(key=lambda p: p.confidence, reverse=True)
    return pairs


def _score_pair(
    a: Paper, b: Paper,
    embeddings: dict[str, list[float]] | None = None,
) -> tuple[float, str]:
    """Score a pair of papers for duplicate likelihood. Returns (score, reason)."""
    reasons: list[str] = []

    # Signal 1: DOI match — automatic 1.0
    if a.doi and b.doi and a.doi.lower() == b.doi.lower():
        return 1.0, "same DOI"

    # Signal 2: arXiv version match (same base ID, different versions)
    base_a = _arxiv_base_id(a.arxiv_id)
    base_b = _arxiv_base_id(b.arxiv_id)
    arxiv_score = 0.0
    if base_a and base_b and base_a == base_b:
        return 1.0, "same arXiv paper (different versions)"

    # Signal 3: Title similarity (Jaccard)
    words_a = _title_words(a.title)
    words_b = _title_words(b.title)
    title_score = 0.0
    if words_a and words_b:
        intersection = words_a & words_b
        union = words_a | words_b
        title_score = len(intersection) / len(union) if union else 0.0

    # Signal 4: Author overlap (Jaccard on last names)
    names_a = _author_names(a)
    names_b = _author_names(b)
    author_score = 0.0
    if names_a and names_b:
        intersection = names_a & names_b
        union = names_a | names_b
        author_score = len(intersection) / len(union) if union else 0.0

    # Signal 5: Embedding cosine similarity (optional boost)
    embed_score = 0.0
    if embeddings and a.id in embeddings and b.id in embeddings:
        embed_score = _cosine_similarity(embeddings[a.id], embeddings[b.id])

    # Weighted combination
    if embeddings and a.id in embeddings and b.id in embeddings:
        # With embeddings: title 0.3, authors 0.25, embedding 0.45
        combined = title_score * 0.3 + author_score * 0.25 + embed_score * 0.45
    else:
        # Without embeddings: title 0.5, authors 0.5
        combined = title_score * 0.5 + author_score * 0.5

    if title_score > 0.7:
        reasons.append(f"title similarity {title_score:.0%}")
    if author_score > 0.5:
        reasons.append(f"author overlap {author_score:.0%}")
    if embed_score > 0.8:
        reasons.append(f"semantic similarity {embed_score:.0%}")

    return combined, ", ".join(reasons) if reasons else "low similarity"


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
