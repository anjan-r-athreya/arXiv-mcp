"""MCP tools for importing papers into the library."""

from __future__ import annotations

from arxiv_library_mcp.config import config
from arxiv_library_mcp.core.embedding import chunk_text
from arxiv_library_mcp.server import mcp, get_sqlite, get_chroma, get_arxiv
from arxiv_library_mcp.utils.formatting import format_paper_summary
from arxiv_library_mcp.utils.identifiers import parse_identifier


@mcp.tool()
def add_paper(
    identifier: str,
    download_pdf: bool = True,
    tags: list[str] | None = None,
) -> str:
    """Add a paper to your library by arXiv ID, DOI, or URL.

    Downloads metadata from arXiv, optionally downloads the PDF, extracts text
    for semantic search, and stores everything persistently.

    Args:
        identifier: arXiv ID (e.g. "2301.07041"), DOI, or URL
        download_pdf: Whether to download and store the PDF locally
        tags: Optional tags to apply immediately
    """
    tags = tags or []
    db = get_sqlite()
    chroma = get_chroma()
    arxiv_client = get_arxiv()

    # Parse the identifier
    parsed = parse_identifier(identifier)
    if parsed.type == "unknown":
        return f"Could not parse identifier: `{identifier}`. Provide an arXiv ID, DOI, or URL."

    # Check for duplicates
    if parsed.type == "arxiv":
        existing = db.get_paper_by_arxiv_id(parsed.value)
        if existing:
            return f"Paper already in library: **{existing.title}** (ID: `{existing.id}`)"
    elif parsed.type == "doi":
        existing = db.get_paper_by_doi(parsed.value)
        if existing:
            return f"Paper already in library: **{existing.title}** (ID: `{existing.id}`)"

    # Fetch metadata
    if parsed.type == "arxiv":
        try:
            meta = arxiv_client.fetch_by_id(parsed.value)
        except Exception as e:
            return f"arXiv API error: {e}"
        if meta is None:
            return f"Paper not found on arXiv: `{parsed.value}`"
    elif parsed.type == "doi":
        # For DOIs, try to find it on arXiv first (many DOIs map to arXiv papers)
        # For now, return an informative message — full DOI support comes in Phase 2
        return f"DOI import (`{parsed.value}`) is not yet supported. Use the arXiv ID instead."
    else:
        return f"Unsupported identifier type: `{parsed.type}`"

    # Download PDF if requested
    local_pdf_path: str | None = None
    full_text: str | None = None
    if download_pdf and config.download_pdfs and meta.arxiv_id:
        pdf_path = arxiv_client.download_pdf(meta.arxiv_id, config.pdf_dir)
        if pdf_path:
            local_pdf_path = str(pdf_path)
            # PDF text extraction comes in Phase 2 (core/pdf_processor.py)

    # Insert into SQLite
    paper_id = db.insert_paper(
        title=meta.title,
        arxiv_id=meta.arxiv_id,
        doi=meta.doi,
        abstract=meta.abstract,
        published_date=meta.published_date,
        updated_date=meta.updated_date,
        journal_ref=meta.journal_ref,
        pdf_url=meta.pdf_url,
        local_pdf_path=local_pdf_path,
        source="arxiv",
        primary_category=meta.primary_category,
        full_text=full_text,
        authors=meta.authors,
        categories=meta.categories,
    )

    # Apply tags
    if tags:
        db.add_tags(paper_id, tags)

    # Index in ChromaDB for semantic search
    chroma.index_paper(
        paper_id=paper_id,
        title=meta.title,
        abstract=meta.abstract,
        metadata={
            "arxiv_id": meta.arxiv_id or "",
            "primary_category": meta.primary_category or "",
        },
    )

    # Retrieve the full paper object for formatting
    paper = db.get_paper(paper_id)
    return format_paper_summary(paper)
