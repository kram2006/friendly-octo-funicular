import os
import sys
import shutil
import logging
import argparse
import hashlib
import re
import json
import uuid
import yaml
import csv
import asyncio
import glob
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Fix for Windows asyncio subprocesses
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api_client import OpenRouterClient, LocalTransformersClient
from logger import setup_logger, log_step, log_error
from eval_utils import (
    unload_ollama_model, execute_command, GREEN, RED, CYAN, YELLOW, BOLD, RESET
)
from eval_core import evaluate_task
from models import GlobalConfig, ModelConfig

MAX_CHAIN_SLUG_LENGTH = 50
CHAIN_HASH_LENGTH = 16
# A terraform.tfstate file must contain at least this many bytes to be considered
# non-empty and worth copying or snapshotting.  Files strictly below this threshold
# are stubs (e.g. {} = 2 bytes) and are silently skipped.
TFSTATE_MIN_VALID_BYTES = 11
PLACEHOLDER_PATTERN = re.compile(r'^\$\{[^}]+\}$')
DEFAULT_OPENROUTER_TIMEOUT = 300
DEFAULT_OPENROUTER_MAX_RETRIES = 3
# Normalized-lowercase IDs for the fixed 10-task benchmark independent cleanup set.
INDEPENDENT_TASK_IDS = {"c1.1", "c1.2", "c2.2", "c5.2"}
# Fixed chain fallback rules for the 10-task benchmark:
# chain 1: C1.3/U1.2 failures fall through to D1.2 cleanup;
# chain 2: C2.3/R1.2 failures fall through to D2.2 cleanup.
CHAIN_FALLBACK_DELETE_TASK_BY_FAILURE = {
    "c1.3": "d1.2",
    "u1.2": "d1.2",
    "c2.3": "d2.2",
    "r1.2": "d2.2",
}
FIXED_BENCHMARK_TASK_ORDER = [
    "c1.1", "c1.2", "c2.2", "c5.2",
    "c1.3", "u1.2", "d1.2",
    "c2.3", "r1.2", "d2.2",
]
PARTIAL_CHAIN_GROUPS = [
    ["c1.3", "u1.2", "d1.2"],
    ["c2.3", "r1.2", "d2.2"],
]
PARTIAL_CHAIN_GROUPS_BY_START = {group[0]: group for group in PARTIAL_CHAIN_GROUPS}

def _validate_local_path(path_value, arg_name):
    normalized = os.path.normpath(path_value)
    path_parts = normalized.split(os.sep)
    if ".." in path_parts:
        raise ValueError(f"Invalid {arg_name} path: parent directory traversal is not allowed.")
    return normalized

def _is_unresolved_placeholder(value):
    return isinstance(value, str) and bool(PLACEHOLDER_PATTERN.match(value.strip()))

def _normalize_positive_int(value, fallback):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else fallback
    except (TypeError, ValueError):
        return fallback

def _next_chain_index_after_result(tasks, current_index, task_success):
    """Decide next chain index based on task outcome and cleanup progression rules."""
    if task_success:
        next_index = current_index + 1
        return next_index if next_index < len(tasks) else None

    failed_task_id = str(tasks[current_index].get("task_id", "")).strip().lower()
    fallback_delete_task_id = CHAIN_FALLBACK_DELETE_TASK_BY_FAILURE.get(failed_task_id)
    if not fallback_delete_task_id:
        return None
    for idx in range(current_index + 1, len(tasks)):
        if str(tasks[idx].get("task_id", "")).strip().lower() == fallback_delete_task_id:
            return idx
    return None

def _order_fixed_benchmark_tasks(dataset_tasks):
    """Return tasks in fixed benchmark order for the 10-task evaluation scope."""
    tasks_by_id = {str(row.get("task_id", "")).strip().lower(): row for row in dataset_tasks}
    missing = [task_id for task_id in FIXED_BENCHMARK_TASK_ORDER if task_id not in tasks_by_id]
    if missing:
        raise ValueError(f"Dataset is missing required benchmark tasks: {', '.join(missing)}")
    return [tasks_by_id[task_id] for task_id in FIXED_BENCHMARK_TASK_ORDER]

def _preserve_tfstate_snapshot(workspace_dir, snapshot_label=None):
    """Preserve a pre-destroy terraform state snapshot as JSON."""
    tfstate_path = os.path.join(workspace_dir, "terraform.tfstate")
    if not os.path.exists(tfstate_path) or os.path.getsize(tfstate_path) == 0:
        return None

    snapshots_dir = os.path.join(workspace_dir, "state_snapshots")
    os.makedirs(snapshots_dir, exist_ok=True)
    label = snapshot_label or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    snapshot_path = os.path.join(snapshots_dir, f"terraform_tfstate_pre_destroy_{label}.json")
    if os.path.exists(snapshot_path):
        unique_label = f"{label}_{uuid.uuid4().hex[:8]}"
        snapshot_path = os.path.join(snapshots_dir, f"terraform_tfstate_pre_destroy_{unique_label}.json")

    try:
        with open(tfstate_path, "r", encoding="utf-8") as src:
            tfstate_data = json.load(src)
        with open(snapshot_path, "w", encoding="utf-8") as dst:
            json.dump(tfstate_data, dst, indent=2)
    except (OSError, json.JSONDecodeError) as exc:
        log_error(f"Failed to preserve terraform state snapshot for {workspace_dir}: {exc}")
        return None

    log_step(f"Saved pre-destroy terraform state snapshot: {snapshot_path}")
    return snapshot_path

def _copy_chain_tfstate(src_workspace, dst_workspace):
    """Copy terraform.tfstate from a previous chain task workspace into the next task's workspace.

    This is how Terraform state flows through a chain: each task starts with the state
    produced by the last successful task, so Terraform can see and act on existing resources
    (e.g. UPDATE or DELETE the VM that CREATE built).  If the source state file is absent or
    empty the copy is silently skipped and the destination task starts with a clean slate.
    """
    src = os.path.join(src_workspace, "terraform.tfstate")
    if not os.path.exists(src) or os.path.getsize(src) < TFSTATE_MIN_VALID_BYTES:
        return
    dst = os.path.join(dst_workspace, "terraform.tfstate")
    shutil.copy2(src, dst)
    log_step(f"Copied chain terraform state: {src} -> {dst}")

def load_config(config_path):
    import re
    # Custom loader to handle env vars
    pattern = re.compile(r'\$\{([^}^{]+)\}')
    
    # Use a custom Loader class to avoid global state pollution
    class EnvVarLoader(yaml.SafeLoader):
        pass
    
    def env_var_constructor(loader, node):
        value = loader.construct_scalar(node)
        match = pattern.match(value)
        if match:
            env_var = match.group(1)
            return os.environ.get(env_var, value)
        return value

    # Register the resolver only for this specific loader instance
    EnvVarLoader.add_implicit_resolver('!env', pattern, None)
    EnvVarLoader.add_constructor('!env', env_var_constructor)
    
    with open(config_path, 'r') as f:
        config = yaml.load(f, Loader=EnvVarLoader)
        
    def expand_env_vars(data):
        if isinstance(data, dict):
            return {k: expand_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [expand_env_vars(v) for v in data]
        elif isinstance(data, str):
            res = pattern.search(data)
            if res:
                var_name = res.group(1)
                val = os.environ.get(var_name)
                if val:
                    return data.replace(res.group(0), val)
            return data
        return data
        
    expanded = expand_env_vars(config)
    
    # Validate with Pydantic
    try:
        GlobalConfig(**expanded)
        logging.info(f"Config {config_path} validated successfully.")
    except Exception as e:
        raise ValueError(f"Config validation failed for {config_path}: {e}") from e
        
    return expanded

async def main():
    parser = argparse.ArgumentParser(description="IaC Evaluation Framework")
    parser.add_argument("--config", default="config/openrouter_config.yaml", help="Path to config file")
    parser.add_argument("--output_dir", default="results", help="Directory to save results")
    parser.add_argument("--dataset", default="tasks/vm_provisioning_tasks.csv", help="Path to dataset")
    parser.add_argument("--model", default="phi4_openrouter", help="Model key from config")
    parser.add_argument("--task_id", help="Run specific task ID")
    parser.add_argument("--chain", help="Comma-separated list of task IDs to run as a chain (sharing state)")
    parser.add_argument("--samples", type=int, default=1, help="Number of independent samples per task for Pass@k (default=1)")
    parser.add_argument("--pass", type=int, default=None, dest="pass_num", help="Run as a specific pass number (1-indexed).")
    parser.add_argument("--plan-only", action="store_true", dest="plan_only", help="Skip terraform apply, evaluate based on Plan only")
    parser.add_argument("--no-confirm", action="store_true", dest="no_confirm", help="Skip manual authorization prompts")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for LLM calls")
    parser.add_argument("--enhance-strat", "-e", dest="enhance_strat", choices=["", "COT", "FSP", "multi-turn", "multi-error", "dataset"], default="", help="Prompt enhancement strategy")
    parser.add_argument("--compare-with-ground-truth", dest="compare_ground_truth", action="store_true", help="Compare results with ground truth after evaluation completes")
    parser.add_argument("--ground-truth-dir", dest="ground_truth_dir", default="ground_truth_results", help="Directory containing ground truth results (default: ground_truth_results)")

    args = parser.parse_args()
    args.config = _validate_local_path(args.config, "--config")
    args.dataset = _validate_local_path(args.dataset, "--dataset")
    args.output_dir = _validate_local_path(args.output_dir, "--output_dir")

    if args.chain and args.plan_only:
        print(f"\n{RED}{BOLD}ERROR: --plan-only is incompatible with --chain.{RESET}")
        return
    
    expanded_config = load_config(args.config)
    
    model_name = args.model
    if model_name not in expanded_config['models']:
        available = ", ".join(sorted(expanded_config.get('models', {}).keys()))
        print(f"{RED}Error: Model '{model_name}' not found in config. Available models: {available}{RESET}")
        return
    
    expanded_config['active_model_name'] = model_name
    model_config = expanded_config['models'][model_name]

    # Initialize model-specific logging
    folder_name = model_config.get('folder_name', model_name)
    if args.enhance_strat:
        folder_name = f"{folder_name}_{args.enhance_strat}"
    
    log_dir = os.path.join(args.output_dir, "logs", folder_name)
    setup_logger(log_dir)
    
    base_seed = args.seed if args.seed is not None else model_config.get('seed')

    def create_client(sample_seed=None):
        if model_config.get('local'):
            return LocalTransformersClient(
                model_name=model_config['name'],
                temperature=model_config.get('temperature', 0.2),
                max_tokens=model_config.get('max_tokens', 4096),
                seed=sample_seed
            )

        api_key = model_config.get('api_key') or os.environ.get('OPENROUTER_API_KEY') or expanded_config.get('openrouter', {}).get('api_key')
        if _is_unresolved_placeholder(api_key):
            raise ValueError(
                f"Unresolved API key placeholder for model '{model_name}': {api_key}. "
                "Set the referenced environment variable before running evaluation."
            )
        base_url = model_config.get('base_url') or expanded_config.get('openrouter', {}).get('base_url', "https://openrouter.ai/api/v1/chat/completions")
        openrouter_cfg = expanded_config.get('openrouter', {})
        timeout = _normalize_positive_int(
            model_config.get('timeout', openrouter_cfg.get('timeout', DEFAULT_OPENROUTER_TIMEOUT)),
            DEFAULT_OPENROUTER_TIMEOUT
        )
        max_retries = _normalize_positive_int(
            model_config.get('max_retries', openrouter_cfg.get('max_retries', DEFAULT_OPENROUTER_MAX_RETRIES)),
            DEFAULT_OPENROUTER_MAX_RETRIES
        )
        return OpenRouterClient(
            api_key=api_key,
            model_name=model_config['name'],
            temperature=model_config.get('temperature', 0.2),
            max_tokens=model_config.get('max_tokens', 4096),
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            seed=sample_seed
        )

    # Load Tasks
    dataset_tasks = []
    with open(args.dataset, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            dataset_tasks.append(row)

    tasks = dataset_tasks
    if args.task_id:
        if args.chain:
            print(f"{RED}Error: --task_id cannot be used together with --chain.{RESET}")
            return
        tasks = [row for row in dataset_tasks if row['task_id'].lower() == args.task_id.lower()]

    if not tasks:
        print(f"{RED}No tasks found matching criteria.{RESET}")
        return

    # Filter for chain if requested
    if args.chain:
        chain_ids = [tid.strip().lower() for tid in args.chain.split(',') if tid.strip()]
        if not chain_ids:
            print(f"{RED}Error: --chain must contain at least one task ID.{RESET}")
            return

        duplicates = sorted({tid for tid in chain_ids if chain_ids.count(tid) > 1})
        if duplicates:
            print(f"{RED}Error: Duplicate task IDs in --chain: {', '.join(duplicates)}{RESET}")
            return

        all_tasks_by_id = {row['task_id'].lower(): row for row in dataset_tasks}
        missing = [tid for tid in chain_ids if tid not in all_tasks_by_id]
        if missing:
            available = ", ".join(sorted(all_tasks_by_id.keys()))
            print(
                f"{RED}Error: Unknown task IDs in --chain: {', '.join(missing)}. "
                f"Available task IDs: {available}{RESET}"
            )
            return

        tasks = [all_tasks_by_id[tid] for tid in chain_ids]
    elif not args.task_id:
        # BUG-H9 FIX: Updated comment - tasks run sequentially, not concurrently
        # Fixed benchmark mode: tasks and chain groups run sequentially in dependency order.
        # Each task/group completes (including VM cleanup) before the next begins.
        tasks = _order_fixed_benchmark_tasks(dataset_tasks)

    # Pass@k Loop
    num_passes = args.samples
    pass_start = 0
    if args.pass_num is not None:
        # BUG-H8 FIX: Validate pass number >= 1
        if args.pass_num < 1:
            print(f"{RED}Error: --pass must be >= 1{RESET}")
            return
        num_passes = 1
        pass_start = args.pass_num - 1
    
    # --- Parallel Execution Logic ---
    async def run_sample(pass_idx):
        """Run a single Pass@k sample (standalone or chain)."""
        pass_num = pass_idx + 1
        sample_seed = (base_seed + pass_idx) if base_seed is not None else None
        client = create_client(sample_seed)
        log_step(f"Starting Pass {pass_num}")
        cleanup_workspaces = []
        xo_cfg = expanded_config.get('xenorchestra', {})
        tf_env = {
            'TF_VAR_xo_username': xo_cfg.get('username') or os.environ.get('XO_USERNAME', ''),
            'TF_VAR_xo_password': xo_cfg.get('password') or os.environ.get('XO_PASSWORD', '')
        }
        
        workspace_dir = None
        base_folder_name = model_config.get('folder_name', model_name)
        effective_folder_name = f"{base_folder_name}_{args.enhance_strat}" if args.enhance_strat else base_folder_name
        
        async def cleanup_workspace_if_state_exists(cleanup_workspace):
            tfstate_path = os.path.join(cleanup_workspace, "terraform.tfstate")
            if not os.path.exists(tfstate_path):
                return
            sanitized_label = re.sub(r"[^A-Za-z0-9_-]+", "_", os.path.basename(cleanup_workspace))
            normalized_label = re.sub(r"_+", "_", sanitized_label)
            workspace_label = normalized_label.strip("_")
            _preserve_tfstate_snapshot(cleanup_workspace, snapshot_label=workspace_label)
            destroy_res = await execute_command(
                "terraform destroy -auto-approve -no-color",
                cwd=cleanup_workspace,
                timeout=300,
                env=tf_env
            )
            if destroy_res.get('exit_code') != 0:
                print(f"\n{RED}{BOLD}[TERRAFORM DESTROY FAILED]{RESET}")
                print(f"{RED}Exit Code: {destroy_res.get('exit_code')}{RESET}")
                print(f"{RED}Error Output:{RESET}\n{destroy_res.get('stderr', '')}")
                log_error(f"Cleanup failed for {cleanup_workspace}: {destroy_res.get('stderr', '')}")
                log_step("Executing Recovery Destroy mechanism...")
                
                # Write a minimal valid main.tf to force terraform to use the state file for destruction
                minimal_tf = """terraform {
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
                try:
                    main_tf_path = os.path.join(cleanup_workspace, "main.tf")
                    with open(main_tf_path, 'w') as f:
                        f.write(minimal_tf)
                    
                    # Re-initialize to resolve any lockfile or provider consistency errors from the minimal tf
                    await execute_command(
                        "terraform init",
                        cwd=cleanup_workspace,
                        timeout=120,
                        print_output=False,
                        env=tf_env
                    )
                    
                    # Retry destroy with the minimal manifest
                    recovery_res = await execute_command(
                        "terraform destroy -auto-approve -no-color",
                        cwd=cleanup_workspace,
                        timeout=300,
                        env=tf_env
                    )
                    if recovery_res.get('exit_code') == 0:
                        log_step(f"Recovery Destroy succeeded for {cleanup_workspace}.")
                    else:
                        error_msg = f"Recovery Destroy also failed for {cleanup_workspace}: {recovery_res.get('stderr', '')}"
                        log_error(error_msg)
                        print(f"\n{RED}{BOLD}⚠ CRITICAL: Recovery Destroy Failed!{RESET}")
                        print(f"{RED}Workspace: {cleanup_workspace}{RESET}")
                        print(f"{RED}This may leave orphaned VMs on the platform.{RESET}")
                        print(f"{RED}Manual cleanup may be required.{RESET}")
                        print(f"{YELLOW}Check XenOrchestra for orphaned resources.{RESET}\n")
                except Exception as e:
                    log_error(f"Failed to execute Recovery Destroy: {e}")
                    print(f"\n{RED}{BOLD}⚠ CRITICAL: Exception during Recovery Destroy!{RESET}")
                    print(f"{RED}Error: {e}{RESET}")
                    print(f"{RED}Manual cleanup may be required.{RESET}\n")

        if args.chain:
            # Chained mode: each task runs in its own workspace directory.
            # The terraform.tfstate is passed forward explicitly from the last successful
            # task so Terraform can see existing resources (e.g. UPDATE / DELETE the VM
            # that a previous CREATE step provisioned).
            #
            # State fallback: if task N fails, task N+1 (the cleanup/fallback task)
            # receives the state from the last SUCCESSFUL task, not from the failed one.
            # Example: D1.2 receives C1.3's state when U1.2 fails.
            chain_ids = [t['task_id'].replace('.', '_') for t in tasks]
            chain_slug = "_".join(chain_ids)
            if len(chain_slug) > MAX_CHAIN_SLUG_LENGTH:
                chain_slug = hashlib.sha256(chain_slug.encode("utf-8")).hexdigest()[:CHAIN_HASH_LENGTH]

            chain_state_workspace = None   # workspace holding the last successfully applied state
            chain_last_task_workspace = None  # last executed workspace, used for final cleanup

            i = 0
            while i < len(tasks):
                task_spec = tasks[i]
                task_id_slug = task_spec['task_id'].replace('.', '_')
                task_category = task_spec.get('category', '').strip().upper()
                task_plan_only = args.plan_only or (task_category == 'READ')

                # Per-task workspace — each chain step writes its own main.tf here.
                task_workspace = os.path.join(
                    args.output_dir,
                    "terraform_code",
                    effective_folder_name,
                    f"chain_{chain_slug}_{task_id_slug}_p{pass_num}"
                )
                os.makedirs(task_workspace, exist_ok=True)
                cleanup_workspaces.append(task_workspace)
                chain_last_task_workspace = task_workspace

                # Pass state from the last successful task into this task's workspace so
                # Terraform can plan updates/deletes against the existing infrastructure.
                if chain_state_workspace:
                    _copy_chain_tfstate(chain_state_workspace, task_workspace)

                # READ tasks execute in an isolated read workspace so they do not write
                # back into the chain state; the dependent-context tfstate is sourced from
                # task_workspace (where the state was copied to above).
                actual_workspace = task_workspace
                if task_category == 'READ':
                    actual_workspace = os.path.join(
                        args.output_dir,
                        "terraform_code",
                        effective_folder_name,
                        f"chain_{chain_slug}_read_{task_spec['task_id'].replace('.', '_')}_p{pass_num}"
                    )
                    os.makedirs(actual_workspace, exist_ok=True)
                    cleanup_workspaces.append(actual_workspace)

                task_result = await evaluate_task(
                    task=task_spec,
                    config=expanded_config,
                    client=client,
                    output_dir=args.output_dir,
                    workspace_override=actual_workspace,
                    plan_only=task_plan_only,
                    sample_num=pass_num,
                    chain_index=i,
                    state_workspace_override=task_workspace,
                    no_confirm=args.no_confirm,
                    enhance_strat=args.enhance_strat,
                    return_result=True
                )
                # Advance the authoritative chain state only when the task successfully
                # applied (READ tasks are plan-only and never modify the shared state).
                if task_result.get("success") and task_category != 'READ':
                    chain_state_workspace = task_workspace

                next_index = _next_chain_index_after_result(tasks, i, task_result.get("success", False))
                if next_index is None:
                    break
                is_fallback_jump = next_index > i + 1
                if is_fallback_jump:
                    log_step(
                        f"Task {task_spec.get('task_id')} failed; skipping intermediate chain tasks and continuing with cleanup task {tasks[next_index].get('task_id')}"
                    )
                i = next_index

            # Destroy infrastructure using the last executed task's workspace, which holds
            # the most current terraform.tfstate for the chain.
            if not args.plan_only and chain_last_task_workspace:
                await cleanup_workspace_if_state_exists(chain_last_task_workspace)
        else:
            # Sequential benchmark mode: tasks run one after another in the fixed order.
            # Each independent task starts with a fresh workspace (no shared state with other tasks).
            # Each chain group shares a workspace internally; that workspace is destroyed after the
            # group completes. All evaluation artifacts (dataset JSON, logs, terraform files) are
            # written by evaluate_task/eval_core before cleanup runs.
            task_lookup = {str(t.get("task_id", "")).strip().lower(): t for t in tasks}

            async def run_independent_task(task_spec):
                tid = task_spec.get('task_id', '').replace('.', '_')
                sample_workspace = os.path.join(
                    args.output_dir,
                    "terraform_code",
                    effective_folder_name,
                    f"{tid}_p{pass_num}"
                )
                os.makedirs(sample_workspace, exist_ok=True)
                cleanup_workspaces.append(sample_workspace)

                await evaluate_task(
                    task=task_spec,
                    config=expanded_config,
                    client=client,
                    output_dir=args.output_dir,
                    workspace_override=sample_workspace,
                    sample_num=pass_num,
                    plan_only=args.plan_only,
                    no_confirm=args.no_confirm,
                    enhance_strat=args.enhance_strat,
                    return_result=False
                )
                # evaluate_task writes all artifacts (dataset JSON, logs, terraform files) before
                # returning. Destroy VMs now so the next task starts on clean infrastructure.
                if not args.plan_only:
                    await cleanup_workspace_if_state_exists(sample_workspace)

            async def run_chain_group(chain_group_ids):
                chain_tasks = [task_lookup[tid] for tid in chain_group_ids if tid in task_lookup]
                if len(chain_tasks) != len(chain_group_ids):
                    return
                chain_task_names = [t.get('task_id', '').replace('.', '_') for t in chain_tasks]
                chain_slug = "_".join(chain_task_names)
                if len(chain_slug) > MAX_CHAIN_SLUG_LENGTH:
                    chain_slug = hashlib.sha256(chain_slug.encode("utf-8")).hexdigest()[:CHAIN_HASH_LENGTH]

                # Each task in the chain runs in its own workspace directory.
                # The terraform.tfstate is passed forward explicitly from the last successful
                # task so Terraform can see existing resources (UPDATE / DELETE the VM that
                # a previous CREATE step provisioned).
                #
                # State fallback: if task N fails, the fallback cleanup task receives the
                # state from the last SUCCESSFUL task, not from the failed one.
                # Example: D1.2 receives C1.3's state when U1.2 fails.
                chain_state_workspace = None   # workspace holding the last successfully applied state
                chain_last_task_workspace = None  # last executed workspace, used for final cleanup

                i = 0
                while i < len(chain_tasks):
                    chain_task_spec = chain_tasks[i]
                    chain_task_id_slug = chain_task_spec.get('task_id', '').replace('.', '_')
                    chain_task_category = chain_task_spec.get('category', '').strip().upper()
                    chain_task_plan_only = args.plan_only or (chain_task_category == 'READ')

                    # Per-task workspace — each chain step writes its own main.tf here.
                    per_task_workspace = os.path.join(
                        args.output_dir,
                        "terraform_code",
                        effective_folder_name,
                        f"chain_{chain_slug}_{chain_task_id_slug}_p{pass_num}"
                    )
                    os.makedirs(per_task_workspace, exist_ok=True)
                    cleanup_workspaces.append(per_task_workspace)
                    chain_last_task_workspace = per_task_workspace

                    # Pass state from the last successful task into this task's workspace.
                    if chain_state_workspace:
                        _copy_chain_tfstate(chain_state_workspace, per_task_workspace)

                    # READ tasks execute in an isolated read workspace so they do not write
                    # back into the chain state; dependent-context tfstate is sourced from
                    # per_task_workspace (where the state was copied to above).
                    chain_task_workspace = per_task_workspace
                    if chain_task_category == 'READ':
                        chain_task_workspace = os.path.join(
                            args.output_dir,
                            "terraform_code",
                            effective_folder_name,
                            f"chain_{chain_slug}_read_{chain_task_spec.get('task_id', '').replace('.', '_')}_p{pass_num}"
                        )
                        os.makedirs(chain_task_workspace, exist_ok=True)
                        cleanup_workspaces.append(chain_task_workspace)

                    chain_result = await evaluate_task(
                        task=chain_task_spec,
                        config=expanded_config,
                        client=client,
                        output_dir=args.output_dir,
                        workspace_override=chain_task_workspace,
                        plan_only=chain_task_plan_only,
                        sample_num=pass_num,
                        chain_index=i,
                        state_workspace_override=per_task_workspace,
                        no_confirm=args.no_confirm,
                        enhance_strat=args.enhance_strat,
                        return_result=True
                    )
                    # Advance the authoritative chain state only when the task successfully
                    # applied (READ tasks are plan-only and never modify the shared state).
                    if chain_result.get("success") and chain_task_category != 'READ':
                        chain_state_workspace = per_task_workspace

                    next_index = _next_chain_index_after_result(chain_tasks, i, chain_result.get("success", False))
                    if next_index is None:
                        break
                    i = next_index

                # Destroy infrastructure using the last executed task's workspace, which
                # holds the most current terraform.tfstate for the chain.
                if not args.plan_only and chain_last_task_workspace:
                    await cleanup_workspace_if_state_exists(chain_last_task_workspace)

            # Execute tasks and chain groups sequentially in fixed benchmark order.
            # Independent tasks have no shared state with each other or with chain groups.
            seen_chain_ids = set()
            for task_spec in tasks:
                task_id_normalized = str(task_spec.get("task_id", "")).strip().lower()
                if task_id_normalized in seen_chain_ids:
                    continue
                chain_group = PARTIAL_CHAIN_GROUPS_BY_START.get(task_id_normalized)
                if chain_group:
                    await run_chain_group(chain_group)
                    seen_chain_ids.update(chain_group)
                else:
                    await run_independent_task(task_spec)

    base_folder_name = model_config.get("folder_name", model_name)
    # Lock is scoped to the effective output folder (model + optional enhance strategy suffix)
    # so independent strategy runs can proceed without sharing a dataset directory/lock.
    effective_lock_folder = f"{base_folder_name}_{args.enhance_strat}" if args.enhance_strat else base_folder_name
    dataset_lock_dir = os.path.join(args.output_dir, "dataset", effective_lock_folder)
    os.makedirs(dataset_lock_dir, exist_ok=True)
    lockfile_path = os.path.join(dataset_lock_dir, ".evaluation_in_progress")
    if os.path.exists(lockfile_path):
        print(
            f"{RED}ERROR: Evaluation already in progress for this model output folder "
            f"({lockfile_path}). Remove the lockfile if no evaluation is running.{RESET}"
        )
        return

    # Check available disk space for long runs
    if num_passes >= 10:
        import shutil
        try:
            stat = shutil.disk_usage(args.output_dir)
            free_gb = stat.free / (1024**3)
            # Estimate: ~100MB per task × 10 tasks × num_passes
            estimated_gb_needed = (0.1 * 10 * num_passes)

            print(f"\n{BOLD}Disk Space Check:{RESET}")
            print(f"  Available: {free_gb:.1f} GB")
            print(f"  Estimated needed: {estimated_gb_needed:.1f} GB")

            if free_gb < estimated_gb_needed:
                print(f"{RED}⚠ WARNING: Low disk space! Available ({free_gb:.1f} GB) may be insufficient.{RESET}")
                print(f"{YELLOW}Consider cleaning up old results or using fewer samples.{RESET}")
            elif free_gb < estimated_gb_needed * 2:
                print(f"{YELLOW}⚠ Disk space is tight. Monitor usage during evaluation.{RESET}")
            else:
                print(f"{GREEN}✓ Sufficient disk space available{RESET}")
        except Exception as e:
            log_step(f"Could not check disk space: {e}")

    try:
        with open(lockfile_path, "w", encoding="utf-8") as lock_file:
            lock_file.write(f"model={model_name}\n")

        print(f"\n{BOLD}{CYAN}>>> Running {num_passes} sample(s) sequentially...{RESET}")

        # Estimate total runtime for user awareness
        if num_passes > 1:
            estimated_minutes_per_sample = 10  # Conservative estimate per task
            total_tasks = len(tasks)
            estimated_total_minutes = num_passes * total_tasks * estimated_minutes_per_sample
            print(f"{CYAN}Estimated total runtime: ~{estimated_total_minutes} minutes ({estimated_total_minutes/60:.1f} hours){RESET}")
            print(f"{CYAN}Processing {num_passes} samples × {total_tasks} tasks = {num_passes * total_tasks} evaluations{RESET}")
            if num_passes >= 50:
                print(f"{YELLOW}⚠ Long-running evaluation detected. Consider using --pass to split into smaller batches.{RESET}")

        import time
        overall_start_time = time.time()

        for p in range(pass_start, pass_start + num_passes):
            sample_start_time = time.time()
            current_sample = p - pass_start + 1
            log_step(f"Starting sample {current_sample}/{num_passes}")
            print(f"{BOLD}{CYAN}{'='*80}{RESET}")
            print(f"{BOLD}{CYAN}  SAMPLE {current_sample}/{num_passes} (Pass Index: {p}){RESET}")
            print(f"{BOLD}{CYAN}{'='*80}{RESET}")

            await run_sample(p)

            sample_elapsed = time.time() - sample_start_time
            overall_elapsed = time.time() - overall_start_time
            samples_completed = current_sample
            samples_remaining = num_passes - samples_completed

            if samples_completed > 0:
                avg_time_per_sample = overall_elapsed / samples_completed
                eta_seconds = avg_time_per_sample * samples_remaining
                eta_minutes = eta_seconds / 60

                print(f"\n{GREEN}✓ Sample {current_sample}/{num_passes} completed in {sample_elapsed/60:.1f} minutes{RESET}")
                print(f"{CYAN}Progress: {current_sample}/{num_passes} ({100*current_sample/num_passes:.1f}%){RESET}")
                if samples_remaining > 0:
                    print(f"{CYAN}Estimated time remaining: ~{eta_minutes:.1f} minutes ({eta_minutes/60:.1f} hours){RESET}")
                print(f"{CYAN}Average time per sample: {avg_time_per_sample/60:.1f} minutes{RESET}")
            print()
    finally:
        unload_ollama_model(model_config)
        if os.path.exists(lockfile_path):
            os.remove(lockfile_path)

    # Print final summary for multi-sample runs
    if num_passes > 1:
        total_elapsed = time.time() - overall_start_time
        print(f"\n{BOLD}{GREEN}{'='*80}{RESET}")
        print(f"{BOLD}{GREEN}  EVALUATION COMPLETE{RESET}")
        print(f"{BOLD}{GREEN}{'='*80}{RESET}")
        print(f"{GREEN}Total samples completed: {num_passes}{RESET}")
        print(f"{GREEN}Total time elapsed: {total_elapsed/60:.1f} minutes ({total_elapsed/3600:.2f} hours){RESET}")
        print(f"{GREEN}Average time per sample: {total_elapsed/num_passes/60:.1f} minutes{RESET}")
        print(f"{BOLD}{GREEN}{'='*80}{RESET}\n")

    print(f"\n{BOLD}{GREEN}Evaluation Complete. All files saved to: {os.path.abspath(args.output_dir)}{RESET}")

    # Optional: Compare with ground truth results
    if args.compare_ground_truth:
        print(f"\n{BOLD}{CYAN}>>> Comparing results with ground truth...{RESET}")
        _compare_with_ground_truth(
            results_dir=os.path.join(args.output_dir, "dataset", effective_lock_folder),
            ground_truth_dir=args.ground_truth_dir,
            task_csv_path=args.dataset
        )

def _compare_with_ground_truth(results_dir, ground_truth_dir, task_csv_path):
    """Compare evaluation results with ground truth dataset."""
    import csv
    from compute_metrics import bleu_score, codebert_score

    # Load task IDs from CSV
    task_ids = []
    with open(task_csv_path, 'r', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            task_ids.append(row['task_id'])

    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{CYAN}  COMPARISON WITH GROUND TRUTH RESULTS{RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"  Results dir:      {results_dir}")
    print(f"  Ground truth dir: {ground_truth_dir}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}\n")

    # Find ground truth dataset directory
    gt_dataset_dirs = []
    if os.path.exists(os.path.join(ground_truth_dir, "dataset")):
        gt_base = os.path.join(ground_truth_dir, "dataset")
        for entry in os.listdir(gt_base):
            if os.path.isdir(os.path.join(gt_base, entry)):
                gt_dataset_dirs.append(os.path.join(gt_base, entry))

    if not gt_dataset_dirs:
        print(f"{YELLOW}WARNING: No ground truth dataset directories found in {ground_truth_dir}/dataset/{RESET}")
        return

    # Use the first ground truth directory (or could let user choose)
    gt_dir = gt_dataset_dirs[0]
    print(f"Using ground truth: {gt_dir}\n")

    comparison_results = []

    for task_id in task_ids:
        # Find result files for this task
        result_files = glob.glob(os.path.join(results_dir, f"*{task_id.replace('.', '_')}*.json"))
        gt_files = glob.glob(os.path.join(gt_dir, f"*{task_id.replace('.', '_')}*.json"))

        if not result_files:
            continue

        for result_file in result_files:
            with open(result_file, 'r') as f:
                result_data = json.load(f)

            # Extract metrics from result
            result_metrics = {
                'task_id': task_id,
                'file': os.path.basename(result_file),
                'plan_success': result_data.get('execution_results', {}).get('terraform_plan', {}).get('status') == 'success',
                'apply_success': result_data.get('execution_results', {}).get('terraform_apply', {}).get('status') == 'success',
                'spec_passed': result_data.get('spec_accuracy', {}).get('passed', False),
                'iterations': result_data.get('final_outcome', {}).get('total_iterations', 1),
                'generated_code': result_data.get('llm_response', {}).get('generated_code', '')
            }

            # Find matching ground truth
            gt_match = None
            if gt_files:
                # Use first ground truth file for this task
                with open(gt_files[0], 'r') as f:
                    gt_match = json.load(f)

            if gt_match:
                gt_metrics = {
                    'plan_success': gt_match.get('execution_results', {}).get('terraform_plan', {}).get('status') == 'success',
                    'apply_success': gt_match.get('execution_results', {}).get('terraform_apply', {}).get('status') == 'success',
                    'spec_passed': gt_match.get('spec_accuracy', {}).get('passed', False),
                    'iterations': gt_match.get('final_outcome', {}).get('total_iterations', 1),
                    'gt_code': gt_match.get('llm_response', {}).get('generated_code', '')
                }

                # Calculate code similarity if both codes exist
                code_bleu = None
                code_codebert = None
                if result_metrics['generated_code'] and gt_metrics['gt_code']:
                    code_bleu = bleu_score(gt_metrics['gt_code'], result_metrics['generated_code'])
                    code_codebert = codebert_score(gt_metrics['gt_code'], result_metrics['generated_code'])

                comparison = {
                    'task_id': task_id,
                    'result_file': os.path.basename(result_file),
                    'plan_match': result_metrics['plan_success'] == gt_metrics['plan_success'],
                    'apply_match': result_metrics['apply_success'] == gt_metrics['apply_success'],
                    'spec_match': result_metrics['spec_passed'] == gt_metrics['spec_passed'],
                    'result_plan': result_metrics['plan_success'],
                    'gt_plan': gt_metrics['plan_success'],
                    'result_apply': result_metrics['apply_success'],
                    'gt_apply': gt_metrics['apply_success'],
                    'result_spec': result_metrics['spec_passed'],
                    'gt_spec': gt_metrics['spec_passed'],
                    'result_iters': result_metrics['iterations'],
                    'gt_iters': gt_metrics['iterations'],
                    'code_bleu': code_bleu,
                    'code_codebert_f1': code_codebert['f1'] if code_codebert else None
                }
                comparison_results.append(comparison)
            else:
                print(f"{YELLOW}No ground truth found for task {task_id}{RESET}")

    if not comparison_results:
        print(f"{YELLOW}No comparison results generated.{RESET}")
        return

    # Print comparison table
    print(f"\n{BOLD}Comparison Summary:{RESET}")
    print(f"{'Task':<8} {'File':<30} {'Plan':>6} {'Apply':>6} {'Spec':>6} {'BLEU':>8}")
    print(f"{'-'*8} {'-'*30} {'-'*6} {'-'*6} {'-'*6} {'-'*8}")

    total_plan_match = 0
    total_apply_match = 0
    total_spec_match = 0
    bleu_scores = []

    for comp in comparison_results:
        plan_sym = GREEN + "✓" + RESET if comp['plan_match'] else RED + "✗" + RESET
        apply_sym = GREEN + "✓" + RESET if comp['apply_match'] else RED + "✗" + RESET
        spec_sym = GREEN + "✓" + RESET if comp['spec_match'] else RED + "✗" + RESET
        bleu_str = f"{comp['code_bleu']:.4f}" if comp['code_bleu'] is not None else "N/A"

        print(f"{comp['task_id']:<8} {comp['result_file']:<30} {plan_sym:>6} {apply_sym:>6} {spec_sym:>6} {bleu_str:>8}")

        if comp['plan_match']:
            total_plan_match += 1
        if comp['apply_match']:
            total_apply_match += 1
        if comp['spec_match']:
            total_spec_match += 1
        if comp['code_bleu'] is not None:
            bleu_scores.append(comp['code_bleu'])

    print(f"{'-'*8} {'-'*30} {'-'*6} {'-'*6} {'-'*6} {'-'*8}")

    total = len(comparison_results)
    avg_bleu = sum(bleu_scores) / len(bleu_scores) if bleu_scores else 0

    print(f"\n{BOLD}Overall Agreement:{RESET}")
    print(f"  Plan Success Match:  {total_plan_match}/{total} ({100*total_plan_match/total:.1f}%)")
    print(f"  Apply Success Match: {total_apply_match}/{total} ({100*total_apply_match/total:.1f}%)")
    print(f"  Spec Pass Match:     {total_spec_match}/{total} ({100*total_spec_match/total:.1f}%)")
    if bleu_scores:
        print(f"  Avg Code BLEU:       {avg_bleu:.4f}")

    print(f"\n{BOLD}{GREEN}Comparison complete!{RESET}\n")

if __name__ == "__main__":
    asyncio.run(main())
