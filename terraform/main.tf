
terraform {
  required_version = ">= 1.0"

  required_providers {
    docker = {
      source  = "kreuzwerker/docker"
      version = "~> 3.0"
    }
  }
}

provider "docker" {
  host = var.docker_host
}

resource "docker_image" "backend" {
  name = "subsmate-backend:${var.image_tag}"

  build {
    context = "${path.module}/../backend"
  }
}

resource "docker_image" "frontend" {
  name = "subsmate-frontend:${var.image_tag}"

  build {
    context = "${path.module}/../frontend"
  }
}

resource "docker_container" "backend" {
  name  = "subsmate-backend"
  image = docker_image.backend.image_id

  env = [
    "SECRET_KEY=${var.secret_key}",
    "DATABASE_URL=sqlite:////data/subsmate.db",
    "SEED_DEMO_DATA=${var.seed_demo_data}"
  ]

  ports {
    internal = 5000
    external = 5000
  }

  volumes {
    volume_name    = "subsmate-data"
    container_path = "/data"
  }

  restart = "unless-stopped"
}

resource "docker_container" "frontend" {
  name  = "subsmate-frontend"
  image = docker_image.frontend.image_id

  ports {
    internal = 80
    external = var.http_port
  }

  depends_on = [
    docker_container.backend
  ]

  restart = "unless-stopped"
}

resource "docker_volume" "subsmate_data" {
  name = "subsmate-data"
}
