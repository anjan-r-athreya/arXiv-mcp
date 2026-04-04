"""MCP tools for searching the paper library."""

from __future__ import annotations

from arxiv_library_mcp.db.models import Paper, SearchResult
from arxiv_library_mcp.server import mcp, get_sqlite, get_chroma
from arxiv_library_mcp.utils.formatting import format_search_results


@mcp.tool()
def search_library(
    query: str,
    scope: str = "all",
    tags: list[str] | None = None,
    categories: list[str] | None = None,
    after: str = "",
    before: str = "",
    limit: int = 10,
) -> str:
    """Search your paper library using natural language semantic similarity.

    Args:
        query: Natural language search query
        scope: What to search — "titles" (title+abstract), "fulltext", "notes", or "all"
        tags: Filter to papers with ALL of these tags
        categories: Filter to papers in ANY of these arXiv categories
        after: Only papers added after this date (YYYY-MM-DD)
        before: Only papers added before this date (YYYY-MM-DD)
        limit: Max results to return (default 10)
    """
    db = get_sqlite()
    chroma = get_chroma()
    limit = min(limit, 50)

    valid_scopes = {"titles", "fulltext", "notes", "all"}
    if scope not in valid_scopes:
        scope = "all"

    # Build a set of allowed paper IDs from SQLite filters (tags, categories, dates)
    allowed_ids = _get_filtered_paper_ids(db, tags, categories, after, before)

    results: list[SearchResult] = []
    seen_paper_ids: set[str] = set()

    # Search title+abstract embeddings
    if scope in ("titles", "all"):
        hits = chroma.search_papers(query, n_results=limit * 2)
        for hit in hits:
            pid = hit["paper_id"]
            if allowed_ids is not None and pid not in allowed_ids:
                continue
            if pid in seen_paper_ids:
                continue
            paper = db.get_paper(pid)
            if paper is None:
                continue
            seen_paper_ids.add(pid)
            results.append(SearchResult(paper=paper, score=hit["score"], source="titles"))

    # Search fulltext chunks
    if scope in ("fulltext", "all"):
        hits = chroma.search_fulltext(query, n_results=limit * 2)
        for hit in hits:
            pid = hit["metadata"].get("paper_id", "")
            if allowed_ids is not None and pid not in allowed_ids:
                continue
            if pid in seen_paper_ids:
                continue
            paper = db.get_paper(pid)
            if paper is None:
                continue
            seen_paper_ids.add(pid)
            results.append(SearchResult(
                paper=paper, score=hit["score"], source="fulltext",
                matched_chunk=hit.get("document", ""),
            ))

    # Search notes + annotations
    if scope in ("notes", "all"):
        hits = chroma.search_notes(query, n_results=limit * 2)
        for hit in hits:
            pid = hit["metadata"].get("paper_id", "")
            if allowed_ids is not None and pid not in allowed_ids:
                continue
            if pid in seen_paper_ids:
                continue
            paper = db.get_paper(pid)
            if paper is None:
                continue
            seen_paper_ids.add(pid)
            results.append(SearchResult(
                paper=paper, score=hit["score"], source="notes",
                matched_chunk=hit.get("document", ""),
            ))

    # Sort by score descending, take top N
    results.sort(key=lambda r: r.score, reverse=True)
    results = results[:limit]

    return format_search_results(results)


def _get_filtered_paper_ids(
    db, tags: list[str] | None, categories: list[str] | None,
    after: str, before: str,
) -> set[str] | None:
    """Get the set of paper IDs matching the filters, or None if no filters active."""
    has_filters = bool(tags or categories or after or before)
    if not has_filters:
        return None

    # Use list_papers with a high limit to get all matching IDs
    papers, _ = db.list_papers(
        tags=tags or [],
        categories=categories or [],
        sort_by="added_at",
        sort_order="desc",
        offset=0,
        limit=10000,
    )

    ids = {p.id for p in papers}

    # Apply date filters on top
    if after:
        ids = {p.id for p in papers if p.added_at and p.added_at >= after}
    if before:
        before_ids = {p.id for p in papers if p.added_at and p.added_at <= before}
        ids = ids & before_ids if after else before_ids

    return ids
