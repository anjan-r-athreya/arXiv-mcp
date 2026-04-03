"""MCP tools for browsing and managing the paper library."""

from __future__ import annotations

from arxiv_library_mcp.server import mcp, get_sqlite, get_chroma
from arxiv_library_mcp.utils.formatting import (
    format_paper_summary,
    format_paper_list,
    format_notes,
)


@mcp.tool()
def list_papers(
    tags: list[str] | None = None,
    categories: list[str] | None = None,
    sort_by: str = "added_at",
    sort_order: str = "desc",
    offset: int = 0,
    limit: int = 20,
) -> str:
    """List papers in your library with optional filtering and sorting.

    Args:
        tags: Filter to papers with ALL of these tags
        categories: Filter to papers in ANY of these arXiv categories (e.g. "cs.CL")
        sort_by: Sort field — "added_at", "published_date", or "title"
        sort_order: "asc" or "desc"
        offset: Pagination offset
        limit: Page size (max 50)
    """
    limit = min(limit, 50)
    db = get_sqlite()
    papers, total = db.list_papers(
        tags=tags or [],
        categories=categories or [],
        sort_by=sort_by,
        sort_order=sort_order,
        offset=offset,
        limit=limit,
    )
    return format_paper_list(papers, total)


@mcp.tool()
def get_paper(paper_id: str) -> str:
    """Get full details for a specific paper, including metadata, tags, notes, and annotations.

    Args:
        paper_id: Library paper ID or arXiv ID
    """
    db = get_sqlite()
    paper = db.get_paper(paper_id)
    if paper is None:
        return f"Paper not found: `{paper_id}`"

    sections = [format_paper_summary(paper)]

    # Notes
    notes = db.get_notes(paper.id)
    if notes:
        sections.append(f"**Notes** ({len(notes)})")
        sections.append(format_notes(notes))

    # Annotations summary
    annotations = db.get_annotations(paper.id)
    if annotations:
        sections.append(f"**Annotations**: {len(annotations)} total")

    # PDF info
    if paper.local_pdf_path:
        sections.append(f"**PDF**: `{paper.local_pdf_path}`")

    return "\n\n".join(sections)
