Looking at the error, the issue is that the VM template has a disk size of ~53.7GB (50GiB), and the Terraform code is trying to set a smaller disk size (20GB). The VDI size must be equal to or larger than the template's existing disk size.

I need to set the disk size to at least 53687091200 bytes (which is 50GiB) or larger.

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
}

data "xenorchestra_network" "network" {
  name_label = "Pool-wide network associated with eth0"
}

data "xenorchestra_sr" "sr" {
  name_label = "Local storage"
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