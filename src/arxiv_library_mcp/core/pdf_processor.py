"""PDF text and annotation extraction using PyMuPDF."""

from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF

from arxiv_library_mcp.db.models import Annotation


class PDFProcessor:
    """Extracts text and annotations from PDF files."""

    @staticmethod
    def extract_text(pdf_path: Path | str) -> str:
        """Extract full text from a PDF, with page break markers.

        Returns concatenated text from all pages.
        """
        doc = fitz.open(str(pdf_path))
        pages = []
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text("text")
            if text.strip():
                pages.append(text.strip())
        doc.close()
        return "\n\n--- Page Break ---\n\n".join(pages)

    @staticmethod
    def extract_annotations(pdf_path: Path | str) -> list[Annotation]:
        """Extract highlights, comments, and other annotations from a PDF.

        Supports: highlight, underline, strikeout, squiggly, freetext, text (sticky notes).
        """
        # Map PyMuPDF annotation type codes to readable names
        type_map = {
            fitz.PDF_ANNOT_HIGHLIGHT: "highlight",
            fitz.PDF_ANNOT_UNDERLINE: "underline",
            fitz.PDF_ANNOT_STRIKE_OUT: "strikeout",
            fitz.PDF_ANNOT_SQUIGGLY: "squiggly",
            fitz.PDF_ANNOT_FREE_TEXT: "freetext",
            fitz.PDF_ANNOT_TEXT: "comment",  # sticky note
        }

        doc = fitz.open(str(pdf_path))
        annotations = []

        for page_num in range(len(doc)):
            page = doc[page_num]
            for annot in page.annots() or []:
                annot_type = type_map.get(annot.type[0])
                if annot_type is None:
                    continue

                # Get the comment/content text
                content = annot.info.get("content", "").strip() or None

                # For highlights/underlines, get the underlying text
                quoted_text = None
                if annot_type in ("highlight", "underline", "strikeout", "squiggly"):
                    try:
                        # Get text within the annotation's rectangle(s)
                        if annot.vertices:
                            # Vertices define the quad points of the highlight
                            quads = annot.vertices
                            # Group vertices into quads (4 points each)
                            texts = []
                            for i in range(0, len(quads), 4):
                                if i + 3 < len(quads):
                                    quad = fitz.Quad(quads[i], quads[i+1], quads[i+2], quads[i+3])
                                    text = page.get_textbox(quad.rect)
                                    if text.strip():
                                        texts.append(text.strip())
                            quoted_text = " ".join(texts) if texts else None
                        if not quoted_text:
                            # Fallback: use the annotation rect
                            quoted_text = page.get_textbox(annot.rect).strip() or None
                    except Exception:
                        quoted_text = None

                # For freetext, the content is the displayed text
                if annot_type == "freetext" and not content:
                    content = page.get_textbox(annot.rect).strip() or None

                # Extract color
                color = None
                try:
                    colors = annot.colors
                    if colors and colors.get("stroke"):
                        rgb = colors["stroke"]
                        color = "#{:02x}{:02x}{:02x}".format(
                            int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255)
                        )
                except Exception:
                    pass

                # Build rect JSON
                rect_json = None
                try:
                    r = annot.rect
                    rect_json = f'{{"x0":{r.x0:.1f},"y0":{r.y0:.1f},"x1":{r.x1:.1f},"y1":{r.y1:.1f}}}'
                except Exception:
                    pass

                annotations.append(Annotation(
                    page=page_num + 1,  # 1-indexed
                    type=annot_type,
                    content=content,
                    quoted_text=quoted_text,
                    color=color,
                    rect_json=rect_json,
                ))

        doc.close()
        return annotations

    @staticmethod
    def extract_identifier(pdf_path: Path | str) -> str | None:
        """Try to find an arXiv ID or DOI in the first page of a PDF.

        Scans text on page 1 for patterns like 'arXiv:2301.07041' or '10.1234/...'.
        """
        doc = fitz.open(str(pdf_path))
        if len(doc) == 0:
            doc.close()
            return None

        text = doc[0].get_text("text")
        doc.close()

        # Look for arXiv ID
        m = re.search(r"arXiv:(\d{4}\.\d{4,5})", text)
        if m:
            return m.group(1)

        # Look for new-style arXiv ID without prefix
        m = re.search(r"\b(\d{4}\.\d{4,5})(?:v\d+)?\b", text)
        if m:
            return m.group(1)

        # Look for DOI
        m = re.search(r"(10\.\d{4,9}/[^\s]+)", text)
        if m:
            return m.group(1)

        return None

    @staticmethod
    def get_page_count(pdf_path: Path | str) -> int:
        """Get the number of pages in a PDF."""
        doc = fitz.open(str(pdf_path))
        count = len(doc)
        doc.close()
        return count
