"""TF-IDF + logistic regression baseline.

This is the cheap fallback model from the project plan (risk #2 in Assignment 1): if
the fine-tuned transformer misses the F1 target, the platform falls back to this
baseline plus rules. Character n-grams are used instead of words because Kazakh is
agglutinative - one root takes many suffixes ("банк", "банкке", "банктің",
"банктерден"), and word-level features would treat each form as a separate rare word.

Requires the optional dependency: ``pip install kaznlp-toolkit[baseline]``.
"""

from __future__ import annotations

from collections.abc import Sequence

from kaznlp.normalize import normalize


def build_baseline(seed: int = 42):
    """Return an untrained scikit-learn pipeline."""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.pipeline import Pipeline
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise ImportError(
            "The baseline needs scikit-learn: pip install 'kaznlp-toolkit[baseline]'"
        ) from exc

    return Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    preprocessor=lambda t: normalize(t, lowercase=True),
                    analyzer="char_wb",
                    ngram_range=(2, 5),
                    sublinear_tf=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(class_weight="balanced", max_iter=2000, random_state=seed),
            ),
        ]
    )


def train_baseline(texts: Sequence[str], labels: Sequence[str], seed: int = 42):
    """Fit the baseline on texts and labels and return the fitted pipeline."""
    model = build_baseline(seed=seed)
    model.fit(list(texts), list(labels))
    return model
