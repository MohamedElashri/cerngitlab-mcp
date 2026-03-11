# CERN GitLab Benchmark Pipeline

A  benchmark pipeline for comparing **cerngitlab-cli** vs **cerngitlab-mcp** approaches when answering questions about CERN GitLab repositories.

This benchmark suite:
- Tests both approaches with **identical questions**
- Uses **AI evaluation** (LiteLLM API) to score responses from 1-5
- Measures **accuracy**, **latency**, and **success rates**
- Handles **timeouts** gracefully for both LiteLLM and GitLab APIs
- Treats each question as an **isolated session** with fresh context
- Generates detailed **comparison reports**

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Benchmark Runner                          │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Question   │  │   Question   │  │   Question   │      │
│  │   Session 1  │  │   Session 2  │  │   Session N  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │               │
│         ▼                 ▼                 ▼               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ CLI + Model  │  │ CLI + Model  │  │ CLI + Model  │      │
│  │ MCP + Model  │  │ MCP + Model  │  │ MCP + Model  │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                 │               │
│         ▼                 ▼                 ▼               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              AI Judge (Scores 1-5)                   │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │  Results &      │
                  │  Analysis       │
                  └─────────────────┘
```

## Installation

The benchmark module is part of the `cerngitlab-mcp` package. Ensure you have the dependencies installed:

```bash
cd /home/melashri/projects/cerngitlab-mcp
uv sync
```

## Configuration

### Required Environment Variables

Set up your API credentials **securely** (e.g., using `.env` file or environment variables):

```bash
# LiteLLM API (CERN)
export CERNGITLAB_LITELLM_API_KEY="your-litellm-api-key"

# GitLab Personal Access Token
export CERNGITLAB_GITLAB_TOKEN="glpat-xxxxxxxxxxxx"
```

### Optional Environment Variables

```bash
# LiteLLM Configuration
export CERNGITLAB_LITELLM_BASE="https://llmgw-litellm.web.cern.ch/v1"
export CERNGITLAB_LITELLM_MODEL="gpt-5.2"

# Timeout Configuration (seconds)
export CERNGITLAB_LLM_TIMEOUT="120"        # LLM API timeout
export CERNGITLAB_GITLAB_TIMEOUT="60"      # GitLab API timeout
export CERNGITLAB_SESSION_TIMEOUT="300"    # Per-question session timeout

# Retry Configuration
export CERNGITLAB_MAX_RETRIES="3"
export CERNGITLAB_RETRY_DELAY="2.0"

# GitLab Configuration
export CERNGITLAB_GITLAB_URL="https://gitlab.cern.ch"
```

### Using a `.env` File

Create a `.env` file in the project root:

```bash
# .env file (DO NOT COMMIT - add to .gitignore)
CERNGITLAB_LITELLM_API_KEY=your-api-key-here
CERNGITLAB_GITLAB_TOKEN=glpat-your-token-here
CERNGITLAB_LITELLM_MODEL=gpt-5.2
CERNGITLAB_LLM_TIMEOUT=120
```

Load it before running:

```bash
source .env
# or use python-dotenv
```

## Usage

### Running the Benchmark

#### Run All Questions

```bash
python -m benchmark run
```

#### Run Specific Questions

```bash
python -m benchmark run -q q1 -q q2 -q q3
```

#### Test Only CLI Approach

```bash
python -m benchmark run --cli-only
```

#### Test Only MCP Approach

```bash
python -m benchmark run --mcp-only
```

#### Verbose Output

```bash
python -m benchmark run --verbose
```

#### Custom Output Directory

```bash
python -m benchmark run --output-dir ./my-results
```

### Analyzing Results

#### Analyze a Results File

```bash
python -m benchmark analyze benchmark/results/benchmark_20260311_120000.json
```

#### Show Configuration Info

```bash
python -m benchmark info
```

## Benchmark Questions

The benchmark includes **10 questions** across different categories:

| ID | Category | Difficulty | Tools Tested |
|----|----------|------------|--------------|
| q1 | Project Discovery | Easy | search-projects, get-project-info |
| q2 | Project Discovery | Easy | search-projects |
| q3 | Build Configuration | Easy | get-file, inspect-project |
| q4 | Project Structure | Medium | get-file |
| q5 | CI/CD Configuration | Medium | get-file, inspect-project |
| q6 | Legal/Compliance | Medium | get-file |
| q7 | Project Structure | Medium | list-files, get-file |
| q8 | Project Analysis | Easy | inspect-project |
| q9 | Configuration | Easy | test-connection |
| q10 | Multi-Step Research | Medium | search-projects, get-project-info |

### Why These Questions?

All questions focus on **stable information** that won't change frequently:
- Project IDs and paths (immutable)
- File contents (change infrequently)
- Configuration files (stable by nature)
- Project descriptions and purposes (rarely change)
- Build systems and structures (long-term decisions)

**Avoids** volatile metrics like:
- Latest releases
- Open issue counts
- Recent activity dates

## Scoring System

The AI Judge scores responses from **0-5**:

| Score | Criteria |
|-------|----------|
| 5/5 | All facts correct, properly sourced, complete answer |
| 4/5 | Minor details incorrect but core facts accurate |
| 3/5 | Major facts correct but missing key details |
| 2/5 | Some correct information but significant errors |
| 1/5 | Mostly incorrect or hallucinated information |
| 0/5 | No answer or completely wrong |

### Evaluation Criteria

The AI Judge evaluates:
1. **Factual Accuracy** - Project IDs, paths, versions must be exact
2. **Completeness** - All parts of the question answered
3. **Hallucinations** - Invented information is penalized
4. **Source Attribution** - References to tool outputs
5. **Confidence Level** - Judge's confidence in the score (0.0-1.0)

## Output Files

### Full Results (`benchmark_<timestamp>.json`)

```json
{
  "run_id": "20260311_120000",
  "started_at": "2026-03-11T12:00:00",
  "completed_at": "2026-03-11T12:10:00",
  "config": {
    "model": "gpt-5.2",
    "test_cli": true,
    "test_mcp": true
  },
  "summary": {
    "total_questions": 10,
    "cli_avg_score": 4.2,
    "mcp_avg_score": 4.5,
    "cli_avg_latency": 15.3,
    "mcp_avg_latency": 18.7,
    "cli_success_rate": 0.9,
    "mcp_success_rate": 0.95
  },
  "question_results": [...]
}
```

### Summary (`summary_<timestamp>.json`)

```json
{
  "total_questions": 10,
  "cli_avg_score": 4.2,
  "mcp_avg_score": 4.5,
  "cli_avg_latency": 15.3,
  "mcp_avg_latency": 18.7,
  "cli_success_rate": 0.9,
  "mcp_success_rate": 0.95
}
```

## Timeout Handling

The benchmark handles timeouts at multiple levels:

### LiteLLM API Timeouts

- **Default**: 120 seconds per request
- **Retries**: Up to 3 attempts with 2-second delays
- **Behavior**: Logs warning, retries, then marks as error

### GitLab API Timeouts

- **Default**: 60 seconds per request
- **Session Timeout**: 300 seconds per question
- **Behavior**: Graceful error handling, continues to next question

### Session Isolation

Each question runs in an **isolated session**:
- Fresh context for each question
- No carryover between questions
- Independent timeout handling
- Prevents cascading failures

## Adding Custom Questions

### 1. Add to `questions.json`

```json
{
  "id": "q11",
  "category": "Your Category",
  "difficulty": "easy|medium|hard",
  "question": "Your question text here?",
  "expected_tools": ["tool1", "tool2"],
  "stability": "high|very_high"
}
```

### 2. Add to `reference_answers.json`

```json
{
  "question_id": "q11",
  "category": "Your Category",
  "facts": {
    "fact1": "value1",
    "fact2": "value2"
  },
  "full_answer": "Complete reference answer",
  "scoring_criteria": {
    "fact1": {"required": true, "weight": 2},
    "fact2": {"required": false, "weight": 1}
  }
}
```

## Best Practices

### Running Benchmarks

1. **Run multiple times** for statistical significance
2. **Use consistent network conditions** for fair latency comparison
3. **Monitor API rate limits** to avoid throttling
4. **Save all results** for trend analysis

### Interpreting Results

1. **Look at confidence scores** - Low confidence may indicate ambiguous questions
2. **Check hallucination rates** - High rates suggest model is guessing
3. **Consider category breakdown** - One approach may excel in specific areas
4. **Factor in latency** - Small accuracy gains may not justify large latency costs


## Troubleshooting

### Common Issues

#### "CERNGITLAB_LITELLM_API_KEY environment variable is required"

**Solution**: Set the environment variable:
```bash
export CERNGITLAB_LITELLM_API_KEY="your-key"
```

#### "CERNGITLAB_GITLAB_TOKEN environment variable is required"

**Solution**: Create a GitLab token at https://gitlab.cern.ch/-/user_settings/personal_access_tokens

#### Timeout errors

**Solution**: Increase timeout values:
```bash
export CERNGITLAB_LLM_TIMEOUT=180
export CERNGITLAB_GITLAB_TIMEOUT=90
```

#### Low scores across the board

**Possible causes**:
- Model not receiving tool outputs
- Questions too ambiguous
- Reference answers too strict

**Solution**: Review question clarity and reference answer criteria
