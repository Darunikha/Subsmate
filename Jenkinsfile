
pipeline {
    agent any

    options {
        timestamps()
        timeout(time: 20, unit: 'MINUTES')
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Backend tests') {
            steps {
                dir('backend') {
                    bat 'python -m pip install --no-cache-dir -r requirements-dev.txt'
                    bat 'python -m pytest -q'
                }
            }
        }

        stage('Frontend build') {
            steps {
                dir('frontend') {
                    bat 'npm ci --no-audit --no-fund'
                    bat 'npm run build'
                }
            }
        }
    }

    post {
        always {
            echo 'Subsmate pipeline execution completed.'
        }
        success {
            echo 'Subsmate build successful!'
        }
        failure {
            echo 'Subsmate build failed. Check the console output.'
        }
    }
}
