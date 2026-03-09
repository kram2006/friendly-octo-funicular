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

# ---------------------
# Data Sources
# ---------------------

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

# ---------------------
# Variables
# ---------------------

variable "vm_names" {
  description = "List of VM names to create"
  type        = list(string)
  default     = ["web-01", "web-02", "web-03"]
}

variable "vm_cpus" {
  description = "Number of vCPUs per VM"
  type        = number
  default     = 2
}

variable "vm_memory_max" {
  description = "Maximum memory in bytes (4GB)"
  type        = number
  default     = 4294967296 # 4 * 1024 * 1024 * 1024
}

variable "vm_disk_size" {
  description = "Disk size in bytes (50GB)"
  type        = number
  default     = 53687091200 # 50 * 1024 * 1024 * 1024
}

# ---------------------
# Cloud Config (DHCP)
# ---------------------

resource "xenorchestra_cloud_config" "web" {
  for_each = toset(var.vm_names)

  name = "${each.value}-cloud-config"

  template = <<-EOF
#cloud-config
hostname: ${each.value}
manage_etc_hosts: true
network:
  version: 2
  ethernets:
    eth0:
      dhcp4: true
users:
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: false
EOF
}

# ---------------------
# Virtual Machines
# ---------------------

resource "xenorchestra_vm" "web" {
  for_each = toset(var.vm_names)

  name_label       = each.value
  name_description = "Ubuntu 22.04 web server - ${each.value}"
  template         = data.xenorchestra_template.ubuntu.id
  cloud_config     = xenorchestra_cloud_config.web[each.key].template

  cpus       = var.vm_cpus
  memory_max = var.vm_memory_max

  disk {
    sr_id      = data.xenorchestra_sr.local_storage.id
    name_label = "${each.value}-root"
    size       = var.vm_disk_size
  }

  network {
    network_id = data.xenorchestra_network.net.id
  }

  auto_poweron = true
  wait_for_ip  = true
  power_state  = "Running"
}

# ---------------------
# Outputs
# ---------------------

output "vm_ids" {
  description = "IDs of the created VMs"
  value = {
    for name, vm in xenorchestra_vm.web : name => vm.id
  }
}

output "vm_ip_addresses" {
  description = "IP addresses of the created VMs (first detected)"
  value = {
    for name, vm in xenorchestra_vm.web : name => vm.ipv4_addresses
  }
}