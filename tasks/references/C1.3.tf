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

# -------------------------------------------------------
# Data Sources – look up existing objects in Xen Orchestra
# -------------------------------------------------------

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

# -------------------------------------------------------
# Virtual Machine – app-01
# -------------------------------------------------------

resource "xenorchestra_vm" "app_01" {
  name_label       = "app-01"
  name_description = "Ubuntu 22.04 application server provisioned by Terraform"
  template         = data.xenorchestra_template.ubuntu.id

  cpus       = 2
  memory_max = 4294967296  # 4 GB in bytes (4 * 1024^3)

  network {
    network_id = data.xenorchestra_network.net.id
  }

  disk {
    sr_id      = data.xenorchestra_sr.local_storage.id
    name_label = "app-01-root"
    size       = 53687091200  # 50 GB in bytes (50 * 1024^3)
  }

  # Cloud-init network configuration – DHCP on the primary interface
  cloud_network_config = <<-EOF
    version: 1
    config:
      - type: physical
        name: eth0
        subnets:
          - type: dhcp
  EOF

  # Ensure the VM starts after creation
  auto_poweron = true
  wait_for_ip  = false

  tags = [
    "managed-by:terraform",
    "environment:production"
  ]
}

# -------------------------------------------------------
# Outputs
# -------------------------------------------------------

output "vm_id" {
  description = "The Xen Orchestra ID of the app-01 VM"
  value       = xenorchestra_vm.app_01.id
}

output "vm_name" {
  description = "The name of the VM"
  value       = xenorchestra_vm.app_01.name_label
}