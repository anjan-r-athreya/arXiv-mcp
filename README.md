# arxiv-library-mcp

A personal research library MCP server. Import arXiv papers, search semantically, tag, annotate, track preprints, detect duplicates, cluster by topic, and export — all through Claude.

## Quick Start

```bash
# Install uv if needed
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Clone and install
cd arxiv-library-mcp
uv sync

# Register with Claude Code
claude mcp add arxiv-library -- uv run --directory $(pwd) python -m arxiv_library_mcp

# Or register with Claude Desktop (macOS)
# Add to ~/Library/Application Support/Claude/claude_desktop_config.json:
# {
#   "mcpServers": {
#     "arxiv-library": {
#       "command": "uv",
#       "args": ["run", "--directory", "/absolute/path/to/arxiv-library-mcp",
#                "python", "-m", "arxiv_library_mcp"]
#     }
#   }
# }
```

## Tools (15)

### Import
| Tool | Description |
|---|---|
| `add_paper` | Add paper by arXiv ID, DOI, or URL. Downloads PDF and indexes full text. |
| `import_pdf` | Import a local PDF. Auto-identifies arXiv papers from PDF content. |
| `bulk_import` | Batch import from a list of identifiers. |

### Search
| Tool | Description |
|---|---|
| `search_library` | Semantic search across titles, abstracts, full text, and notes. Filter by tags, categories, date. |
| `find_similar` | Find papers similar to a given paper via embedding cosine similarity. |

### Library Management
| Tool | Description |
|---|---|
| `list_papers` | Browse library with tag/category filters, sorting, pagination. |
| `get_paper` | Full details: metadata, tags, notes, annotations, PDF path. |
| `tag_paper` | Add or remove tags. |
| `add_note` | Add a searchable note (indexed for semantic search). |
| `remove_paper` | Remove paper from all stores and optionally delete PDF. |

### Annotations
| Tool | Description |
|---|---|
| `extract_annotations` | Extract highlights, comments, underlines from a PDF via PyMuPDF. |

### Tracking & Duplicates
| Tool | Description |
|---|---|
| `check_published` | Check if arXiv preprints have published DOIs (via Semantic Scholar + Crossref). |
| `find_duplicates` | Detect duplicate/variant papers using title, author, arXiv version, and embedding similarity. |

### Clustering
| Tool | Description |
|---|---|
| `cluster_library` | Group papers by topic using KMeans on embeddings. Auto-generates cluster labels via TF-IDF. |

### Export
| Tool | Description |
|---|---|
| `export_library` | Export as BibTeX, Markdown reading list, or JSON. Filter by tags/categories. |

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `ARXIV_LIBRARY_PATH` | `~/.arxiv-library` | Root directory for all library data |
| `S2_API_KEY` | *(none)* | Semantic Scholar API key for higher rate limits |
| `ARXIV_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model for embeddings |
| `ARXIV_DOWNLOAD_PDFS` | `true` | Auto-download PDFs on import |

Library data stored at `~/.arxiv-library/`:
```
~/.arxiv-library/
├── library.db       # SQLite (metadata, tags, notes, annotations)
├── chroma/          # ChromaDB (semantic search embeddings)
└── pdfs/            # Downloaded PDFs
```

## Architecture

**Dual storage**: SQLite for relational queries (filter, sort, join, paginate) + ChromaDB for semantic similarity search. Paper IDs (16-char hex) are the join key.

**Embeddings**: `all-MiniLM-L6-v2` (22MB, 384-dim) via ChromaDB's built-in `SentenceTransformerEmbeddingFunction`. Three collections: paper titles+abstracts, fulltext chunks (~512 tokens), and user notes+annotations.

**arXiv API**: 3-second rate limit enforced. PDF text extracted via PyMuPDF.

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Run a single test
uv run pytest tests/test_sqlite_store.py::TestPaperCRUD::test_insert_and_get -v

# Lint
uv run ruff check src/ tests/

# Test the MCP server starts
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | uv run python -m arxiv_library_mcp
```

## License

MIT
