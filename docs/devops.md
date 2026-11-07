# DevOps: Docker, Jenkins and Kubernetes

```
git commit ──► Jenkins (pollSCM, every minute)
                │
                ├─ Checkout            tag = <version>-<build>-<commit>
                ├─ Lint & unit tests   docker build --target test  (ruff, pytest, coverage ≥ 90 %)
                ├─ Build image         docker build --target runtime
                ├─ Smoke test          docker run …; GET /health; POST /clean (PII must be masked)
                ├─ Quality gate        ci/quality_gate.sh inside the image (macro-F1 ≥ MIN_F1)
                ├─ Push (optional)     Docker Hub, when PUSH_TO_DOCKERHUB=true
                ├─ Deploy              image → Minikube node; kubectl apply; set image; rollout status
                └─ Verify              Service DNS + NodePort 30080 /health
```

| File | Purpose |
|---|---|
| `Dockerfile` | `test`, `build`, `runtime` stages; non-root user, healthcheck |
| `Jenkinsfile` | declarative pipeline above; parameters `MIN_F1`, `DEPLOY`, `PUSH_TO_DOCKERHUB` |
| `ci/quality_gate.sh` | clean → split → baseline → evaluate, streamed into the container |
| `jenkins/` | Jenkins image (Docker CLI, kubectl, plugins) and `casc.yaml` (users, credentials, job) |
| `k8s/` | namespace, Deployment (2 replicas, probes, limits, rolling update), NodePort Service |

## Rollback

Every deployment records the build and commit as its change cause:

```bash
kubectl -n kaznlp rollout history deployment/kaznlp
kubectl -n kaznlp rollout undo deployment/kaznlp            # previous build
kubectl -n kaznlp rollout undo deployment/kaznlp --to-revision=2
```

## Notes for macOS / Docker Desktop

- Jenkins reaches the Kubernetes API as `https://minikube:8443` because it joins the
  `minikube` Docker network; `jenkins/make-kubeconfig.sh` writes that kubeconfig.
- If port 8080 is busy: `JENKINS_PORT=8088 JENKINS_URL=http://localhost:8088/ docker compose up -d`.
- If Docker Hub pulls fail, build Jenkins from a mirror:
  `JENKINS_IMAGE=mirror.gcr.io/jenkins/jenkins:lts-jdk21 docker compose build`.
