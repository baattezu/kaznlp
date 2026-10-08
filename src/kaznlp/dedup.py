"""Near-duplicate detection with MinHash and locality-sensitive hashing (LSH).

The same news story is reposted across many Telegram channels with small edits
("Репост:", an added emoji, a shortened link). If two copies land in the training set
and the test set, the test score is inflated. MinHash estimates the Jaccard similarity
of two texts' character shingles, and LSH banding finds candidate pairs without
comparing every pair of documents.
"""

from __future__ import annotations

import zlib
from collections import defaultdict
from collections.abc import Sequence

import numpy as np

from kaznlp.normalize import normalize

_PRIME = (1 << 31) - 1  # Mersenne prime; a * h stays below 2**62, so uint64 never overflows


def shingles(text: str, k: int = 5) -> set[str]:
    """Character k-grams of the normalized, lower-cased text."""
    text = normalize(text, lowercase=True)
    if len(text) <= k:
        return {text}
    return {text[i : i + k] for i in range(len(text) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    """Exact Jaccard similarity of two sets."""
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


class MinHasher:
    """Computes fixed-length MinHash signatures.

    ``seed`` fixes the random hash functions, so signatures are reproducible between
    runs and machines.
    """

    def __init__(self, num_perm: int = 128, k: int = 5, seed: int = 42) -> None:
        rng = np.random.default_rng(seed)
        self.num_perm = num_perm
        self.k = k
        self._a = rng.integers(1, _PRIME, size=num_perm, dtype=np.uint64)
        self._b = rng.integers(0, _PRIME, size=num_perm, dtype=np.uint64)

    def signature(self, text: str) -> np.ndarray:
        hashes = np.fromiter(
            (zlib.crc32(s.encode("utf-8")) % _PRIME for s in shingles(text, self.k)),
            dtype=np.uint64,
        )
        values = (self._a[:, None] * hashes[None, :] + self._b[:, None]) % _PRIME
        return values.min(axis=1)

    @staticmethod
    def similarity(sig_a: np.ndarray, sig_b: np.ndarray) -> float:
        """Estimated Jaccard similarity: share of equal signature positions."""
        return float(np.mean(sig_a == sig_b))


def find_near_duplicates(
    texts: Sequence[str],
    threshold: float = 0.8,
    num_perm: int = 128,
    bands: int = 32,
    seed: int = 42,
) -> list[tuple[int, int, float]]:
    """Return pairs ``(i, j, similarity)`` with ``i < j`` and similarity >= threshold."""
    if num_perm % bands:
        raise ValueError("num_perm must be divisible by bands")
    rows = num_perm // bands
    hasher = MinHasher(num_perm=num_perm, seed=seed)
    signatures = [hasher.signature(t) for t in texts]

    candidates: set[tuple[int, int]] = set()
    for band in range(bands):
        buckets: dict[bytes, list[int]] = defaultdict(list)
        for idx, sig in enumerate(signatures):
            buckets[sig[band * rows : (band + 1) * rows].tobytes()].append(idx)
        for members in buckets.values():
            for x, i in enumerate(members):
                for j in members[x + 1 :]:
                    candidates.add((i, j))

    pairs = []
    for i, j in sorted(candidates):
        sim = MinHasher.similarity(signatures[i], signatures[j])
        if sim >= threshold:
            pairs.append((i, j, sim))
    return pairs


def duplicate_clusters(n: int, pairs: Sequence[tuple[int, int, float]]) -> list[list[int]]:
    """Group indices into clusters (connected components) of near-duplicates."""
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, j, _ in pairs:
        root_i, root_j = find(i), find(j)
        if root_i != root_j:
            parent[max(root_i, root_j)] = min(root_i, root_j)

    clusters: dict[int, list[int]] = defaultdict(list)
    for idx in range(n):
        clusters[find(idx)].append(idx)
    return sorted(clusters.values())


def deduplicate(texts: Sequence[str], threshold: float = 0.8, seed: int = 42) -> list[int]:
    """Return the indices to keep: the first text of every near-duplicate cluster."""
    pairs = find_near_duplicates(texts, threshold=threshold, seed=seed)
    return sorted(cluster[0] for cluster in duplicate_clusters(len(texts), pairs))
