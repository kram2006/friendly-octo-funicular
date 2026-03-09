"""
prompt_templates.py

Enhancement strategy prompts for IaC evaluation.
All XenOrchestra platform constants are injected via xo_config dict
(read from openrouter_config.yaml → xenorchestra: section).

CoT and FSP examples deliberately use tasks NOT in the test set
(infra-ubuntu-node) to avoid data leakage.
"""


# ─────────────────────────────────────────────────────────────────────────────
# INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _boilerplate():
    """
    Return the mandatory Terraform boilerplate block for prompt examples.
    Common to all XenOrchestra tasks.
    BUG-C5 FIX: Omit specific credentials from examples to prevent leakage.
    Note: Actual execution uses credentials from environment variables.
    """
    return """terraform {
  required_providers {
    xenorchestra = {
      source  = "terra-farm/xenorchestra"
      version = "~> 0.26.0"
    }
  }
}

provider "xenorchestra" {
  url      = "ws://localhost:8080"
  username = var.xo_username
  password = var.xo_password
  insecure = true
}

data "xenorchestra_pool" "pool" {
  name_label = "DAO-Agentic-Infra"
}"""


# ─────────────────────────────────────────────────────────────────────────────
# CHAIN-OF-THOUGHT PROMPT
# Based on IaC-Eval paper (NeurIPS 2024) CoT template (Appendix B.2)
# Examples use non-test tasks (infra-ubuntu-node) to avoid data leakage.
# ─────────────────────────────────────────────────────────────────────────────

def CoT_prompt(question_prompt, task_category="CREATE"):
    """
    Wrap the user prompt with Chain-of-Thought instructions and a single, category-specific complete example.
    Aligned with official IaC-Eval (Appendix B.2) structure and wording.
    Examples use a consistent 'infra-ubuntu-node' to show a clear lifecycle across categories.
    """
    task_category = task_category.upper()

    # Define the single, comprehensive "Full Code" Master Example per category
    # Each example includes ALL blocks: terraform, provider, all data sources, and resource/output.
    # Refined to match state-of-the-art results (Claude 4.6 / Gemini) including cdrom, tags, and cloud_config.
    
    examples = {
        "CREATE": {
            "prompt": "Create a virtual machine named 'infra-ubuntu-node' with 2GB RAM and a 10GB disk.",
            "thought": "First, we identify the necessary Xen Orchestra resources: a VM (xenorchestra_vm) and four critical data sources (pool, network, storage repository, and template). We MUST use data sources to resolve ALL infrastructure IDs (e.g., template_id, sr_id, network_id) dynamically from the environment rather than using hardcoded UUIDs. Second, we configure the VM attributes: 'name_label' is 'infra-ubuntu-node', 'name_description' is 'Lifecycle node', 'memory_max' is 2147483648 bytes (2 GB), 'cpus' is 1, and 'auto_poweron' is true. Finally, we link all components together, including optional blocks like 'cdrom' (using a placeholder ID to demonstrate structure), 'tags', and 'cloud_config'.",
            "hcl": """terraform {
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
  pool_id    = data.xenorchestra_pool.pool.id
  name_label = "Ubuntu-22"
}

data "xenorchestra_sr" "sr" {
  pool_id    = data.xenorchestra_pool.pool.id
  name_label = "Local storage"
}

data "xenorchestra_network" "net" {
  pool_id    = data.xenorchestra_pool.pool.id
  name_label = "Pool-wide network associated with eth0"
}

resource "xenorchestra_vm" "infra_node" {
  name_label       = "infra-ubuntu-node"
  name_description = "Lifecycle node for evaluation"
  template         = data.xenorchestra_template.template.id
  cpus             = 1
  memory_max       = 2147483648
  auto_poweron     = true
  cloud_config     = ""
  wait_for_ip      = false

  tags = [
    "eval-env",
    "lifecycle-test"
  ]

  # Optional CDROM for ISO based installations
  # cdrom {
  #   id = "<TARGET-ISO-UUID>"
  # }

  disk {
    name_label = "node-disk"
    sr_id      = data.xenorchestra_sr.sr.id
    size       = 10737418240
  }

  network {
    network_id = data.xenorchestra_network.net.id
  }
}"""
        },
        "UPDATE": {
            "prompt": "Update the VM 'infra-ubuntu-node' to have 4GB RAM.",
            "thought": "First, we identify the existing resource config. Second, we update the 'memory_max' attribute to 4294967296 (4 GB) while keeping the 'name_label' as 'infra-ubuntu-node'. We ensure all IDs are resolved via the mandatory data sources (pool, SR, template, network) to maintain environment-specific accuracy. Finally, we ensure all boilerplate blocks like 'name_description', 'tags', and 'cloud_config' are present to maintain the configuration's integrity.",
            "hcl": """terraform {
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
  pool_id    = data.xenorchestra_pool.pool.id
  name_label = "Ubuntu-22"
}

data "xenorchestra_sr" "sr" {
  pool_id    = data.xenorchestra_pool.pool.id
  name_label = "Local storage"
}

data "xenorchestra_network" "net" {
  pool_id    = data.xenorchestra_pool.pool.id
  name_label = "Pool-wide network associated with eth0"
}

resource "xenorchestra_vm" "infra_node" {
  name_label       = "infra-ubuntu-node"
  name_description = "Lifecycle node updated memory"
  template         = data.xenorchestra_template.template.id
  cpus             = 1
  memory_max       = 4294967296
  auto_poweron     = true
  cloud_config     = ""
  wait_for_ip      = false

  tags = [
    "eval-env",
    "lifecycle-test"
  ]

  disk {
    name_label = "node-disk"
    sr_id      = data.xenorchestra_sr.sr.id
    size       = 10737418240
  }

  network {
    network_id = data.xenorchestra_network.net.id
  }
}"""
        },
        "READ": {
            "prompt": "Retrieve the management IP addresses of the VM 'infra-ubuntu-node'.",
            "thought": "First, we include the boilerplate and pool context. Second, we use the 'xenorchestra_vms' data source to query all VMs in the pool. Finally, we define a Terraform output with description and values, filtering the resulting VM list to only show the IPv4 addresses for 'infra-ubuntu-node'.",
            "hcl": """terraform {
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

data "xenorchestra_vms" "all_nodes" {
  pool_id = data.xenorchestra_pool.pool.id
}

output "node_ip" {
  description = "IPv4 addresses for the infra-ubuntu-node"
  value = { for vm in data.xenorchestra_vms.all_nodes.vms : vm.name_label => vm.ipv4_addresses if vm.name_label == "infra-ubuntu-node" }
}"""
        },
        "DELETE": {
            "prompt": "Remove the virtual machine 'infra-ubuntu-node'.",
            "thought": "In Terraform, deletion is achieved by removing the resource block from the configuration. For a deletion task, we provide the full provider and data lookups to maintain context, but omit the resource block for 'infra-ubuntu-node' entirely. This triggers a 'destroy' plan for the removed resource.",
            "hcl": """terraform {
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
}"""
        }
    }

    # Select the example for the category
    example = examples.get(task_category, examples["CREATE"])
    
    prompt_body = "Here is an example:\n\n"
    prompt_body += f"Example prompt: {example['prompt']}\n"
    prompt_body += f"Example output: Let's think step by step. {example['thought']}\n"
    prompt_body += f"```hcl\n{example['hcl']}\n```\n\n"

    footer = "Here is the actual prompt to answer. Let's think step by step:\n"
    return prompt_body + footer + question_prompt


# ─────────────────────────────────────────────────────────────────────────────
# FEW-SHOT PROMPT
# Based on IaC-Eval paper (NeurIPS 2024) FSP template (Appendix B.1)
# ─────────────────────────────────────────────────────────────────────────────

def FSP_prompt(question_prompt, task_category="CREATE"):
    """
    Wrap the user prompt with a single fully-worked, category-specific complete example.
    Aligned with official IaC-Eval (Appendix B.1) structure.
    Examples use a consistent 'infra-ubuntu-node' to show a clear lifecycle across categories.
    """
    task_category = task_category.upper()

    # Define the single, comprehensive "Full Code" Master Example per category
    
    examples = {
        "CREATE": {
            "prompt": "Create a virtual machine named 'infra-ubuntu-node' with 2GB RAM and a 10GB disk.",
            "hcl": """terraform {
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
  pool_id    = data.xenorchestra_pool.pool.id
  name_label = "Ubuntu-22"
}

data "xenorchestra_sr" "sr" {
  pool_id    = data.xenorchestra_pool.pool.id
  name_label = "Local storage"
}

data "xenorchestra_network" "net" {
  pool_id    = data.xenorchestra_pool.pool.id
  name_label = "Pool-wide network associated with eth0"
}

resource "xenorchestra_vm" "infra_node" {
  name_label       = "infra-ubuntu-node"
  name_description = "Lifecycle node for evaluation"
  template         = data.xenorchestra_template.template.id
  cpus             = 1
  memory_max       = 2147483648
  auto_poweron     = true
  cloud_config     = ""
  wait_for_ip      = false

  tags = [
    "eval-env",
    "lifecycle-test"
  ]

  # Optional CDROM for ISO based installations
  # cdrom {
  #   id = "<TARGET-ISO-UUID>"
  # }

  disk {
    name_label = "node-disk"
    sr_id      = data.xenorchestra_sr.sr.id
    size       = 10737418240
  }

  network {
    network_id = data.xenorchestra_network.net.id
  }
}"""
        },
        "UPDATE": {
            "prompt": "Update the VM 'infra-ubuntu-node' to have 4GB RAM.",
            "hcl": """terraform {
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
  pool_id    = data.xenorchestra_pool.pool.id
  name_label = "Ubuntu-22"
}

data "xenorchestra_sr" "sr" {
  pool_id    = data.xenorchestra_pool.pool.id
  name_label = "Local storage"
}

data "xenorchestra_network" "net" {
  pool_id    = data.xenorchestra_pool.pool.id
  name_label = "Pool-wide network associated with eth0"
}

resource "xenorchestra_vm" "infra_node" {
  name_label       = "infra-ubuntu-node"
  name_description = "Lifecycle node updated memory"
  template         = data.xenorchestra_template.template.id
  cpus             = 1
  memory_max       = 4294967296
  auto_poweron     = true
  cloud_config     = ""
  wait_for_ip      = false

  tags = [
    "eval-env",
    "lifecycle-test"
  ]

  disk {
    name_label = "node-disk"
    sr_id      = data.xenorchestra_sr.sr.id
    size       = 10737418240
  }

  network {
    network_id = data.xenorchestra_network.net.id
  }
}"""
        },
        "READ": {
            "prompt": "Retrieve the management IP addresses of the VM 'infra-ubuntu-node'.",
            "hcl": """terraform {
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

data "xenorchestra_vms" "all_nodes" {
  pool_id = data.xenorchestra_pool.pool.id
}

output "node_ip" {
  description = "IPv4 addresses for the infra-ubuntu-node"
  value = { for vm in data.xenorchestra_vms.all_nodes.vms : vm.name_label => vm.ipv4_addresses if vm.name_label == "infra-ubuntu-node" }
}"""
        },
        "DELETE": {
            "prompt": "Remove the virtual machine 'infra-ubuntu-node'.",
            "hcl": """terraform {
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
}"""
        }
    }

    # Select the example for the category
    example = examples.get(task_category, examples["CREATE"])
    
    prompt_body = "Here is an example:\n\n"
    prompt_body += f"Example prompt: {example['prompt']}\n"
    prompt_body += f"Example output:\n```hcl\n{example['hcl']}\n```\n\n"

    footer = "Here is the actual prompt to answer:\n"
    return prompt_body + footer + question_prompt


# ─────────────────────────────────────────────────────────────────────────────
# REPAIR PROMPTS (Multi-turn)
# Based on IaC-Eval paper (NeurIPS 2024) Multi-turn approach.
# ─────────────────────────────────────────────────────────────────────────────

def multi_turn_plan_error_prompt(question_prompt, candidate_config, error_message):
    """
    Build the descriptive context format used by the IaC-Eval evaluation engine for multi-turn (Appendix B.3).
    Headers align with official research standards.
    """
    if "SPEC ACCURACY ERRORS" in error_message:
        # Research-Standard structure (B.3) using official rigid headers
        prompt = """Here is the actual prompt:
{}

Here is the incorrect configuration:
{}

Give me the full complete code, without these below errors:

{}""".format(question_prompt, candidate_config, error_message)
    else:
        # Research-Standard structure (B.3) using official rigid headers
        prompt = """Here is the actual prompt:
{}

Here is the incorrect configuration:
{}

Here is the Terraform plan error message (potentially empty):
{}

Give me the full complete code, without these below errors:""".format(question_prompt, candidate_config, error_message)
    
    return prompt

def multi_error_prompt(question_prompt, error_history):
    """
    Build the descriptive context format for the 'multi-error' strategy.
    Includes the original prompt and the last 2 error messages, but NO incorrect code.
    """
    # Take only the last 2 errors from history
    recent_errors = error_history[-2:] if len(error_history) >= 2 else error_history
    
    error_text = ""
    for idx, err in enumerate(recent_errors):
        error_text += f"\nError {idx + 1}:\n{err}\n"
    
    prompt = """Here is the actual prompt:
{}

Give me the full complete code, without these below errors:

{}
""".format(question_prompt, error_text)
    
    return prompt


def dataset_prompt(question_prompt):
    """
    High-fidelity prompt for ground truth dataset generation.
    """
    return f"""TASK:
Generate the definitive ground-truth Terraform HCL for the following infrastructure requirement.

REQUIREMENT:
{question_prompt}

Follow the structural rules defined in the system prompt. RESOLVE ALL IDENTIFIERS using data sources.
Provide the code in a single ```hcl block.
"""


def dataset_repair_prompt(question_prompt, error_history):
    """
    Multi-turn repair prompt for ground truth dataset generation.
    Passes the last two errors in XML format for high-fidelity correction.
    """
    # Take only the last 2 errors from history
    recent_errors = error_history[-2:] if len(error_history) >= 2 else error_history
    
    error_text = ""
    for idx, err in enumerate(recent_errors):
        error_text += f"ERROR {idx + 1}:\n{err}\n\n"
    
    return f"""TASK:
Refine the ground-truth Terraform HCL to resolve the documented errors.

ORIGINAL REQUIREMENT:
{question_prompt}

ERROR HISTORY:
{error_text}

INSTRUCTION:
The generation MUST NOT contain the errors listed above. Provide a single, complete, and definitive ground-truth HCL block using standard Markdown (```hcl).

Follow the structural rules defined in the system prompt.
"""
