"""Tests for the ChromaDB storage layer."""

import pytest

from arxiv_library_mcp.db.chroma_store import ChromaStore


@pytest.fixture
def store(tmp_path):
    """Create a fresh ChromaStore with a temp directory."""
    return ChromaStore(chroma_path=tmp_path / "chroma")


PAPERS = [
    ("p1", "Attention Is All You Need",
     "We propose a new simple network architecture, the Transformer, based solely on attention mechanisms."),
    ("p2", "BERT: Pre-training of Deep Bidirectional Transformers",
     "We introduce BERT, a new language representation model designed to pre-train deep bidirectional representations."),
    ("p3", "ImageNet Classification with Deep Convolutional Neural Networks",
     "We trained a large deep convolutional neural network to classify images into 1000 different classes."),
    ("p4", "Generative Adversarial Nets",
     "We propose a new framework for estimating generative models via an adversarial process."),
]


class TestPaperIndexAndSearch:
    def test_index_and_count(self, store):
        for pid, title, abstract in PAPERS:
            store.index_paper(pid, title, abstract, metadata={"arxiv_id": pid})
        assert store.paper_count() == 4

    def test_search_returns_relevant_results(self, store):
        for pid, title, abstract in PAPERS:
            store.index_paper(pid, title, abstract)

        results = store.search_papers("transformer attention mechanism", n_results=2)
        assert len(results) == 2
        # Top results should be the transformer papers
        top_ids = {r["paper_id"] for r in results}
        assert "p1" in top_ids  # Attention Is All You Need

    def test_search_scores_are_normalized(self, store):
        for pid, title, abstract in PAPERS:
            store.index_paper(pid, title, abstract)

        results = store.search_papers("attention", n_results=4)
        for r in results:
            assert 0.0 <= r["score"] <= 1.0

    def test_search_empty_collection(self, store):
        results = store.search_papers("anything")
        assert results == []

    def test_upsert_updates_existing(self, store):
        store.index_paper("p1", "Old Title", "Old abstract")
        store.index_paper("p1", "New Title", "New abstract")
        assert store.paper_count() == 1
        results = store.search_papers("New Title", n_results=1)
        assert "New Title" in results[0]["document"]

    def test_get_paper_embedding(self, store):
        store.index_paper("p1", "Test Paper", "Test abstract")
        emb = store.get_paper_embedding("p1")
        assert emb is not None
        assert len(emb) == 384  # all-MiniLM-L6-v2 dimension

    def test_get_nonexistent_embedding(self, store):
        emb = store.get_paper_embedding("nonexistent")
        assert emb is None


class TestFulltextIndex:
    def test_index_chunks(self, store):
        chunks = ["This is chunk one about transformers.", "This is chunk two about attention."]
        count = store.index_fulltext("p1", chunks, arxiv_id="2301.07041", title="Test")
        assert count == 2
        assert store.fulltext_chunk_count() == 2

    def test_search_fulltext(self, store):
        store.index_fulltext("p1", [
            "The transformer architecture uses self-attention.",
            "We trained on the WMT 2014 English-German dataset.",
        ])
        store.index_fulltext("p2", [
            "Convolutional neural networks are used for image recognition.",
            "We use max pooling after each conv layer.",
        ])
        results = store.search_fulltext("self-attention transformer", n_results=2)
        assert len(results) == 2
        assert results[0]["metadata"]["paper_id"] == "p1"

    def test_empty_chunks(self, store):
        count = store.index_fulltext("p1", [])
        assert count == 0


class TestNotesIndex:
    def test_index_and_search_note(self, store):
        store.index_note(1, "p1", "This paper introduces the transformer architecture")
        store.index_note(2, "p2", "Good overview of convolutional networks for vision tasks")

        results = store.search_notes("transformer", n_results=1)
        assert len(results) == 1
        assert results[0]["metadata"]["paper_id"] == "p1"
        assert results[0]["metadata"]["type"] == "note"

    def test_index_and_search_annotation(self, store):
        store.index_annotation(10, "p1", "Key finding: attention outperforms recurrence")
        results = store.search_notes("attention vs recurrence", n_results=1)
        assert len(results) == 1
        assert results[0]["metadata"]["type"] == "annotation"


class TestDeletion:
    def test_delete_paper_removes_from_all_collections(self, store):
        store.index_paper("p1", "Test Paper", "Abstract")
        store.index_fulltext("p1", ["chunk one", "chunk two"])
        store.index_note(1, "p1", "A note about this paper")
        store.index_annotation(1, "p1", "A highlight")

        assert store.paper_count() == 1
        assert store.fulltext_chunk_count() == 2
        assert store.notes_count() == 2

        store.delete_paper("p1")

        assert store.paper_count() == 0
        assert store.fulltext_chunk_count() == 0
        assert store.notes_count() == 0

    def test_delete_nonexistent_paper(self, store):
        # Should not raise
        store.delete_paper("nonexistent")
