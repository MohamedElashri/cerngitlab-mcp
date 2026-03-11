# CERN GitLab Benchmark - Simple Python Pipeline

A benchmark tool for comparing **cerngitlab-cli** vs **cerngitlab-mcp** approaches.

## Quick Start

```bash
cd benchmark

# Set required environment variables
export CERNGITLAB_LITELLM_API_KEY="your-litellm-api-key"
export CERNGITLAB_GITLAB_TOKEN="glpat-xxxxxxxxxxxx"

# Run all benchmark questions
python run_benchmark.py

# Run specific questions
python run_benchmark.py q1 q2 q3

# Analyze results
python analyze_results.py results/benchmark_*.json
```

## Configuration

### Required Environment Variables

```bash
export CERNGITLAB_LITELLM_API_KEY="your-api-key"
export CERNGITLAB_GITLAB_TOKEN="glpat-token"
```

### Optional Environment Variables

```bash
export CERNGITLAB_LITELLM_MODEL="gpt-5.2"      # Default: gpt-5.2
export CERNGITLAB_LITELLM_BASE="https://llmgw-litellm.web.cern.ch/v1"
export CERNGITLAB_LLM_TIMEOUT=120               # Default: 120 seconds
export CERNGITLAB_GITLAB_TIMEOUT=60             # Default: 60 seconds
export CERNGITLAB_MAX_RETRIES=3                 # Default: 3
export CERNGITLAB_RETRY_DELAY=2.0               # Default: 2.0 seconds
```

## Files

- `run_benchmark.py` - Main benchmark runner
- `analyze_results.py` - Results analyzer
- `questions.json` - 10 benchmark questions
- `reference_answers.json` - Reference answers with scoring criteria
- `results/` - Generated results (gitignored)

## Output

### Console Output

```
============================================================
BENCHMARK COMPLETE
============================================================
CLI Avg Score: 4.20/5
MCP Avg Score: 4.50/5
CLI Avg Latency: 15.30s
MCP Avg Latency: 18.70s
============================================================
```

### JSON Results

Saved to `results/benchmark_<timestamp>.json`:
- Full responses from both approaches
- AI judge scores and reasoning
- Latency measurements
- Per-question breakdown

### Analysis Report

Run `python analyze_results.py results/benchmark_*.json` for detailed report:
- Summary statistics
- Winner determination
- Per-question breakdown with judge reasoning
- Hallucination tracking

## How It Works

1. **Load questions** from `questions.json`
2. **For each question**, run two isolated sessions:
   - **CLI approach**: Model with cerngitlab-cli tool descriptions
   - **MCP approach**: Model with SKILL.md and MCP tool descriptions
3. **AI Judge** scores each response 0-5 against reference answers
4. **Calculate metrics**: accuracy, latency, success rates
5. **Save results** to JSON files

## Scoring

The AI Judge scores from **0-5**:

| Score | Criteria |
|-------|----------|
| 5/5 | All facts correct, complete answer |
| 4/5 | Minor details wrong, core facts accurate |
| 3/5 | Major facts correct, missing details |
| 2/5 | Some correct info, significant errors |
| 1/5 | Mostly incorrect or hallucinated |
| 0/5 | No answer or completely wrong |

## Questions

10 questions across different categories:

| ID | Category | Difficulty |
|----|----------|------------|
| q1 | Project Discovery | Easy |
| q2 | Project Discovery | Easy |
| q3 | Build Configuration | Easy |
| q4 | Project Structure | Medium |
| q5 | CI/CD Configuration | Medium |
| q6 | Legal/Compliance | Medium |
| q7 | Project Structure | Medium |
| q8 | Project Analysis | Easy |
| q9 | Configuration | Easy |
| q10 | Multi-Step Research | Medium |

All questions focus on **stable information** (project IDs, file contents, configurations) that won't change frequently.

## Timeout Handling

- **LLM API timeout**: Default 120s, configurable via `CERNGITLAB_LLM_TIMEOUT`
- **Retries**: Up to 3 attempts with 2s delay
- **Per-session timeout**: Each question runs independently
- **Graceful errors**: Failed questions don't stop the benchmark

## Example Session

```bash
# Set credentials
export CERNGITLAB_LITELLM_API_KEY="key123"
export CERNGITLAB_GITLAB_TOKEN="glpat-xyz"

# Run benchmark
python run_benchmark.py

# Output:
# 2026-03-11 12:00:00 - INFO - Running benchmark 20260311_120000 with 10 questions
# 2026-03-11 12:00:01 - INFO - Running q1: Find the LHCb DaVinci project...
# 2026-03-11 12:00:01 - INFO -   Testing CLI...
# 2026-03-11 12:00:15 - INFO -   Testing MCP...
# ...
# Results saved to results/benchmark_20260311_120000.json

# Analyze
python analyze_results.py results/benchmark_20260311_120000.json
```

## License

AGPL-3.0 (same as main project)
