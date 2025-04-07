terraform {
  backend "gcs" {
    bucket = "repsheet-app-prod-tf-state"
  }
}

provider "google" {
  project = "repsheet-app-prod"
  region  = "northamerica-northeast1"
}

locals {
  namespace = "repsheet-app-prod"
  domain    = "repsheet.info"
  region    = "northamerica-northeast1"
}
