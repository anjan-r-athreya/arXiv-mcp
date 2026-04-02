"""Data models for the ArXiv Library."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Author:
    id: int | None = None
    name: str = ""


@dataclass
class Tag:
    id: int | None = None
    name: str = ""


@dataclass
class Paper:
    id: str = ""
    arxiv_id: str | None = None
    doi: str | None = None
    title: str = ""
    abstract: str | None = None
    published_date: str | None = None
    updated_date: str | None = None
    journal_ref: str | None = None
    pdf_url: str | None = None
    local_pdf_path: str | None = None
    source: str = "arxiv"
    primary_category: str | None = None
    full_text: str | None = None
    added_at: str = ""
    updated_at: str = ""
    authors: list[Author] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)


@dataclass
class Note:
    id: int | None = None
    paper_id: str = ""
    content: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass
class Annotation:
    id: int | None = None
    paper_id: str = ""
    page: int = 0
    type: str = ""  # highlight, comment, underline, strikeout, freetext
    content: str | None = None
    quoted_text: str | None = None
    color: str | None = None
    rect_json: str | None = None
    created_at: str = ""


@dataclass
class PaperVersion:
    id: int | None = None
    paper_id: str = ""
    version_type: str = ""  # arxiv_version, published_doi, duplicate
    related_paper_id: str | None = None
    external_doi: str | None = None
    external_url: str | None = None
    detected_at: str = ""
    confidence: float = 1.0


@dataclass
class Cluster:
    id: int | None = None
    name: str | None = None
    method: str = ""
    created_at: str = ""
    paper_ids: list[str] = field(default_factory=list)


@dataclass
class SearchResult:
    paper: Paper
    score: float = 0.0
    source: str = ""  # which collection matched
    matched_chunk: str | None = None  # for fulltext matches


@dataclass
class DuplicatePair:
    paper_a_id: str = ""
    paper_b_id: str = ""
    confidence: float = 0.0
    reason: str = ""


@dataclass
class DOIResult:
    doi: str = ""
    title: str | None = None
    journal: str | None = None
    url: str | None = None
    confidence: float = 1.0


@dataclass
class PaperMetadata:
    """Metadata fetched from arXiv or other sources before insertion."""
    arxiv_id: str | None = None
    doi: str | None = None
    title: str = ""
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    published_date: str | None = None
    updated_date: str | None = None
    journal_ref: str | None = None
    pdf_url: str | None = None
    primary_category: str | None = None
    categories: list[str] = field(default_factory=list)
