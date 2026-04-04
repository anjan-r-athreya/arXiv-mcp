"""MCP tools for importing papers into the library."""

from __future__ import annotations

import shutil
from pathlib import Path

from arxiv_library_mcp.config import config
from arxiv_library_mcp.core.embedding import chunk_text
from arxiv_library_mcp.core.pdf_processor import PDFProcessor
from arxiv_library_mcp.server import mcp, get_sqlite, get_chroma, get_arxiv
from arxiv_library_mcp.utils.formatting import format_paper_summary
from arxiv_library_mcp.utils.identifiers import parse_identifier


def _extract_and_index_pdf(paper_id: str, pdf_path: str, db, chroma,
                           arxiv_id: str | None = None, title: str | None = None) -> str | None:
    """Extract text from a PDF, store in SQLite, and index fulltext chunks in ChromaDB.

    Returns the extracted full text, or None on failure.
    """
    proc = PDFProcessor()
    try:
        full_text = proc.extract_text(pdf_path)
    except Exception:
        return None

    if not full_text or not full_text.strip():
        return None

    # Store full text in SQLite
    db.update_paper(paper_id, full_text=full_text)

    # Chunk and index in ChromaDB for fulltext search
    chunks = chunk_text(full_text)
    if chunks:
        chroma.index_fulltext(paper_id, chunks, arxiv_id=arxiv_id, title=title)

    return full_text


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
        return f"DOI import (`{parsed.value}`) is not yet supported. Use the arXiv ID instead."
    else:
        return f"Unsupported identifier type: `{parsed.type}`"

    # Download PDF if requested
    local_pdf_path: str | None = None
    if download_pdf and config.download_pdfs and meta.arxiv_id:
        try:
            pdf_path = arxiv_client.download_pdf(meta.arxiv_id, config.pdf_dir)
            if pdf_path:
                local_pdf_path = str(pdf_path)
        except Exception:
            pass  # Non-fatal: paper is still added without PDF

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
        authors=meta.authors,
        categories=meta.categories,
    )

    # Apply tags
    if tags:
        db.add_tags(paper_id, tags)

    # Index title+abstract in ChromaDB
    chroma.index_paper(
        paper_id=paper_id,
        title=meta.title,
        abstract=meta.abstract,
        metadata={
            "arxiv_id": meta.arxiv_id or "",
            "primary_category": meta.primary_category or "",
        },
    )

    # Extract and index PDF full text
    if local_pdf_path:
        _extract_and_index_pdf(paper_id, local_pdf_path, db, chroma,
                               arxiv_id=meta.arxiv_id, title=meta.title)

    paper = db.get_paper(paper_id)
    return format_paper_summary(paper)


@mcp.tool()
def import_pdf(
    file_path: str,
    tags: list[str] | None = None,
) -> str:
    """Import a local PDF file into your library.

    Extracts text, attempts to identify the paper via arXiv ID or DOI found
    in the PDF content, then fetches full metadata. If identification fails,
    creates an entry from the PDF filename and extracted text.

    Args:
        file_path: Absolute path to the PDF file
        tags: Optional tags to apply
    """
    tags = tags or []
    db = get_sqlite()
    chroma = get_chroma()
    arxiv_client = get_arxiv()
    proc = PDFProcessor()

    source_path = Path(file_path)
    if not source_path.exists():
        return f"File not found: `{file_path}`"
    if not source_path.suffix.lower() == ".pdf":
        return f"Not a PDF file: `{file_path}`"

    # Try to identify the paper from PDF content
    identifier = proc.extract_identifier(source_path)
    parsed = parse_identifier(identifier) if identifier else None

    meta = None
    if parsed and parsed.type == "arxiv":
        # Check for duplicates by arXiv ID
        existing = db.get_paper_by_arxiv_id(parsed.value)
        if existing:
            return f"Paper already in library: **{existing.title}** (ID: `{existing.id}`)"
        try:
            meta = arxiv_client.fetch_by_id(parsed.value)
        except Exception:
            meta = None

    # Determine destination path and check for path-based duplicates
    config.ensure_dirs()
    if meta and meta.arxiv_id:
        safe_id = meta.arxiv_id.replace("/", "_")
        dest_name = f"{safe_id}.pdf"
    else:
        dest_name = source_path.name
    dest_path = config.pdf_dir / dest_name

    if dest_path != source_path:
        shutil.copy2(str(source_path), str(dest_path))

    if meta:
        # We identified the paper — use full metadata
        paper_id = db.insert_paper(
            title=meta.title,
            arxiv_id=meta.arxiv_id,
            doi=meta.doi,
            abstract=meta.abstract,
            published_date=meta.published_date,
            updated_date=meta.updated_date,
            journal_ref=meta.journal_ref,
            pdf_url=meta.pdf_url,
            local_pdf_path=str(dest_path),
            source="pdf",
            primary_category=meta.primary_category,
            authors=meta.authors,
            categories=meta.categories,
        )
        chroma.index_paper(
            paper_id=paper_id,
            title=meta.title,
            abstract=meta.abstract,
            metadata={
                "arxiv_id": meta.arxiv_id or "",
                "primary_category": meta.primary_category or "",
            },
        )
    else:
        # Unknown paper — create entry from filename
        title = source_path.stem.replace("_", " ").replace("-", " ").title()
        paper_id = db.insert_paper(
            title=title,
            local_pdf_path=str(dest_path),
            source="pdf",
        )
        # We'll index with extracted text below
        chroma.index_paper(paper_id=paper_id, title=title)

    if tags:
        db.add_tags(paper_id, tags)

    # Extract and index full text
    _extract_and_index_pdf(
        paper_id, str(dest_path), db, chroma,
        arxiv_id=meta.arxiv_id if meta else None,
        title=meta.title if meta else None,
    )

    paper = db.get_paper(paper_id)
    status = "identified" if meta else "unidentified (metadata from filename)"
    return format_paper_summary(paper) + f"\n\n*Import status: {status}*"


@mcp.tool()
def bulk_import(
    identifiers: list[str],
    download_pdfs: bool = True,
    tags: list[str] | None = None,
) -> str:
    """Import multiple papers at once from a list of arXiv IDs, DOIs, or URLs.

    Processes them sequentially with rate limiting. Reports successes and failures.

    Args:
        identifiers: List of arXiv IDs, DOIs, or URLs
        download_pdfs: Whether to download PDFs
        tags: Tags to apply to all imported papers
    """
    if not identifiers:
        return "No identifiers provided."

    results: list[str] = []
    success = 0
    failed = 0

    for ident in identifiers:
        result = add_paper(ident, download_pdf=download_pdfs, tags=tags)
        # Check if it was a success (contains "Library ID")
        if "Library ID" in result or "already in library" in result:
            status = "ok" if "Library ID" in result else "duplicate"
            # Extract title from the result
            title = result.split("###")[1].split("\n")[0].strip() if "###" in result else ident
            if "already in library" in result:
                title = result.split("**")[1] if "**" in result else ident
            results.append(f"| {ident} | {status} | {title[:50]} |")
            success += 1
        else:
            results.append(f"| {ident} | FAILED | {result[:50]} |")
            failed += 1

    header = "| Identifier | Status | Details |\n|---|---|---|"
    table = header + "\n" + "\n".join(results)
    summary = f"\n\n**{success} succeeded, {failed} failed** out of {len(identifiers)} total."
    return table + summary
