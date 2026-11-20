variable "docker_host" {
  description = "Docker daemon to provision against (local socket, npipe on Windows, or ssh://user@host)."
  type        = string
  default     = "unix:///var/run/docker.sock"
}

variable "image_tag" {
  description = "Tag for the locally built images."
  type        = string
  default     = "latest"
}

variable "secret_key" {
  description = "Flask SECRET_KEY used to sign auth tokens."
  type        = string
  sensitive   = true
}

variable "seed_demo_data" {
  description = "Load demo data into an empty database."
  type        = bool
  default     = true
}

variable "http_port" {
  description = "Host port that serves the web app."
  type        = number
  default     = 8080
}
