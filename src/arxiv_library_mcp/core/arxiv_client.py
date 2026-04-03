"""ArXiv API client wrapper with rate limiting."""

from __future__ import annotations

import re
from pathlib import Path

import arxiv

from arxiv_library_mcp.db.models import PaperMetadata
from arxiv_library_mcp.utils.identifiers import normalize_arxiv_id
from arxiv_library_mcp.utils.rate_limiter import RateLimiter


class ArxivClient:
    """Fetches paper metadata and PDFs from arXiv with rate limiting."""

    def __init__(self, pdf_dir: Path | None = None) -> None:
        self._client = arxiv.Client(
            page_size=10,
            delay_seconds=3.0,
            num_retries=3,
        )
        self._rate_limiter = RateLimiter(min_interval=3.0)
        self._pdf_dir = pdf_dir

    def fetch_by_id(self, arxiv_id: str) -> PaperMetadata | None:
        """Fetch metadata for a single arXiv paper. Returns None if not found."""
        arxiv_id = normalize_arxiv_id(arxiv_id)
        self._rate_limiter.wait()
        search = arxiv.Search(id_list=[arxiv_id])
        try:
            result = next(self._client.results(search))
        except StopIteration:
            return None
        return self._result_to_metadata(result)

    def fetch_by_ids(self, arxiv_ids: list[str]) -> list[PaperMetadata]:
        """Fetch metadata for multiple arXiv papers."""
        normalized = [normalize_arxiv_id(aid) for aid in arxiv_ids]
        self._rate_limiter.wait()
        search = arxiv.Search(id_list=normalized)
        results = []
        for result in self._client.results(search):
            results.append(self._result_to_metadata(result))
        return results

    def download_pdf(self, arxiv_id: str, dest_dir: Path | None = None) -> Path | None:
        """Download the PDF for an arXiv paper. Returns the file path or None on failure."""
        arxiv_id = normalize_arxiv_id(arxiv_id)
        dest = dest_dir or self._pdf_dir
        if dest is None:
            return None
        dest.mkdir(parents=True, exist_ok=True)

        self._rate_limiter.wait()
        search = arxiv.Search(id_list=[arxiv_id])
        try:
            result = next(self._client.results(search))
        except StopIteration:
            return None

        # Sanitize filename: replace / with _ for old-style IDs like hep-th/9901001
        safe_id = arxiv_id.replace("/", "_")
        filename = f"{safe_id}.pdf"
        result.download_pdf(dirpath=str(dest), filename=filename)
        pdf_path = dest / filename
        if pdf_path.exists():
            return pdf_path
        return None

    @staticmethod
    def _result_to_metadata(result: arxiv.Result) -> PaperMetadata:
        """Convert an arxiv.Result to our PaperMetadata model."""
        # Extract clean arXiv ID without version
        short_id = result.get_short_id()
        # Strip version suffix
        clean_id = re.sub(r"v\d+$", "", short_id)

        return PaperMetadata(
            arxiv_id=clean_id,
            doi=result.doi,
            title=result.title,
            abstract=result.summary,
            authors=[a.name for a in result.authors],
            published_date=result.published.isoformat() if result.published else None,
            updated_date=result.updated.isoformat() if result.updated else None,
            journal_ref=result.journal_ref,
            pdf_url=result.pdf_url,
            primary_category=result.primary_category,
            categories=list(result.categories),
        )
