# Preflight infrastructure.
#
# The resources here were created with gcloud during Gate 7 and this
# configuration describes them so they can be reproduced or adopted with
# `terraform import`. It is written to match what is actually running rather
# than to describe an intention — a Terraform file that has never matched
# reality is worse than none, because it invites trust it has not earned.
#
# Reproduce from nothing:
#   terraform init && terraform apply
#
# Adopt what already exists:
#   terraform import google_storage_bucket.media preflight-505021-media
#   terraform import google_cloud_tasks_queue.jobs \
#     projects/preflight-505021/locations/us-central1/queues/preflight-jobs

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

variable "project_id" {
  type    = string
  default = "preflight-505021"
}

variable "region" {
  type    = string
  default = "us-central1"
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  services = [
    "storage.googleapis.com",
    "aiplatform.googleapis.com",
    "run.googleapis.com",
    "cloudtasks.googleapis.com",
    "sqladmin.googleapis.com",
    "identitytoolkit.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
  ]
}

resource "google_project_service" "enabled" {
  for_each = toset(local.services)
  service  = each.value

  # Disabling an API would break a running deployment; removal from this list
  # should be a deliberate act, not a side effect of an edit.
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Media storage
# ---------------------------------------------------------------------------

resource "google_storage_bucket" "media" {
  name     = "${var.project_id}-media"
  location = upper(var.region)

  # Unreleased films. Access is only ever granted through short-lived signed
  # URLs issued by the API, so every public path is closed at the bucket.
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  versioning {
    enabled = false
  }

  # Scratch space is reclaimed automatically. Originals and packages are
  # deleted on user request, never on a timer, because a producer's master
  # disappearing on a schedule they did not set would be a betrayal.
  lifecycle_rule {
    condition {
      age            = 1
      matches_prefix = ["temporary/"]
    }
    action {
      type = "Delete"
    }
  }
}

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

resource "google_service_account" "runtime" {
  account_id   = "preflight-api"
  display_name = "Preflight API and worker"
}

# Object-level access only. The service account cannot create, delete or
# reconfigure buckets, so a compromised runtime cannot widen its own access.
resource "google_project_iam_member" "storage" {
  project = var.project_id
  role    = "roles/storage.objectAdmin"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_project_iam_member" "vertex" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

# Required to sign download URLs without holding a key on disk.
resource "google_project_iam_member" "token_creator" {
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  member  = "serviceAccount:${google_service_account.runtime.email}"
}

# ---------------------------------------------------------------------------
# Job queue
# ---------------------------------------------------------------------------

resource "google_cloud_tasks_queue" "jobs" {
  name     = "preflight-jobs"
  location = var.region

  rate_limits {
    max_concurrent_dispatches = 5
    max_dispatches_per_second = 2
  }

  retry_config {
    # Media jobs are idempotent, so retrying is safe. It is bounded anyway:
    # a job that has failed five times is failing for a reason retries will
    # not fix, and unbounded retries on a media worker are unbounded cost.
    max_attempts       = 5
    min_backoff        = "10s"
    max_backoff        = "300s"
    max_retry_duration = "3600s"
  }
}

# ---------------------------------------------------------------------------
# Secrets
# ---------------------------------------------------------------------------

resource "google_secret_manager_secret" "parallel_api_key" {
  secret_id = "parallel-api-key"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "database_url" {
  secret_id = "database-url"
  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_iam_member" "runtime_reads_parallel" {
  secret_id = google_secret_manager_secret.parallel_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

resource "google_secret_manager_secret_iam_member" "runtime_reads_database" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime.email}"
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

resource "google_sql_database_instance" "main" {
  name             = "preflight-db"
  database_version = "POSTGRES_16"
  region           = var.region

  settings {
    tier    = "db-f1-micro"
    edition = "ENTERPRISE"

    ip_configuration {
      # Reached over the Cloud SQL connector rather than a public address.
      ipv4_enabled = true
    }
  }

  # A hackathon project should still not be one fat-fingered command away from
  # losing every user's project lineage.
  deletion_protection = true
}

resource "google_sql_database" "preflight" {
  name     = "preflight"
  instance = google_sql_database_instance.main.name
}

output "bucket" {
  value = google_storage_bucket.media.name
}

output "service_account" {
  value = google_service_account.runtime.email
}
