// Needs a Jenkins agent with Docker installed (the stages run inside containers).
pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 20, unit: 'MINUTES')
    }

    environment {
        IMAGE = "subsmate:${env.BUILD_NUMBER}"
        SMOKE_PORT = '8091'
    }

    stages {
        stage('Checkout') {
            steps { checkout scm }
        }

        stage('Backend tests') {
            agent { docker { image 'python:3.12-slim'; reuseNode true } }
            environment { HOME = "${env.WORKSPACE}" }
            steps {
                dir('backend') {
                    sh 'pip install --no-cache-dir -r requirements-dev.txt'
                    sh 'python -m pytest -q'
                }
            }
        }

        stage('Frontend build') {
            agent { docker { image 'node:22-slim'; reuseNode true } }
            environment { HOME = "${env.WORKSPACE}" }
            steps {
                dir('frontend') {
                    sh 'npm ci --no-audit --no-fund'
                    sh 'npm run build'
                }
            }
        }

        stage('Docker build') {
            steps { sh 'docker build -t $IMAGE .' }
        }

        stage('Smoke test') {
            steps {
                sh '''
                    docker rm -f subsmate-smoke 2>/dev/null || true
                    docker run -d --name subsmate-smoke -p $SMOKE_PORT:5000 -e SECRET_KEY=ci-secret $IMAGE
                    for i in $(seq 1 30); do
                        curl -fs http://localhost:$SMOKE_PORT/api/health && exit 0
                        sleep 2
                    done
                    docker logs subsmate-smoke
                    exit 1
                '''
            }
        }
    }

    post {
        always {
            sh 'docker rm -f subsmate-smoke 2>/dev/null || true'
        }
    }
}
