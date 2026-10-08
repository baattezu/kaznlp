# Technology choices

Each choice below is checked against the requirements of the Kazakh NLP module
(Assignment 2): accuracy (NFR1), privacy (NFR3), reproducibility (NFR6),
maintainability (NFR7), plus the 16-week / small-team constraint.

| Decision | Chosen | Alternatives considered | Reason |
|---|---|---|---|
| Language | Python 3.10+ | Java, Go, R | The model side (PyTorch, Hugging Face, XLM-R) is Python, so the data tools must be importable from the same training code. Go/Java would need a second code base. |
| Core dependency | numpy only | pandas, datasketch | Small install, fewer version conflicts on the GPU training image. MinHash is ~60 lines, so a dependency would not save much and would hide the algorithm. |
| Baseline model | scikit-learn (optional extra) | fastText, spaCy | Standard, stable API; char n-gram TF-IDF handles Kazakh suffixes without a Kazakh tokenizer. Optional, so the core library stays light. |
| Packaging | `pyproject.toml` + hatchling | setup.py, Poetry | PEP 621 standard metadata, one file, no extra tool for users. |
| Testing | pytest + pytest-cov | unittest | Less boilerplate, parametrised tests, fixtures (`tmp_path`, `capsys`), coverage gate. |
| Lint / format | ruff | flake8 + black + isort | One fast tool instead of three; same config locally, in pre-commit and in CI. |
| VCS / hosting | Git + GitHub | GitLab, Bitbucket | Free public repositories and CI minutes, Issues/PRs/Releases in one place, the platform most reviewers and employers already use. |
| CI/CD | GitHub Actions | GitLab CI, Jenkins | Built into GitHub, no server to maintain (Jenkins), YAML in the repository, OS/Python matrix out of the box. |
| Data format | JSON Lines, UTF-8 | CSV, Parquet | Streams line by line, keeps Kazakh letters readable in diffs (`ensure_ascii=False`), no quoting problems with commas in posts. |
| License | MIT | Apache-2.0, GPL-3.0 | Short and permissive; the platform owner can use it in a commercial product. |

## CI/CD pipeline

```
push / pull request
  -> lint (ruff check, ruff format --check)
  -> test matrix: Ubuntu py3.10-3.13 + Windows py3.12, coverage >= 90%
      -> pipeline smoke run: clean -> split -> baseline -> evaluate (reports as artifacts)
      -> build: wheel + sdist, twine check (dist as artifact)

tag vX.Y.Z
  -> tests -> tag/version check -> build -> GitHub Release with wheel and sdist
```
