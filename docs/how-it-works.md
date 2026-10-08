# How it works

kaznlp-toolkit prepares Kazakh social-media and news text for training a
sentiment/risk classifier, and measures how good the classifier is. It does not
contain the transformer model itself (XLM-R, trained separately); it makes sure
the data that goes into the model, and the numbers that come out, can be trusted.

## The pipeline on one message

```
input:      Менің ЖСН 950512300457, телефон +7 701 123 45 67. Қaзақстан ҡызметі жақсы
normalized: Менің ЖСН 950512300457, телефон +7 701 123 45 67. Қазақстан қызметі жақсы
            letters fixed: 'a'->'а', 'ҡ'->'қ'
scrubbed:   Менің ЖСН <IIN>, телефон <PHONE>. Қазақстан қызметі жақсы
```

Run it yourself with `kaznlp show "<text>"`, or just `kaznlp show` for an
interactive prompt.

## Steps and the problem each one solves

| Step | Module | Problem | Solution |
|---|---|---|---|
| 1 | `normalize` | Latin `a` inside a Cyrillic word, Bashkir `ҡ` instead of `қ`: they look the same but the model sees different words | map look-alikes to Kazakh letters, but only inside words that already contain Cyrillic, so `Telegram` stays intact |
| 2 | `pii` | personal data must not be stored or shown to annotators | regular expressions for e-mail, URL, card, phone, IIN, @username; an IIN is masked only if its check digit is valid |
| 3 | `dedup` | the same story reposted many times; copies in train and test inflate the score | MinHash signatures estimate similarity, LSH finds candidate pairs fast, union-find groups chains of copies, the earliest post is kept |
| 4 | `split` | a random split leaks reposts and "future" data into training | sort by date and cut 70/15/15; records with the same date are never separated |
| 5 | `baseline` | need a cheap fallback model | TF-IDF on character 2-5-grams (handles Kazakh suffixes) + class-weighted logistic regression (handles rare risk classes) |
| 6 | `metrics` | risk mentions are ~5%, so accuracy is misleading | macro-F1, recall on risk classes, Cohen's kappa for annotator agreement |

## MinHash in three sentences

A text becomes a set of 5-character pieces (shingles). 128 random hash functions
are applied to all pieces and only the smallest value of each is kept, giving a
signature of 128 numbers. The share of equal positions in two signatures is an
estimate of how many pieces the two texts share (Jaccard similarity); above 0.8
they are treated as duplicates.

## Commands

| Command | Input | Output |
|---|---|---|
| `kaznlp show [text]` | one text or interactive input | step-by-step explanation |
| `kaznlp clean IN OUT` | raw JSONL | cleaned JSONL + statistics |
| `kaznlp split IN DIR` | cleaned JSONL | `train.jsonl`, `val.jsonl`, `test.jsonl` |
| `kaznlp baseline TRAIN TEST OUT` | train and test JSONL | test records with a `prediction` field |
| `kaznlp evaluate PRED [--min-f1 X]` | predictions JSONL | metrics JSON; exit code 1 if macro-F1 < X |

## How quality is ensured

- 57 pytest tests, 98% coverage; metrics are checked against scikit-learn.
- GitHub Actions runs lint, tests on Python 3.10-3.13 and Windows, the whole
  pipeline on the sample data, and a package build on every push and pull request.
- A version tag (`v0.1.0`) builds the package and publishes a GitHub Release.
- All randomness is seeded, so results are reproducible.
