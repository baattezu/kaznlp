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
    """Split a text into overlapping character k-grams ("shingles").

    Example with ``k=3``: "банк" -> {"бан", "анк"}. Two texts that share most of their
    shingles are near-duplicates. Characters are used instead of words because a repost
    often changes punctuation or word endings, which would change whole word tokens.

    Args:
        text: any text; it is normalized and lower-cased first.
        k: shingle length in characters.

    Returns:
        The set of shingles (the whole text if it is shorter than ``k``).
    """
    text = normalize(text, lowercase=True)
    if len(text) <= k:
        return {text}
    return {text[i : i + k] for i in range(len(text) - k + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    """Exact Jaccard similarity ``|A & B| / |A | B|`` of two sets (1.0 = identical).

    Used in tests as the "true" value that the MinHash estimate is compared with.
    """
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


class MinHasher:
    """Computes fixed-length MinHash signatures.

    Idea: apply ``num_perm`` different random hash functions to all shingles of a text
    and keep only the minimum value of each function. For two texts, the probability
    that the minimums are equal is exactly their Jaccard similarity, so the share of
    equal positions in two signatures estimates the similarity - without comparing
    the shingle sets themselves.

    ``seed`` fixes the random hash functions, so signatures are reproducible between
    runs and machines.
    """

    def __init__(self, num_perm: int = 128, k: int = 5, seed: int = 42) -> None:
        """Create ``num_perm`` hash functions of the form ``h(x) = (a * x + b) mod p``.

        Args:
            num_perm: signature length; more functions = more accurate estimate.
            k: shingle length passed to :func:`shingles`.
            seed: random seed for ``a`` and ``b``.
        """
        rng = np.random.default_rng(seed)
        self.num_perm = num_perm
        self.k = k
        self._a = rng.integers(1, _PRIME, size=num_perm, dtype=np.uint64)
        self._b = rng.integers(0, _PRIME, size=num_perm, dtype=np.uint64)

    def signature(self, text: str) -> np.ndarray:
        """Return the MinHash signature of a text: an array of ``num_perm`` integers."""
        # 1) every shingle -> one integer (CRC32), reduced modulo the prime
        hashes = np.fromiter(
            (zlib.crc32(s.encode("utf-8")) % _PRIME for s in shingles(text, self.k)),
            dtype=np.uint64,
        )
        # 2) all hash functions applied to all shingles at once:
        #    matrix of shape (num_perm, number_of_shingles)
        values = (self._a[:, None] * hashes[None, :] + self._b[:, None]) % _PRIME
        # 3) keep the smallest value of every hash function
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
    """Find all pairs of near-duplicate texts.

    Comparing every pair would take ``n * n`` comparisons. LSH (locality-sensitive
    hashing) avoids that: each signature is cut into ``bands`` pieces, and two texts
    become candidates only if at least one piece is exactly equal. Similar texts almost
    always share a piece, different texts almost never do. Only candidates are then
    compared properly.

    Args:
        texts: the texts to check.
        threshold: minimum estimated Jaccard similarity to count as a duplicate.
        num_perm: signature length (must be divisible by ``bands``).
        bands: number of LSH bands; more bands = more candidates found.
        seed: random seed of the hash functions.

    Returns:
        Pairs ``(i, j, similarity)`` with ``i < j`` and similarity >= threshold.

    Raises:
        ValueError: if ``num_perm`` is not divisible by ``bands``.
    """
    if num_perm % bands:
        raise ValueError("num_perm must be divisible by bands")
    rows = num_perm // bands
    hasher = MinHasher(num_perm=num_perm, seed=seed)
    signatures = [hasher.signature(t) for t in texts]

    # LSH: texts whose band is identical land in the same bucket -> candidate pair
    candidates: set[tuple[int, int]] = set()
    for band in range(bands):
        buckets: dict[bytes, list[int]] = defaultdict(list)
        for idx, sig in enumerate(signatures):
            buckets[sig[band * rows : (band + 1) * rows].tobytes()].append(idx)
        for members in buckets.values():
            for x, i in enumerate(members):
                for j in members[x + 1 :]:
                    candidates.add((i, j))

    # check candidates with the full signature
    pairs = []
    for i, j in sorted(candidates):
        sim = MinHasher.similarity(signatures[i], signatures[j])
        if sim >= threshold:
            pairs.append((i, j, sim))
    return pairs


def duplicate_clusters(n: int, pairs: Sequence[tuple[int, int, float]]) -> list[list[int]]:
    """Group indices into clusters (connected components) of near-duplicates.

    Duplicates are transitive: if A~B and B~C, then A, B and C are one story. A
    union-find structure merges such chains. Each cluster is identified by its smallest
    index, i.e. the earliest text.

    Args:
        n: total number of texts.
        pairs: output of :func:`find_near_duplicates`.

    Returns:
        Sorted list of clusters; every index from ``0`` to ``n - 1`` is in exactly one.
    """
    parent = list(range(n))  # parent[x] == x means x is the root of its cluster

    def find(x: int) -> int:
        """Return the root of ``x``'s cluster (with path compression)."""
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
    """Return the indices of texts to keep: the first text of every duplicate cluster.

    Example: for ``[news, "other", "Репост: " + news]`` the result is ``[0, 1]``.
    Keeping the first (earliest) post matters because records are in time order.
    """
    pairs = find_near_duplicates(texts, threshold=threshold, seed=seed)
    return sorted(cluster[0] for cluster in duplicate_clusters(len(texts), pairs))
