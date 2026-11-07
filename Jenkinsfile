// CI/CD pipeline for kaznlp-toolkit (Assignment 5).
//
//   Checkout -> Lint & unit tests (in Docker) -> Build image -> Smoke test
//            -> Data pipeline quality gate -> [Push to Docker Hub] -> Deploy to Minikube -> Verify
//
// Jenkins only needs the Docker CLI and kubectl: Python, ruff and pytest run inside
// the `test` stage of the Dockerfile, so the build is the same on any machine.

pipeline {
    agent any

    options {
        buildDiscarder(logRotator(numToKeepStr: '20'))
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
        timestamps()
        ansiColor('xterm')
    }

    parameters {
        booleanParam(name: 'PUSH_TO_DOCKERHUB', defaultValue: false,
                     description: 'Push the image to Docker Hub (needs the "dockerhub" credential)')
        booleanParam(name: 'DEPLOY', defaultValue: true,
                     description: 'Deploy to the Minikube cluster after a green build')
        string(name: 'MIN_F1', defaultValue: '0.3',
               description: 'Quality gate: minimum macro-F1 of the baseline on the test split')
    }

    environment {
        IMAGE      = 'kaznlp'
        CI_NETWORK = 'kaznlp-ci'          // Docker network shared with the Jenkins container
        K8S_NS     = 'kaznlp'
        // parameters do not exist yet on the very first build of a new job
        MIN_F1     = "${params.MIN_F1 ?: '0.3'}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.GIT_SHORT = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    env.VERSION   = sh(script: "sed -n 's/^__version__ = \"\\(.*\\)\"/\\1/p' src/kaznlp/__init__.py",
                                       returnStdout: true).trim()
                    env.TAG       = "${env.VERSION}-${env.BUILD_NUMBER}-${env.GIT_SHORT}"
                    currentBuild.displayName = "#${env.BUILD_NUMBER} ${env.GIT_SHORT}"
                    currentBuild.description = sh(script: 'git log -1 --pretty=%s', returnStdout: true).trim()
                }
                sh 'git log -1 --stat'
            }
        }

        stage('Lint & unit tests') {
            steps {
                // ruff + pytest (coverage >= 90 %) run while the `test` stage is built;
                // a failing test fails `docker build` and therefore this stage.
                sh 'docker build --target test -t ${IMAGE}:test-${TAG} .'
                sh '''
                    rm -rf reports && mkdir -p reports
                    cid=$(docker create ${IMAGE}:test-${TAG})
                    docker cp "$cid":/reports/. reports/
                    docker rm "$cid"
                '''
            }
            post {
                always {
                    junit allowEmptyResults: true, testResults: 'reports/junit.xml'
                    archiveArtifacts artifacts: 'reports/*.xml', allowEmptyArchive: true
                }
            }
        }

        stage('Build image') {
            steps {
                sh '''
                    docker build --target runtime \
                      --build-arg VERSION=${VERSION} --build-arg GIT_COMMIT=${GIT_SHORT} \
                      -t ${IMAGE}:${TAG} -t ${IMAGE}:latest .
                    docker image inspect ${IMAGE}:${TAG} --format 'size: {{.Size}} bytes, user: {{.Config.User}}'
                '''
            }
        }

        stage('Smoke test') {
            steps {
                sh '''
                    docker rm -f kaznlp-smoke-${BUILD_NUMBER} >/dev/null 2>&1 || true
                    docker run -d --name kaznlp-smoke-${BUILD_NUMBER} --network ${CI_NETWORK} ${IMAGE}:${TAG}
                    for i in $(seq 1 20); do
                      curl -fsS http://kaznlp-smoke-${BUILD_NUMBER}:8000/health && break
                      sleep 1
                    done
                    echo
                    curl -fsS -X POST http://kaznlp-smoke-${BUILD_NUMBER}:8000/clean \
                      -H 'Content-Type: application/json' \
                      -d '{"text": "Менің ЖСН 950512300457, телефон +7 701 123 45 67. Қaзақстан ҡызметі жақсы"}' \
                      | tee smoke.json
                    echo
                    grep -q '<IIN>' smoke.json && grep -q '<PHONE>' smoke.json
                '''
            }
            post {
                always {
                    sh 'docker logs kaznlp-smoke-${BUILD_NUMBER} || true; docker rm -f kaznlp-smoke-${BUILD_NUMBER} || true'
                }
            }
        }

        stage('Data pipeline quality gate') {
            steps {
                // clean -> split -> baseline -> evaluate inside the image (ci/quality_gate.sh);
                // `kaznlp evaluate --min-f1` exits with 1 when the model is too weak.
                sh '''
                    rm -rf pipeline && mkdir -p pipeline
                    docker run --rm -i -e MIN_F1=${MIN_F1} --entrypoint sh ${IMAGE}:${TAG} -s \
                      < ci/quality_gate.sh > pipeline/reports.tar
                    tar -xf pipeline/reports.tar -C pipeline && rm pipeline/reports.tar
                '''
            }
            post {
                success { archiveArtifacts artifacts: 'pipeline/*.json' }
            }
        }

        stage('Push to Docker Hub') {
            when { expression { params.PUSH_TO_DOCKERHUB == true } }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub',
                                 usernameVariable: 'DH_USER', passwordVariable: 'DH_TOKEN')]) {
                    sh '''
                        echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
                        docker tag ${IMAGE}:${TAG} $DH_USER/${IMAGE}:${TAG}
                        docker tag ${IMAGE}:${TAG} $DH_USER/${IMAGE}:latest
                        docker push $DH_USER/${IMAGE}:${TAG}
                        docker push $DH_USER/${IMAGE}:latest
                        docker logout
                    '''
                }
            }
        }

        stage('Deploy to Minikube') {
            when {
                allOf {
                    expression { params.DEPLOY != false }
                    expression { currentBuild.currentResult == 'SUCCESS' }
                }
            }
            steps {
                withCredentials([file(credentialsId: 'minikube-kubeconfig', variable: 'KUBECONFIG')]) {
                    sh '''
                        # same as `minikube image load`: copy the image into the node's Docker
                        docker save ${IMAGE}:${TAG} | docker exec -i minikube docker load
                        kubectl apply -f k8s/namespace.yaml
                        kubectl apply -f k8s/
                        kubectl -n ${K8S_NS} set image deployment/kaznlp kaznlp=${IMAGE}:${TAG}
                        kubectl -n ${K8S_NS} annotate deployment/kaznlp --overwrite \
                          kubernetes.io/change-cause="Jenkins build ${BUILD_NUMBER}, commit ${GIT_SHORT}"
                        kubectl -n ${K8S_NS} rollout status deployment/kaznlp --timeout=120s
                    '''
                }
            }
        }

        stage('Verify deployment') {
            when {
                allOf {
                    expression { params.DEPLOY != false }
                    expression { currentBuild.currentResult == 'SUCCESS' }
                }
            }
            steps {
                withCredentials([file(credentialsId: 'minikube-kubeconfig', variable: 'KUBECONFIG')]) {
                    sh '''
                        kubectl -n ${K8S_NS} get deploy,rs,pods,svc -o wide
                        kubectl -n ${K8S_NS} rollout history deployment/kaznlp
                        # call the Service through cluster DNS from inside a pod
                        kubectl -n ${K8S_NS} exec deploy/kaznlp -- python -c "
import json, urllib.request
h = json.load(urllib.request.urlopen('http://kaznlp.${K8S_NS}.svc/health', timeout=5))
print('service /health:', h)
assert h['status'] == 'ok'
"
                        curl -fsS http://minikube:30080/health && echo '  <- NodePort 30080'
                    '''
                }
            }
        }
    }

    post {
        always {
            sh 'docker image rm ${IMAGE}:test-${TAG} >/dev/null 2>&1 || true'
            cleanWs(deleteDirs: true, notFailBuild: true)
        }
        success {
            echo "Image ${IMAGE}:${TAG} tested, built and deployed."
        }
        failure {
            echo 'Pipeline failed - see the stage marked red in the graph.'
        }
    }
}
