# Contributing

1. Open an issue first (bug report or feature request template).
2. Create a branch from `main`: `feature/<short-name>` or `fix/<short-name>`.
3. Install the dev environment: `pip install -e ".[dev]"`.
4. Add or update tests in `tests/` for every change in `src/kaznlp/`.
5. Run `ruff check . && ruff format . && pytest --cov=kaznlp` locally.
6. Open a pull request that references the issue (`Closes #N`). CI must be green
   before merging.

Commit messages are short and in the imperative mood ("Add ...", "Fix ...").

## Releasing

1. Update `__version__` in `src/kaznlp/__init__.py`, `version` in `pyproject.toml`
   and `CHANGELOG.md`.
2. Merge to `main`, then tag: `git tag v0.2.0 && git push origin v0.2.0`.
3. The Release workflow builds the package and publishes the GitHub Release.

## Data

Never commit real social-media data. Use synthetic examples, or data that has been
passed through `kaznlp clean` (PII masked) and is allowed to be published.
