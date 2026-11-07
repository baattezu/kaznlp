#!/usr/bin/env bash
# Export the Minikube kubeconfig with embedded certificates and point it at the
# API server's address inside the "minikube" Docker network, where Jenkins runs.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p secrets
kubectl config view --context minikube --minify --flatten --raw \
  | sed -E 's#server: https://[^ ]+#server: https://minikube:8443#' > secrets/kubeconfig
chmod 600 secrets/kubeconfig
echo "wrote jenkins/secrets/kubeconfig"
