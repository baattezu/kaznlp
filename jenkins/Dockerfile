# Jenkins controller for the kaznlp CI/CD pipeline.
# Adds the Docker CLI (it talks to the host Docker daemon through the mounted socket),
# kubectl (deploys to Minikube) and the plugins listed in plugins.txt.
# Configuration (admin user, credentials, the pipeline job) is code: casc.yaml.
ARG JENKINS_IMAGE=jenkins/jenkins:lts-jdk21
FROM ${JENKINS_IMAGE}

USER root
ARG DOCKER_VERSION=27.4.0
ARG KUBECTL_VERSION=v1.35.0
RUN set -eux; \
    arch="$(uname -m)"; case "$arch" in aarch64) karch=arm64 ;; x86_64) karch=amd64 ;; esac; \
    curl -fsSL "https://download.docker.com/linux/static/stable/${arch}/docker-${DOCKER_VERSION}.tgz" \
      | tar -xz --strip-components=1 -C /usr/local/bin docker/docker; \
    curl -fsSLo /usr/local/bin/kubectl "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${karch}/kubectl"; \
    chmod +x /usr/local/bin/kubectl; \
    docker --version; kubectl version --client
USER jenkins

COPY --chown=jenkins plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --plugin-file /usr/share/jenkins/ref/plugins.txt

# skip the setup wizard: everything comes from configuration-as-code
ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false -Dhudson.plugins.git.GitSCM.ALLOW_LOCAL_CHECKOUT=true" \
    CASC_JENKINS_CONFIG=/var/jenkins_home/casc.yaml
COPY --chown=jenkins casc.yaml /var/jenkins_home/casc.yaml
