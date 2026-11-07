"""Command-line interface: ``kaznlp show | clean | split | baseline | evaluate | serve``.

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
from kaznlp.pii import count_pii, find_pii, scrub
from kaznlp.split import temporal_split

RISK_LABELS = ["reputational", "legal", "misinformation"]


def show_text(text: str) -> str:
    """Explain step by step what the cleaning pipeline does to one text."""
    normalized = normalize(text)
    lines = [f"input:      {text}", f"normalized: {normalized}"]
    if normalized != text:
        changed = [f"{a!r}->{b!r}" for a, b in zip(text, normalized, strict=False) if a != b]
        if len(text) == len(normalized) and changed:
            lines.append(f"            letters fixed: {', '.join(changed)}")
    found = find_pii(normalized)
    lines.append(f"scrubbed:   {scrub(normalized)}")
    lines.append(
        "pii found:  " + (", ".join(f"{m.kind}={m.value!r}" for m in found) if found else "none")
    )
    return "\n".join(lines)


def cmd_show(args: argparse.Namespace) -> int:
    """``kaznlp show``: explain cleaning for one text, or ask for texts interactively."""
    if args.text:
        print(show_text(" ".join(args.text)))
        return 0
    print("Type a message (empty line or Ctrl+D to quit).")
    while True:
        try:
            text = input("> ")
        except EOFError:
            break
        if not text.strip():
            break
        print(show_text(text) + "\n")
    return 0


def cmd_clean(args: argparse.Namespace) -> int:
    """``kaznlp clean``: normalize -> mask PII -> remove near-duplicates.

    Reads a JSONL file, writes the cleaned records to a new JSONL file and prints
    statistics (how many records were removed, how many PII items were masked).
    PII is counted on the raw text, before masking, so the numbers are honest.
    """
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
    """``kaznlp split``: write train/val/test JSONL files split by date."""
    parts = temporal_split(
        read_jsonl(args.input), date_field=args.date_field, ratios=tuple(args.ratios)
    )
    out = Path(args.output_dir)
    for name, records in parts.items():
        write_jsonl(out / f"{name}.jsonl", records)
    print(json.dumps({name: len(records) for name, records in parts.items()}))
    return 0


def cmd_baseline(args: argparse.Namespace) -> int:
    """``kaznlp baseline``: train the TF-IDF model on train, predict the test file.

    The output is the test file with an extra ``prediction`` field per record, which
    is exactly the input format of ``kaznlp evaluate``.
    """
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
    """``kaznlp evaluate``: print a metrics report and apply the quality gate.

    Returns exit code 1 when macro-F1 is below ``--min-f1``. A non-zero exit code makes
    the CI job fail, so the same command works as an automatic model quality gate.
    """
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


def cmd_serve(args: argparse.Namespace) -> int:  # pragma: no cover (blocks forever)
    """``kaznlp serve``: start the HTTP cleaning service (used in the Docker image)."""
    from kaznlp.server import serve

    serve(args.host, args.port)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Define the ``kaznlp`` command and its subcommands with their options."""
    parser = argparse.ArgumentParser(prog="kaznlp", description=__doc__.splitlines()[0])
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("show", help="show what cleaning does to one text (interactive demo)")
    p.add_argument("text", nargs="*", help="text to check; omit for interactive mode")
    p.set_defaults(func=cmd_show)

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

    p = sub.add_parser("serve", help="run the HTTP cleaning service (GET /health, POST /clean)")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point of the ``kaznlp`` command.

    Args:
        argv: arguments without the program name; ``None`` means ``sys.argv[1:]``.
            Passing a list makes the CLI easy to call from tests.

    Returns:
        Process exit code (0 = success).
    """
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
