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

data "xenorchestra_network" "network" {
  name_label = "Pool-wide network associated with eth0"
}

data "xenorchestra_sr" "local_storage" {
  name_label = "Local storage"
}

# ---------------------
# Variables
# ---------------------

variable "vm_count" {
  description = "Number of Ubuntu VMs to create"
  type        = number
  default     = 10
}

variable "vm_memory" {
  description = "Memory per VM in bytes (3GB)"
  type        = number
  default     = 3221225472 # 3 * 1024^3
}

variable "vm_cpus" {
  description = "Number of vCPUs per VM"
  type        = number
  default     = 3
}

variable "vm_disk_size" {
  description = "Disk size per VM in bytes (50GB - matches template VDI size)"
  type        = number
  default     = 53687091200 # 50 * 1024^3
}

variable "vm_name_prefix" {
  description = "Prefix for VM names"
  type        = string
  default     = "ubuntu-vm"
}

# ---------------------
# Cloud Config
# ---------------------

resource "xenorchestra_cloud_config" "ubuntu_config" {
  count = var.vm_count

  name = "${var.vm_name_prefix}-${format("%02d", count.index + 1)}-cloud-config"

  template = <<-EOF
    #cloud-config
    hostname: ${var.vm_name_prefix}-${format("%02d", count.index + 1)}
    manage_etc_hosts: true
    users:
      - name: ubuntu
        sudo: ALL=(ALL) NOPASSWD:ALL
        shell: /bin/bash
        lock_passwd: false
    package_update: true
    packages:
      - qemu-guest-agent
    runcmd:
      - systemctl enable qemu-guest-agent
      - systemctl start qemu-guest-agent
  EOF
}

# ---------------------
# Virtual Machines
# ---------------------

resource "xenorchestra_vm" "ubuntu_vm" {
  count = var.vm_count

  name_label       = "${var.vm_name_prefix}-${format("%02d", count.index + 1)}"
  name_description = "Ubuntu 22.04 VM ${count.index + 1} of ${var.vm_count}"
  template         = data.xenorchestra_template.ubuntu.id
  cloud_config     = xenorchestra_cloud_config.ubuntu_config[count.index].template

  cpus       = var.vm_cpus
  memory_max = var.vm_memory

  disk {
    sr_id      = data.xenorchestra_sr.local_storage.id
    name_label = "${var.vm_name_prefix}-${format("%02d", count.index + 1)}-disk"
    size       = var.vm_disk_size
  }

  network {
    network_id = data.xenorchestra_network.network.id
  }

  tags = [
    "ubuntu",
    "managed-by-terraform"
  ]

  wait_for_ip = false
}

# ---------------------
# Outputs
# ---------------------

output "vm_names" {
  description = "Names of all created VMs"
  value       = xenorchestra_vm.ubuntu_vm[*].name_label
}

output "vm_ids" {
  description = "IDs of all created VMs"
  value       = xenorchestra_vm.ubuntu_vm[*].id
}

output "vm_summary" {
  description = "Summary of VM resource allocation"
  value = {
    total_vms      = var.vm_count
    ram_per_vm_gb  = var.vm_memory / pow(1024, 3)
    total_ram_gb   = (var.vm_count * var.vm_memory) / pow(1024, 3)
    cpus_per_vm    = var.vm_cpus
    total_cpus     = var.vm_count * var.vm_cpus
    disk_per_vm_gb = var.vm_disk_size / pow(1024, 3)
    total_disk_gb  = (var.vm_count * var.vm_disk_size) / pow(1024, 3)
  }
}