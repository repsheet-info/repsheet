
resource "google_compute_global_address" "main" {
  name         = local.namespace
  address_type = "EXTERNAL"
  ip_version   = "IPV4"
}

resource "google_compute_ssl_policy" "main" {
  name            = "default-ssl-policy"
  profile         = "MODERN"
  min_tls_version = "TLS_1_2"
}

resource "google_compute_managed_ssl_certificate" "main" {
  name = local.namespace
  managed {
    domains = [local.domain]
  }
}

resource "google_compute_url_map" "http" {
  name = "${local.namespace}-http"

  default_url_redirect {
    https_redirect = true
    strip_query    = false
  }
}

resource "google_compute_url_map" "https" {
  name            = "${local.namespace}-https"
  default_service = google_compute_backend_bucket.web_backend.id
}

resource "google_compute_target_https_proxy" "main" {
  name              = "${local.namespace}-https"
  url_map           = google_compute_url_map.https.self_link
  ssl_certificates  = [google_compute_managed_ssl_certificate.main.self_link]
  ssl_policy        = google_compute_ssl_policy.main.id
}

resource "google_compute_target_http_proxy" "main" {
  name    = "${local.namespace}-http"
  url_map = google_compute_url_map.http.id
}

resource "google_compute_global_forwarding_rule" "https" {
  name                  = "${local.namespace}-https"
  load_balancing_scheme = "EXTERNAL"
  ip_address            = google_compute_global_address.main.address
  ip_protocol           = "TCP"
  port_range            = "443"
  target                = google_compute_target_https_proxy.main.self_link
}

resource "google_compute_global_forwarding_rule" "http" {
  name                  = "${local.namespace}-http"
  load_balancing_scheme = "EXTERNAL"
  ip_address            = google_compute_global_address.main.address
  ip_protocol           = "TCP"
  target                = google_compute_target_http_proxy.main.id
  port_range            = "80"
}
