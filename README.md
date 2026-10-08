# kaznlp-toolkit

[![CI](https://github.com/baattezu/kaznlp/actions/workflows/ci.yml/badge.svg)](https://github.com/baattezu/kaznlp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)

Data preparation and evaluation tools for **Kazakh-language sentiment and risk
classification**. This is the data-processing part of the Kazakh NLP module for
*PulseGuard AI*, the media-monitoring case study used in my AppSoft assignments
(Assignment 1: project plan and budget, Assignment 2: methodology and architecture).

Before a model like XLM-R can be fine-tuned on Kazakh Telegram posts and news
comments, the raw text has to be cleaned, anonymized, deduplicated and split
correctly - otherwise the test score is not trustworthy. This package does exactly
these steps and computes the metrics the project is judged on.

## Features

| Module | What it does | Why it matters for this project |
|---|---|---|
| `kaznlp.normalize` | maps look-alike letters (Latin `a` in a Cyrillic word, Bashkir `ҡ`, Latin `ə`) to Kazakh letters, NFC, removes zero-width characters | the same word must become the same token |
| `kaznlp.pii` | masks e-mails, URLs, phones (+7), card numbers, IINs (with checksum), @usernames | Kazakhstan's personal data law; annotators never see PII |
| `kaznlp.dedup` | MinHash + LSH near-duplicate detection, keeps the first post of each cluster | reposts in both train and test inflate the score |
| `kaznlp.split` | time-based 70/15/15 train/val/test split | the model is trained on the past and used on new mentions |
| `kaznlp.metrics` | confusion matrix, per-class P/R/F1, macro-F1, risk recall, Cohen's kappa | risk classes are rare (5-8%), accuracy alone is misleading |
| `kaznlp.baseline` | TF-IDF (char 2-5 grams) + class-weighted logistic regression | fallback model from the project's risk plan |
| `kaznlp` CLI | `show` (demo on one text), `clean`, `split`, `baseline`, `evaluate` with a macro-F1 quality gate | the same pipeline runs locally and in CI |

## Installation

```bash
git clone https://github.com/baattezu/kaznlp.git
cd kaznlp
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # core + scikit-learn + test tools
```

Only `numpy` is required for the core library; scikit-learn is an optional extra
(`pip install ".[baseline]"`) used by the baseline model.

## Quick start

### Try it on one sentence

```bash
kaznlp show "Менің ЖСН 950512300457, телефон +7 701 123 45 67. Қaзақстан ҡызметі жақсы"
kaznlp show            # interactive mode: type messages, empty line to quit
```

```
input:      Менің ЖСН 950512300457, телефон +7 701 123 45 67. Қaзақстан ҡызметі жақсы
normalized: Менің ЖСН 950512300457, телефон +7 701 123 45 67. Қазақстан қызметі жақсы
            letters fixed: 'a'->'а', 'ҡ'->'қ'
scrubbed:   Менің ЖСН <IIN>, телефон <PHONE>. Қазақстан қызметі жақсы
pii found:  IIN='950512300457', PHONE='+7 701 123 45 67'
```

### Command line pipeline

```bash
kaznlp clean data/sample.jsonl build/clean.jsonl          # normalize, mask PII, deduplicate
kaznlp split build/clean.jsonl build/split                  # train/val/test by date
kaznlp baseline build/split/train.jsonl build/split/test.jsonl build/pred.jsonl --label-field risk
kaznlp evaluate build/pred.jsonl --label-field risk --min-f1 0.85   # exit code 1 if below target
```

Input is [JSON Lines](https://jsonlines.org/), one mention per line:

```json
{"id": 9, "date": "2026-07-09", "text": "Altyn Bank ертең жабылады деп естідім...", "sentiment": "negative", "risk": "misinformation"}
```

### Python

```python
from kaznlp.normalize import normalize
from kaznlp.pii import scrub
from kaznlp.dedup import deduplicate
from kaznlp.metrics import macro_f1, cohen_kappa

normalize("Қaзақстан ҡызметі")  # 'Қазақстан қызметі'
scrub("Хабарласыңыз: +7 701 123 45 67")  # 'Хабарласыңыз: <PHONE>'
deduplicate([news, "Репост: " + news])  # [0]
cohen_kappa(annotator_a, annotator_b)  # agreement on the gold set (target >= 0.80)
```

## Sample data

`data/sample.jsonl` contains 64 **synthetic** mentions I wrote myself about two
fictional companies ("KazNet", "Altyn Bank"). It includes Kazakh-Russian
code-switching, a repost, fake phone/card/IIN numbers and homoglyphs, so every step of
the pipeline has something to do. It is far too small to measure real model quality;
the CI uses it only as a smoke test of the pipeline.

## Project structure

```
src/kaznlp/          library code (one module per pipeline step)
tests/               pytest test suite (metrics are checked against scikit-learn)
data/sample.jsonl    synthetic sample dataset
docs/                technology choices and CI/CD description
.github/workflows/   CI (ci.yml) and release (release.yml) pipelines
```

## Development workflow

- `main` is protected; work happens on short feature branches (`feature/...`, `fix/...`)
  and is merged through pull requests after CI passes.
- Every push and pull request runs [CI](.github/workflows/ci.yml): ruff lint and format
  check, tests on Python 3.10-3.13 (Ubuntu) and 3.12 (Windows) with a 90% coverage
  minimum, a pipeline smoke run on the sample data, and a package build.
- Pushing a tag `vX.Y.Z` runs [Release](.github/workflows/release.yml): tests again,
  checks that the tag matches the package version, builds the wheel and publishes a
  GitHub Release.

```bash
ruff check . && ruff format --check .
pytest --cov=kaznlp
```

See [docs/how-it-works.md](docs/how-it-works.md) for a step-by-step explanation, [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/technology-choices.md](docs/technology-choices.md).

## Reproducibility

- All randomness is seeded (`seed=42` in MinHash and the baseline).
- The split depends only on dates, not on random shuffling.
- Dependencies are declared in `pyproject.toml`; CI tests every supported Python version.
- [CITATION.cff](CITATION.cff) describes how to cite the software.

## License

[MIT](LICENSE) © 2026 Temirkhan Bayassov
