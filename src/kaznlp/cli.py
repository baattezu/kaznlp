"""Command-line interface: ``kaznlp clean | split | baseline | evaluate``.

The four commands form the data pipeline of the project:

    raw mentions -> clean (normalize, scrub PII, deduplicate) -> split by date
                 -> baseline (train + predict) -> evaluate (report + quality gate)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kaznlp import __version__
from kaznlp.dedup import deduplicate
from kaznlp.io import read_jsonl, write_jsonl
from kaznlp.metrics import classification_report
from kaznlp.normalize import normalize
from kaznlp.pii import count_pii, scrub
from kaznlp.split import temporal_split

RISK_LABELS = ["reputational", "legal", "misinformation"]


def cmd_clean(args: argparse.Namespace) -> int:
    records = read_jsonl(args.input)
    texts = [str(r[args.text_field]) for r in records]
    pii = count_pii(texts)
    for record, text in zip(records, texts, strict=True):
        record[args.text_field] = scrub(normalize(text))

    keep = range(len(records))
    if not args.no_dedup:
        keep = deduplicate([r[args.text_field] for r in records], threshold=args.threshold)
    kept = [records[i] for i in keep]
    write_jsonl(args.output, kept)

    stats = {
        "input": len(records),
        "output": len(kept),
        "duplicates_removed": len(records) - len(kept),
        "pii_masked": dict(sorted(pii.items())),
    }
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def cmd_split(args: argparse.Namespace) -> int:
    parts = temporal_split(
        read_jsonl(args.input), date_field=args.date_field, ratios=tuple(args.ratios)
    )
    out = Path(args.output_dir)
    for name, records in parts.items():
        write_jsonl(out / f"{name}.jsonl", records)
    print(json.dumps({name: len(records) for name, records in parts.items()}))
    return 0


def cmd_baseline(args: argparse.Namespace) -> int:
    from kaznlp.baseline import train_baseline

    train = read_jsonl(args.train)
    test = read_jsonl(args.test)
    model = train_baseline(
        [r[args.text_field] for r in train], [r[args.label_field] for r in train], seed=args.seed
    )
    predictions = model.predict([r[args.text_field] for r in test])
    write_jsonl(
        args.output,
        ({**r, "prediction": str(p)} for r, p in zip(test, predictions, strict=True)),
    )
    print(f"wrote {len(test)} predictions to {args.output}")
    return 0


def cmd_evaluate(args: argparse.Namespace) -> int:
    records = read_jsonl(args.predictions)
    y_true = [r[args.label_field] for r in records]
    y_pred = [r[args.prediction_field] for r in records]
    positive = RISK_LABELS if args.label_field == "risk" else []
    report = classification_report(y_true, y_pred, positive_labels=positive)
    report["label_field"] = args.label_field

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(text + "\n", encoding="utf-8")

    if report["macro_f1"] < args.min_f1:
        print(
            f"quality gate failed: macro-F1 {report['macro_f1']:.3f} < {args.min_f1}",
            file=sys.stderr,
        )
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kaznlp", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("clean", help="normalize text, mask PII and remove near-duplicates")
    p.add_argument("input")
    p.add_argument("output")
    p.add_argument("--text-field", default="text")
    p.add_argument("--threshold", type=float, default=0.8, help="MinHash similarity threshold")
    p.add_argument("--no-dedup", action="store_true")
    p.set_defaults(func=cmd_clean)

    p = sub.add_parser("split", help="time-based train/val/test split")
    p.add_argument("input")
    p.add_argument("output_dir")
    p.add_argument("--date-field", default="date")
    p.add_argument("--ratios", type=float, nargs=3, default=[0.7, 0.15, 0.15])
    p.set_defaults(func=cmd_split)

    p = sub.add_parser("baseline", help="train the TF-IDF baseline and predict the test set")
    p.add_argument("train")
    p.add_argument("test")
    p.add_argument("output")
    p.add_argument("--text-field", default="text")
    p.add_argument("--label-field", default="sentiment")
    p.add_argument("--seed", type=int, default=42)
    p.set_defaults(func=cmd_baseline)

    p = sub.add_parser("evaluate", help="metrics report with an optional macro-F1 gate")
    p.add_argument("predictions")
    p.add_argument("--label-field", default="sentiment")
    p.add_argument("--prediction-field", default="prediction")
    p.add_argument("--min-f1", type=float, default=0.0)
    p.add_argument("--output")
    p.set_defaults(func=cmd_evaluate)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
