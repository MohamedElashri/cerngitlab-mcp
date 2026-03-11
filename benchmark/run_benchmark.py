#!/usr/bin/env python3
"""
CERN GitLab Benchmark - Simple Python Pipeline

Compares cerngitlab-cli vs cerngitlab-mcp approaches using AI evaluation.

Usage:
    python run_benchmark.py          # Run all questions
    python run_benchmark.py q1 q2    # Run specific questions
    python analyze_results.py <file> # Analyze results
"""

import asyncio
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class Config:
    """Benchmark configuration from environment variables."""
    
    # Required
    litellm_api_key: str = field(default_factory=lambda: os.getenv("CERNGITLAB_LITELLM_API_KEY", ""))
    gitlab_token: str = field(default_factory=lambda: os.getenv("CERNGITLAB_GITLAB_TOKEN", ""))
    
    # Optional with defaults
    litellm_api_base: str = field(default_factory=lambda: os.getenv("CERNGITLAB_LITELLM_BASE", "https://llmgw-litellm.web.cern.ch/v1"))
    litellm_model: str = field(default_factory=lambda: os.getenv("CERNGITLAB_LITELLM_MODEL", "gpt-5.2"))
    gitlab_url: str = field(default_factory=lambda: os.getenv("CERNGITLAB_GITLAB_URL", "https://gitlab.cern.ch"))
    llm_timeout: int = field(default_factory=lambda: int(os.getenv("CERNGITLAB_LLM_TIMEOUT", "120")))
    gitlab_timeout: int = field(default_factory=lambda: int(os.getenv("CERNGITLAB_GITLAB_TIMEOUT", "60")))
    max_retries: int = field(default_factory=lambda: int(os.getenv("CERNGITLAB_MAX_RETRIES", "3")))
    retry_delay: float = field(default_factory=lambda: float(os.getenv("CERNGITLAB_RETRY_DELAY", "2.0")))
    results_dir: str = "results"
    skill_file: str = "../SKILL.md"
    
    def validate(self) -> None:
        if not self.litellm_api_key:
            raise ValueError("CERNGITLAB_LITELLM_API_KEY environment variable is required")
        if not self.gitlab_token:
            raise ValueError("CERNGITLAB_GITLAB_TOKEN environment variable is required")
    
    @property
    def chat_completions_endpoint(self) -> str:
        return f"{self.litellm_api_base}/chat/completions"


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class JudgeResult:
    """AI Judge evaluation result."""
    question_id: str
    score: int
    reasoning: str
    facts_correct: list
    facts_incorrect: list
    facts_missing: list
    hallucinations: list
    evaluation_time: float
    confidence: float


@dataclass
class ModelResponse:
    """Model response from a session."""
    question_id: str
    approach: str
    response_text: str
    tool_calls: list
    total_time: float
    token_usage: Optional[dict] = None
    error: Optional[str] = None


@dataclass
class QuestionResult:
    """Result for a single question."""
    question_id: str
    question_text: str
    category: str
    difficulty: str
    cli_response: Optional[ModelResponse] = None
    cli_judge_result: Optional[JudgeResult] = None
    mcp_response: Optional[ModelResponse] = None
    mcp_judge_result: Optional[JudgeResult] = None


# =============================================================================
# AI Judge
# =============================================================================

class AIJudge:
    """Scores model responses from 0-5."""
    
    SYSTEM_PROMPT = """You are an expert evaluator for CERN GitLab benchmark responses.
Score model responses from 0-5 based on accuracy compared to reference answers.

SCORING CRITERIA:
- 5/5: All facts correct, properly sourced, complete answer
- 4/5: Minor details incorrect but core facts accurate
- 3/5: Major facts correct but missing key details
- 2/5: Some correct information but significant errors
- 1/5: Mostly incorrect or hallucinated information
- 0/5: No answer or completely wrong

Provide evaluation in JSON format:
{
    "score": <integer 0-5>,
    "reasoning": "<brief explanation>",
    "facts_correct": ["fact1", "fact2"],
    "facts_incorrect": [{"stated": "wrong", "correct": "right"}],
    "facts_missing": ["missing fact"],
    "hallucinations": ["invented fact"],
    "confidence": <float 0.0-1.0>
}"""

    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.AsyncClient(
            timeout=config.llm_timeout,
            headers={
                "Authorization": f"Bearer {config.litellm_api_key}",
                "Content-Type": "application/json",
            },
        )
    
    async def close(self):
        await self.client.aclose()
    
    async def evaluate(
        self,
        question_id: str,
        question: str,
        reference: dict,
        model_response: str,
    ) -> JudgeResult:
        """Evaluate a model response."""
        start = time.time()
        
        prompt = f"""QUESTION: {question}

REFERENCE ANSWER: {reference.get('full_answer', '')}

KEY FACTS: {json.dumps(reference.get('facts', {}), indent=2)}

MODEL RESPONSE:
{model_response}

Provide evaluation in JSON format as described in the system prompt."""

        payload = {
            "model": self.config.litellm_model,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
        }
        
        for attempt in range(self.config.max_retries):
            try:
                resp = await self.client.post(
                    self.config.chat_completions_endpoint,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                
                # Parse JSON
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                if content.endswith("```"):
                    content = content[:-3]
                
                eval_data = json.loads(content.strip())
                
                return JudgeResult(
                    question_id=question_id,
                    score=max(0, min(5, int(eval_data.get("score", 0)))),
                    reasoning=eval_data.get("reasoning", ""),
                    facts_correct=eval_data.get("facts_correct", []),
                    facts_incorrect=eval_data.get("facts_incorrect", []),
                    facts_missing=eval_data.get("facts_missing", []),
                    hallucinations=eval_data.get("hallucinations", []),
                    evaluation_time=time.time() - start,
                    confidence=float(eval_data.get("confidence", 0.5)),
                )
                
            except Exception as e:
                logger.warning(f"Judge attempt {attempt + 1} failed: {e}")
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(self.config.retry_delay)
        
        raise RuntimeError("Judge failed after all retries")


# =============================================================================
# Benchmark Runner
# =============================================================================

class BenchmarkRunner:
    """Runs benchmark tests."""
    
    def __init__(self, config: Config):
        self.config = config
        self.client = httpx.AsyncClient(
            timeout=config.llm_timeout,
            headers={
                "Authorization": f"Bearer {config.litellm_api_key}",
                "Content-Type": "application/json",
            },
        )
        self.judge = AIJudge(config)
        self.questions = self._load_json("questions.json")
        self.references = self._load_json("reference_answers.json")
        self.skill_content = self._load_skill()
        
        Path(config.results_dir).mkdir(exist_ok=True)
    
    def _load_json(self, name: str) -> dict:
        with open(name, "r") as f:
            return json.load(f)
    
    def _load_skill(self) -> str:
        path = Path(self.config.skill_file)
        return path.read_text() if path.exists() else ""
    
    async def close(self):
        await self.client.aclose()
        await self.judge.close()
    
    def _build_cli_prompt(self) -> str:
        return f"""You are an AI assistant helping users query CERN GitLab repositories.
You have access to the cerngitlab-cli command-line interface with these tools:

1. search-projects - Search for projects by keyword/topic/language
2. get-project-info - Get detailed project metadata
3. list-files - List files in a repository
4. get-file - Read a specific file
5. get-readme - Get project README
6. search-code - Search code across repositories (requires auth)
7. search-lhcb-stack - Search code in LHCb software stacks
8. search-issues - Search issues
9. get-wiki - Access wiki pages (requires auth)
10. inspect-project - Comprehensive project analysis
11. list-releases - List project releases
12. get-release - Get specific release details
13. list-tags - List project tags
14. test-connection - Test GitLab connection

GITLAB CONFIGURATION:
- URL: {self.config.gitlab_url}
- Token: [CONFIGURED]
- Timeout: {self.config.gitlab_timeout}s

Use appropriate tools to answer questions. Cite which tool you used. Be precise with IDs, paths, and versions."""

    def _build_mcp_prompt(self) -> str:
        return f"""You are an AI assistant with access to the CERN GitLab MCP server.

{self.skill_content}

GITLAB CONFIGURATION:
- URL: {self.config.gitlab_url}
- Token: [CONFIGURED]
- Timeout: {self.config.gitlab_timeout}s

Use the MCP tools to query CERN GitLab. Cite which tool you used. Be precise with technical details."""

    async def _call_llm(self, messages: list) -> dict:
        """Call LiteLLM API."""
        payload = {
            "model": self.config.litellm_model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 4000,
        }
        
        for attempt in range(self.config.max_retries):
            try:
                resp = await self.client.post(
                    self.config.chat_completions_endpoint,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return {
                    "content": data["choices"][0]["message"]["content"],
                    "tool_calls": data["choices"][0]["message"].get("tool_calls", []),
                    "usage": data.get("usage"),
                }
            except httpx.TimeoutException as e:
                logger.warning(f"LLM timeout (attempt {attempt + 1}): {e}")
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(self.config.retry_delay)
            except httpx.HTTPError as e:
                logger.error(f"LLM API error: {e}")
                raise
        
        raise RuntimeError("LLM call failed after all retries")
    
    async def run_session(
        self,
        question: dict,
        approach: str,
    ) -> ModelResponse:
        """Run a single question session."""
        start = time.time()
        system_prompt = self._build_cli_prompt() if approach == "cli" else self._build_mcp_prompt()
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question["question"]},
        ]
        
        try:
            response = await self._call_llm(messages)
            return ModelResponse(
                question_id=question["id"],
                approach=approach,
                response_text=response["content"],
                tool_calls=response.get("tool_calls", []),
                total_time=time.time() - start,
                token_usage=response.get("usage"),
            )
        except httpx.TimeoutException as e:
            return ModelResponse(
                question_id=question["id"],
                approach=approach,
                response_text="",
                tool_calls=[],
                total_time=time.time() - start,
                error=f"Timeout: {e}",
            )
        except Exception as e:
            return ModelResponse(
                question_id=question["id"],
                approach=approach,
                response_text="",
                tool_calls=[],
                total_time=time.time() - start,
                error=str(e),
            )
    
    def _get_reference(self, question_id: str) -> Optional[dict]:
        for ref in self.references.get("reference_answers", []):
            if ref["question_id"] == question_id:
                return ref
        return None
    
    async def run_benchmark(self, question_ids: Optional[list] = None) -> dict:
        """Run the complete benchmark."""
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        started_at = datetime.now().isoformat()
        
        # Filter questions
        questions = self.questions["questions"]
        if question_ids:
            questions = [q for q in questions if q["id"] in question_ids]
        
        logger.info(f"Running benchmark {run_id} with {len(questions)} questions")
        
        results = []
        for q in questions:
            logger.info(f"Running {q['id']}: {q['question'][:50]}...")
            
            result = QuestionResult(
                question_id=q["id"],
                question_text=q["question"],
                category=q.get("category", "Unknown"),
                difficulty=q.get("difficulty", "medium"),
            )
            
            # CLI approach
            logger.info(f"  Testing CLI...")
            cli_resp = await self.run_session(q, "cli")
            result.cli_response = cli_resp
            
            ref = self._get_reference(q["id"])
            if cli_resp.error is None and ref:
                judge_result = await self.judge.evaluate(
                    q["id"], q["question"], ref, cli_resp.response_text
                )
                result.cli_judge_result = judge_result
            
            # MCP approach
            logger.info(f"  Testing MCP...")
            mcp_resp = await self.run_session(q, "mcp")
            result.mcp_response = mcp_resp
            
            if mcp_resp.error is None and ref:
                judge_result = await self.judge.evaluate(
                    q["id"], q["question"], ref, mcp_resp.response_text
                )
                result.mcp_judge_result = judge_result
            
            results.append(result)
        
        # Calculate summary
        summary = self._calculate_summary(results)
        
        # Save results
        data = {
            "run_id": run_id,
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(),
            "config": {
                "model": self.config.litellm_model,
            },
            "summary": summary,
            "question_results": [
                self._result_to_dict(r) for r in results
            ],
        }
        
        filepath = Path(self.config.results_dir) / f"benchmark_{run_id}.json"
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Results saved to {filepath}")
        
        # Save summary
        summary_path = Path(self.config.results_dir) / f"summary_{run_id}.json"
        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)
        
        return data
    
    def _result_to_dict(self, r: QuestionResult) -> dict:
        d = {
            "question_id": r.question_id,
            "question_text": r.question_text,
            "category": r.category,
            "difficulty": r.difficulty,
        }
        
        if r.cli_response:
            d["cli_response"] = {
                "response_text": r.cli_response.response_text,
                "total_time": r.cli_response.total_time,
                "error": r.cli_response.error,
            }
        
        if r.cli_judge_result:
            d["cli_judge"] = {
                "score": r.cli_judge_result.score,
                "reasoning": r.cli_judge_result.reasoning,
                "confidence": r.cli_judge_result.confidence,
                "hallucinations": r.cli_judge_result.hallucinations,
            }
        
        if r.mcp_response:
            d["mcp_response"] = {
                "response_text": r.mcp_response.response_text,
                "total_time": r.mcp_response.total_time,
                "error": r.mcp_response.error,
            }
        
        if r.mcp_judge_result:
            d["mcp_judge"] = {
                "score": r.mcp_judge_result.score,
                "reasoning": r.mcp_judge_result.reasoning,
                "confidence": r.mcp_judge_result.confidence,
                "hallucinations": r.mcp_judge_result.hallucinations,
            }
        
        return d
    
    def _calculate_summary(self, results: list) -> dict:
        """Calculate summary statistics."""
        cli_scores = [r.cli_judge_result.score for r in results if r.cli_judge_result]
        mcp_scores = [r.mcp_judge_result.score for r in results if r.mcp_judge_result]
        
        cli_latencies = [r.cli_response.total_time for r in results if r.cli_response and not r.cli_response.error]
        mcp_latencies = [r.mcp_response.total_time for r in results if r.mcp_response and not r.mcp_response.error]
        
        return {
            "total_questions": len(results),
            "cli_avg_score": sum(cli_scores) / len(cli_scores) if cli_scores else 0.0,
            "mcp_avg_score": sum(mcp_scores) / len(mcp_scores) if mcp_scores else 0.0,
            "cli_avg_latency": sum(cli_latencies) / len(cli_latencies) if cli_latencies else 0.0,
            "mcp_avg_latency": sum(mcp_latencies) / len(mcp_latencies) if mcp_latencies else 0.0,
            "cli_success_rate": len(cli_scores) / len(results) if results else 0.0,
            "mcp_success_rate": len(mcp_scores) / len(results) if results else 0.0,
        }


# =============================================================================
# Results Analyzer
# =============================================================================

def analyze_results(filepath: str) -> None:
    """Analyze and print benchmark results."""
    with open(filepath, "r") as f:
        data = json.load(f)
    
    summary = data["summary"]
    
    print("\n" + "=" * 60)
    print("BENCHMARK ANALYSIS")
    print("=" * 60)
    print(f"Run ID: {data['run_id']}")
    print(f"Model: {data['config'].get('model', 'Unknown')}")
    print("")
    print("SUMMARY")
    print("-" * 40)
    print(f"Total Questions: {summary['total_questions']}")
    print("")
    print(f"CLI Average Score:  {summary['cli_avg_score']:.2f}/5")
    print(f"CLI Avg Latency:    {summary['cli_avg_latency']:.2f}s")
    print(f"CLI Success Rate:   {summary['cli_success_rate'] * 100:.1f}%")
    print("")
    print(f"MCP Average Score:  {summary['mcp_avg_score']:.2f}/5")
    print(f"MCP Avg Latency:    {summary['mcp_avg_latency']:.2f}s")
    print(f"MCP Success Rate:   {summary['mcp_success_rate'] * 100:.1f}%")
    print("")
    
    # Winner
    score_diff = summary["mcp_avg_score"] - summary["cli_avg_score"]
    if score_diff > 0.1:
        print(f"WINNER: MCP (score +{score_diff:.2f})")
    elif score_diff < -0.1:
        print(f"WINNER: CLI (score +{abs(score_diff):.2f})")
    else:
        print("RESULT: Tie")
    
    print("=" * 60)
    
    # Per-question breakdown
    print("\nPER-QUESTION BREAKDOWN")
    print("-" * 40)
    
    for qr in data["question_results"]:
        print(f"\n{qr['question_id']} ({qr['category']}):")
        
        if "cli_judge" in qr:
            print(f"  CLI: {qr['cli_judge']['score']}/5 - {qr['cli_judge']['reasoning'][:60]}...")
        if "mcp_judge" in qr:
            print(f"  MCP: {qr['mcp_judge']['score']}/5 - {qr['mcp_judge']['reasoning'][:60]}...")


# =============================================================================
# CLI
# =============================================================================

def print_usage():
    print("""
CERN GitLab Benchmark

Usage:
    python run_benchmark.py              Run all questions
    python run_benchmark.py q1 q2 q3     Run specific questions
    python analyze_results.py <file>     Analyze results

Required Environment Variables:
    export CERNGITLAB_LITELLM_API_KEY="your-key"
    export CERNGITLAB_GITLAB_TOKEN="glpat-token"

Optional:
    export CERNGITLAB_LITELLM_MODEL="gpt-5.2"
    export CERNGITLAB_LLM_TIMEOUT=120
""")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ["-h", "--help", "help"]:
        print_usage()
        sys.exit(0)
    
    question_ids = sys.argv[1:] if len(sys.argv) > 1 else None
    
    async def main():
        config = Config()
        try:
            config.validate()
        except ValueError as e:
            logger.error(e)
            print_usage()
            sys.exit(1)
        
        runner = BenchmarkRunner(config)
        try:
            results = await runner.run_benchmark(question_ids)
            
            # Print summary
            print("\n" + "=" * 60)
            print("BENCHMARK COMPLETE")
            print("=" * 60)
            summary = results["summary"]
            print(f"CLI Avg Score: {summary['cli_avg_score']:.2f}/5")
            print(f"MCP Avg Score: {summary['mcp_avg_score']:.2f}/5")
            print(f"CLI Avg Latency: {summary['cli_avg_latency']:.2f}s")
            print(f"MCP Avg Latency: {summary['mcp_avg_latency']:.2f}s")
            print("=" * 60)
        finally:
            await runner.close()
    
    asyncio.run(main())
