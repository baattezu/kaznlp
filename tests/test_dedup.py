import numpy as np
import pytest

from kaznlp.dedup import (
    MinHasher,
    deduplicate,
    duplicate_clusters,
    find_near_duplicates,
    jaccard,
    shingles,
)

NEWS = "Ұлттық банк базалық мөлшерлемені 14,25 пайыз деңгейінде сақтап қалды деп хабарлады."


def test_shingles_short_text():
    assert shingles("иә", k=5) == {"иә"}


def test_shingles_use_normalized_text():
    # Latin "a" and upper case must not change the shingle set
    assert shingles("ҚAЗАҚ") == shingles("қазақ")


def test_jaccard_bounds():
    assert jaccard(set(), set()) == 1.0
    assert jaccard({"a"}, {"b"}) == 0.0
    assert jaccard({"a", "b"}, {"a"}) == 0.5


def test_signature_is_reproducible_with_same_seed():
    a = MinHasher(seed=7).signature(NEWS)
    b = MinHasher(seed=7).signature(NEWS)
    assert np.array_equal(a, b)


def test_minhash_estimate_close_to_exact_jaccard():
    other = NEWS.replace("сақтап қалды", "өзгертпеді")
    exact = jaccard(shingles(NEWS), shingles(other))
    hasher = MinHasher(num_perm=256)
    estimate = MinHasher.similarity(hasher.signature(NEWS), hasher.signature(other))
    assert abs(estimate - exact) < 0.1


def test_repost_is_found_and_unrelated_text_is_not():
    texts = [
        NEWS,
        "Ертең Алматыда күн жылы болады, жаңбыр күтілмейді.",
        "Репост: " + NEWS,
    ]
    pairs = find_near_duplicates(texts, threshold=0.7)
    assert [(i, j) for i, j, _ in pairs] == [(0, 2)]


def test_num_perm_must_divide_into_bands():
    with pytest.raises(ValueError):
        find_near_duplicates(["a", "b"], num_perm=100, bands=32)


def test_clusters_are_transitive():
    # 0-2 and 1-2 are duplicates, so 0, 1 and 2 form one cluster
    clusters = duplicate_clusters(4, [(0, 2, 0.9), (1, 2, 0.9)])
    assert clusters == [[0, 1, 2], [3]]


def test_deduplicate_keeps_first_of_each_cluster():
    texts = [NEWS, "Мүлде басқа хабар.", NEWS + "!!", "Репост: " + NEWS]
    assert deduplicate(texts, threshold=0.7) == [0, 1]
