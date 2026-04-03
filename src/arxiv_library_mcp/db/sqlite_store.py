"""SQLite storage layer for the ArXiv Library."""

from __future__ import annotations

import sqlite3
import uuid
from pathlib import Path

from arxiv_library_mcp.db.models import Author, Paper, Tag, Note, Annotation


_SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id              TEXT PRIMARY KEY,
    arxiv_id        TEXT UNIQUE,
    doi             TEXT,
    title           TEXT NOT NULL,
    abstract        TEXT,
    published_date  TEXT,
    updated_date    TEXT,
    journal_ref     TEXT,
    pdf_url         TEXT,
    local_pdf_path  TEXT,
    source          TEXT NOT NULL DEFAULT 'arxiv',
    primary_category TEXT,
    full_text       TEXT,
    added_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS authors (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS paper_authors (
    paper_id  TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (paper_id, author_id)
);

CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS paper_tags (
    paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    tag_id   INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (paper_id, tag_id)
);

CREATE TABLE IF NOT EXISTS notes (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id  TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    content   TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS annotations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id   TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    page       INTEGER NOT NULL,
    type       TEXT NOT NULL,
    content    TEXT,
    quoted_text TEXT,
    color      TEXT,
    rect_json  TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS paper_categories (
    paper_id    TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    category    TEXT NOT NULL,
    PRIMARY KEY (paper_id, category)
);

CREATE TABLE IF NOT EXISTS paper_versions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id        TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    version_type    TEXT NOT NULL,
    related_paper_id TEXT REFERENCES papers(id),
    external_doi    TEXT,
    external_url    TEXT,
    detected_at     TEXT NOT NULL DEFAULT (datetime('now')),
    confidence      REAL NOT NULL DEFAULT 1.0
);

CREATE TABLE IF NOT EXISTS tracking_queue (
    paper_id       TEXT PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
    last_checked   TEXT,
    check_count    INTEGER NOT NULL DEFAULT 0,
    status         TEXT NOT NULL DEFAULT 'pending',
    resolved_doi   TEXT
);

CREATE INDEX IF NOT EXISTS idx_papers_arxiv_id ON papers(arxiv_id);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_added_at ON papers(added_at);
CREATE INDEX IF NOT EXISTS idx_papers_primary_category ON papers(primary_category);
CREATE INDEX IF NOT EXISTS idx_paper_authors_paper ON paper_authors(paper_id);
CREATE INDEX IF NOT EXISTS idx_paper_tags_paper ON paper_tags(paper_id);
CREATE INDEX IF NOT EXISTS idx_notes_paper ON notes(paper_id);
CREATE INDEX IF NOT EXISTS idx_annotations_paper ON annotations(paper_id);
CREATE INDEX IF NOT EXISTS idx_tracking_status ON tracking_queue(status);
"""


def _new_id() -> str:
    return uuid.uuid4().hex[:16]


class SQLiteStore:
    """Manages all SQLite operations for the library."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = str(db_path)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ── Paper CRUD ──────────────────────────────────────────────

    def insert_paper(
        self,
        title: str,
        arxiv_id: str | None = None,
        doi: str | None = None,
        abstract: str | None = None,
        published_date: str | None = None,
        updated_date: str | None = None,
        journal_ref: str | None = None,
        pdf_url: str | None = None,
        local_pdf_path: str | None = None,
        source: str = "arxiv",
        primary_category: str | None = None,
        full_text: str | None = None,
        authors: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> str:
        """Insert a new paper. Returns the generated paper ID."""
        paper_id = _new_id()
        self._conn.execute(
            """INSERT INTO papers
               (id, arxiv_id, doi, title, abstract, published_date, updated_date,
                journal_ref, pdf_url, local_pdf_path, source, primary_category, full_text)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (paper_id, arxiv_id, doi, title, abstract, published_date, updated_date,
             journal_ref, pdf_url, local_pdf_path, source, primary_category, full_text),
        )
        if authors:
            self._link_authors(paper_id, authors)
        if categories:
            for cat in categories:
                self._conn.execute(
                    "INSERT OR IGNORE INTO paper_categories (paper_id, category) VALUES (?, ?)",
                    (paper_id, cat),
                )
        self._conn.commit()
        return paper_id

    def get_paper(self, paper_id: str) -> Paper | None:
        """Get a paper by library ID or arXiv ID."""
        row = self._conn.execute(
            "SELECT * FROM papers WHERE id = ? OR arxiv_id = ?", (paper_id, paper_id)
        ).fetchone()
        if not row:
            return None
        return self._row_to_paper(row)

    def get_paper_by_arxiv_id(self, arxiv_id: str) -> Paper | None:
        row = self._conn.execute(
            "SELECT * FROM papers WHERE arxiv_id = ?", (arxiv_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_paper(row)

    def get_paper_by_doi(self, doi: str) -> Paper | None:
        row = self._conn.execute(
            "SELECT * FROM papers WHERE doi = ?", (doi,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_paper(row)

    def update_paper(self, paper_id: str, **fields: str | None) -> bool:
        """Update specific fields on a paper. Returns True if the paper existed."""
        allowed = {
            "doi", "title", "abstract", "published_date", "updated_date",
            "journal_ref", "pdf_url", "local_pdf_path", "source",
            "primary_category", "full_text",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return False
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        set_clause += ", updated_at = datetime('now')"
        values = list(updates.values()) + [paper_id]
        cur = self._conn.execute(
            f"UPDATE papers SET {set_clause} WHERE id = ?", values
        )
        self._conn.commit()
        return cur.rowcount > 0

    def delete_paper(self, paper_id: str) -> bool:
        """Delete a paper and all related data (cascade). Returns True if it existed."""
        cur = self._conn.execute("DELETE FROM papers WHERE id = ?", (paper_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def list_papers(
        self,
        tags: list[str] | None = None,
        categories: list[str] | None = None,
        sort_by: str = "added_at",
        sort_order: str = "desc",
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Paper], int]:
        """List papers with optional filters. Returns (papers, total_count)."""
        allowed_sort = {"added_at", "published_date", "title"}
        if sort_by not in allowed_sort:
            sort_by = "added_at"
        if sort_order not in ("asc", "desc"):
            sort_order = "desc"

        where_clauses: list[str] = []
        params: list[object] = []

        if tags:
            placeholders = ", ".join("?" for _ in tags)
            where_clauses.append(
                f"""id IN (
                    SELECT pt.paper_id FROM paper_tags pt
                    JOIN tags t ON pt.tag_id = t.id
                    WHERE t.name IN ({placeholders})
                    GROUP BY pt.paper_id
                    HAVING COUNT(DISTINCT t.name) = ?
                )"""
            )
            params.extend(tags)
            params.append(len(tags))

        if categories:
            placeholders = ", ".join("?" for _ in categories)
            where_clauses.append(
                f"""id IN (
                    SELECT paper_id FROM paper_categories
                    WHERE category IN ({placeholders})
                )"""
            )
            params.extend(categories)

        where = ""
        if where_clauses:
            where = "WHERE " + " AND ".join(where_clauses)

        count_row = self._conn.execute(
            f"SELECT COUNT(*) FROM papers {where}", params
        ).fetchone()
        total = count_row[0]

        rows = self._conn.execute(
            f"SELECT * FROM papers {where} ORDER BY {sort_by} {sort_order} LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()

        papers = [self._row_to_paper(r) for r in rows]
        return papers, total

    # ── Authors ─────────────────────────────────────────────────

    def _link_authors(self, paper_id: str, author_names: list[str]) -> None:
        for i, name in enumerate(author_names):
            self._conn.execute("INSERT OR IGNORE INTO authors (name) VALUES (?)", (name,))
            row = self._conn.execute("SELECT id FROM authors WHERE name = ?", (name,)).fetchone()
            self._conn.execute(
                "INSERT OR IGNORE INTO paper_authors (paper_id, author_id, position) VALUES (?, ?, ?)",
                (paper_id, row["id"], i),
            )

    def _get_authors(self, paper_id: str) -> list[Author]:
        rows = self._conn.execute(
            """SELECT a.id, a.name FROM authors a
               JOIN paper_authors pa ON a.id = pa.author_id
               WHERE pa.paper_id = ?
               ORDER BY pa.position""",
            (paper_id,),
        ).fetchall()
        return [Author(id=r["id"], name=r["name"]) for r in rows]

    # ── Tags ────────────────────────────────────────────────────

    def add_tags(self, paper_id: str, tag_names: list[str]) -> list[Tag]:
        """Add tags to a paper. Returns the full tag list for the paper."""
        for name in tag_names:
            self._conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
            row = self._conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
            self._conn.execute(
                "INSERT OR IGNORE INTO paper_tags (paper_id, tag_id) VALUES (?, ?)",
                (paper_id, row["id"]),
            )
        self._conn.commit()
        return self._get_tags(paper_id)

    def remove_tags(self, paper_id: str, tag_names: list[str]) -> list[Tag]:
        """Remove tags from a paper. Returns the remaining tag list."""
        for name in tag_names:
            row = self._conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
            if row:
                self._conn.execute(
                    "DELETE FROM paper_tags WHERE paper_id = ? AND tag_id = ?",
                    (paper_id, row["id"]),
                )
        self._conn.commit()
        return self._get_tags(paper_id)

    def _get_tags(self, paper_id: str) -> list[Tag]:
        rows = self._conn.execute(
            """SELECT t.id, t.name FROM tags t
               JOIN paper_tags pt ON t.id = pt.tag_id
               WHERE pt.paper_id = ?
               ORDER BY t.name""",
            (paper_id,),
        ).fetchall()
        return [Tag(id=r["id"], name=r["name"]) for r in rows]

    # ── Notes ───────────────────────────────────────────────────

    def add_note(self, paper_id: str, content: str) -> Note:
        """Add a note to a paper. Returns the created note."""
        cur = self._conn.execute(
            "INSERT INTO notes (paper_id, content) VALUES (?, ?)", (paper_id, content)
        )
        self._conn.commit()
        row = self._conn.execute("SELECT * FROM notes WHERE id = ?", (cur.lastrowid,)).fetchone()
        return Note(
            id=row["id"], paper_id=row["paper_id"], content=row["content"],
            created_at=row["created_at"], updated_at=row["updated_at"],
        )

    def get_notes(self, paper_id: str) -> list[Note]:
        rows = self._conn.execute(
            "SELECT * FROM notes WHERE paper_id = ? ORDER BY created_at", (paper_id,)
        ).fetchall()
        return [
            Note(id=r["id"], paper_id=r["paper_id"], content=r["content"],
                 created_at=r["created_at"], updated_at=r["updated_at"])
            for r in rows
        ]

    def delete_note(self, note_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ── Annotations ─────────────────────────────────────────────

    def insert_annotations(self, paper_id: str, annotations: list[Annotation]) -> int:
        """Bulk insert annotations. Returns count inserted."""
        count = 0
        for a in annotations:
            self._conn.execute(
                """INSERT INTO annotations (paper_id, page, type, content, quoted_text, color, rect_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (paper_id, a.page, a.type, a.content, a.quoted_text, a.color, a.rect_json),
            )
            count += 1
        self._conn.commit()
        return count

    def get_annotations(self, paper_id: str, types: list[str] | None = None) -> list[Annotation]:
        query = "SELECT * FROM annotations WHERE paper_id = ?"
        params: list[str] = [paper_id]
        if types:
            placeholders = ", ".join("?" for _ in types)
            query += f" AND type IN ({placeholders})"
            params.extend(types)
        query += " ORDER BY page, id"
        rows = self._conn.execute(query, params).fetchall()
        return [
            Annotation(
                id=r["id"], paper_id=r["paper_id"], page=r["page"], type=r["type"],
                content=r["content"], quoted_text=r["quoted_text"], color=r["color"],
                rect_json=r["rect_json"], created_at=r["created_at"],
            )
            for r in rows
        ]

    # ── Internal helpers ────────────────────────────────────────

    def _row_to_paper(self, row: sqlite3.Row) -> Paper:
        paper_id = row["id"]
        return Paper(
            id=paper_id,
            arxiv_id=row["arxiv_id"],
            doi=row["doi"],
            title=row["title"],
            abstract=row["abstract"],
            published_date=row["published_date"],
            updated_date=row["updated_date"],
            journal_ref=row["journal_ref"],
            pdf_url=row["pdf_url"],
            local_pdf_path=row["local_pdf_path"],
            source=row["source"],
            primary_category=row["primary_category"],
            full_text=row["full_text"],
            added_at=row["added_at"],
            updated_at=row["updated_at"],
            authors=self._get_authors(paper_id),
            tags=self._get_tags(paper_id),
        )
