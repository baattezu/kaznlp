import json
from pathlib import Path

import pytest

from kaznlp.cli import main
from kaznlp.io import read_jsonl, write_jsonl

SAMPLE = Path(__file__).resolve().parents[1] / "data" / "sample.jsonl"


def test_clean_masks_pii_and_removes_reposts(tmp_path, capsys):
    out = tmp_path / "clean.jsonl"
    assert main(["clean", str(SAMPLE), str(out)]) == 0
    stats = json.loads(capsys.readouterr().out)
    records = read_jsonl(out)

    assert stats["duplicates_removed"] >= 1
    assert stats["output"] == len(records)
    assert set(stats["pii_masked"]) >= {"PHONE", "EMAIL", "IIN", "CARD", "USER"}
    texts = " ".join(r["text"] for r in records)
    assert "+7 701" not in texts and "950512300457" not in texts
    assert "Қазақстан" in texts  # Latin "a" fixed


def test_split_writes_three_files(tmp_path, capsys):
    assert main(["split", str(SAMPLE), str(tmp_path)]) == 0
    sizes = json.loads(capsys.readouterr().out)
    assert sum(sizes.values()) == len(read_jsonl(SAMPLE))
    for name in ("train", "val", "test"):
        assert (tmp_path / f"{name}.jsonl").exists()


def test_full_pipeline_baseline_and_evaluate(tmp_path):
    clean = tmp_path / "clean.jsonl"
    main(["clean", str(SAMPLE), str(clean)])
    main(["split", str(clean), str(tmp_path / "split")])
    preds = tmp_path / "pred.jsonl"
    assert (
        main(
            [
                "baseline",
                str(tmp_path / "split" / "train.jsonl"),
                str(tmp_path / "split" / "test.jsonl"),
                str(preds),
                "--label-field",
                "risk",
            ]
        )
        == 0
    )
    report_path = tmp_path / "report.json"
    code = main(["evaluate", str(preds), "--label-field", "risk", "--output", str(report_path)])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert code == 0
    assert 0.0 <= report["macro_f1"] <= 1.0
    assert "positive_recall" in report


def test_evaluate_quality_gate_fails_below_threshold(tmp_path, capsys):
    preds = tmp_path / "pred.jsonl"
    write_jsonl(
        preds,
        [
            {"sentiment": "positive", "prediction": "negative"},
            {"sentiment": "negative", "prediction": "positive"},
        ],
    )
    assert main(["evaluate", str(preds), "--min-f1", "0.5"]) == 1
    assert "quality gate failed" in capsys.readouterr().err


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "kaznlp" in capsys.readouterr().out


def test_show_explains_cleaning(capsys):
    assert main(["show", "Қ\u0061зақстан, телефон +7 701 123 45 67"]) == 0
    out = capsys.readouterr().out
    assert "normalized: Қазақстан" in out
    assert "<PHONE>" in out
    assert "PHONE=" in out


def test_show_interactive_mode(monkeypatch, capsys):
    answers = iter(["жазыңыз a@b.kz", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    assert main(["show"]) == 0
    assert "<EMAIL>" in capsys.readouterr().out


def test_show_interactive_mode_stops_on_eof(monkeypatch):
    def eof(_):
        raise EOFError

    monkeypatch.setattr("builtins.input", eof)
    assert main(["show"]) == 0
