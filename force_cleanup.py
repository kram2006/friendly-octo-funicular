import os
import subprocess
import glob

MINIMAL_TF = """terraform {
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
"""

def force_cleanup(base_dir):
    tfstate_files = glob.glob(os.path.join(base_dir, "**", "terraform.tfstate"), recursive=True)
    
    for tfstate in tfstate_files:
        workspace = os.path.dirname(tfstate)
        print(f"\nChecking workspace: {workspace}")
        
        main_tf_path = os.path.join(workspace, "main.tf")
        
        # Try normal destroy first
        res = subprocess.run(["terraform", "destroy", "-auto-approve", "-no-color"], cwd=workspace, capture_output=True, text=True)
        
        if res.returncode != 0:
            print(f"  Normal destroy failed. Triggering recovery destroy...")
            with open(main_tf_path, 'w') as f:
                f.write(MINIMAL_TF)
                
            subprocess.run(["terraform", "init"], cwd=workspace, capture_output=True, text=True)
            rec_res = subprocess.run(["terraform", "destroy", "-auto-approve", "-no-color"], cwd=workspace, capture_output=True, text=True)
            if rec_res.returncode == 0:
                print("  Recovery destroy succeeded.")
            else:
                print(f"  Recovery destroy failed: {rec_res.stderr.strip()}")
        else:
            print("  Normal destroy succeeded.")

if __name__ == "__main__":
    force_cleanup("results/terraform_code/phi4_or_COT")
