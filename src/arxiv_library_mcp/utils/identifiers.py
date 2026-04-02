"""Parse and normalize arXiv IDs, DOIs, and URLs."""

from __future__ import annotations

import re
from dataclasses import dataclass

# arXiv ID patterns:
#   New format: YYMM.NNNNN (with optional vN version suffix)
#   Old format: archive/YYMMNNN (e.g. hep-th/9901001)
_ARXIV_NEW = re.compile(r"^(\d{4}\.\d{4,5})(v\d+)?$")
_ARXIV_OLD = re.compile(r"^([a-z-]+/\d{7})(v\d+)?$")

# DOI pattern: 10.NNNN/anything
_DOI = re.compile(r"^10\.\d{4,9}/\S+$")

# URL patterns for extracting identifiers
_ARXIV_ABS_URL = re.compile(r"arxiv\.org/abs/([a-z-]*/?\d+\.?\d*)(v\d+)?", re.IGNORECASE)
_ARXIV_PDF_URL = re.compile(r"arxiv\.org/pdf/([a-z-]*/?\d+\.?\d*)(v\d+)?", re.IGNORECASE)
_DOI_URL = re.compile(r"(?:dx\.)?doi\.org/(10\.\d{4,9}/\S+)", re.IGNORECASE)


@dataclass
class ParsedIdentifier:
    """Result of parsing a user-provided identifier string."""
    type: str  # "arxiv", "doi", "url", "unknown"
    value: str  # normalized identifier (arXiv ID without version, or DOI)
    version: str | None = None  # arXiv version suffix if present (e.g. "v2")
    original: str = ""  # the raw input


def parse_identifier(raw: str) -> ParsedIdentifier:
    """Parse a string into a typed identifier.

    Accepts:
        - arXiv IDs: "2301.07041", "2301.07041v2", "hep-th/9901001"
        - DOIs: "10.1234/foo.bar"
        - arXiv URLs: "https://arxiv.org/abs/2301.07041"
        - DOI URLs: "https://doi.org/10.1234/foo.bar"
    """
    s = raw.strip()

    # Try direct arXiv ID (new format)
    m = _ARXIV_NEW.match(s)
    if m:
        return ParsedIdentifier(
            type="arxiv", value=m.group(1), version=m.group(2), original=s
        )

    # Try direct arXiv ID (old format)
    m = _ARXIV_OLD.match(s)
    if m:
        return ParsedIdentifier(
            type="arxiv", value=m.group(1), version=m.group(2), original=s
        )

    # Try direct DOI
    m = _DOI.match(s)
    if m:
        return ParsedIdentifier(type="doi", value=s, original=s)

    # Try arXiv URL (abs or pdf)
    for pattern in (_ARXIV_ABS_URL, _ARXIV_PDF_URL):
        m = pattern.search(s)
        if m:
            return ParsedIdentifier(
                type="arxiv", value=m.group(1), version=m.group(2), original=s
            )

    # Try DOI URL
    m = _DOI_URL.search(s)
    if m:
        return ParsedIdentifier(type="doi", value=m.group(1), original=s)

    return ParsedIdentifier(type="unknown", value=s, original=s)


def normalize_arxiv_id(arxiv_id: str) -> str:
    """Strip version suffix from an arXiv ID. '2301.07041v2' -> '2301.07041'."""
    m = _ARXIV_NEW.match(arxiv_id.strip())
    if m:
        return m.group(1)
    m = _ARXIV_OLD.match(arxiv_id.strip())
    if m:
        return m.group(1)
    return arxiv_id.strip()
