"""Markdown output formatting helpers for MCP tool responses."""

from __future__ import annotations

from arxiv_library_mcp.db.models import Paper, Note, Annotation, SearchResult


def format_paper_summary(paper: Paper) -> str:
    """One-paper summary block for tool responses."""
    authors = ", ".join(a.name for a in paper.authors[:5])
    if len(paper.authors) > 5:
        authors += f" (+{len(paper.authors) - 5} more)"

    tags = ", ".join(f"`{t.name}`" for t in paper.tags) if paper.tags else "none"

    lines = [
        f"### {paper.title}",
        "",
        f"**Authors**: {authors}" if authors else "",
        f"**arXiv**: {paper.arxiv_id}" if paper.arxiv_id else "",
        f"**DOI**: {paper.doi}" if paper.doi else "",
        f"**Category**: {paper.primary_category}" if paper.primary_category else "",
        f"**Published**: {paper.published_date}" if paper.published_date else "",
        f"**Tags**: {tags}",
        f"**Library ID**: `{paper.id}`",
    ]

    if paper.abstract:
        abstract = paper.abstract[:300]
        if len(paper.abstract) > 300:
            abstract += "..."
        lines += ["", f"> {abstract}"]

    return "\n".join(line for line in lines if line is not None)


def format_paper_row(paper: Paper) -> str:
    """Single-line table row for list views."""
    authors_short = paper.authors[0].name if paper.authors else "Unknown"
    if len(paper.authors) > 1:
        authors_short += " et al."
    tags = ", ".join(t.name for t in paper.tags) if paper.tags else ""
    date = paper.published_date[:10] if paper.published_date else ""
    return f"| `{paper.id[:8]}` | {paper.title[:60]} | {authors_short} | {date} | {tags} |"


def format_paper_list(papers: list[Paper], total: int | None = None) -> str:
    """Formatted table of papers."""
    if not papers:
        return "No papers found."

    header = "| ID | Title | Authors | Date | Tags |\n|---|---|---|---|---|"
    rows = [format_paper_row(p) for p in papers]
    result = header + "\n" + "\n".join(rows)

    if total is not None:
        result += f"\n\n*Showing {len(papers)} of {total} papers.*"
    return result


def format_search_results(results: list[SearchResult]) -> str:
    """Ranked search results with scores."""
    if not results:
        return "No matching papers found."

    lines = []
    for i, r in enumerate(results, 1):
        authors = ", ".join(a.name for a in r.paper.authors[:3])
        if len(r.paper.authors) > 3:
            authors += " et al."
        score_pct = f"{r.score * 100:.0f}%"
        lines.append(f"**{i}. {r.paper.title}** (relevance: {score_pct})")
        lines.append(f"   {authors} | {r.paper.arxiv_id or r.paper.doi or ''}")
        if r.matched_chunk:
            chunk = r.matched_chunk[:150]
            if len(r.matched_chunk) > 150:
                chunk += "..."
            lines.append(f"   > {chunk}")
        lines.append("")
    return "\n".join(lines)


def format_notes(notes: list[Note]) -> str:
    """Format a list of notes for display."""
    if not notes:
        return "No notes."
    lines = []
    for n in notes:
        lines.append(f"**Note #{n.id}** ({n.created_at[:10] if n.created_at else ''})")
        lines.append(n.content)
        lines.append("")
    return "\n".join(lines)


def format_annotations(annotations: list[Annotation]) -> str:
    """Format annotations grouped by page."""
    if not annotations:
        return "No annotations found."

    by_page: dict[int, list[Annotation]] = {}
    for a in annotations:
        by_page.setdefault(a.page, []).append(a)

    lines = []
    for page in sorted(by_page):
        lines.append(f"**Page {page}**")
        for a in by_page[page]:
            prefix = f"[{a.type}]"
            if a.quoted_text:
                lines.append(f"- {prefix} \"{a.quoted_text[:100]}\"")
            if a.content:
                lines.append(f"  Comment: {a.content}")
        lines.append("")
    return "\n".join(lines)
