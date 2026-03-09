terraform {
  required_providers {
    xenorchestra = {
      source  = "terra-farm/xenorchestra"
      version = "~> 0.26.0"
    }
  }
}

provider "xenorchestra" {
  url      = "ws://localhost:8080"
  username = "admin@admin.net"
  password = "admin"
  insecure = true
}

# Retain data sources for future use

data "xenorchestra_pool" "pool" {
  name_label = "DAO-Agentic-Infra"
}

data "xenorchestra_template" "ubuntu" {
  name_label = "Ubuntu-22"
}

data "xenorchestra_network" "network" {
  name_label = "Pool-wide network associated with eth0"
  pool_id    = data.xenorchestra_pool.pool.id
}

data "xenorchestra_sr" "local_storage" {
  name_label = "Local storage"
  pool_id    = data.xenorchestra_pool.pool.id
}

# The xenorchestra_vm "app-01" resource has been removed.
# Running `terraform apply` will destroy the app-01 VM.