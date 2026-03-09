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

# -----------------------------
# Data Sources
# -----------------------------

data "xenorchestra_pool" "pool" {
  name_label = "DAO-Agentic-Infra"
}

data "xenorchestra_template" "ubuntu22" {
  name_label = "Ubuntu-22"
}

data "xenorchestra_network" "net" {
  name_label = "Pool-wide network associated with eth0"
  pool_id    = data.xenorchestra_pool.pool.id
}

data "xenorchestra_sr" "local_storage" {
  name_label = "Local storage"
  pool_id    = data.xenorchestra_pool.pool.id
}

# -----------------------------
# Import existing web-01 so Terraform adopts it
# -----------------------------

import {
  to = xenorchestra_vm.web_01
  id = "4b9eb2a7-b0c4-b660-c816-c8a5c034d4b0"
}

# -----------------------------
# Virtual Machines
# -----------------------------

# web-01 — retained (imported from existing state)
resource "xenorchestra_vm" "web_01" {
  name_label       = "web-01"
  name_description = "Ubuntu 22.04 web server - web-01"
  template         = data.xenorchestra_template.ubuntu22.id
  cpus             = 2
  memory_max       = 4294967296 # 4 GB
  wait_for_ip      = true

  disk {
    name_label = "web-01-root"
    size       = 53687091200 # 50 GB
    sr_id      = data.xenorchestra_sr.local_storage.id
  }

  network {
    network_id = data.xenorchestra_network.net.id
  }
}

# web-02 — REMOVED
# web-03 — REMOVED