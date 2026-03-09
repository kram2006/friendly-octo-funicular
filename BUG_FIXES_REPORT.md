# SLM Evaluation Framework Audit Report (No Code Changes Applied)

## 1) Repository Architecture Summary

### Core backend pipeline
- Orchestration and execution scheduling: `src/evaluate.py`
- Per-task eval loop (prompt -> generate -> terraform -> validation -> JSON): `src/eval_core.py`
- Provider and model clients: `src/api_client.py`, `src/xo_client.py`
- Prompt enhancement templates: `src/prompt_templates.py`
- Terraform/spec validation: `src/spec_checker.py`
- Result schema and persistence: `src/json_generator.py`
- Metric aggregation (pass@k + BLEU/CodeBERT): `src/compute_metrics.py`
- Utilities/logging: `src/eval_utils.py`, `src/logger.py`, `src/models.py`

### Data/config/artifacts
- Dataset: `tasks/vm_provisioning_tasks.csv`
- Task reference HCL: `tasks/references/*.tf`
- Task semantic rules: `config/task_specs.yaml`
- Provider/model config: `config/openrouter_config.yaml`

### Additional scripts/tests
- Operational scripts in `scripts/`
- Regression tests in `tests/`
- Standalone judge: `llm_judge.py`
- Dataset/reference utilities: `populate_references.py`, `verify_fixes.py`

### Benchmark scope verified
- Independent tasks: `C1.1`, `C1.2`, `C2.2`, `C5.2`
- Chain 1: `C1.3 -> U1.2 -> D1.2`
- Chain 2: `C2.3 -> R1.2 -> D2.2`

---

## 2) Pipeline Verification (Stage-by-Stage)

1. Task Prompt Generation: Implemented (`src/eval_core.py`, `src/prompt_templates.py`)  
   Status: Present, but has configuration/security drift.
2. Model Output Generation: Implemented (`src/api_client.py`)  
   Status: Present, with local endpoint auth handling gap.
3. Static Validation / Compile Checks: Implemented (`terraform init/validate/plan/apply` in `src/eval_core.py`)  
   Status: Present.
4. Intent / Constraint Validation: Implemented (`src/spec_checker.py`)  
   Status: Present, but READ and quota validation are incomplete.
5. Metric Calculation: Implemented (`src/compute_metrics.py`, additional scripts)  
   Status: Present, but script ecosystem is inconsistent.
6. Result Logging: Implemented (`src/json_generator.py`, `src/logger.py`, task artifacts)  
   Status: Present, reproducibility metadata incomplete.

---

## 3) Detected Issues (Prioritized)

### Critical
1. False-positive success path for expected refusal tasks  
   - File: `src/eval_core.py:370-389`  
   - Problem: `success = True` is set immediately when empty code is treated as refusal for `expected_error == resource_exhaustion`, before terraform stages finish. If later stages fail, final task outcome can remain incorrectly successful.  
   - Required fix: Track refusal via a separate flag; set `success=True` only after terminal validation confirms expected behavior.

### High
2. Reference population utility cannot add missing `reference_hcl` column  
   - File: `populate_references.py:37-50`  
   - Problem: Writer uses original `fieldnames`; if CSV lacks `reference_hcl`, populated values are silently dropped.  
   - Required fix: Ensure `reference_hcl` is appended to `fieldnames` when absent.

3. Dataset/tooling schema drift (`reference_hcl`)  
   - Files: `tasks/vm_provisioning_tasks.csv:1`, `tests/test_bug_fixes.py:212`, `populate_references.py`  
   - Problem: Current CSV header omits `reference_hcl`, while tests/utilities expect it.  
   - Required fix: Choose one canonical contract:
     - add `reference_hcl` to CSV, or
     - fully migrate tooling/tests to `tasks/references/*.tf`.

4. Local OpenAI-compatible endpoints blocked by mandatory API key check  
   - File: `src/api_client.py:23-24`  
   - Problem: Client raises if API key missing, even for local LM Studio/Ollama endpoints that may not require auth.  
   - Required fix: Require key conditionally (remote providers only), allow no-auth localhost endpoints.

5. READ-task semantic checks are too weak  
   - File: `src/spec_checker.py:213-219`  
   - Problem: READ validation only checks "no resource changes"; does not verify expected READ behavior (data sources + output semantics).  
   - Required fix: Add static checks for required data/output constructs and reject trivial no-op non-READ-like plans.

6. Host quota validation ignores existing infrastructure state  
   - File: `src/spec_checker.py:103-139`  
   - Problem: Quota check sums only changed resources in plan, not full pre-existing VM footprint.  
   - Required fix: Merge `pre_vms` state into quota calculation for UPDATE/DELETE chain scenarios.

7. Reproducibility metadata is incomplete in output JSON  
   - File: `src/json_generator.py`  
   - Problem: Missing seed, endpoint/base URL, config hash, dataset hash, task-order hash; limits reproducibility and auditability.  
   - Required fix: Persist these fields in `metadata` / run-manifest output.

### Medium
8. Inconsistent `checks_performed` type in spec results  
   - File: `src/spec_checker.py:325-327`  
   - Problem: List mixes strings and dicts.  
   - Required fix: Standardize to one schema (recommended: list of objects with `check`, `passed`, `detail`).

9. No explicit UTF-8 when saving dataset JSON  
   - File: `src/json_generator.py:445-446`  
   - Problem: Platform-default encoding can corrupt non-ASCII outputs.  
   - Required fix: `open(..., encoding="utf-8")`.

10. CLI/documentation mismatch for metrics command  
    - Files: `README.md:67-69`, `src/compute_metrics.py:264-269`  
    - Problem: README says `--help`, but script has no argparse and treats args positionally.  
    - Required fix: Add argparse with proper `--help`, `--dataset-folder`, `--tasks-csv` options.

11. Legacy metrics script incompatible with repository dataset schema  
    - File: `scripts/evaluate_bleu_codebertscore.py:414-416,565-567`  
    - Problem: Expects CSV columns `Prompt`, `Intent`, `Reference output`, which do not exist in `tasks/vm_provisioning_tasks.csv`.  
    - Required fix: Align parser with canonical dataset schema or deprecate/remove script.

12. Phi4 verification script path assumptions do not match current artifact layout  
    - File: `scripts/verify_phi4_codes.py:48-50`  
    - Problem: Looks for `.../<task>/main.tf`; runtime actually writes per-sample/per-chain workspaces.  
    - Required fix: Resolve `sample_*` and `chain_*` directories; compare latest valid artifact.

13. Judge summary labels `execution_successful` as apply status  
    - File: `llm_judge.py:194,311`  
    - Problem: "Apply" column displays `final_outcome.execution_successful`, not true apply result.  
    - Required fix: Use `final_outcome.apply_success` (fallback to execution_successful only when apply is skipped by design).

14. Prompt templates hardcode credentials and platform constants  
    - File: `src/prompt_templates.py:31-55`  
    - Problem: Hardcoded URL/username/password/pool/template increase leakage risk and break portability.  
    - Required fix: Parameterize template boilerplate from loaded config context.

15. Run scripts are not cross-platform operational in current environment  
    - File: `run_experiments.sh:1-83`  
    - Problem: Bash + `python` executable assumptions fail in Windows PowerShell environment.  
    - Required fix: Add PowerShell equivalent and executable detection.

### Low
16. `--pass` accepts non-positive values  
    - File: `src/evaluate.py:319-321`  
    - Problem: Allows pass index `<= 0` leading to negative start index / invalid pass labeling.  
    - Required fix: Validate `pass_num >= 1`.

17. Stale comments claim parallel behavior where code is sequential  
    - File: `src/evaluate.py:312-314,323`  
    - Problem: Documentation comments diverge from actual execution mode.  
    - Required fix: Update comments to prevent operator confusion.

18. Committed bytecode artifacts in source tree  
    - Files: `src/__pycache__/*.pyc`  
    - Problem: Non-source artifacts increase drift/confusion and can mask real source changes.  
    - Required fix: Remove tracked bytecode and ignore via `.gitignore`.

---

## 4) Files Modified

- `BUG_FIXES_REPORT.md` (this report only)

---

## 5) Code Patches Applied

- No production code patches were applied (per request).
- This is an audit-only deliverable with required edit recommendations.

---

## 6) Recommended Edit Plan (Execution Order)

1. Fix critical success-state bug in `src/eval_core.py`.  
2. Resolve dataset/reference schema contract (`reference_hcl`) across CSV/tests/utilities.  
3. Fix client auth logic for LM Studio/Ollama/OpenAI-compatible local endpoints.  
4. Strengthen READ + quota validation in `src/spec_checker.py`.  
5. Add reproducibility metadata and UTF-8-safe persistence in `src/json_generator.py`.  
6. Unify metrics tooling (make `src/compute_metrics.py` canonical CLI, deprecate mismatched legacy scripts).  
7. Clean operational scripts (`run_experiments.sh`, `scripts/verify_phi4_codes.py`, `llm_judge.py` label fix).  
8. Remove bytecode artifacts and align comments/docs with runtime behavior.

---

## 7) Final Verification Status

- Deep static audit completed for all repository files (source, configs, tasks, references, scripts, tests, docs, and binary artifacts inventory).  
- Runtime test execution is blocked in current environment: Python interpreter is unavailable in shell (`python`, `py`, `python3` not found), so compile/test commands could not be executed here.  
- After environment restoration, run:
  - `python -m pytest -q`
  - `python src/evaluate.py --help`
  - `python src/compute_metrics.py --help`
  - smoke benchmark on independent + chain tasks.
