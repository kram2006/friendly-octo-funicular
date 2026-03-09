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

data "xenorchestra_pool" "pool" {
  name_label = "DAO-Agentic-Infra"
}

data "xenorchestra_template" "ubuntu" {
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

resource "xenorchestra_vm" "vm" {
  name_label       = "ubuntu-vm"
  name_description = "Ubuntu 22 VM created by Terraform"
  template         = data.xenorchestra_template.ubuntu.id
  cloud_config     = ""

  cpus = 2

  memory_max = 4294967296 # 4 GB in bytes

  network {
    network_id = data.xenorchestra_network.net.id
  }

  disk {
    sr_id      = data.xenorchestra_sr.local_storage.id
    name_label = "ubuntu-vm-root"
    size       = 53687091200 # 50 GB in bytes (matches template VDI size)
  }

  tags = []

  wait_for_ip = false
}