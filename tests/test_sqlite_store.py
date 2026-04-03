"""Tests for the SQLite storage layer."""

import tempfile
from pathlib import Path

import pytest

from arxiv_library_mcp.db.sqlite_store import SQLiteStore
from arxiv_library_mcp.db.models import Annotation


@pytest.fixture
def store(tmp_path):
    """Create a fresh SQLiteStore with a temp database."""
    db_path = tmp_path / "test.db"
    s = SQLiteStore(db_path)
    yield s
    s.close()


class TestPaperCRUD:
    def test_insert_and_get(self, store):
        pid = store.insert_paper(
            title="Attention Is All You Need",
            arxiv_id="1706.03762",
            abstract="The dominant sequence transduction models...",
            source="arxiv",
            primary_category="cs.CL",
            authors=["Ashish Vaswani", "Noam Shazeer"],
        )
        assert len(pid) == 16

        paper = store.get_paper(pid)
        assert paper is not None
        assert paper.title == "Attention Is All You Need"
        assert paper.arxiv_id == "1706.03762"
        assert paper.primary_category == "cs.CL"
        assert len(paper.authors) == 2
        assert paper.authors[0].name == "Ashish Vaswani"
        assert paper.authors[1].name == "Noam Shazeer"

    def test_get_by_arxiv_id(self, store):
        store.insert_paper(title="Test Paper", arxiv_id="2301.07041")
        paper = store.get_paper("2301.07041")
        assert paper is not None
        assert paper.title == "Test Paper"

    def test_get_nonexistent(self, store):
        assert store.get_paper("nonexistent") is None

    def test_duplicate_arxiv_id_rejected(self, store):
        store.insert_paper(title="Paper 1", arxiv_id="2301.07041")
        with pytest.raises(Exception):
            store.insert_paper(title="Paper 2", arxiv_id="2301.07041")

    def test_update_paper(self, store):
        pid = store.insert_paper(title="Old Title", arxiv_id="2301.07041")
        result = store.update_paper(pid, title="New Title", doi="10.1234/test")
        assert result is True
        paper = store.get_paper(pid)
        assert paper.title == "New Title"
        assert paper.doi == "10.1234/test"

    def test_update_nonexistent(self, store):
        assert store.update_paper("fake", title="X") is False

    def test_delete_paper(self, store):
        pid = store.insert_paper(title="To Delete", arxiv_id="2301.00001")
        assert store.delete_paper(pid) is True
        assert store.get_paper(pid) is None

    def test_delete_cascades_tags_notes(self, store):
        pid = store.insert_paper(title="Cascade Test")
        store.add_tags(pid, ["ml", "nlp"])
        store.add_note(pid, "Some note")
        store.delete_paper(pid)
        assert store.get_notes(pid) == []


class TestListPapers:
    def test_list_all(self, store):
        store.insert_paper(title="Paper A")
        store.insert_paper(title="Paper B")
        store.insert_paper(title="Paper C")
        papers, total = store.list_papers()
        assert total == 3
        assert len(papers) == 3

    def test_list_pagination(self, store):
        for i in range(5):
            store.insert_paper(title=f"Paper {i}")
        papers, total = store.list_papers(limit=2, offset=0)
        assert total == 5
        assert len(papers) == 2

        papers2, _ = store.list_papers(limit=2, offset=2)
        assert len(papers2) == 2
        # Different papers
        assert papers[0].id != papers2[0].id

    def test_list_filter_by_tags(self, store):
        pid1 = store.insert_paper(title="ML Paper")
        pid2 = store.insert_paper(title="NLP Paper")
        pid3 = store.insert_paper(title="CV Paper")
        store.add_tags(pid1, ["ml"])
        store.add_tags(pid2, ["ml", "nlp"])
        store.add_tags(pid3, ["cv"])

        # Filter by ml tag
        papers, total = store.list_papers(tags=["ml"])
        assert total == 2
        titles = {p.title for p in papers}
        assert "ML Paper" in titles
        assert "NLP Paper" in titles

        # Filter by both ml AND nlp
        papers, total = store.list_papers(tags=["ml", "nlp"])
        assert total == 1
        assert papers[0].title == "NLP Paper"

    def test_list_filter_by_categories(self, store):
        store.insert_paper(title="CL Paper", primary_category="cs.CL", categories=["cs.CL", "cs.AI"])
        store.insert_paper(title="CV Paper", primary_category="cs.CV", categories=["cs.CV"])
        papers, total = store.list_papers(categories=["cs.AI"])
        assert total == 1
        assert papers[0].title == "CL Paper"

    def test_list_sort_by_title(self, store):
        store.insert_paper(title="Zebra Paper")
        store.insert_paper(title="Alpha Paper")
        papers, _ = store.list_papers(sort_by="title", sort_order="asc")
        assert papers[0].title == "Alpha Paper"
        assert papers[1].title == "Zebra Paper"


class TestTags:
    def test_add_tags(self, store):
        pid = store.insert_paper(title="Tagged Paper")
        tags = store.add_tags(pid, ["ml", "nlp"])
        assert len(tags) == 2
        names = {t.name for t in tags}
        assert names == {"ml", "nlp"}

    def test_add_duplicate_tag(self, store):
        pid = store.insert_paper(title="Tagged Paper")
        store.add_tags(pid, ["ml"])
        tags = store.add_tags(pid, ["ml", "nlp"])
        assert len(tags) == 2

    def test_remove_tags(self, store):
        pid = store.insert_paper(title="Tagged Paper")
        store.add_tags(pid, ["ml", "nlp", "cv"])
        remaining = store.remove_tags(pid, ["nlp"])
        assert len(remaining) == 2
        names = {t.name for t in remaining}
        assert names == {"cv", "ml"}

    def test_remove_nonexistent_tag(self, store):
        pid = store.insert_paper(title="Paper")
        store.add_tags(pid, ["ml"])
        remaining = store.remove_tags(pid, ["fake"])
        assert len(remaining) == 1


class TestNotes:
    def test_add_and_get_notes(self, store):
        pid = store.insert_paper(title="Paper With Notes")
        note = store.add_note(pid, "This is a great paper")
        assert note.id is not None
        assert note.content == "This is a great paper"
        assert note.paper_id == pid

        notes = store.get_notes(pid)
        assert len(notes) == 1
        assert notes[0].content == "This is a great paper"

    def test_multiple_notes(self, store):
        pid = store.insert_paper(title="Paper")
        store.add_note(pid, "Note 1")
        store.add_note(pid, "Note 2")
        notes = store.get_notes(pid)
        assert len(notes) == 2

    def test_delete_note(self, store):
        pid = store.insert_paper(title="Paper")
        note = store.add_note(pid, "To delete")
        assert store.delete_note(note.id) is True
        assert store.get_notes(pid) == []


class TestAnnotations:
    def test_insert_and_get(self, store):
        pid = store.insert_paper(title="Annotated Paper")
        annots = [
            Annotation(page=1, type="highlight", quoted_text="important text", color="#FFFF00"),
            Annotation(page=1, type="comment", content="My comment"),
            Annotation(page=3, type="highlight", quoted_text="another highlight"),
        ]
        count = store.insert_annotations(pid, annots)
        assert count == 3

        result = store.get_annotations(pid)
        assert len(result) == 3
        assert result[0].page == 1
        assert result[0].quoted_text == "important text"

    def test_filter_by_type(self, store):
        pid = store.insert_paper(title="Paper")
        annots = [
            Annotation(page=1, type="highlight", quoted_text="text"),
            Annotation(page=1, type="comment", content="note"),
        ]
        store.insert_annotations(pid, annots)
        highlights = store.get_annotations(pid, types=["highlight"])
        assert len(highlights) == 1
        assert highlights[0].type == "highlight"
