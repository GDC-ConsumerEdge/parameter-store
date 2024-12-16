output "app_load_balancer_ip" {
  value = google_compute_forwarding_rule.eps-fwd-rule.ip_address
}

output "cloud_run_direct_endpoints" {
  value = join(", ", google_cloud_run_v2_service.eps.urls)
}

output "jwt_audience" {
  value = "/projects/${data.google_project.eps.number}/us-central1/backendServices/${google_compute_region_backend_service.eps-lb-backend-service.generated_id}"
}