"""Topic clustering of papers using embeddings."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass
class ClusterResult:
    """A single cluster with its label and member paper IDs."""
    cluster_id: int
    label: str
    paper_ids: list[str] = field(default_factory=list)


def cluster_papers(
    paper_ids: list[str],
    embeddings: dict[str, list[float]],
    titles: dict[str, str],
    num_clusters: int = 0,
    min_cluster_size: int = 3,
) -> list[ClusterResult]:
    """Cluster papers by embedding similarity.

    Args:
        paper_ids: Papers to cluster (must have embeddings)
        embeddings: paper_id -> embedding vector
        titles: paper_id -> title (for label generation)
        num_clusters: Number of clusters (0 = auto-detect)
        min_cluster_size: Minimum papers per cluster for auto-detect
    """
    # Filter to papers that have embeddings
    valid_ids = [pid for pid in paper_ids if pid in embeddings]
    if len(valid_ids) < 2:
        return []

    X = np.array([embeddings[pid] for pid in valid_ids])

    # Determine number of clusters
    if num_clusters <= 0:
        # Auto: sqrt(n/2), clamped to [2, n/min_cluster_size]
        n = len(valid_ids)
        auto_k = max(2, int(np.sqrt(n / 2)))
        max_k = max(2, n // max(min_cluster_size, 1))
        num_clusters = min(auto_k, max_k)

    num_clusters = min(num_clusters, len(valid_ids))

    # KMeans clustering
    km = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
    labels = km.fit_predict(X)

    # Group papers by cluster
    clusters: dict[int, list[str]] = {}
    for i, pid in enumerate(valid_ids):
        c = int(labels[i])
        clusters.setdefault(c, []).append(pid)

    # Generate labels from top TF-IDF terms of cluster titles
    results = []
    for cluster_id in sorted(clusters):
        member_ids = clusters[cluster_id]
        label = _generate_label(member_ids, titles)
        results.append(ClusterResult(
            cluster_id=cluster_id,
            label=label,
            paper_ids=member_ids,
        ))

    return results


def _generate_label(paper_ids: list[str], titles: dict[str, str]) -> str:
    """Generate a human-readable cluster label from member titles using TF-IDF."""
    texts = [titles.get(pid, "") for pid in paper_ids]
    texts = [t for t in texts if t.strip()]
    if not texts:
        return "Unlabeled"

    if len(texts) == 1:
        # Single paper: use first few words
        words = texts[0].split()[:4]
        return " ".join(words)

    try:
        tfidf = TfidfVectorizer(
            max_features=50,
            stop_words="english",
            token_pattern=r"[a-zA-Z]{3,}",
        )
        matrix = tfidf.fit_transform(texts)
        feature_names = tfidf.get_feature_names_out()

        # Sum TF-IDF scores across all documents in the cluster
        scores = matrix.sum(axis=0).A1
        top_indices = scores.argsort()[-3:][::-1]
        top_words = [feature_names[i].capitalize() for i in top_indices]
        return " / ".join(top_words)
    except Exception:
        # Fallback: first words of first title
        words = texts[0].split()[:3]
        return " ".join(words)
