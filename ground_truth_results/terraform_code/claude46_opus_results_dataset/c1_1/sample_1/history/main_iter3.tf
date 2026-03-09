<hcl>
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

data "xenorchestra_template" "template" {
  name_label = "Ubuntu-22"
  pool_id    = data.xenorchestra_pool.pool.id
}

data "xenorchestra_network" "network" {
  name_label = "Pool-wide network associated with eth0"
  pool_id    = data.xenorchestra_pool.pool.id
}

data "xenorchestra_sr" "sr" {
  name_label = "Local storage"
  pool_id    = data.xenorchestra_pool.pool.id
}

resource "xenorchestra_vm" "vm" {
  name_label       = "terraform-vm"
  name_description = "VM created by Terraform"
  template         = data.xenorchestra_template.template.id
  memory_max       = 4294967296
  cpus             = 2

  network {
    network_id = data.xenorchestra_network.network.id
  }

  disk {
    sr_id      = data.xenorchestra_sr.sr.id
    name_label = "terraform-vm-disk"
    size       = 53687091200
  }
}
</hcl>