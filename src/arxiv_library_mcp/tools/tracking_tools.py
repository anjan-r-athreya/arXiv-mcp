"""MCP tools for preprint tracking and duplicate detection."""

from __future__ import annotations

from arxiv_library_mcp.config import config
from arxiv_library_mcp.core.doi_resolver import DOIResolver
from arxiv_library_mcp.core.duplicate_detector import detect_duplicates
from arxiv_library_mcp.server import mcp, get_sqlite, get_chroma


def _get_resolver() -> DOIResolver:
    return DOIResolver(s2_api_key=config.s2_api_key)


@mcp.tool()
def check_published(
    paper_id: str = "",
    add_to_tracking: bool = True,
) -> str:
    """Check whether arXiv preprints have been published in a journal.

    Queries Semantic Scholar and Crossref for DOI resolution. Can check a
    specific paper or all unresolved preprints in the library.

    Args:
        paper_id: Specific paper to check (empty = check all arXiv papers without DOI)
        add_to_tracking: Add unresolved papers to the tracking queue for future checks
    """
    db = get_sqlite()
    resolver = _get_resolver()

    if paper_id:
        # Check a single paper
        paper = db.get_paper(paper_id)
        if paper is None:
            return f"Paper not found: `{paper_id}`"
        if paper.doi:
            return f"**{paper.title}** already has DOI: `{paper.doi}`"
        if not paper.arxiv_id:
            return f"**{paper.title}** has no arXiv ID — cannot check for published version."
        return _check_single(db, resolver, paper.id, paper.arxiv_id,
                             paper.title, paper.authors, add_to_tracking)
    else:
        # Check all papers without DOI
        papers, _ = db.list_papers(sort_by="added_at", sort_order="desc", limit=10000)
        candidates = [p for p in papers if p.arxiv_id and not p.doi]
        if not candidates:
            return "All papers in your library already have DOIs or are non-arXiv papers."

        results = []
        resolved = 0
        for p in candidates:
            first_author = p.authors[0].name if p.authors else None
            result = _check_single(db, resolver, p.id, p.arxiv_id,
                                   p.title, p.authors, add_to_tracking)
            if "Resolved" in result:
                resolved += 1
            results.append(result)

        header = f"**Checked {len(candidates)} papers, resolved {resolved} DOIs.**\n\n"
        return header + "\n".join(results)


def _check_single(db, resolver, paper_id, arxiv_id, title, authors, add_to_tracking) -> str:
    """Check a single paper for published DOI."""
    # Try Semantic Scholar first
    result = resolver.resolve_arxiv_to_doi(arxiv_id)

    # Fall back to Crossref title search
    if not result:
        first_author = authors[0].name if authors else None
        result = resolver.resolve_by_title(title, first_author)

    if result:
        # Update paper with DOI
        db.update_paper(paper_id, doi=result.doi, journal_ref=result.journal)

        # Record in tracking queue as resolved
        _update_tracking(db, paper_id, "resolved", result.doi)

        parts = [f"- **{title}**: Resolved → `{result.doi}`"]
        if result.journal:
            parts[0] += f" ({result.journal})"
        return parts[0]
    else:
        if add_to_tracking:
            _update_tracking(db, paper_id, "pending", None)
        return f"- **{title}**: No published version found"


def _update_tracking(db, paper_id: str, status: str, doi: str | None) -> None:
    """Insert or update the tracking queue."""
    existing = db._conn.execute(
        "SELECT paper_id FROM tracking_queue WHERE paper_id = ?", (paper_id,)
    ).fetchone()
    if existing:
        db._conn.execute(
            """UPDATE tracking_queue
               SET last_checked = datetime('now'), check_count = check_count + 1,
                   status = ?, resolved_doi = ?
               WHERE paper_id = ?""",
            (status, doi, paper_id),
        )
    else:
        db._conn.execute(
            """INSERT INTO tracking_queue (paper_id, last_checked, check_count, status, resolved_doi)
               VALUES (?, datetime('now'), 1, ?, ?)""",
            (paper_id, status, doi),
        )
    db._conn.commit()


@mcp.tool()
def find_duplicates(
    threshold: float = 0.85,
    paper_id: str = "",
) -> str:
    """Scan your library for potential duplicate or variant papers.

    Uses title similarity, author overlap, arXiv version detection, and
    optionally embedding cosine similarity. Reports pairs with confidence scores.

    Args:
        threshold: Minimum similarity score to flag (0.0-1.0, default 0.85)
        paper_id: Check a specific paper against all others, or empty for full scan
    """
    db = get_sqlite()
    chroma = get_chroma()

    if paper_id:
        target = db.get_paper(paper_id)
        if target is None:
            return f"Paper not found: `{paper_id}`"
        all_papers, _ = db.list_papers(limit=10000)
        papers = [target] + [p for p in all_papers if p.id != target.id]
    else:
        papers, _ = db.list_papers(limit=10000)

    if len(papers) < 2:
        return "Need at least 2 papers in the library to check for duplicates."

    # Try to get embeddings for cosine similarity boost
    embeddings: dict[str, list[float]] = {}
    for p in papers:
        emb = chroma.get_paper_embedding(p.id)
        if emb:
            embeddings[p.id] = emb

    pairs = detect_duplicates(papers, threshold=threshold, embeddings=embeddings or None)

    if not pairs:
        return f"No potential duplicates found (threshold: {threshold:.0%})."

    # Format output
    lines = [f"**Found {len(pairs)} potential duplicate pair{'s' if len(pairs) != 1 else ''}:**\n"]

    # Build ID-to-paper lookup
    paper_map = {p.id: p for p in papers}

    for pair in pairs:
        a = paper_map.get(pair.paper_a_id)
        b = paper_map.get(pair.paper_b_id)
        if not a or not b:
            continue
        conf = f"{pair.confidence:.0%}"
        lines.append(f"- **{conf}** confidence: {pair.reason}")
        lines.append(f"  - `{a.id[:8]}` {a.title}")
        lines.append(f"  - `{b.id[:8]}` {b.title}")
        lines.append("")

    return "\n".join(lines)
