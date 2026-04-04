"""BibTeX generation from paper metadata."""

from __future__ import annotations

import re
import unicodedata

from arxiv_library_mcp.db.models import Paper


def _make_citation_key(paper: Paper) -> str:
    """Generate a citation key like 'Vaswani2017Attention'.

    Format: FirstAuthorLastName + Year + FirstTitleWord (capitalized).
    Falls back to arXiv ID or paper ID if metadata is sparse.
    """
    # Author component
    author = ""
    if paper.authors:
        # Take the last name of the first author (last word of name)
        name = paper.authors[0].name.strip()
        parts = name.split()
        author = parts[-1] if parts else "Unknown"
        # Remove non-ASCII
        author = unicodedata.normalize("NFKD", author).encode("ascii", "ignore").decode()
        author = re.sub(r"[^a-zA-Z]", "", author)

    # Year component
    year = ""
    if paper.published_date:
        m = re.search(r"(\d{4})", paper.published_date)
        if m:
            year = m.group(1)

    # Title word component
    title_word = ""
    if paper.title:
        # Take the first meaningful word (skip articles)
        skip = {"a", "an", "the", "on", "of", "for", "in", "to", "and", "with"}
        words = re.findall(r"[a-zA-Z]+", paper.title)
        for w in words:
            if w.lower() not in skip:
                title_word = w.capitalize()
                break

    key = f"{author}{year}{title_word}"
    if not key:
        key = paper.arxiv_id or paper.id
        key = re.sub(r"[^a-zA-Z0-9]", "", key)

    return key


def _escape_bibtex(value: str) -> str:
    """Escape special BibTeX characters."""
    # Wrap in braces to preserve capitalization and handle special chars
    return value.replace("{", "\\{").replace("}", "\\}")


def paper_to_bibtex(paper: Paper) -> str:
    """Convert a single Paper to a BibTeX entry string."""
    key = _make_citation_key(paper)

    # Determine entry type
    if paper.journal_ref:
        entry_type = "article"
    elif paper.arxiv_id:
        entry_type = "article"
    else:
        entry_type = "misc"

    fields: list[str] = []

    # Title
    if paper.title:
        fields.append(f"  title = {{{_escape_bibtex(paper.title)}}}")

    # Authors in BibTeX format: "LastName, FirstName and LastName, FirstName"
    if paper.authors:
        author_strs = []
        for a in paper.authors:
            name = a.name.strip()
            parts = name.split()
            if len(parts) >= 2:
                # "FirstName LastName" -> "LastName, FirstName"
                author_strs.append(f"{parts[-1]}, {' '.join(parts[:-1])}")
            else:
                author_strs.append(name)
        fields.append(f"  author = {{{' and '.join(author_strs)}}}")

    # Year
    if paper.published_date:
        m = re.search(r"(\d{4})", paper.published_date)
        if m:
            fields.append(f"  year = {{{m.group(1)}}}")

    # Abstract
    if paper.abstract:
        fields.append(f"  abstract = {{{_escape_bibtex(paper.abstract)}}}")

    # Journal / eprint
    if paper.journal_ref:
        fields.append(f"  journal = {{{_escape_bibtex(paper.journal_ref)}}}")

    if paper.doi:
        fields.append(f"  doi = {{{paper.doi}}}")

    if paper.arxiv_id:
        fields.append(f"  eprint = {{{paper.arxiv_id}}}")
        fields.append(f"  archiveprefix = {{arXiv}}")
        if paper.primary_category:
            fields.append(f"  primaryclass = {{{paper.primary_category}}}")

    if paper.pdf_url:
        fields.append(f"  url = {{{paper.pdf_url}}}")

    fields_str = ",\n".join(fields)
    return f"@{entry_type}{{{key},\n{fields_str}\n}}"


def papers_to_bibtex(papers: list[Paper]) -> str:
    """Convert a list of Papers to a BibTeX string with all entries."""
    if not papers:
        return "% No papers to export."
    entries = [paper_to_bibtex(p) for p in papers]
    return "\n\n".join(entries) + "\n"
