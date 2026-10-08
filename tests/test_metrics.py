import random

import pytest
from sklearn import metrics as skm

from kaznlp.metrics import (
    classification_report,
    cohen_kappa,
    confusion_matrix,
    macro_f1,
    per_class_scores,
)

LABELS = ["none", "reputational", "legal", "misinformation"]


@pytest.fixture
def random_labels():
    rng = random.Random(0)
    y_true = rng.choices(LABELS, weights=[85, 7, 4, 4], k=400)
    y_pred = [t if rng.random() < 0.8 else rng.choice(LABELS) for t in y_true]
    return y_true, y_pred


def test_confusion_matrix_matches_sklearn(random_labels):
    y_true, y_pred = random_labels
    ours, labels = confusion_matrix(y_true, y_pred)
    assert (ours == skm.confusion_matrix(y_true, y_pred, labels=labels)).all()


def test_macro_f1_matches_sklearn(random_labels):
    y_true, y_pred = random_labels
    expected = skm.f1_score(y_true, y_pred, average="macro")
    assert macro_f1(y_true, y_pred) == pytest.approx(expected)


def test_cohen_kappa_matches_sklearn(random_labels):
    a, b = random_labels
    assert cohen_kappa(a, b) == pytest.approx(skm.cohen_kappa_score(a, b))


def test_kappa_perfect_agreement_single_class():
    assert cohen_kappa(["none"] * 5, ["none"] * 5) == 1.0


def test_always_none_model_has_high_accuracy_but_low_macro_f1():
    y_true = ["none"] * 93 + ["legal"] * 7
    y_pred = ["none"] * 100
    report = classification_report(y_true, y_pred, positive_labels=["legal"])
    assert report["accuracy"] == pytest.approx(0.93)
    assert report["macro_f1"] < 0.5
    assert report["positive_recall"] == 0.0


def test_positive_recall_counts_any_risk_class_as_hit():
    y_true = ["legal", "reputational", "none"]
    y_pred = ["reputational", "reputational", "none"]
    report = classification_report(y_true, y_pred, positive_labels=["legal", "reputational"])
    assert report["positive_recall"] == 1.0


def test_unseen_class_gets_zero_scores():
    scores = per_class_scores(["a", "a"], ["a", "a"], labels=["a", "b"])
    assert scores["b"] == {"precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0}


def test_input_validation():
    with pytest.raises(ValueError):
        macro_f1(["a"], ["a", "b"])
    with pytest.raises(ValueError):
        macro_f1([], [])
