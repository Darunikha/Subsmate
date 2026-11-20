# Provisions the Subsmate stack on a Docker host with the Docker provider.
# Works against local Docker out of the box; point `docker_host` at a remote
# daemon (e.g. ssh://user@server) to provision a server prepared by Ansible.
terraform {
  required_version = ">= 1.5"
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

resource "docker_network" "subsmate" {
  name = "subsmate"
}

resource "docker_volume" "data" {
  name = "subsmate-data"
}

resource "docker_image" "backend" {
  name = "subsmate-backend:${var.image_tag}"
  build {
    context = "${path.module}/../backend"
  }
  keep_locally = true
}

resource "docker_image" "frontend" {
  name = "subsmate-frontend:${var.image_tag}"
  build {
    context = "${path.module}/../frontend"
  }
  keep_locally = true
}

resource "docker_container" "backend" {
  name    = "subsmate-backend"
  image   = docker_image.backend.image_id
  restart = "unless-stopped"

  env = [
    "SECRET_KEY=${var.secret_key}",
    "DATABASE_URL=sqlite:////data/subsmate.db",
    "SEED_DEMO_DATA=${var.seed_demo_data}",
  ]

  networks_advanced {
    name    = docker_network.subsmate.name
    aliases = ["backend"]
  }

  volumes {
    volume_name    = docker_volume.data.name
    container_path = "/data"
  }
}

resource "docker_container" "frontend" {
  name    = "subsmate-frontend"
  image   = docker_image.frontend.image_id
  restart = "unless-stopped"

  networks_advanced {
    name = docker_network.subsmate.name
  }

  ports {
    internal = 80
    external = var.http_port
  }

  depends_on = [docker_container.backend]
}
