"""MCP tools for preprint tracking and duplicate detection."""

from __future__ import annotations

from arxiv_library_mcp.config import config
from arxiv_library_mcp.core.doi_resolver import DOIResolver
from arxiv_library_mcp.server import mcp, get_sqlite


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
