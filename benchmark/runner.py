"""
Benchmark Runner for CERN GitLab MCP.

Runs benchmark questions through both cerngitlab-cli and cerngitlab-mcp approaches,
collects responses, and evaluates them with AI Judge.
"""

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

from .config import BenchmarkConfig, BenchmarkRunConfig
from .judge import AIJudge, JudgeResult

logger = logging.getLogger(__name__)


@dataclass
class ModelResponse:
    """Response from a model session."""

    question_id: str
    approach: str  # "cli" or "mcp"
    response_text: str
    tool_calls: list[dict[str, Any]]
    total_time: float  # seconds
    token_usage: Optional[dict[str, int]] = None
    error: Optional[str] = None


@dataclass
class QuestionResult:
    """Result for a single benchmark question."""

    question_id: str
    question_text: str
    category: str
    difficulty: str

    # CLI approach results
    cli_response: Optional[ModelResponse] = None
    cli_judge_result: Optional[JudgeResult] = None

    # MCP approach results
    mcp_response: Optional[ModelResponse] = None
    mcp_judge_result: Optional[JudgeResult] = None


@dataclass
class BenchmarkResults:
    """Complete benchmark results."""

    run_id: str
    started_at: str
    completed_at: str
    config: dict

    # Results per question
    question_results: list[QuestionResult] = field(default_factory=list)

    # Summary statistics
    total_questions: int = 0
    cli_avg_score: float = 0.0
    mcp_avg_score: float = 0.0
    cli_avg_latency: float = 0.0
    mcp_avg_latency: float = 0.0
    cli_success_rate: float = 0.0
    mcp_success_rate: float = 0.0


class BenchmarkRunner:
    """Runs benchmark tests against both CLI and MCP approaches."""

    def __init__(
        self, config: BenchmarkConfig, run_config: Optional[BenchmarkRunConfig] = None
    ):
        """Initialize benchmark runner.

        Args:
            config: Benchmark configuration.
            run_config: Specific run configuration.
        """
        self.config = config
        self.run_config = run_config or BenchmarkRunConfig()
        self.run_config.validate()

        # Initialize HTTP client for LLM calls
        self.http_client = httpx.AsyncClient(
            timeout=config.llm_timeout,
            headers={
                "Authorization": f"Bearer {config.litellm_api_key}",
                "Content-Type": "application/json",
            },
        )

        # Initialize judge
        self.judge = AIJudge(config)

        # Load questions and reference answers
        self.questions = self._load_json(config.questions_file)
        self.reference_answers = self._load_json(config.reference_answers_file)

        # Create results directory
        Path(self.config.results_dir).mkdir(parents=True, exist_ok=True)

        # Skill file content for MCP approach
        self.skill_content = self._load_skill_file()

    def _load_json(self, filepath: str) -> dict:
        """Load JSON file."""
        with open(filepath, "r") as f:
            return json.load(f)

    def _load_skill_file(self) -> str:
        """Load SKILL.md file content."""
        skill_path = Path(self.config.skill_file)
        if not skill_path.exists():
            logger.warning(f"Skill file not found: {skill_path}")
            return ""
        return skill_path.read_text()

    async def close(self) -> None:
        """Cleanup resources."""
        await self.http_client.aclose()
        await self.judge.close()

    async def run_benchmark(self) -> BenchmarkResults:
        """Run the complete benchmark.

        Returns:
            BenchmarkResults with all scores and metrics.
        """
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        started_at = datetime.now().isoformat()

        logger.info(f"Starting benchmark run {run_id}")
        logger.info(f"Testing {len(self.questions['questions'])} questions")

        # Filter questions if specific IDs provided
        questions_to_run = self._filter_questions()

        # Run each question as isolated session
        question_results = []
        for question in questions_to_run:
            result = await self._run_question_session(question)
            question_results.append(result)

        completed_at = datetime.now().isoformat()

        # Build results
        results = BenchmarkResults(
            run_id=run_id,
            started_at=started_at,
            completed_at=completed_at,
            config={
                "model": self.config.litellm_model,
                "test_cli": self.run_config.test_cli,
                "test_mcp": self.run_config.test_mcp,
            },
            question_results=question_results,
        )

        # Calculate summary statistics
        self._calculate_summary(results)

        # Save results
        self._save_results(results)

        logger.info(
            f"Benchmark complete. CLI avg: {results.cli_avg_score:.2f}, "
            f"MCP avg: {results.mcp_avg_score:.2f}"
        )

        return results

    def _filter_questions(self) -> list[dict]:
        """Filter questions based on run config."""
        all_questions = self.questions["questions"]

        if self.run_config.question_ids:
            return [
                q for q in all_questions if q["id"] in self.run_config.question_ids
            ]

        return all_questions

    async def _run_question_session(self, question: dict) -> QuestionResult:
        """Run a single question as an isolated session.

        Each session is independent with fresh context.

        Args:
            question: Question dictionary.

        Returns:
            QuestionResult with responses and scores.
        """
        question_id = question["id"]
        question_text = question["question"]
        reference = self._get_reference_answer(question_id)

        logger.info(f"Running session for {question_id}: {question_text[:50]}...")

        result = QuestionResult(
            question_id=question_id,
            question_text=question_text,
            category=question.get("category", "Unknown"),
            difficulty=question.get("difficulty", "medium"),
        )

        # Run CLI approach
        if self.run_config.test_cli:
            logger.info(f"  Testing CLI approach for {question_id}")
            try:
                cli_response = await self._run_cli_session(question_text)
                result.cli_response = cli_response

                # Judge the response
                if cli_response.error is None and reference:
                    judge_result = await self.judge.evaluate(
                        question_id, question_text, reference, cli_response.response_text
                    )
                    result.cli_judge_result = judge_result
            except Exception as e:
                logger.error(f"CLI session failed for {question_id}: {e}")
                result.cli_response = ModelResponse(
                    question_id=question_id,
                    approach="cli",
                    response_text="",
                    tool_calls=[],
                    total_time=0,
                    error=str(e),
                )

        # Run MCP approach
        if self.run_config.test_mcp:
            logger.info(f"  Testing MCP approach for {question_id}")
            try:
                mcp_response = await self._run_mcp_session(question_text)
                result.mcp_response = mcp_response

                # Judge the response
                if mcp_response.error is None and reference:
                    judge_result = await self.judge.evaluate(
                        question_id, question_text, reference, mcp_response.response_text
                    )
                    result.mcp_judge_result = judge_result
            except Exception as e:
                logger.error(f"MCP session failed for {question_id}: {e}")
                result.mcp_response = ModelResponse(
                    question_id=question_id,
                    approach="mcp",
                    response_text="",
                    tool_calls=[],
                    total_time=0,
                    error=str(e),
                )

        return result

    async def _run_cli_session(self, question: str) -> ModelResponse:
        """Run a session using cerngitlab-cli approach.

        Simulates the CLI interaction by calling LLM with tool descriptions.

        Args:
            question: The question to answer.

        Returns:
            ModelResponse with the model's answer.
        """
        start_time = time.time()

        # Build system prompt for CLI approach
        system_prompt = self._build_cli_system_prompt()

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        try:
            response = await self._call_llm(messages)
            total_time = time.time() - start_time

            return ModelResponse(
                question_id="pending",  # Will be set by caller
                approach="cli",
                response_text=response["content"],
                tool_calls=response.get("tool_calls", []),
                total_time=total_time,
                token_usage=response.get("usage"),
            )

        except httpx.TimeoutException as e:
            total_time = time.time() - start_time
            logger.error(f"CLI session timeout: {e}")
            return ModelResponse(
                question_id="pending",
                approach="cli",
                response_text="",
                tool_calls=[],
                total_time=total_time,
                error=f"Timeout after {total_time:.1f}s: {str(e)}",
            )

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"CLI session error: {e}")
            raise

    async def _run_mcp_session(self, question: str) -> ModelResponse:
        """Run a session using cerngitlab-mcp approach.

        Uses MCP protocol with SKILL.md for tool context.

        Args:
            question: The question to answer.

        Returns:
            ModelResponse with the model's answer.
        """
        start_time = time.time()

        # Build system prompt for MCP approach
        system_prompt = self._build_mcp_system_prompt()

        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

        try:
            response = await self._call_llm(messages)
            total_time = time.time() - start_time

            return ModelResponse(
                question_id="pending",  # Will be set by caller
                approach="mcp",
                response_text=response["content"],
                tool_calls=response.get("tool_calls", []),
                total_time=total_time,
                token_usage=response.get("usage"),
            )

        except httpx.TimeoutException as e:
            total_time = time.time() - start_time
            logger.error(f"MCP session timeout: {e}")
            return ModelResponse(
                question_id="pending",
                approach="mcp",
                response_text="",
                tool_calls=[],
                total_time=total_time,
                error=f"Timeout after {total_time:.1f}s: {str(e)}",
            )

        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"MCP session error: {e}")
            raise

    def _build_cli_system_prompt(self) -> str:
        """Build system prompt for CLI approach.

        Describes the cerngitlab-cli tools and usage.
        """
        return f"""You are an AI assistant helping users query CERN GitLab repositories.
You have access to the cerngitlab-cli command-line interface with the following tools:

AVAILABLE CLI TOOLS:
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

USAGE:
- When the user asks about a project, use appropriate tools to find information
- Always cite which tool you used to get information
- If a tool requires authentication and you don't have it, say so
- Be precise with project IDs, paths, and versions
- Think step-by-step for complex questions

GITLAB CONFIGURATION:
- URL: {self.config.gitlab_url}
- Token: [CONFIGURED]
- Timeout: {self.config.gitlab_timeout}s

Provide accurate, factual answers based on the tool outputs."""

    def _build_mcp_system_prompt(self) -> str:
        """Build system prompt for MCP approach.

        Includes SKILL.md for tool context.
        """
        return f"""You are an AI assistant with access to the CERN GitLab MCP (Model Context Protocol) server.
You have access to cerngitlab-mcp tools for interacting with gitlab.cern.ch.

{self.skill_content}

GITLAB CONFIGURATION:
- URL: {self.config.gitlab_url}
- Token: [CONFIGURED]
- Timeout: {self.config.gitlab_timeout}s

USAGE GUIDELINES:
- Use the MCP tools to query CERN GitLab
- Always cite which tool you used
- Be precise with technical details (IDs, versions, paths)
- Think step-by-step for complex questions
- Handle timeouts gracefully - retry or explain the issue

Provide accurate, factual answers based on the tool outputs."""

    async def _call_llm(self, messages: list[dict]) -> dict:
        """Call LiteLLM API.

        Args:
            messages: List of message dictionaries.

        Returns:
            Model response dictionary.

        Raises:
            httpx.HTTPError: If API call fails.
        """
        payload = {
            "model": self.config.litellm_model,
            "messages": messages,
            "temperature": 0.2,  # Low temperature for factual accuracy
            "max_tokens": 4000,
        }

        for attempt in range(self.config.max_retries):
            try:
                response = await self.http_client.post(
                    self.config.chat_completions_endpoint, json=payload
                )
                response.raise_for_status()
                data = response.json()

                return {
                    "content": data["choices"][0]["message"]["content"],
                    "tool_calls": data["choices"][0]["message"].get("tool_calls", []),
                    "usage": data.get("usage"),
                }

            except httpx.TimeoutException as e:
                logger.warning(
                    f"LLM timeout (attempt {attempt + 1}/{self.config.max_retries}): {e}"
                )
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(self.config.retry_delay)

            except httpx.HTTPError as e:
                logger.error(f"LLM API error: {e}")
                raise

        raise RuntimeError("Failed to call LLM after all retries")

    def _get_reference_answer(self, question_id: str) -> Optional[dict]:
        """Get reference answer for a question."""
        for answer in self.reference_answers.get("reference_answers", []):
            if answer["question_id"] == question_id:
                return answer
        return None

    def _calculate_summary(self, results: BenchmarkResults) -> None:
        """Calculate summary statistics."""
        results.total_questions = len(results.question_results)

        # CLI statistics
        cli_scores = []
        cli_latencies = []
        cli_successes = 0

        for qr in results.question_results:
            if qr.cli_judge_result:
                cli_scores.append(qr.cli_judge_result.score)
                cli_successes += 1
            if qr.cli_response and qr.cli_response.error is None:
                cli_latencies.append(qr.cli_response.total_time)

        results.cli_avg_score = sum(cli_scores) / len(cli_scores) if cli_scores else 0.0
        results.cli_avg_latency = (
            sum(cli_latencies) / len(cli_latencies) if cli_latencies else 0.0
        )
        results.cli_success_rate = (
            cli_successes / results.total_questions if results.total_questions else 0.0
        )

        # MCP statistics
        mcp_scores = []
        mcp_latencies = []
        mcp_successes = 0

        for qr in results.question_results:
            if qr.mcp_judge_result:
                mcp_scores.append(qr.mcp_judge_result.score)
                mcp_successes += 1
            if qr.mcp_response and qr.mcp_response.error is None:
                mcp_latencies.append(qr.mcp_response.total_time)

        results.mcp_avg_score = sum(mcp_scores) / len(mcp_scores) if mcp_scores else 0.0
        results.mcp_avg_latency = (
            sum(mcp_latencies) / len(mcp_latencies) if mcp_latencies else 0.0
        )
        results.mcp_success_rate = (
            mcp_successes / results.total_questions if results.total_questions else 0.0
        )

    def _save_results(self, results: BenchmarkResults) -> None:
        """Save results to JSON file."""
        filename = f"benchmark_{results.run_id}.json"
        filepath = Path(self.config.results_dir) / filename

        # Convert to serializable dict
        data = {
            "run_id": results.run_id,
            "started_at": results.started_at,
            "completed_at": results.completed_at,
            "config": results.config,
            "summary": {
                "total_questions": results.total_questions,
                "cli_avg_score": results.cli_avg_score,
                "mcp_avg_score": results.mcp_avg_score,
                "cli_avg_latency": results.cli_avg_latency,
                "mcp_avg_latency": results.mcp_avg_latency,
                "cli_success_rate": results.cli_success_rate,
                "mcp_success_rate": results.mcp_success_rate,
            },
            "question_results": [],
        }

        for qr in results.question_results:
            question_data = {
                "question_id": qr.question_id,
                "question_text": qr.question_text,
                "category": qr.category,
                "difficulty": qr.difficulty,
            }

            if qr.cli_response:
                question_data["cli_response"] = {
                    "response_text": qr.cli_response.response_text,
                    "total_time": qr.cli_response.total_time,
                    "error": qr.cli_response.error,
                    "token_usage": qr.cli_response.token_usage,
                }

            if qr.cli_judge_result:
                question_data["cli_judge"] = {
                    "score": qr.cli_judge_result.score,
                    "reasoning": qr.cli_judge_result.reasoning,
                    "facts_correct": qr.cli_judge_result.facts_correct,
                    "facts_incorrect": qr.cli_judge_result.facts_incorrect,
                    "facts_missing": qr.cli_judge_result.facts_missing,
                    "hallucinations": qr.cli_judge_result.hallucinations,
                    "confidence": qr.cli_judge_result.confidence,
                }

            if qr.mcp_response:
                question_data["mcp_response"] = {
                    "response_text": qr.mcp_response.response_text,
                    "total_time": qr.mcp_response.total_time,
                    "error": qr.mcp_response.error,
                    "token_usage": qr.mcp_response.token_usage,
                }

            if qr.mcp_judge_result:
                question_data["mcp_judge"] = {
                    "score": qr.mcp_judge_result.score,
                    "reasoning": qr.mcp_judge_result.reasoning,
                    "facts_correct": qr.mcp_judge_result.facts_correct,
                    "facts_incorrect": qr.mcp_judge_result.facts_incorrect,
                    "facts_missing": qr.mcp_judge_result.facts_missing,
                    "hallucinations": qr.mcp_judge_result.hallucinations,
                    "confidence": qr.mcp_judge_result.confidence,
                }

            data["question_results"].append(question_data)

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        logger.info(f"Results saved to {filepath}")

        # Also save summary to a separate file
        summary_path = Path(self.config.results_dir) / f"summary_{results.run_id}.json"
        with open(summary_path, "w") as f:
            json.dump(data["summary"], f, indent=2)

        logger.info(f"Summary saved to {summary_path}")
