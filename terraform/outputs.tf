output "app_url" {
  description = "Where the Subsmate web app is served."
  value       = "http://localhost:${var.http_port}"
}

output "backend_container" {
  value = docker_container.backend.name
}
