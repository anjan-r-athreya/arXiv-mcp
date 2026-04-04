"""MCP tools for extracting and viewing PDF annotations."""

from __future__ import annotations

from arxiv_library_mcp.core.pdf_processor import PDFProcessor
from arxiv_library_mcp.server import mcp, get_sqlite, get_chroma
from arxiv_library_mcp.utils.formatting import format_annotations


@mcp.tool()
def extract_annotations(
    paper_id: str,
    types: list[str] | None = None,
) -> str:
    """Extract highlights, comments, and other annotations from a paper's PDF.

    Reads the local PDF with PyMuPDF, extracts all annotations, stores them in
    the library, and indexes them for semantic search.

    Args:
        paper_id: Library paper ID or arXiv ID
        types: Filter by annotation type: "highlight", "comment", "underline",
               "strikeout", "freetext". Empty = all types.
    """
    db = get_sqlite()
    chroma = get_chroma()
    paper = db.get_paper(paper_id)
    if paper is None:
        return f"Paper not found: `{paper_id}`"

    if not paper.local_pdf_path:
        return f"No local PDF for **{paper.title}**. Re-add with `download_pdf=True` or use `import_pdf`."

    proc = PDFProcessor()
    try:
        annotations = proc.extract_annotations(paper.local_pdf_path)
    except Exception as e:
        return f"Error reading PDF: {e}"

    if not annotations:
        return f"No annotations found in **{paper.title}**."

    # Filter by type if requested
    if types:
        annotations = [a for a in annotations if a.type in types]
        if not annotations:
            type_list = ", ".join(f"`{t}`" for t in types)
            return f"No annotations of type {type_list} found in **{paper.title}**."

    # Clear old annotations for this paper and insert fresh
    # (re-extraction replaces previous results)
    old = db.get_annotations(paper.id)
    if old:
        # Delete old annotations by re-inserting (SQLite has no bulk delete by paper+type)
        db._conn.execute("DELETE FROM annotations WHERE paper_id = ?", (paper.id,))
        db._conn.commit()

    db.insert_annotations(paper.id, annotations)

    # Index annotation text in ChromaDB for semantic search
    for a in annotations:
        text_parts = []
        if a.quoted_text:
            text_parts.append(a.quoted_text)
        if a.content:
            text_parts.append(a.content)
        if text_parts:
            combined = " — ".join(text_parts)
            # Use a stable ID based on paper + page + index
            annot_db = db.get_annotations(paper.id)
            # Find the matching annotation to get its DB id
            for db_annot in annot_db:
                if (db_annot.page == a.page and db_annot.type == a.type
                        and db_annot.quoted_text == a.quoted_text):
                    chroma.index_annotation(db_annot.id, paper.id, combined)
                    break

    # Format output — apply type filter for display
    display = annotations if not types else [a for a in annotations if a.type in types]
    header = f"**{paper.title}** — {len(display)} annotation{'s' if len(display) != 1 else ''}\n\n"
    return header + format_annotations(display)
