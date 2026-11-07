# Changelog

All notable changes are listed here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `kaznlp serve`: HTTP cleaning service (`GET /health`, `POST /clean`), standard library only.
- Multi-stage `Dockerfile` (test stage runs ruff + pytest; non-root runtime with healthcheck).
- Jenkins CI/CD pipeline (`Jenkinsfile`) and Jenkins server as code (`jenkins/`).
- Kubernetes manifests (`k8s/`) and automatic deployment to Minikube.

## [0.1.0] - 2026-10-08

### Added
- Kazakh text normalization (look-alike letters, mixed script, NFC, zero-width characters).
- PII masking for e-mails, URLs, phones, cards, IINs (checksum) and usernames.
- MinHash/LSH near-duplicate detection and clustering.
- Time-based train/validation/test split.
- Metrics: confusion matrix, per-class scores, macro-F1, risk recall, Cohen's kappa.
- TF-IDF + logistic regression baseline.
- `kaznlp` command-line interface (including `kaznlp show` demo) and synthetic sample dataset.
- GitHub Actions CI and tag-based release workflow.
