# CERN GitLab Benchmark - LLM-Driven Tool Execution

A benchmark comparing **two approaches for LLM tool execution** when querying CERN GitLab.

## Quick Start

```bash
cd benchmark

# Install cerngitlab-mcp (required)
pip install cerngitlab-mcp

# Set environment variables
export CERNGITLAB_LITELLM_API_KEY="your-litellm-api-key"
export CERNGITLAB_GITLAB_TOKEN="glpat-xxxxxxxxxxxx"

# Run benchmark
python run_benchmark.py

# Analyze results
python analyze_results.py results/*.json
```

## What This Benchmarks

**Both approaches let the LLM drive tool execution:**

### Flow (Both Approaches)
```
┌─────────────┐
│    LLM      │  ← Given SKILL.md + tool descriptions
└──────┬──────┘
       │ "Call search-projects(query='DaVinci')"
       ▼
┌─────────────────┐
│   Benchmark     │  → Executes tool (CLI or MCP)
└──────┬──────────┘
       │ Returns result to LLM
       ▼
┌─────────────┐
│    LLM      │  → May call more tools or provide final answer
└─────────────┘
       │
       ▼
┌─────────────┐
│  AI Judge   │  → Scores answer 0-5 vs reference
└─────────────┘
```

### CLI Approach
- LLM given SKILL.md + tool descriptions
- LLM calls tools via OpenAI format
- Benchmark executes: `cerngitlab-cli <tool> <args>`
- Results returned to LLM
- LLM synthesizes final answer
- **AI Judge scores answer 0-5**

### MCP Approach
- LLM given SKILL.md + MCP protocol
- LLM calls tools via OpenAI format
- Benchmark executes: `await search_projects(...)`
- Results returned to LLM
- LLM synthesizes final answer
- **AI Judge scores answer 0-5**

## What's Compared

| Metric | Description |
|--------|-------------|
| **Accuracy Score** | AI Judge scores 0-5 vs reference answers |
| **Latency** | Total time (LLM + tool execution) |
| **Tool Calls** | Number of tools called per question |
| **Overhead** | Subprocess (CLI) vs direct calls (MCP) |
| **Hallucinations** | Invented facts detected by AI Judge |

## Installation Requirements

### Required

```bash
pip install cerngitlab-mcp
```

### Environment Variables

```bash
# Required
export CERNGITLAB_LITELLM_API_KEY="your-api-key"
export CERNGITLAB_GITLAB_TOKEN="glpat-token"

# Optional
export CERNGITLAB_LITELLM_MODEL="gpt-5.2"
export CERNGITLAB_LLM_TIMEOUT=120
```

## AI Judge

The AI Judge evaluates each response:

### Scoring Criteria

| Score | Criteria |
|-------|----------|
| 5/5 | All facts correct, complete answer |
| 4/5 | Minor details wrong, core facts accurate |
| 3/5 | Major facts correct, missing details |
| 2/5 | Some correct info, significant errors |
| 1/5 | Mostly incorrect or hallucinated |
| 0/5 | No answer or completely wrong |

### What Judge Evaluates

- **Factual accuracy** - Project IDs, paths, versions must be exact
- **Completeness** - All parts of question answered
- **Hallucinations** - Invented information penalized
- **Confidence** - Judge's confidence in score (0.0-1.0)

## How It Works

### Session Flow

1. **LLM receives question** + SKILL.md
2. **LLM calls tool** (OpenAI tool format)
3. **Benchmark executes tool**:
   - CLI: `subprocess.run(["cerngitlab-cli", ...])`
   - MCP: `await search_projects(...)`
4. **Result returned to LLM**
5. **Repeat** (up to 5 turns)
6. **LLM provides final answer**
7. **AI Judge scores** answer 0-5

### Tool Execution Loop

```python
while turn < max_turns:
    # Call LLM
    response = await call_llm(messages)
    
    # Check for tool calls
    if response.tool_calls:
        for tool_call in response.tool_calls:
            # Execute tool
            result = execute_tool(tool_call.name, tool_call.args)
            messages.append({"role": "tool", "content": result})
    else:
        # Final answer
        return response.content

# Judge the answer
judge_result = await judge.evaluate(question, answer, reference)
```

## Files

- `run_benchmark.py` - LLM-driven tool execution + AI Judge
- `analyze_results.py` - Results analyzer
- `questions.json` - 10 benchmark questions
- `reference_answers.json` - Reference answers
- `results/` - Generated results (gitignored)

### Analysis Report

```bash
python analyze_results.py results/benchmark_*.json
```

Shows:
- Summary statistics
- Winner determination
- Per-question breakdown with judge reasoning
- Hallucination tracking

## Questions

10 questions requiring tool usage:

| ID | Category | Expected Tools |
|----|----------|----------------|
| q1 | Project Discovery | search-projects, get-project-info |
| q2 | Project Discovery | search-projects |
| q3 | Build Configuration | get-file, inspect-project |
| q4 | Project Structure | get-file |
| q5 | CI/CD Configuration | get-file |
| q6 | Legal/Compliance | get-file |
| q7 | Project Structure | list-files, get-file |
| q8 | Project Analysis | inspect-project |
| q9 | Configuration | test-connection |
| q10 | Multi-Step Research | search-projects, get-project-info |

## Troubleshooting

### "cerngitlab-cli not found"

```bash
pip install cerngitlab-mcp
```

### "ModuleNotFoundError: No module named 'cerngitlab_mcp'"

```bash
pip install cerngitlab-mcp
```

### "CERNGITLAB_LITELLM_API_KEY environment variable is required"

```bash
export CERNGITLAB_LITELLM_API_KEY="your-key"
```

