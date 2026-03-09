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

# Data Sources

data "xenorchestra_pool" "pool" {
  name_label = "DAO-Agentic-Infra"
}

data "xenorchestra_template" "ubuntu22" {
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

# Virtual Machines

resource "xenorchestra_vm" "app_01" {
  name_label       = "app-01"
  name_description = "Ubuntu 22.04 application server provisioned by Terraform"
  template         = data.xenorchestra_template.ubuntu22.id
  cpus             = 2
  memory_max       = 6442450944 # 6GB (increased from 4GB)

  network {
    network_id = data.xenorchestra_network.network.id
  }

  disk {
    name_label = "app-01-root"
    size       = 53687091200 # 50GB
    sr_id      = data.xenorchestra_sr.local_storage.id
  }

  tags = [
    "environment:production",
    "managed-by:terraform"
  ]

  wait_for_ip = false
}