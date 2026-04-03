"""ChromaDB vector storage for semantic search."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


class ChromaStore:
    """Manages ChromaDB collections for semantic search over the library."""

    def __init__(self, chroma_path: Path | str, model_name: str = "all-MiniLM-L6-v2") -> None:
        self._client = chromadb.PersistentClient(path=str(chroma_path))
        self._ef = SentenceTransformerEmbeddingFunction(model_name=model_name)

        self._papers = self._client.get_or_create_collection(
            name="paper_embeddings",
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )
        self._fulltext = self._client.get_or_create_collection(
            name="fulltext_embeddings",
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )
        self._notes = self._client.get_or_create_collection(
            name="notes_embeddings",
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )

    # ── Paper embeddings (title + abstract) ─────────────────────

    def index_paper(self, paper_id: str, title: str, abstract: str | None = None,
                    metadata: dict[str, Any] | None = None) -> None:
        """Index a paper's title + abstract for semantic search."""
        doc = title
        if abstract:
            doc += "\n\n" + abstract
        meta = metadata or {}
        meta["paper_id"] = paper_id
        self._papers.upsert(ids=[paper_id], documents=[doc], metadatas=[meta])

    def search_papers(self, query: str, n_results: int = 10,
                      where: dict | None = None) -> list[dict]:
        """Semantic search over paper titles + abstracts.

        Returns list of dicts with keys: paper_id, score, document.
        Score is 0-1 where 1 = most similar (converted from cosine distance).
        """
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": min(n_results, self._papers.count() or 1),
        }
        if where:
            kwargs["where"] = where
        if kwargs["n_results"] == 0:
            return []
        results = self._papers.query(**kwargs)
        return self._format_results(results)

    def get_paper_embedding(self, paper_id: str) -> list[float] | None:
        """Get the stored embedding for a paper (for similarity comparisons)."""
        result = self._papers.get(ids=[paper_id], include=["embeddings"])
        embeddings = result.get("embeddings")
        if embeddings is not None and len(embeddings) > 0 and len(embeddings[0]) > 0:
            return list(embeddings[0])
        return None

    # ── Fulltext embeddings (chunked) ───────────────────────────

    def index_fulltext(self, paper_id: str, chunks: list[str],
                       arxiv_id: str | None = None, title: str | None = None) -> int:
        """Index fulltext chunks for a paper. Returns count indexed."""
        if not chunks:
            return 0
        ids = [f"{paper_id}::chunk::{i}" for i in range(len(chunks))]
        metadatas = [
            {"paper_id": paper_id, "chunk_index": i, "total_chunks": len(chunks),
             "arxiv_id": arxiv_id or "", "title": title or ""}
            for i in range(len(chunks))
        ]
        self._fulltext.upsert(ids=ids, documents=chunks, metadatas=metadatas)
        return len(chunks)

    def search_fulltext(self, query: str, n_results: int = 10,
                        where: dict | None = None) -> list[dict]:
        """Semantic search over fulltext chunks."""
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": min(n_results, self._fulltext.count() or 1),
        }
        if where:
            kwargs["where"] = where
        if kwargs["n_results"] == 0:
            return []
        results = self._fulltext.query(**kwargs)
        return self._format_results(results)

    # ── Notes + annotations embeddings ──────────────────────────

    def index_note(self, note_id: int, paper_id: str, text: str) -> None:
        """Index a user note for semantic search."""
        self._notes.upsert(
            ids=[f"note::{note_id}"],
            documents=[text],
            metadatas=[{"paper_id": paper_id, "type": "note", "source_id": note_id}],
        )

    def index_annotation(self, annot_id: int, paper_id: str, text: str) -> None:
        """Index an annotation's text for semantic search."""
        self._notes.upsert(
            ids=[f"annot::{annot_id}"],
            documents=[text],
            metadatas=[{"paper_id": paper_id, "type": "annotation", "source_id": annot_id}],
        )

    def search_notes(self, query: str, n_results: int = 10,
                     where: dict | None = None) -> list[dict]:
        """Semantic search over notes and annotations."""
        kwargs: dict[str, Any] = {
            "query_texts": [query],
            "n_results": min(n_results, self._notes.count() or 1),
        }
        if where:
            kwargs["where"] = where
        if kwargs["n_results"] == 0:
            return []
        results = self._notes.query(**kwargs)
        return self._format_results(results)

    # ── Deletion ────────────────────────────────────────────────

    def delete_paper(self, paper_id: str) -> None:
        """Remove a paper from all collections."""
        # Paper embeddings — direct ID match
        try:
            self._papers.delete(ids=[paper_id])
        except Exception:
            pass

        # Fulltext chunks — filter by metadata
        try:
            self._fulltext.delete(where={"paper_id": paper_id})
        except Exception:
            pass

        # Notes/annotations — filter by metadata
        try:
            self._notes.delete(where={"paper_id": paper_id})
        except Exception:
            pass

    # ── Stats ───────────────────────────────────────────────────

    def paper_count(self) -> int:
        return self._papers.count()

    def fulltext_chunk_count(self) -> int:
        return self._fulltext.count()

    def notes_count(self) -> int:
        return self._notes.count()

    # ── Internal ────────────────────────────────────────────────

    @staticmethod
    def _format_results(results: dict) -> list[dict]:
        """Convert ChromaDB query results into a flat list of dicts."""
        out = []
        if not results or not results.get("ids") or not results["ids"][0]:
            return out
        ids = results["ids"][0]
        distances = results.get("distances", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        for i, id_ in enumerate(ids):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite.
            # Convert to similarity: 1 - (distance / 2)
            distance = distances[i] if i < len(distances) else 0.0
            score = 1.0 - (distance / 2.0)
            doc = documents[i] if i < len(documents) else ""
            meta = metadatas[i] if i < len(metadatas) else {}
            out.append({
                "id": id_,
                "paper_id": meta.get("paper_id", id_),
                "score": score,
                "document": doc,
                "metadata": meta,
            })
        return out
