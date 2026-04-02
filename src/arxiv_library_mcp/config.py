"""Configuration management for the ArXiv Library MCP server."""

import os
from pathlib import Path


class Config:
    """Resolved configuration from environment variables and defaults."""

    def __init__(self) -> None:
        self.library_path = Path(
            os.environ.get("ARXIV_LIBRARY_PATH", Path.home() / ".arxiv-library")
        )
        self.db_path = self.library_path / "library.db"
        self.chroma_path = self.library_path / "chroma"
        self.pdf_dir = self.library_path / "pdfs"
        self.s2_api_key: str | None = os.environ.get("S2_API_KEY")
        self.embedding_model = os.environ.get("ARXIV_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
        self.download_pdfs = os.environ.get("ARXIV_DOWNLOAD_PDFS", "true").lower() == "true"

    def ensure_dirs(self) -> None:
        """Create library directories if they don't exist."""
        self.library_path.mkdir(parents=True, exist_ok=True)
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)


# Global singleton — initialized once at import time.
config = Config()
