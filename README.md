# IaC-Eval: Infrastructure as Code Evaluation Framework

**A comprehensive, production-ready framework for benchmarking Large Language Models (LLMs) and Small Language Models (SLMs) on Terraform HCL code generation for XenOrchestra/XCP-NG infrastructure provisioning.**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Terraform](https://img.shields.io/badge/terraform-1.5+-purple.svg)](https://www.terraform.io/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 📋 Table of Contents

1. [What is IaC-Eval?](#what-is-iac-eval)
2. [Key Features](#key-features)
3. [Architecture Overview](#architecture-overview)
4. [Quick Start](#quick-start)
5. [Installation](#installation)
6. [Configuration](#configuration)
7. [Running Evaluations](#running-evaluations)
8. [Production Features](#production-features)
9. [Metrics and Analysis](#metrics-and-analysis)
10. [Advanced Usage](#advanced-usage)
11. [Troubleshooting](#troubleshooting)
12. [Internal Architecture](#internal-architecture)
13. [Best Practices](#best-practices)
14. [Contributing](#contributing)
15. [Documentation](#documentation)

---

## 🎯 What is IaC-Eval?

IaC-Eval is a **research-grade evaluation framework** designed to systematically benchmark the ability of language models to generate valid, executable Terraform HCL code for infrastructure provisioning. Unlike general code generation benchmarks, IaC-Eval focuses specifically on Infrastructure as Code with real infrastructure execution and validation.

### Purpose

- **Benchmark LLMs/SLMs** on their ability to write Terraform code that actually provisions infrastructure
- **Execute generated code** against real XenOrchestra/XCP-NG infrastructure
- **Validate correctness** through specification checking, terraform validation, and post-execution verification
- **Generate reproducible metrics** for research papers and model comparisons
- **Support various prompting strategies** (Baseline, Chain-of-Thought, Few-Shot, Multi-turn repair)

### What Makes It Unique

1. **Real Infrastructure Execution**: Unlike benchmarks that only check syntax, IaC-Eval executes terraform code and provisions actual VMs
2. **Comprehensive CRUD Coverage**: Tests CREATE, READ, UPDATE, and DELETE operations with stateful task chains
3. **Automatic Cleanup**: Every task automatically destroys infrastructure after validation
4. **Production-Ready**: Supports 100+ sample runs with progress tracking, disk monitoring, and error recovery
5. **Research Integrity**: Implements unbiased Pass@k metrics, prevents data leakage, and ensures reproducibility

---

## ✨ Key Features

### Core Capabilities

#### 🚀 **Model Support**
- **OpenRouter API** - Access to GPT-4, Claude, Gemini, and 200+ models
- **Ollama** - Local models (Phi-4, Llama, Mistral, etc.)
- **HuggingFace Inference** - Direct API access to HF models
- **LM Studio** - Local OpenAI-compatible endpoints
- **Custom Endpoints** - Any OpenAI-compatible API

#### 📊 **Benchmark Tasks**
- **10-task benchmark suite** covering VM provisioning workflows
- **4 independent tasks**: C1.1, C1.2, C2.2, C5.2 (various VM counts and specs)
- **2 stateful task chains**:
  - Chain 1: C1.3 (CREATE) → U1.2 (UPDATE) → D1.2 (DELETE)
  - Chain 2: C2.3 (CREATE) → R1.2 (READ) → D2.2 (DELETE)
- **Resource constraints**: 20GB RAM, 30 CPUs, 500GB disk limits enforced

#### 🔬 **Prompting Strategies**
- **Baseline** - Raw task prompt (control condition)
- **Chain-of-Thought (COT)** - Step-by-step reasoning examples
- **Few-Shot Prompting (FSP)** - Complete working examples
- **Multi-turn Repair** - Automatic self-correction (up to 10 iterations)
- **Multi-error** - Semantic error pattern history
- **Dataset Mode** - Research-grade strict 10-turn evaluation

#### 🎯 **Validation & Verification**
- **Terraform Validation**: `init`, `validate`, `plan`, `apply` execution
- **Specification Checking**: Validates resource counts, memory, CPUs, disk, VM names
- **Post-State Verification**: Confirms UPDATE operations are in-place (not recreate)
- **Resource Quota Enforcement**: Prevents over-provisioning beyond host limits
- **Plan JSON Analysis**: Deep inspection of terraform plan output

#### 📈 **Metrics & Analysis**
- **Pass@k** - Unbiased estimator (Pass@1, Pass@3, Pass@5)
- **BLEU Score** - N-gram similarity with reference code
- **CodeBERT** - Semantic code similarity (precision, recall, F1, F3)
- **Success Rates** - Plan, apply, spec accuracy breakdowns
- **Iteration Tracking** - Multi-turn repair effectiveness
- **Ground Truth Comparison** - Automated baseline comparison

#### 🛡️ **Production Features (New!)**

**For Long-Running Evaluations:**
- ✅ **Progress Tracking** - Real-time ETA and completion percentage
- ✅ **Runtime Estimation** - Predicts total time before starting
- ✅ **Disk Space Monitoring** - Warns before running out of space
- ✅ **Enhanced Error Reporting** - All terraform failures visible in terminal
- ✅ **Final Summary Statistics** - Complete run metrics at end
- ✅ **Recovery Mechanisms** - Automatic retry on destroy failures
- ✅ **State Preservation** - Pre-destroy snapshots for debugging

**Production-Ready:**
- Supports **100+ sequential samples** with automatic cleanup
- Estimated 8-16 hours for 100 samples (model-dependent)
- ~100GB disk space for full 100-sample run
- Restart capability with `--pass N` flag
- Lockfile protection against concurrent runs

---

## 🏗️ Architecture Overview

### Design Philosophy

IaC-Eval follows a **layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                   CLI & Orchestration                   │
│                   (evaluate.py)                         │
└─────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│              Task Execution & Repair Loop               │
│                  (eval_core.py)                         │
└─────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────┬──────────────────┬──────────────────┐
│  LLM Interface   │  Terraform Exec  │  Spec Validator  │
│ (api_client.py)  │ (eval_utils.py)  │(spec_checker.py) │
└──────────────────┴──────────────────┴──────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│              Metrics & Result Generation                │
│      (json_generator.py, compute_metrics.py)            │
└─────────────────────────────────────────────────────────┘
```

### Pipeline Workflow

**7 Layers of Processing:**

1. **Input & Configuration** - Load config, dataset, resolve modes
2. **Orchestration** - Task ordering, sample loops, workspace management
3. **Prompt & Inference** - Prompt assembly, LLM calls, code extraction
4. **Terraform Validation** - Init, validate, plan execution
5. **Intent & State Validation** - Spec checks, post-state verification
6. **Result & Metrics** - Dataset entry generation, artifact persistence
7. **Cleanup & Reproducibility** - Destroy, state snapshots, lockfile removal

### Execution Flow (Per Task)

```
1. Extract infrastructure context (if chain task)
2. Call LLM → Generate Terraform code
3. Write main.tf to workspace
4. terraform init (180s timeout)
5. terraform validate (120s timeout)
6. terraform plan -out=tfplan (300s timeout)
7. Specification accuracy check
8. terraform apply (600s timeout) [if not plan-only]
9. Post-state verification [if UPDATE/DELETE]
10. Save results to JSON
11. Cleanup: terraform destroy (300s timeout)
    └─ If fails: Recovery destroy mechanism
12. Preserve state snapshot before destroy
```

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Terraform 1.5+
- XenOrchestra/XCP-NG infrastructure access
- API key for LLM provider (OpenRouter, HuggingFace, or local Ollama)

### 30-Second Setup

```bash
# Clone repository
git clone <repository-url>
cd friendly-octo-funicular

# Install dependencies
pip install -r requirements.txt

# Set credentials
export OPENROUTER_API_KEY="sk-or-v1-..."
export XO_USERNAME="your-xo-username"
export XO_PASSWORD="your-xo-password"

# Run a quick test (plan-only, no VMs created)
python src/evaluate.py \
  --model phi4_openrouter \
  --task_id C1.1 \
  --plan-only \
  --no-confirm
```

### Your First Evaluation

```bash
# Run single task with actual VM provisioning
python src/evaluate.py \
  --model phi4_openrouter \
  --task_id C1.1 \
  --samples 1 \
  --seed 42 \
  --no-confirm

# Check results
python src/compute_metrics.py --folder results/dataset/phi4_or
```

---

## 📦 Installation

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd friendly-octo-funicular
```

### Step 2: Create Virtual Environment (Recommended)

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt

# Optional: For testing
pip install pytest

# Optional: For CodeBERT metrics
pip install code-bert-score
```

### Step 4: Set Environment Variables

Create a `.env` file or export directly:

```bash
# Required for OpenRouter
export OPENROUTER_API_KEY="sk-or-v1-..."

# Required for XenOrchestra
export XO_USERNAME="admin@admin.net"
export XO_PASSWORD="your-password"

# Optional for HuggingFace
export HF_TOKEN="hf_..."
```

### Step 5: Verify Installation

```bash
# Check CLI help
python src/evaluate.py --help
python src/compute_metrics.py --help

# Run tests
python -m pytest tests/test_bug_fixes.py -q

# Verify terraform
terraform --version
```

---

## ⚙️ Configuration

### Configuration Files

#### `config/openrouter_config.yaml`

Main configuration file with:

```yaml
openrouter:
  api_key: "${OPENROUTER_API_KEY}"  # Environment variable substitution
  base_url: "https://openrouter.ai/api/v1/chat/completions"
  timeout: 600
  max_retries: 3

xenorchestra:
  url: "ws://localhost:8080"
  username: "${XO_USERNAME}"
  password: "${XO_PASSWORD}"
  pool_name: "Your-Pool-Name"
  network_name: "Pool-wide network associated with eth0"
  sr_name: "Local storage"
  template_name: "Ubuntu-22"

max_repair_iterations: 9  # 1 initial + 9 repairs = 10 total

baseline_system_prompt: |
  You are TerraformAI, an AI agent specialized in generating
  Terraform HCL code for XenOrchestra infrastructure...

multi_turn_system_prompt: |
  You are TerraformAI... Based on provided feedback...

dataset_system_prompt: |
  You are an Expert Infrastructure Architect...

platform_context: |
  ### Infrastructure Instructions:
  - Environment: Single bare-metal host
  - Usable Resources: 20GB RAM, 30 CPUs, 500GB disk
  - ...

models:
  phi4_openrouter:
    name: "microsoft/phi-4"
    display_name: "Phi-4 (OpenRouter)"
    folder_name: "phi4_or"
    temperature: 0.2
    max_tokens: 16384
    seed: 42
    base_url: "https://openrouter.ai/api/v1/chat/completions"

  llama3_ollama:
    name: "llama3:8b"
    display_name: "Llama 3 8B (Ollama)"
    folder_name: "llama3_local"
    temperature: 0.2
    max_tokens: 4096
    base_url: "http://localhost:11434/v1/chat/completions"
    local: true
```

#### `config/task_specs.yaml`

Task-specific specifications:

```yaml
C1.1:
  category: CREATE
  vm_count: 1

C1.2:
  category: CREATE
  vm_count: 1
  per_vm_memory_max: 2147483648  # 2GB

C1.3:
  category: CREATE
  vm_count: 1
  per_vm_memory_max: 4294967296  # 4GB
  per_vm_cpus: 2
  vm_names: [app-01]
  per_vm_disk_size: 53687091200  # 50GB

U1.2:
  category: UPDATE
  target_vm: app-01
  updated_field: memory_max
  new_value: 6442450944  # 6GB
```

### Adding New Models

Add to `config/openrouter_config.yaml`:

```yaml
models:
  your_model:
    name: "provider/model-name"
    display_name: "Your Model Name"
    folder_name: "your_model_results"
    temperature: 0.2
    max_tokens: 4096
    seed: 42
    base_url: "https://api.provider.com/v1/chat/completions"
    api_key: "${YOUR_API_KEY}"  # Optional override
```

---

## 🎮 Running Evaluations

### Command-Line Interface

```bash
python src/evaluate.py [OPTIONS]
```

**Core Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--config` | Config file path | `config/openrouter_config.yaml` |
| `--output_dir` | Results directory | `results` |
| `--dataset` | Task CSV file | `tasks/vm_provisioning_tasks.csv` |
| `--model` | Model key from config | `phi4_openrouter` |
| `--task_id` | Single task ID | All tasks |
| `--chain` | Chain tasks (comma-separated) | - |
| `--samples` | Number of samples (Pass@k) | `1` |
| `--pass` | Specific pass number | - |
| `--plan-only` | Skip terraform apply | `False` |
| `--no-confirm` | Skip confirmations | `False` |
| `--seed` | Random seed | From config |
| `--enhance-strat` | Prompt strategy | `""` (Baseline) |
| `--compare-with-ground-truth` | Compare with ground truth | `False` |
| `--ground-truth-dir` | Ground truth directory | `ground_truth_results` |

### Common Use Cases

#### 1. Single Task Evaluation (Safe Testing)

```bash
# Plan-only (no actual VMs)
python src/evaluate.py \
  --model phi4_openrouter \
  --task_id C1.1 \
  --plan-only \
  --no-confirm

# Full execution (creates and destroys VM)
python src/evaluate.py \
  --model phi4_openrouter \
  --task_id C1.1 \
  --seed 42 \
  --no-confirm
```

#### 2. Multiple Samples (Pass@k)

```bash
# Generate 10 samples for Pass@k calculation
python src/evaluate.py \
  --model phi4_openrouter \
  --task_id C1.1 \
  --samples 10 \
  --seed 42 \
  --no-confirm

# Compute Pass@k metrics
python src/compute_metrics.py --folder results/dataset/phi4_or
```

#### 3. Full Benchmark Run

```bash
# All 10 tasks in fixed order
python src/evaluate.py \
  --model phi4_openrouter \
  --samples 1 \
  --seed 42 \
  --no-confirm
```

#### 4. Stateful Task Chains

```bash
# Chain 1: CREATE → UPDATE → DELETE
python src/evaluate.py \
  --model phi4_openrouter \
  --chain C1.3,U1.2,D1.2 \
  --seed 42 \
  --no-confirm

# Chain 2: CREATE → READ → DELETE
python src/evaluate.py \
  --model phi4_openrouter \
  --chain C2.3,R1.2,D2.2 \
  --seed 42 \
  --no-confirm
```

#### 5. Prompt Strategy Comparison

```bash
# Baseline
python src/evaluate.py --model phi4 --task_id C1.1 --enhance-strat ""

# Chain-of-Thought
python src/evaluate.py --model phi4 --task_id C1.1 --enhance-strat COT

# Few-Shot
python src/evaluate.py --model phi4 --task_id C1.1 --enhance-strat FSP

# Multi-turn (automatically enabled, max 10 iterations)
python src/evaluate.py --model phi4 --task_id C1.1 --enhance-strat multi-turn
```

#### 6. Production Run (100 Samples)

```bash
# Full 100-sample run (8-16 hours)
python src/evaluate.py \
  --model phi4_openrouter \
  --samples 100 \
  --seed 42 \
  --no-confirm

# Or batch into smaller runs
for i in 1 11 21 31 41 51 61 71 81 91; do
  python src/evaluate.py \
    --model phi4_openrouter \
    --samples 10 \
    --pass $i \
    --seed 42 \
    --no-confirm
done
```

#### 7. With Ground Truth Comparison

```bash
python src/evaluate.py \
  --model phi4_openrouter \
  --samples 5 \
  --compare-with-ground-truth \
  --ground-truth-dir ground_truth_results
```

---

## 🚀 Production Features

### Progress Tracking

For multi-sample runs, the framework displays:

```
>>> Running 100 sample(s) sequentially...
Estimated total runtime: ~1000 minutes (16.7 hours)
Processing 100 samples × 10 tasks = 1000 evaluations
⚠ Long-running evaluation detected. Consider using --pass to split into smaller batches.

Disk Space Check:
  Available: 250.5 GB
  Estimated needed: 100.0 GB
✓ Sufficient disk space available

================================================================================
  SAMPLE 5/100 (Pass Index: 4)
================================================================================

✓ Sample 5/100 completed in 12.3 minutes
Progress: 5/100 (5.0%)
Estimated time remaining: ~194.5 minutes (3.2 hours)
Average time per sample: 12.3 minutes

================================================================================
  EVALUATION COMPLETE
================================================================================
Total samples completed: 100
Total time elapsed: 853.2 minutes (14.22 hours)
Average time per sample: 8.5 minutes
================================================================================
```

### Error Visibility

All terraform failures now print prominently:

```
[TERRAFORM PLAN FAILED]
Exit Code: 1
Error Output:
Error: Invalid resource configuration
  on main.tf line 15, in resource "xenorchestra_vm" "vm":
  15:   memory_max = "2GB"
Expected number, got string.
```

### Disk Space Monitoring

Before starting 10+ sample runs:

```
Disk Space Check:
  Available: 250.5 GB
  Estimated needed: 100.0 GB
✓ Sufficient disk space available
```

Warnings if insufficient:
```
⚠ WARNING: Low disk space! Available (45.2 GB) may be insufficient.
Consider cleaning up old results or using fewer samples.
```

### Recovery Mechanisms

If terraform destroy fails:

```
⚠ CRITICAL: Recovery Destroy Failed!
Workspace: results/terraform_code/phi4_or/c1_1_p42
This may leave orphaned VMs on the platform.
Manual cleanup may be required.
Check XenOrchestra for orphaned resources.
```

### Restart Capability

Resume interrupted runs:

```bash
# If crashed at sample 42, resume from there
python src/evaluate.py \
  --model phi4 \
  --samples 59 \
  --pass 42 \
  --seed 42
```

---

## 📊 Metrics and Analysis

### Computing Metrics

After evaluation completes:

```bash
python src/compute_metrics.py \
  --folder results/dataset/phi4_or \
  --csv tasks/vm_provisioning_tasks.csv
```

**Output:**

```
============================================================
 AGGREGATED EVALUATION SUMMARY
============================================================
  Directory:          results/dataset/phi4_or
  Total Samples:      10
  Unique Tasks:       10
  Pass@1 (Plan):      90.0%
  Pass@1 (Apply):     80.0%
  Pass@1 (Spec):      85.0%
  Avg Iterations:     1.80
  Avg Gen Time (s):   4.2
  Avg BLEU:           0.7234
  Avg CodeBERT-F1:    0.8012
============================================================

============================================================
 PER-TASK BREAKDOWN
============================================================
  Task      N    Plan%  Spec%  AvgIter  BLEU    CBS-F1
  --------  ---  -----  -----  -------  ------  ------
  C1.1      1    100.0% 100.0%    1.00  0.7234  0.8012
  C1.2      1    100.0% 100.0%    1.00  0.6891  0.7654
  C1.3      1    100.0% 100.0%    2.00  0.8123  0.8456
  C2.2      1     0.0%   0.0%    5.00  0.3456  0.4123
  C2.3      1    100.0% 100.0%    1.00  0.7890  0.8234
  C5.2      1    100.0%  0.0%    3.00  0.6543  0.7123
  D1.2      1    100.0% 100.0%    1.00  0.9012  0.9234
  D2.2      1    100.0% 100.0%    1.00  0.8765  0.8901
  R1.2      1    100.0% 100.0%    1.00  0.7654  0.8345
  U1.2      1    100.0% 100.0%    2.00  0.8234  0.8567
============================================================
```

### Pass@k Calculation

Unbiased estimator from Chen et al. (2021):

```
pass@k = 1 - C(n-c, k) / C(n, k)

where:
  n = total samples
  c = correct samples
  k = pass threshold
```

### Ground Truth Comparison

```bash
python src/evaluate.py \
  --model phi4 \
  --samples 5 \
  --compare-with-ground-truth
```

Shows agreement with baseline model:

```
Overall Agreement:
  Plan Success Match:  8/10 (80.0%)
  Apply Success Match: 7/10 (70.0%)
  Spec Pass Match:     9/10 (90.0%)
  Avg Code BLEU:       0.7380
```

---

## 🎓 Advanced Usage

### Custom System Prompts

Edit `config/openrouter_config.yaml`:

```yaml
baseline_system_prompt: |
  You are CustomAI, a specialized agent for...
  [Your custom instructions]
```

### Multi-turn Error Correction

Automatic, but configurable:

```yaml
max_repair_iterations: 9  # 1 initial + 9 repairs = 10 total
```

Strategies:
- `multi-turn` - Standard repair with error history
- `multi-error` - Semantic error deduplication
- `dataset` - Research mode (strict 10 turns)

### LLM Judge (Post-hoc)

Evaluate generated code quality:

```bash
python llm_judge.py \
  --folder results/dataset/phi4_or \
  --config config/openrouter_config.yaml \
  --judge-model openai/gpt-4o
```

### Complexity Scoring

Analyze code complexity:

```bash
python src/complexity_scorer.py
python print_complexity.py
```

### Custom Task Chains

Create your own chains:

```bash
python src/evaluate.py \
  --chain C1.1,C1.2,C2.2 \
  --seed 42
```

**Note:** Only use this for testing. Production chains should maintain state dependencies (CREATE → UPDATE → DELETE).

---

## 🐛 Troubleshooting

### Common Issues

#### 1. Model Not Found

```
Error: Model 'xyz' not found in config. Available models: phi4_openrouter, ...
```

**Solution:** Add model to `config/openrouter_config.yaml` or use existing model key.

#### 2. API Key Issues

```
Unresolved API key placeholder: ${OPENROUTER_API_KEY}
```

**Solution:**
```bash
export OPENROUTER_API_KEY="sk-or-v1-..."
```

#### 3. Evaluation Lockfile

```
ERROR: Evaluation already in progress for this model output folder
```

**Solution:**
```bash
rm results/dataset/phi4_or/.evaluation_in_progress
```

#### 4. Terraform Failures

**Symptoms:** Multiple init/validate/plan failures

**Solutions:**
- Verify XenOrchestra is accessible
- Check credentials: `XO_USERNAME`, `XO_PASSWORD`
- Verify network connectivity to XO server
- Check terraform version: `terraform --version` (need 1.5+)

#### 5. Disk Space Exhaustion

```
⚠ WARNING: Low disk space! Available (45.2 GB) may be insufficient.
```

**Solution:**
```bash
# Clean old results
rm -rf results/old_runs/

# Remove old state snapshots
find results -name "terraform_tfstate_pre_destroy_*.json" -delete
```

#### 6. Orphaned VMs

If destroy fails and VMs remain:

1. Check XenOrchestra web interface
2. Manually destroy VMs via XO UI
3. Or use XO CLI:
```bash
xe vm-list
xe vm-shutdown uuid=<uuid> --force
xe vm-destroy uuid=<uuid>
```

### Debug Mode

Enable verbose logging:

```bash
# Set log level
export LOG_LEVEL=DEBUG

# Run evaluation
python src/evaluate.py --model phi4 --task_id C1.1
```

Check logs:
```bash
cat results/logs/phi4_or/evaluate_*.log
```

---

## 🏛️ Internal Architecture

### Directory Structure

```
friendly-octo-funicular/
├── config/
│   ├── openrouter_config.yaml    # Main configuration
│   └── task_specs.yaml            # Task specifications
├── src/
│   ├── evaluate.py                # Main CLI & orchestration
│   ├── eval_core.py               # Task execution & repair loop
│   ├── api_client.py              # LLM API interfaces
│   ├── eval_utils.py              # Terraform execution utilities
│   ├── spec_checker.py            # Specification validators
│   ├── xo_client.py               # XenOrchestra client
│   ├── json_generator.py          # Result serialization
│   ├── compute_metrics.py         # Metrics calculation
│   ├── prompt_templates.py        # Prompt strategies
│   ├── complexity_scorer.py       # Code complexity metrics
│   ├── models.py                  # Pydantic config schemas
│   └── logger.py                  # Logging utilities
├── tasks/
│   ├── vm_provisioning_tasks.csv  # 10-task benchmark
│   ├── references/                # Golden reference code
│   │   ├── C1.1.tf
│   │   ├── C1.2.tf
│   │   └── ...
│   └── resource_distribution.json
├── tests/
│   └── test_bug_fixes.py          # Regression tests
├── results/                       # Generated (gitignored)
│   ├── dataset/
│   │   └── <model_name>/
│   │       └── *.json             # Task results
│   ├── terraform_code/
│   │   └── <model_name>/
│   │       └── <task_id>/
│   │           └── sample_N/
│   │               ├── main.tf
│   │               ├── terraform.tfstate
│   │               └── history/   # Iteration logs
│   └── logs/
├── ground_truth_results/          # Reference baselines
├── README.md                      # This file
├── PRODUCTION_READINESS_100_SAMPLES.md
├── COMPARISON_USAGE_GUIDE.md
├── IMPLEMENTATION_SUMMARY.md
├── QUICK_ANSWER_100_SAMPLES.md
└── requirements.txt
```

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `evaluate.py` | CLI argument parsing, task ordering, sample loops, cleanup orchestration |
| `eval_core.py` | Per-task LLM calling, terraform execution, multi-turn repair logic |
| `api_client.py` | OpenRouter, Ollama, HuggingFace API clients with retry logic |
| `spec_checker.py` | Strategy pattern validators for CREATE/READ/UPDATE/DELETE |
| `xo_client.py` | WebSocket JSON-RPC client for XenOrchestra VM verification |
| `json_generator.py` | Dataset entry generation with full execution metadata |
| `compute_metrics.py` | Pass@k, BLEU, CodeBERT aggregation |
| `prompt_templates.py` | COT, FSP, multi-turn repair prompt builders |

### State Management

**Independent Tasks:**
- Fresh workspace per task
- No state sharing
- Destroyed after completion

**Chain Tasks:**
- Each task has own workspace
- `terraform.tfstate` copied from last successful task
- State flows: C1.3 → U1.2 → D1.2
- Destroyed after chain completes

**Fallback Rules:**
- If U1.2 fails → D1.2 gets C1.3's state
- If R1.2 fails → D2.2 gets C2.3's state

---

## 📚 Best Practices

### For First-Time Users

1. **Start with plan-only**: Test without creating VMs
2. **Single task first**: Validate setup with `--task_id C1.1`
3. **Check infrastructure**: Ensure XO is accessible
4. **Monitor first run**: Watch logs and XO console
5. **Review results**: Check `results/dataset/` for JSON outputs

### For Production Runs

1. **Batch large runs**: Use `--pass` for 100+ samples
2. **Monitor disk space**: Pre-run checks with 10+ samples
3. **Check first 5-10 samples**: Validate timing and success rate
4. **Have recovery plan**: Know how to manually clean XO
5. **Archive results**: Save successful runs for comparison

### For Research

1. **Fix random seed**: Ensure reproducibility
2. **Document config**: Save exact config used
3. **Multiple samples**: Use Pass@k for statistical rigor
4. **Compare strategies**: Baseline vs COT vs FSP
5. **Ground truth**: Establish baseline with best model

### Security & Safety

1. **Credentials**: Never commit API keys or passwords
2. **Resource limits**: Framework enforces 20GB/30CPU/500GB
3. **Cleanup**: Automatic destroy after every task
4. **Audit trail**: State snapshots preserved
5. **Isolation**: Lockfile prevents concurrent runs

---

## 🤝 Contributing

### Development Setup

```bash
# Clone and setup
git clone <repo-url>
cd friendly-octo-funicular
pip install -r requirements.txt
pip install pytest

# Run tests
python -m pytest tests/ -v

# Check specific test
python -m pytest tests/test_bug_fixes.py::test_extract_terraform_code -v
```

### Adding New Features

1. Create feature branch
2. Add tests in `tests/`
3. Update documentation
4. Submit pull request

### Coding Standards

- Python 3.8+ compatibility
- Type hints for public functions
- Docstrings for modules and functions
- Pydantic for configuration validation
- Async/await for subprocess execution

---

## 📖 Documentation

### Complete Documentation

- **README.md** (this file) - Comprehensive overview
- **PRODUCTION_READINESS_100_SAMPLES.md** - Production deployment guide
- **COMPARISON_USAGE_GUIDE.md** - Ground truth comparison
- **IMPLEMENTATION_SUMMARY.md** - Recent technical changes
- **QUICK_ANSWER_100_SAMPLES.md** - TL;DR production guide
- **BUG_FIXES_REPORT.md** - Bug fix history
- **COMPREHENSIVE_BUG_AUDIT_REPORT.md** - Full audit

### Quick References

**10-Task Benchmark:**
```
C1.1 → C1.2 → C2.2 → C5.2 → [C1.3→U1.2→D1.2] → [C2.3→R1.2→D2.2]
```

**Prompt Strategies:**
- Baseline: `--enhance-strat ""`
- COT: `--enhance-strat COT`
- FSP: `--enhance-strat FSP`
- Multi-turn: `--enhance-strat multi-turn`

**Key Timeouts:**
- terraform init: 180s
- terraform validate: 120s
- terraform plan: 300s
- terraform apply: 600s
- terraform destroy: 300s
- LLM API: 300s (configurable)

---

## 🎯 Example Workflows

### Workflow 1: Quick Model Test

```bash
# Test model on single task (plan-only)
python src/evaluate.py --model phi4 --task_id C1.1 --plan-only

# Full execution
python src/evaluate.py --model phi4 --task_id C1.1 --seed 42

# Check results
python src/compute_metrics.py --folder results/dataset/phi4_or
```

### Workflow 2: Full Benchmark

```bash
# Run all 10 tasks
python src/evaluate.py --model phi4 --samples 1 --seed 42 --no-confirm

# Compute metrics
python src/compute_metrics.py --folder results/dataset/phi4_or

# Compare strategies
python src/evaluate.py --model phi4 --enhance-strat COT --samples 1 --seed 42
python src/evaluate.py --model phi4 --enhance-strat FSP --samples 1 --seed 42
```

### Workflow 3: Pass@10 Evaluation

```bash
# Generate 10 samples per task
python src/evaluate.py --model phi4 --samples 10 --seed 42 --no-confirm

# Compute Pass@k
python src/compute_metrics.py --folder results/dataset/phi4_or
```

### Workflow 4: Production 100-Sample Run

```bash
# Full run with progress tracking
python src/evaluate.py \
  --model phi4 \
  --samples 100 \
  --seed 42 \
  --no-confirm \
  --compare-with-ground-truth

# Or batch into 10-sample runs
for i in {1..10}; do
  start=$((($i-1)*10 + 1))
  python src/evaluate.py \
    --model phi4 \
    --samples 10 \
    --pass $start \
    --seed 42 \
    --no-confirm
done
```

---

## 📊 Expected Performance

### Success Rates (Model-Dependent)

**Typical:**
- Plan Success: 80-95%
- Apply Success: 70-90%
- Spec Accuracy: 75-95%

**By Task Difficulty:**
- C1.1 (simple): 95%+
- C1.2 (2GB spec): 90%+
- C2.2 (3 VMs): 85%+
- C5.2 (10 VMs): 70%+
- Chain tasks: 75-90%

### Iteration Counts

- **First-try success**: 40-60% (iteration 1)
- **With multi-turn**: 70-90% (iterations 1-3)
- **Maximum**: Up to 10 iterations allowed

### Timing Estimates

**Per Task:**
- LLM generation: 2-10 seconds
- Terraform operations: 2-5 minutes
- Total per task: 3-7 minutes

**Full Benchmark (10 tasks):**
- Single sample: 30-70 minutes
- 100 samples: 8-16 hours

---

## 🔒 Security Considerations

### Credential Management

- ✅ Environment variables for secrets
- ✅ No credentials in code or logs
- ✅ Sensitive text redaction in logs
- ✅ YAML placeholder substitution

### Infrastructure Safety

- ✅ Resource quota enforcement (20GB/30CPU/500GB)
- ✅ Automatic VM cleanup after each task
- ✅ Recovery destroy mechanism
- ✅ Lockfile prevents concurrent runs
- ✅ State snapshots for audit

### Data Privacy

- ✅ No external data transmission (except LLM APIs)
- ✅ Results stay local
- ✅ Redacted credentials in artifacts
- ✅ Configurable output directories

---

## 🚧 Known Limitations

1. **XenOrchestra only**: Currently tied to XO/XCP-NG infrastructure
2. **No mid-run checkpointing**: Must use `--pass` for manual restart
3. **Sequential samples**: No parallel sample execution
4. **Disk space**: ~100GB needed for 100-sample runs
5. **Manual cleanup**: Rare destroy failures need manual intervention

---

## 🎓 Research Applications

### Use Cases

1. **Model Benchmarking**: Compare LLM capabilities on IaC
2. **Prompt Engineering**: Test COT vs FSP vs Baseline
3. **Few-shot Learning**: Measure impact of examples
4. **Multi-turn Repair**: Analyze self-correction effectiveness
5. **Code Quality**: BLEU/CodeBERT similarity analysis
6. **Pass@k Studies**: Statistical robustness measurements

### Citation

If you use IaC-Eval in research, please cite:

```bibtex
@software{iac_eval_2024,
  title={IaC-Eval: Infrastructure as Code Evaluation Framework},
  author={[Authors]},
  year={2024},
  url={https://github.com/kram2006/friendly-octo-funicular}
}
```

---

## 📞 Support

### Getting Help

1. Check **TROUBLESHOOTING** section above
2. Review **PRODUCTION_READINESS_100_SAMPLES.md**
3. Check logs in `results/logs/`
4. Review workspace histories in `results/terraform_code/`
5. Open GitHub issue with details

### Reporting Bugs

Include:
- Python version
- Terraform version
- Config file (redact credentials)
- Error logs
- Steps to reproduce

---

## 📜 License

MIT License - See LICENSE file

---

## 🙏 Acknowledgments

- **XenOrchestra** team for excellent virtualization platform
- **terra-farm/xenorchestra** Terraform provider
- **OpenRouter** for LLM API access
- **Ollama** for local model support
- **HuggingFace** for model hosting

---

## 🔄 Version History

**Latest (2024-03-09):**
- ✅ Production features for 100-sample runs
- ✅ Progress tracking and ETA
- ✅ Disk space monitoring
- ✅ Enhanced error reporting
- ✅ Ground truth comparison
- ✅ Comprehensive documentation

**Previous:**
- Multi-turn repair mechanism
- Specification validation
- Pass@k metrics
- State management for chains
- Recovery destroy mechanism

---

**Ready to benchmark your LLM on Infrastructure as Code? Start with the [Quick Start](#-quick-start) section!** 🚀
