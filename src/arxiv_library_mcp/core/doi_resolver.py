"""DOI resolution: find published versions of arXiv preprints.

Uses Semantic Scholar API and Crossref API as fallback.
"""

from __future__ import annotations

import httpx

from arxiv_library_mcp.db.models import DOIResult


_S2_BASE = "https://api.semanticscholar.org/graph/v1/paper"
_CROSSREF_BASE = "https://api.crossref.org/works"

# Timeout for HTTP requests
_TIMEOUT = 15.0


class DOIResolver:
    """Resolves arXiv papers to their published DOI versions."""

    def __init__(self, s2_api_key: str | None = None) -> None:
        self._s2_headers: dict[str, str] = {}
        if s2_api_key:
            self._s2_headers["x-api-key"] = s2_api_key

    def resolve_arxiv_to_doi(self, arxiv_id: str) -> DOIResult | None:
        """Try to find the published DOI for an arXiv paper.

        Strategy:
        1. Query Semantic Scholar by arXiv ID
        2. If no result, query Crossref by title (requires title param)
        """
        result = self._try_semantic_scholar(arxiv_id)
        if result:
            return result
        return None

    def resolve_by_title(self, title: str, first_author: str | None = None) -> DOIResult | None:
        """Try to find a DOI by title + optional author via Crossref."""
        return self._try_crossref(title, first_author)

    def _try_semantic_scholar(self, arxiv_id: str) -> DOIResult | None:
        """Query Semantic Scholar for DOI by arXiv ID."""
        try:
            r = httpx.get(
                f"{_S2_BASE}/ARXIV:{arxiv_id}",
                params={"fields": "externalIds,title,journal,url"},
                headers=self._s2_headers,
                timeout=_TIMEOUT,
            )
            if r.status_code != 200:
                return None
            data = r.json()
        except Exception:
            return None

        external_ids = data.get("externalIds", {})
        doi = external_ids.get("DOI")
        if not doi:
            return None

        journal_info = data.get("journal")
        journal = journal_info.get("name") if journal_info else None

        return DOIResult(
            doi=doi,
            title=data.get("title"),
            journal=journal,
            url=f"https://doi.org/{doi}",
            confidence=1.0,
        )

    def _try_crossref(self, title: str, first_author: str | None = None) -> DOIResult | None:
        """Query Crossref for DOI by bibliographic query."""
        try:
            query = title
            if first_author:
                query += f" {first_author}"

            r = httpx.get(
                _CROSSREF_BASE,
                params={"query.bibliographic": query, "rows": "3"},
                timeout=_TIMEOUT,
            )
            if r.status_code != 200:
                return None
            items = r.json().get("message", {}).get("items", [])
        except Exception:
            return None

        if not items:
            return None

        # Find the best match by comparing titles
        title_lower = title.lower().strip()
        for item in items:
            item_titles = item.get("title", [])
            if not item_titles:
                continue
            item_title = item_titles[0].lower().strip()

            # Check for reasonable title similarity
            # Simple containment check — if one title contains most of the other
            if (self._title_similarity(title_lower, item_title) > 0.7
                    and item.get("DOI")):
                doi = item["DOI"]
                journal_list = item.get("container-title", [])
                journal = journal_list[0] if journal_list else None
                return DOIResult(
                    doi=doi,
                    title=item_titles[0],
                    journal=journal,
                    url=f"https://doi.org/{doi}",
                    confidence=0.8,
                )

        return None

    @staticmethod
    def _title_similarity(a: str, b: str) -> float:
        """Simple word-overlap similarity between two titles."""
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        return len(intersection) / max(len(words_a), len(words_b))
