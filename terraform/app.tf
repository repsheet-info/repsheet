
resource "google_storage_bucket" "web_sources" {
  name     = "${local.namespace}-dist"
  location = local.region

  website {
    main_page_suffix = "index.html"
    not_found_page   = "404.html"
  }
}

resource "google_storage_default_object_access_control" "web_read" {
  bucket = google_storage_bucket.web_sources.name
  role   = "READER"
  entity = "allUsers"
}

resource "google_compute_backend_bucket" "web_backend" {
  name             = local.namespace
  bucket_name      = google_storage_bucket.web_sources.name
  enable_cdn       = true
  compression_mode = "AUTOMATIC"
  cdn_policy {
    cache_mode = "USE_ORIGIN_HEADERS"
  }
}
