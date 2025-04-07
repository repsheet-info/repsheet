
data "google_dns_managed_zone" "main" {
  name    = "repsheet-info"
}

resource "google_dns_record_set" "app" {
  name = "${local.domain}."
  type = "A"
  ttl  = 300

  managed_zone = data.google_dns_managed_zone.main.name

  rrdatas = [google_compute_global_forwarding_rule.https.ip_address]
}
