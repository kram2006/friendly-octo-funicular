# Ground Truth Comparison Usage Guide

## Overview

The evaluation framework now supports automatic comparison of results with ground truth datasets. This feature helps you quickly assess model performance against established baselines.

## Quick Start

### Basic Usage

Run evaluation with comparison enabled:

```bash
python src/evaluate.py \
  --model your_model \
  --compare-with-ground-truth
```

This will:
1. Run the evaluation as normal
2. After completion, compare results with ground truth
3. Display a comprehensive comparison report

### Custom Ground Truth Directory

If your ground truth is in a different location:

```bash
python src/evaluate.py \
  --model your_model \
  --compare-with-ground-truth \
  --ground-truth-dir /path/to/ground_truth
```

## Ground Truth Directory Structure

The comparison function expects ground truth in this structure:

```
ground_truth_results/
├── dataset/
│   ├── model1_results/
│   │   ├── c1_1_model1_pass1.json
│   │   ├── c1_2_model1_pass1.json
│   │   └── ...
│   ├── model2_results/
│   │   └── ...
└── terraform_code/
    └── ...
```

## What Gets Compared

The comparison report includes:

### 1. Success Metrics
- **Plan Success**: Did terraform plan succeed?
- **Apply Success**: Did terraform apply succeed?
- **Spec Pass**: Did the generated code pass specification checks?

### 2. Code Similarity
- **BLEU Score**: Measures n-gram overlap with reference code
- **CodeBERT F1**: Semantic similarity using CodeBERT embeddings (if available)

### 3. Execution Metadata
- **Iterations**: Number of retry attempts needed
- **Generation Time**: LLM response time

## Sample Output

```
================================================================================
  COMPARISON WITH GROUND TRUTH RESULTS
================================================================================
  Results dir:      results/dataset/phi4_or
  Ground truth dir: ground_truth_results
================================================================================

Using ground truth: ground_truth_results/dataset/claude46_opus_results_dataset

Comparison Summary:
Task     File                           Plan  Apply  Spec     BLEU
-------- ------------------------------ ------ ------ ------ --------
C1.1     c1_1_phi4or_pass1.json           ✓      ✓      ✓    0.7234
C1.2     c1_2_phi4or_pass1.json           ✓      ✗      ✓    0.6891
C1.3     c1_3_phi4or_pass1.json           ✓      ✓      ✓    0.8123
C2.2     c2_2_phi4or_pass1.json           ✗      ✗      ✗    0.3456
C2.3     c2_3_phi4or_pass1.json           ✓      ✓      ✓    0.7890
C5.2     c5_2_phi4or_pass1.json           ✓      ✓      ✗    0.6543
D1.2     d1_2_phi4or_pass1.json           ✓      ✓      ✓    0.9012
D2.2     d2_2_phi4or_pass1.json           ✓      ✓      ✓    0.8765
R1.2     r1_2_phi4or_pass1.json           ✓      ✓      ✓    0.7654
U1.2     u1_2_phi4or_pass1.json           ✓      ✓      ✓    0.8234
-------- ------------------------------ ------ ------ ------ --------

Overall Agreement:
  Plan Success Match:  8/10 (80.0%)
  Apply Success Match: 7/10 (70.0%)
  Spec Pass Match:     8/10 (80.0%)
  Avg Code BLEU:       0.7380

Comparison complete!
```

## Understanding the Results

### Success Indicators
- ✓ (Green checkmark): Result matches ground truth
- ✗ (Red X): Result differs from ground truth

### Metrics Interpretation

**High Agreement (>80%)**
- Model performs similarly to ground truth
- Good consistency with expected behavior

**Medium Agreement (50-80%)**
- Some differences in performance
- May indicate model-specific behavior or improvements

**Low Agreement (<50%)**
- Significant divergence from ground truth
- Review individual task failures for patterns

### BLEU Score Ranges
- **0.9-1.0**: Near-identical code (excellent)
- **0.7-0.9**: Very similar code structure (good)
- **0.5-0.7**: Similar approach, different implementation (acceptable)
- **<0.5**: Different approach or errors (needs review)

## Common Use Cases

### 1. Model Evaluation
Compare new models against established baselines:

```bash
# Run evaluation
python src/evaluate.py --model new_model --samples 10

# Compare with ground truth
python src/evaluate.py --model new_model --samples 10 --compare-with-ground-truth
```

### 2. Regression Testing
Verify that code changes don't degrade performance:

```bash
# After making changes to the framework
python src/evaluate.py \
  --model reference_model \
  --compare-with-ground-truth \
  --samples 5
```

### 3. Strategy Comparison
Compare different prompt strategies:

```bash
# Baseline
python src/evaluate.py --model phi4 --enhance-strat "" --compare-with-ground-truth

# Chain-of-Thought
python src/evaluate.py --model phi4 --enhance-strat COT --compare-with-ground-truth

# Few-Shot
python src/evaluate.py --model phi4 --enhance-strat FSP --compare-with-ground-truth
```

## Troubleshooting

### "No ground truth dataset directories found"

**Cause**: Ground truth directory doesn't contain expected structure

**Solution**:
1. Verify ground truth directory exists
2. Check that it contains `dataset/` subdirectory
3. Ensure dataset subdirectory contains model result folders

### "No ground truth found for task X"

**Cause**: Ground truth doesn't have results for that specific task

**Solution**:
- Verify ground truth has complete task coverage
- Check task ID naming matches (e.g., "C1.1" vs "c1_1")

### "No comparison results generated"

**Cause**: No matching files between results and ground truth

**Solution**:
- Check that evaluation completed successfully
- Verify file naming patterns match
- Ensure result files exist in output directory

## Advanced Usage

### Comparing Specific Tasks

Run comparison for a single task:

```bash
python src/evaluate.py \
  --model phi4 \
  --task_id C1.1 \
  --compare-with-ground-truth
```

### Comparing Chain Executions

Run comparison for a task chain:

```bash
python src/evaluate.py \
  --model phi4 \
  --chain C1.3,U1.2,D1.2 \
  --compare-with-ground-truth
```

### Batch Comparisons

Compare multiple models:

```bash
for model in phi4 llama3 mistral; do
  echo "Comparing $model..."
  python src/evaluate.py --model $model --compare-with-ground-truth
done
```

## Integration with Existing Workflows

The comparison feature integrates seamlessly:

1. **No impact on evaluation**: Comparison runs AFTER evaluation completes
2. **Optional**: Only runs when `--compare-with-ground-truth` is specified
3. **Non-blocking**: Comparison errors won't fail the evaluation
4. **Complementary**: Works with all existing flags and options

## Next Steps

After reviewing the comparison report:

1. **Analyze Discrepancies**: Investigate tasks where results differ from ground truth
2. **Review Code**: Check generated code for tasks with low BLEU scores
3. **Iterate**: Adjust model configuration or prompts based on findings
4. **Document**: Save comparison outputs for future reference

## Tips

1. **Establish Baselines**: Run a high-quality model first to create ground truth
2. **Multiple Samples**: Use `--samples` to get statistical significance
3. **Plan-Only Mode**: Use `--plan-only` for faster comparison iterations
4. **Version Control**: Keep ground truth datasets in version control
5. **Automate**: Add comparison to CI/CD pipelines for continuous monitoring
