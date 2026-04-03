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


@mcp.tool()
def tag_paper(
    paper_id: str,
    add_tags: list[str] | None = None,
    remove_tags: list[str] | None = None,
) -> str:
    """Add or remove tags on a paper.

    Args:
        paper_id: Library paper ID or arXiv ID
        add_tags: Tags to add
        remove_tags: Tags to remove
    """
    db = get_sqlite()
    paper = db.get_paper(paper_id)
    if paper is None:
        return f"Paper not found: `{paper_id}`"

    if add_tags:
        db.add_tags(paper.id, add_tags)
    if remove_tags:
        db.remove_tags(paper.id, remove_tags)

    updated_tags = db._get_tags(paper.id)
    tag_list = ", ".join(f"`{t.name}`" for t in updated_tags) or "none"
    return f"**{paper.title}**\nTags: {tag_list}"


@mcp.tool()
def add_note(paper_id: str, content: str) -> str:
    """Add a free-text note to a paper. Notes are indexed for semantic search.

    Args:
        paper_id: Library paper ID or arXiv ID
        content: Note text (Markdown supported)
    """
    db = get_sqlite()
    chroma = get_chroma()
    paper = db.get_paper(paper_id)
    if paper is None:
        return f"Paper not found: `{paper_id}`"

    note = db.add_note(paper.id, content)

    # Index for semantic search
    chroma.index_note(note.id, paper.id, content)

    total = len(db.get_notes(paper.id))
    return f"Note #{note.id} added to **{paper.title}** ({total} note{'s' if total != 1 else ''} total)"


@mcp.tool()
def remove_paper(paper_id: str, delete_pdf: bool = True) -> str:
    """Remove a paper from your library. Deletes metadata, notes, annotations, and embeddings.

    Args:
        paper_id: Library paper ID or arXiv ID
        delete_pdf: Also delete the local PDF file
    """
    import os

    db = get_sqlite()
    chroma = get_chroma()
    paper = db.get_paper(paper_id)
    if paper is None:
        return f"Paper not found: `{paper_id}`"

    title = paper.title
    pdf_path = paper.local_pdf_path

    # Remove from ChromaDB
    chroma.delete_paper(paper.id)

    # Remove from SQLite (cascades to tags, notes, annotations)
    db.delete_paper(paper.id)

    # Optionally delete the PDF file
    if delete_pdf and pdf_path and os.path.exists(pdf_path):
        os.remove(pdf_path)

    return f"Removed **{title}** from library."
