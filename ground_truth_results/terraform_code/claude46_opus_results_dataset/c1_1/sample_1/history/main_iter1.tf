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

# -----------------------------------------------------------------------------
# Data Sources – resolve all identifiers by name
# -----------------------------------------------------------------------------

data "xenorchestra_pool" "pool" {
  name_label = "DAO-Agentic-Infra"
}

data "xenorchestra_template" "ubuntu" {
  name_label = "Ubuntu-22"
  pool_id    = data.xenorchestra_pool.pool.id
}

data "xenorchestra_network" "net" {
  name_label = "Pool-wide network associated with eth0"
  pool_id    = data.xenorchestra_pool.pool.id
}

data "xenorchestra_sr" "local" {
  name_label = "Local storage"
  pool_id    = data.xenorchestra_pool.pool.id
}

# -----------------------------------------------------------------------------
# VM Resource
# -----------------------------------------------------------------------------

resource "xenorchestra_vm" "vm" {
  name_label       = "vm-01"
  name_description = "Virtual machine created via Terraform"
  template         = data.xenorchestra_template.ubuntu.id
  cpus             = 2
  memory_max       = 2147483648 # 2 GB

  network {
    network_id = data.xenorchestra_network.net.id
  }

  disk {
    sr_id      = data.xenorchestra_sr.local.id
    name_label = "vm-01-os-disk"
    size       = 21474836480 # 20 GB
  }
}