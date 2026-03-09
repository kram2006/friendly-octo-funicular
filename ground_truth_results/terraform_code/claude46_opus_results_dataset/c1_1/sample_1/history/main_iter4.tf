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

data "xenorchestra_network" "network" {
  name_label = "Pool-wide network associated with eth0"
}

data "xenorchestra_sr" "local_storage" {
  name_label = "Local storage"
}

resource "xenorchestra_vm" "vm" {
  name_label       = "terraform-vm"
  name_description = "VM created by Terraform"
  template         = data.xenorchestra_template.ubuntu.id
  memory_max       = 4294967296
  cpus             = 2

  network {
    network_id = data.xenorchestra_network.network.id
  }

  disk {
    sr_id      = data.xenorchestra_sr.local_storage.id
    name_label = "terraform-vm-disk"
    size       = 53687091200
  }
}