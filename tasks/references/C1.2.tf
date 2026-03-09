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
}

data "xenorchestra_sr" "local_storage" {
  name_label = "Local storage"
}

# -------------------------------------------------------
# Variables
# -------------------------------------------------------

variable "vm_name" {
  description = "Name of the Ubuntu VM"
  type        = string
  default     = "ubuntu-vm-01"
}

variable "vm_cpus" {
  description = "Number of vCPUs for the VM"
  type        = number
  default     = 2
}

variable "vm_memory_gb" {
  description = "Memory in GB for the VM"
  type        = number
  default     = 2
}

variable "vm_disk_size_gb" {
  description = "Root disk size in GB (must be >= 50 to match the Ubuntu-22 template VDI)"
  type        = number
  default     = 50
}

# -------------------------------------------------------
# Resource – Ubuntu VM
# -------------------------------------------------------

resource "xenorchestra_vm" "ubuntu_vm" {
  name_label       = var.vm_name
  name_description = "Ubuntu 22 VM managed by Terraform"
  template         = data.xenorchestra_template.ubuntu.id
  cloud_config     = ""

  cpus = var.vm_cpus

  memory_max = var.vm_memory_gb * 1024 * 1024 * 1024 # Convert GB to bytes

  network {
    network_id = data.xenorchestra_network.net.id
  }

  disk {
    sr_id      = data.xenorchestra_sr.local_storage.id
    name_label = "${var.vm_name}-root"
    size       = var.vm_disk_size_gb * 1024 * 1024 * 1024 # Convert GB to bytes
  }

  tags = [
    "terraform-managed",
    "ubuntu"
  ]

  auto_poweron = true
  wait_for_ip  = false
}

# -------------------------------------------------------
# Outputs
# -------------------------------------------------------

output "vm_id" {
  description = "The ID of the created VM"
  value       = xenorchestra_vm.ubuntu_vm.id
}

output "vm_name" {
  description = "The name of the created VM"
  value       = xenorchestra_vm.ubuntu_vm.name_label
}