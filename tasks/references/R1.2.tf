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

# Look up the pool
data "xenorchestra_pool" "pool" {
  name_label = "DAO-Agentic-Infra"
}

# Look up all VMs in the pool using the xenorchestra_vms data source
data "xenorchestra_vms" "all_vms" {
  pool_id   = data.xenorchestra_pool.pool.id
  power_state = "Running"
}

# Also query halted VMs
data "xenorchestra_vms" "halted_vms" {
  pool_id     = data.xenorchestra_pool.pool.id
  power_state = "Halted"
}

# Output running VMs with RAM allocation
output "running_vms" {
  description = "List of all running VMs with their RAM allocation"
  value = [
    for vm in data.xenorchestra_vms.all_vms.vms : {
      name_label       = vm.name_label
      id               = vm.id
      power_state      = vm.power_state
      memory_max_bytes = vm.memory_max
      memory_max_gb    = format("%.2f GB", vm.memory_max / 1073741824)
    }
  ]
}

# Output halted VMs with RAM allocation
output "halted_vms" {
  description = "List of all halted VMs with their RAM allocation"
  value = [
    for vm in data.xenorchestra_vms.halted_vms.vms : {
      name_label       = vm.name_label
      id               = vm.id
      power_state      = vm.power_state
      memory_max_bytes = vm.memory_max
      memory_max_gb    = format("%.2f GB", vm.memory_max / 1073741824)
    }
  ]
}

# Summary output
output "vm_summary" {
  description = "Summary of all VMs and total RAM allocated"
  value = {
    total_running_vms = length(data.xenorchestra_vms.all_vms.vms)
    total_halted_vms  = length(data.xenorchestra_vms.halted_vms.vms)
    total_vms         = length(data.xenorchestra_vms.all_vms.vms) + length(data.xenorchestra_vms.halted_vms.vms)
    total_ram_allocated_gb = format("%.2f GB",
      (sum([for vm in data.xenorchestra_vms.all_vms.vms : vm.memory_max]) +
      sum([for vm in data.xenorchestra_vms.halted_vms.vms : vm.memory_max])) / 1073741824
    )
    available_ram_gb = "20.00 GB"
  }
}

# Pool information
output "pool_info" {
  description = "Pool information"
  value = {
    pool_name = data.xenorchestra_pool.pool.name_label
    pool_id   = data.xenorchestra_pool.pool.id
  }
}