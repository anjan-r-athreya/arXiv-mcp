"""FastMCP server instance, shared state, and tool registration."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from arxiv_library_mcp.config import config
from arxiv_library_mcp.core.arxiv_client import ArxivClient
from arxiv_library_mcp.db.chroma_store import ChromaStore
from arxiv_library_mcp.db.sqlite_store import SQLiteStore

mcp = FastMCP(
    name="arxiv-library",
)

# ── Shared state (lazy-initialized on first tool call) ──────────

_sqlite: SQLiteStore | None = None
_chroma: ChromaStore | None = None
_arxiv: ArxivClient | None = None


def get_sqlite() -> SQLiteStore:
    global _sqlite
    if _sqlite is None:
        config.ensure_dirs()
        _sqlite = SQLiteStore(config.db_path)
    return _sqlite


def get_chroma() -> ChromaStore:
    global _chroma
    if _chroma is None:
        config.ensure_dirs()
        _chroma = ChromaStore(config.chroma_path, model_name=config.embedding_model)
    return _chroma


def get_arxiv() -> ArxivClient:
    global _arxiv
    if _arxiv is None:
        _arxiv = ArxivClient(pdf_dir=config.pdf_dir)
    return _arxiv


# ── Tool registration (import triggers @mcp.tool decorators) ───

import arxiv_library_mcp.tools.import_tools  # noqa: F401, E402
import arxiv_library_mcp.tools.library_tools  # noqa: F401, E402
import arxiv_library_mcp.tools.search_tools  # noqa: F401, E402
import arxiv_library_mcp.tools.export_tools  # noqa: F401, E402
import arxiv_library_mcp.tools.annotation_tools  # noqa: F401, E402
import arxiv_library_mcp.tools.tracking_tools  # noqa: F401, E402
