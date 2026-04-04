"""MCP tools for exporting library data."""

from __future__ import annotations

import json

from arxiv_library_mcp.core.bibtex_builder import papers_to_bibtex
from arxiv_library_mcp.server import mcp, get_sqlite
from arxiv_library_mcp.utils.formatting import format_paper_summary, format_notes


@mcp.tool()
def export_library(
    format: str = "bibtex",
    tags: list[str] | None = None,
    categories: list[str] | None = None,
    paper_ids: list[str] | None = None,
    include_notes: bool = False,
    include_abstracts: bool = True,
) -> str:
    """Export papers from your library in various formats.

    Args:
        format: Output format — "bibtex", "markdown", or "json"
        tags: Filter by tags (AND logic)
        categories: Filter by categories (OR logic)
        paper_ids: Export specific papers by ID (overrides tag/category filters)
        include_notes: Include user notes in export (markdown/json only)
        include_abstracts: Include abstracts (default True)
    """
    db = get_sqlite()
    valid_formats = {"bibtex", "markdown", "json"}
    if format not in valid_formats:
        return f"Unknown format: `{format}`. Use one of: {', '.join(valid_formats)}"

    # Get papers
    if paper_ids:
        papers = []
        for pid in paper_ids:
            p = db.get_paper(pid)
            if p:
                papers.append(p)
        if not papers:
            return "No papers found for the given IDs."
    else:
        papers, _ = db.list_papers(
            tags=tags or [],
            categories=categories or [],
            sort_by="added_at",
            sort_order="desc",
            offset=0,
            limit=10000,
        )
        if not papers:
            return "No papers in library matching the filters."

    if format == "bibtex":
        return papers_to_bibtex(papers)

    elif format == "markdown":
        return _export_markdown(db, papers, include_notes, include_abstracts)

    elif format == "json":
        return _export_json(db, papers, include_notes, include_abstracts)

    return "Export failed."


def _export_markdown(db, papers, include_notes: bool, include_abstracts: bool) -> str:
    """Export as a Markdown reading list."""
    lines = [f"# Reading List ({len(papers)} papers)", ""]

    for i, paper in enumerate(papers, 1):
        authors = ", ".join(a.name for a in paper.authors[:5])
        if len(paper.authors) > 5:
            authors += f" (+{len(paper.authors) - 5} more)"

        lines.append(f"## {i}. {paper.title}")
        lines.append("")
        if authors:
            lines.append(f"**Authors**: {authors}")
        if paper.arxiv_id:
            lines.append(f"**arXiv**: [{paper.arxiv_id}](https://arxiv.org/abs/{paper.arxiv_id})")
        if paper.doi:
            lines.append(f"**DOI**: [{paper.doi}](https://doi.org/{paper.doi})")
        if paper.primary_category:
            lines.append(f"**Category**: {paper.primary_category}")
        if paper.published_date:
            lines.append(f"**Published**: {paper.published_date[:10]}")

        tags = ", ".join(f"`{t.name}`" for t in paper.tags)
        if tags:
            lines.append(f"**Tags**: {tags}")

        if include_abstracts and paper.abstract:
            lines.append("")
            lines.append(f"> {paper.abstract[:500]}")

        if include_notes:
            notes = db.get_notes(paper.id)
            if notes:
                lines.append("")
                lines.append("**Notes:**")
                for n in notes:
                    lines.append(f"- {n.content}")

        lines.append("")

    return "\n".join(lines)


def _export_json(db, papers, include_notes: bool, include_abstracts: bool) -> str:
    """Export as JSON."""
    entries = []
    for paper in papers:
        entry = {
            "id": paper.id,
            "title": paper.title,
            "authors": [a.name for a in paper.authors],
            "arxiv_id": paper.arxiv_id,
            "doi": paper.doi,
            "primary_category": paper.primary_category,
            "published_date": paper.published_date,
            "tags": [t.name for t in paper.tags],
        }
        if include_abstracts and paper.abstract:
            entry["abstract"] = paper.abstract
        if include_notes:
            notes = db.get_notes(paper.id)
            entry["notes"] = [n.content for n in notes]
        entries.append(entry)

    return json.dumps(entries, indent=2, ensure_ascii=False)
