"""MCP tools for clustering papers by topic."""

from __future__ import annotations

from arxiv_library_mcp.core.clusterer import cluster_papers
from arxiv_library_mcp.server import mcp, get_sqlite, get_chroma


@mcp.tool()
def cluster_library(
    num_clusters: int = 0,
    tags: list[str] | None = None,
    min_cluster_size: int = 3,
) -> str:
    """Group papers in your library by topical similarity using their embeddings.

    Creates named clusters for literature review organization.

    Args:
        num_clusters: Number of clusters (0 = auto-detect)
        tags: Only cluster papers with these tags
        min_cluster_size: Minimum papers per cluster for auto-detect
    """
    db = get_sqlite()
    chroma = get_chroma()

    # Get papers
    papers, _ = db.list_papers(tags=tags or [], limit=10000)
    if len(papers) < 2:
        return "Need at least 2 papers to cluster."

    # Get embeddings
    embeddings: dict[str, list[float]] = {}
    titles: dict[str, str] = {}
    for p in papers:
        emb = chroma.get_paper_embedding(p.id)
        if emb:
            embeddings[p.id] = emb
            titles[p.id] = p.title

    if len(embeddings) < 2:
        return "Need at least 2 papers with embeddings to cluster."

    clusters = cluster_papers(
        paper_ids=list(embeddings.keys()),
        embeddings=embeddings,
        titles=titles,
        num_clusters=num_clusters,
        min_cluster_size=min_cluster_size,
    )

    if not clusters:
        return "Clustering produced no results."

    # Build paper lookup
    paper_map = {p.id: p for p in papers}

    # Format output
    lines = [f"**{len(clusters)} clusters from {len(embeddings)} papers:**\n"]
    for c in clusters:
        lines.append(f"### Cluster {c.cluster_id + 1}: {c.label}")
        lines.append(f"*{len(c.paper_ids)} papers*\n")
        for pid in c.paper_ids:
            p = paper_map.get(pid)
            if p:
                authors = p.authors[0].name if p.authors else ""
                if len(p.authors) > 1:
                    authors += " et al."
                lines.append(f"- {p.title} ({authors})")
        lines.append("")

    return "\n".join(lines)
