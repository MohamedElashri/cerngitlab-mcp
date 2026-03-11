#!/usr/bin/env python3
"""
CERN GitLab Benchmark - LLM-driven Tool Execution

Compares two approaches for tool execution:
1. MCP approach: LLM connected to MCP server, calls tools via MCP protocol
2. CLI approach: LLM given SKILL.md, calls tools via CLI commands

In BOTH cases:
- LLM decides which tools to call
- Tools are actually executed
- Results returned to LLM for final answer

Usage:
    python run_benchmark.py          # Run all questions
    python run_benchmark.py q1 q2    # Run specific questions
    python analyze_results.py <file> # Analyze results

Requirements:
    - cerngitlab-mcp package installed
    - CERNGITLAB_LITELLM_API_KEY environment variable
    - CERNGITLAB_GITLAB_TOKEN environment variable
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

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
class ToolCall:
    """A tool call from the LLM."""
    tool_name: str
    arguments: dict
    output: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ModelResponse:
    """Model response from a session."""
    question_id: str
    approach: str  # "cli" or "mcp"
    final_answer: str
    tool_calls: list[ToolCall]
    total_time: float
    conversation_turns: int = 0
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
    cli_judge_result: Optional[dict] = None
    mcp_response: Optional[ModelResponse] = None
    mcp_judge_result: Optional[dict] = None


# =============================================================================
# Tool Executors
# =============================================================================

class CLIExecutor:
    """Executes tools via cerngitlab-cli commands."""
    
    def __init__(self, config: Config):
        self.config = config
        self.env = os.environ.copy()
        self.env["CERNGITLAB_GITLAB_TOKEN"] = config.gitlab_token
        self.env["CERNGITLAB_GITLAB_URL"] = config.gitlab_url
        self.env["CERNGITLAB_TIMEOUT"] = str(config.gitlab_timeout)
    
    def execute(self, tool_name: str, arguments: dict) -> tuple[Optional[str], Optional[str]]:
        """
        Execute a tool via cerngitlab-cli.
        
        Returns:
            (output, error) tuple
        """
        # Map tool names to CLI commands
        tool_to_cli = {
            "search-projects": "search-projects",
            "get-project-info": "get-project-info",
            "list-files": "list-files",
            "get-file": "get-file",
            "get-readme": "get-readme",
            "search-code": "search-code",
            "search-lhcb-stack": "search-lhcb-stack",
            "search-issues": "search-issues",
            "get-wiki": "get-wiki",
            "inspect-project": "inspect-project",
            "list-releases": "list-releases",
            "get-release": "get-release",
            "list-tags": "list-tags",
            "test-connection": "test-connection",
        }
        
        cli_command = tool_to_cli.get(tool_name)
        if not cli_command:
            return None, f"Unknown tool: {tool_name}"
        
        # Build command arguments
        args = [cli_command]
        for key, value in arguments.items():
            args.append(f"--{key}")
            args.append(str(value))
        
        try:
            result = subprocess.run(
                ["cerngitlab-cli"] + args,
                capture_output=True,
                text=True,
                env=self.env,
                timeout=self.config.gitlab_timeout,
            )
            
            if result.returncode != 0:
                return None, f"Command failed: {result.stderr}"
            
            return result.stdout, None
            
        except subprocess.TimeoutExpired:
            return None, f"Command timed out after {self.config.gitlab_timeout}s"
        except FileNotFoundError:
            return None, "cerngitlab-cli not found. Install with: pip install cerngitlab-mcp"
        except Exception as e:
            return None, f"Error: {str(e)}"


class MCPExecutor:
    """Executes tools via MCP server Python functions."""
    
    def __init__(self, config: Config):
        self.config = config
        self.tools = {}
        self.available = False
        
        # Try to import MCP tools
        try:
            from cerngitlab_mcp.tools import (
                search_projects,
                get_project_info,
                list_project_files,
                get_file_content,
                get_project_readme,
                search_code,
                search_lhcb_stack,
                search_issues,
                get_wiki_pages,
                inspect_project,
                list_releases,
                get_release,
                list_tags,
                test_connectivity,
            )
            self.tools = {
                "search-projects": search_projects,
                "get-project-info": get_project_info,
                "list-files": list_project_files,
                "get-file": get_file_content,
                "get-readme": get_project_readme,
                "search-code": search_code,
                "search-lhcb-stack": search_lhcb_stack,
                "search-issues": search_issues,
                "get-wiki": get_wiki_pages,
                "inspect-project": inspect_project,
                "list-releases": list_releases,
                "get-release": get_release,
                "list-tags": list_tags,
                "test-connection": test_connectivity,
            }
            self.available = True
            logger.info("MCP tools loaded successfully")
        except ImportError as e:
            logger.warning(f"Could not import MCP tools: {e}")
            self.available = False
    
    async def execute(self, tool_name: str, arguments: dict) -> tuple[Optional[dict], Optional[str]]:
        """Execute a tool via MCP Python function."""
        if not self.available:
            return None, "MCP tools not available"
        
        tool = self.tools.get(tool_name)
        if not tool:
            return None, f"Unknown tool: {tool_name}"
        
        try:
            # Set environment for the tool
            os.environ["CERNGITLAB_GITLAB_TOKEN"] = self.config.gitlab_token
            os.environ["CERNGITLAB_GITLAB_URL"] = self.config.gitlab_url
            
            result = await tool(**arguments)
            return result, None
            
        except Exception as e:
            return None, f"Tool error: {str(e)}"


# =============================================================================
# AI Judge
# =============================================================================

class AIJudge:
    """Scores model responses from 0-5 based on accuracy."""
    
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
    ) -> dict:
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
                
                return {
                    "question_id": question_id,
                    "score": max(0, min(5, int(eval_data.get("score", 0)))),
                    "reasoning": eval_data.get("reasoning", ""),
                    "facts_correct": eval_data.get("facts_correct", []),
                    "facts_incorrect": eval_data.get("facts_incorrect", []),
                    "facts_missing": eval_data.get("facts_missing", []),
                    "hallucinations": eval_data.get("hallucinations", []),
                    "confidence": float(eval_data.get("confidence", 0.5)),
                    "evaluation_time": time.time() - start,
                }
                
            except Exception as e:
                logger.warning(f"Judge attempt {attempt + 1} failed: {e}")
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(self.config.retry_delay)
        
        raise RuntimeError("Judge failed after all retries")


# =============================================================================
# LLM Session Runner
# =============================================================================

class LLMSessionRunner:
    """Runs an LLM session with tool execution loop."""
    
    def __init__(self, config: Config, executor, system_prompt: str, is_async: bool = False):
        self.config = config
        self.executor = executor
        self.system_prompt = system_prompt
        self.is_async = is_async  # True for MCP, False for CLI
        
        self.client = httpx.AsyncClient(
            timeout=config.llm_timeout,
            headers={
                "Authorization": f"Bearer {config.litellm_api_key}",
                "Content-Type": "application/json",
            },
        )
        
        self.conversation_history = []
        self.tool_calls_made = []
    
    async def close(self):
        await self.client.aclose()
    
    def _build_tool_prompt(self) -> str:
        """Build the tool description prompt."""
        return """
You have access to the following tools to query CERN GitLab:

1. search-projects(query, language, topic, sort_by, order, per_page) - Search for projects
2. get-project-info(project) - Get project metadata
3. list-files(project, path, ref, recursive, per_page) - List files in repository
4. get-file(project, file_path, ref) - Read a specific file
5. get-readme(project, ref) - Get project README
6. search-code(search_term, project, scope, ref, page, per_page) - Search code
7. search-lhcb-stack(search_term, stack, project, scope, ref, page, per_page) - Search LHCb stack
8. search-issues(search_term, project, state, per_page) - Search issues
9. get-wiki(project, page_slug) - Access wiki pages
10. inspect-project(project, ref) - Comprehensive project analysis
11. list-releases(project, per_page) - List releases
12. get-release(project, tag_name) - Get release details
13. list-tags(project, search, sort, per_page) - List tags
14. test-connection() - Test GitLab connection

To use a tool, respond with JSON:
{
    "tool_call": {
        "name": "tool-name",
        "arguments": {"arg1": "value1", "arg2": "value2"}
    }
}

After receiving tool results, provide your final answer:
{
    "final_answer": "Your complete answer here"
}

Think step-by-step. Use tools to gather information before answering."""

    async def _call_llm(self, messages: list) -> dict:
        """Call LiteLLM API."""
        payload = {
            "model": self.config.litellm_model,
            "messages": messages,
            "tools": self._get_tool_definitions(),
            "tool_choice": "auto",
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
                return data
                
            except httpx.TimeoutException as e:
                logger.warning(f"LLM timeout (attempt {attempt + 1}): {e}")
                if attempt == self.config.max_retries - 1:
                    raise
                await asyncio.sleep(self.config.retry_delay)
            except httpx.HTTPError as e:
                logger.error(f"LLM API error: {e}")
                raise
        
        raise RuntimeError("LLM call failed after all retries")
    
    def _get_tool_definitions(self) -> list[dict]:
        """Get OpenAI-style tool definitions for the LLM."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "search-projects",
                    "description": "Search for CERN GitLab projects by keyword, topic, or language",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"},
                            "language": {"type": "string", "description": "Filter by language"},
                            "topic": {"type": "string", "description": "Filter by topic"},
                            "sort_by": {"type": "string", "description": "Sort field"},
                            "order": {"type": "string", "description": "Sort order"},
                            "per_page": {"type": "integer", "description": "Results count"}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get-project-info",
                    "description": "Get detailed project metadata",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string", "description": "Project ID or path"}
                        },
                        "required": ["project"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list-files",
                    "description": "List files in a repository",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string", "description": "Project ID or path"},
                            "path": {"type": "string", "description": "Directory path"},
                            "ref": {"type": "string", "description": "Branch/tag"},
                            "recursive": {"type": "boolean", "description": "List recursively"}
                        },
                        "required": ["project"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get-file",
                    "description": "Read a specific file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string", "description": "Project ID or path"},
                            "file_path": {"type": "string", "description": "File path"},
                            "ref": {"type": "string", "description": "Branch/tag"}
                        },
                        "required": ["project", "file_path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get-readme",
                    "description": "Get project README",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string", "description": "Project ID or path"},
                            "ref": {"type": "string", "description": "Branch/tag"}
                        },
                        "required": ["project"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search-code",
                    "description": "Search code across repositories",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "search_term": {"type": "string", "description": "Code to search for"},
                            "project": {"type": "string", "description": "Limit to project"}
                        },
                        "required": ["search_term"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "inspect-project",
                    "description": "Comprehensive project analysis",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project": {"type": "string", "description": "Project ID or path"},
                            "ref": {"type": "string", "description": "Branch/tag"}
                        },
                        "required": ["project"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "test-connection",
                    "description": "Test GitLab connection",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
        ]
    
    async def run(self, question: str) -> ModelResponse:
        """Run a complete LLM session with tool execution loop."""
        start_time = time.time()
        
        # Initialize conversation
        self.conversation_history = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": question},
        ]
        
        max_turns = 5  # Maximum conversation turns
        turn = 0
        
        while turn < max_turns:
            turn += 1
            
            # Call LLM
            response = await self._call_llm(self.conversation_history)
            
            # Check for tool calls
            message = response["choices"][0]["message"]
            tool_calls = message.get("tool_calls", [])
            
            if tool_calls:
                # Execute each tool call
                for tc in tool_calls:
                    func = tc.get("function", {})
                    tool_name = func.get("name", "")
                    args_str = func.get("arguments", "{}")
                    
                    try:
                        arguments = json.loads(args_str)
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    # Execute tool
                    if self.is_async:
                        output, error = await self.executor.execute(tool_name, arguments)
                    else:
                        output, error = self.executor.execute(tool_name, arguments)
                    
                    # Store tool call
                    tool_call = ToolCall(
                        tool_name=tool_name,
                        arguments=arguments,
                        output=output if output else None,
                        error=error,
                    )
                    self.tool_calls_made.append(tool_call)
                    
                    # Add tool result to conversation
                    self.conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id"),
                        "content": output if output else (error or "Error"),
                    })
                
                # Continue conversation
                self.conversation_history.append(message)
                
            else:
                # No tool calls - LLM provided final answer
                final_answer = message.get("content", "")
                
                return ModelResponse(
                    question_id="pending",
                    approach="mcp" if self.is_async else "cli",
                    final_answer=final_answer,
                    tool_calls=self.tool_calls_made,
                    total_time=time.time() - start_time,
                    conversation_turns=turn,
                    token_usage=response.get("usage"),
                )
        
        # Max turns reached
        return ModelResponse(
            question_id="pending",
            approach="mcp" if self.is_async else "cli",
            final_answer="Max conversation turns reached",
            tool_calls=self.tool_calls_made,
            total_time=time.time() - start_time,
            conversation_turns=turn,
            error="Max turns reached",
        )


# =============================================================================
# Benchmark Runner
# =============================================================================

class BenchmarkRunner:
    """Runs benchmark tests."""
    
    def __init__(self, config: Config):
        self.config = config
        self.cli_executor = CLIExecutor(config)
        self.mcp_executor = MCPExecutor(config)
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
    
    def _get_reference(self, question_id: str) -> Optional[dict]:
        for ref in self.references.get("reference_answers", []):
            if ref["question_id"] == question_id:
                return ref
        return None
    
    async def run_cli_session(self, question: dict) -> ModelResponse:
        """Run session with CLI tool execution."""
        system_prompt = f"""You are an AI assistant that uses cerngitlab-cli tools to answer questions about CERN GitLab.

{self.skill_content}

Use the tools described above to gather information. Think step-by-step."""
        
        runner = LLMSessionRunner(
            self.config,
            self.cli_executor,
            system_prompt,
            is_async=False,
        )
        
        try:
            response = await runner.run(question["question"])
            response.question_id = question["id"]
            return response
        finally:
            await runner.close()
    
    async def run_mcp_session(self, question: dict) -> ModelResponse:
        """Run session with MCP tool execution."""
        system_prompt = f"""You are an AI assistant with access to the CERN GitLab MCP server.

{self.skill_content}

Use the tools to gather information. Think step-by-step."""
        
        runner = LLMSessionRunner(
            self.config,
            self.mcp_executor,
            system_prompt,
            is_async=True,
        )
        
        try:
            response = await runner.run(question["question"])
            response.question_id = question["id"]
            return response
        finally:
            await runner.close()
    
    async def run_benchmark(self, question_ids: Optional[list] = None) -> dict:
        """Run the complete benchmark."""
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        started_at = datetime.now().isoformat()
        
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
            logger.info("  Testing CLI...")
            result.cli_response = await self.run_cli_session(q)
            
            # Judge CLI response
            ref = self._get_reference(q["id"])
            if result.cli_response and not result.cli_response.error and ref:
                logger.info("  Judging CLI...")
                result.cli_judge_result = await self.judge.evaluate(
                    q["id"], q["question"], ref, result.cli_response.final_answer
                )
            
            # MCP approach
            logger.info("  Testing MCP...")
            result.mcp_response = await self.run_mcp_session(q)
            
            # Judge MCP response
            if result.mcp_response and not result.mcp_response.error and ref:
                logger.info("  Judging MCP...")
                result.mcp_judge_result = await self.judge.evaluate(
                    q["id"], q["question"], ref, result.mcp_response.final_answer
                )
            
            results.append(result)
        
        # Calculate summary
        summary = self._calculate_summary(results)
        
        # Save results
        data = {
            "run_id": run_id,
            "started_at": started_at,
            "completed_at": datetime.now().isoformat(),
            "config": {"model": self.config.litellm_model},
            "summary": summary,
            "question_results": [self._result_to_dict(r) for r in results],
        }
        
        filepath = Path(self.config.results_dir) / f"benchmark_{run_id}.json"
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Results saved to {filepath}")
        
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
                "final_answer": r.cli_response.final_answer[:500],
                "total_time": r.cli_response.total_time,
                "tool_calls_count": len(r.cli_response.tool_calls),
                "error": r.cli_response.error,
            }
        
        if r.cli_judge_result:
            d["cli_judge"] = {
                "score": r.cli_judge_result["score"],
                "reasoning": r.cli_judge_result["reasoning"],
                "confidence": r.cli_judge_result["confidence"],
                "hallucinations": r.cli_judge_result["hallucinations"],
            }
        
        if r.mcp_response:
            d["mcp_response"] = {
                "final_answer": r.mcp_response.final_answer[:500],
                "total_time": r.mcp_response.total_time,
                "tool_calls_count": len(r.mcp_response.tool_calls),
                "error": r.mcp_response.error,
            }
        
        if r.mcp_judge_result:
            d["mcp_judge"] = {
                "score": r.mcp_judge_result["score"],
                "reasoning": r.mcp_judge_result["reasoning"],
                "confidence": r.mcp_judge_result["confidence"],
                "hallucinations": r.mcp_judge_result["hallucinations"],
            }
        
        return d
    
    def _calculate_summary(self, results: list) -> dict:
        """Calculate summary statistics including AI judge scores."""
        cli_times = [r.cli_response.total_time for r in results if r.cli_response and not r.cli_response.error]
        mcp_times = [r.mcp_response.total_time for r in results if r.mcp_response and not r.mcp_response.error]
        
        # AI Judge scores
        cli_scores = [r.cli_judge_result["score"] for r in results if r.cli_judge_result]
        mcp_scores = [r.mcp_judge_result["score"] for r in results if r.mcp_judge_result]
        
        return {
            "total_questions": len(results),
            "cli_avg_score": sum(cli_scores) / len(cli_scores) if cli_scores else 0.0,
            "mcp_avg_score": sum(mcp_scores) / len(mcp_scores) if mcp_scores else 0.0,
            "cli_avg_latency": sum(cli_times) / len(cli_times) if cli_times else 0.0,
            "mcp_avg_latency": sum(mcp_times) / len(mcp_times) if mcp_times else 0.0,
            "cli_avg_tool_calls": sum(len(r.cli_response.tool_calls) for r in results if r.cli_response) / len(results) if results else 0.0,
            "mcp_avg_tool_calls": sum(len(r.mcp_response.tool_calls) for r in results if r.mcp_response) / len(results) if results else 0.0,
        }


# =============================================================================
# Results Analyzer
# =============================================================================

def analyze_results(filepath: str) -> None:
    """Analyze and print benchmark results."""
    with open(filepath, "r") as f:
        data = json.load(f)
    
    summary = data["summary"]
    
    print("\n" + "=" * 70)
    print("BENCHMARK ANALYSIS")
    print("=" * 70)
    print(f"Run ID: {data['run_id']}")
    print(f"Model: {data['config'].get('model', 'Unknown')}")
    print("")
    print("SUMMARY")
    print("-" * 40)
    print(f"Total Questions: {summary['total_questions']}")
    print("")
    print(f"CLI Avg Latency:     {summary['cli_avg_latency']:.2f}s")
    print(f"CLI Avg Tool Calls:  {summary['cli_avg_tool_calls']:.1f}")
    print("")
    print(f"MCP Avg Latency:     {summary['mcp_avg_latency']:.2f}s")
    print(f"MCP Avg Tool Calls:  {summary['mcp_avg_tool_calls']:.1f}")
    print("")
    
    latency_diff = summary["cli_avg_latency"] - summary["mcp_avg_latency"]
    if latency_diff > 1.0:
        print(f"MCP is {latency_diff:.2f}s faster")
    elif latency_diff < -1.0:
        print(f"CLI is {abs(latency_diff):.2f}s faster")
    else:
        print("Latency is similar")
    
    print("=" * 70)


# =============================================================================
# CLI
# =============================================================================

def print_usage():
    print("""
CERN GitLab Benchmark - LLM-driven Tool Execution

Usage:
    python run_benchmark.py              Run all questions
    python run_benchmark.py q1 q2 q3     Run specific questions
    python analyze_results.py <file>     Analyze results

Requirements:
    - cerngitlab-mcp package installed (pip install cerngitlab-mcp)
    - CERNGITLAB_LITELLM_API_KEY environment variable
    - CERNGITLAB_GITLAB_TOKEN environment variable

Both approaches let the LLM decide which tools to call:
- CLI: LLM calls tools → we execute cerngitlab-cli → return results
- MCP: LLM calls tools → we execute Python functions → return results
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
            
            print("\n" + "=" * 60)
            print("BENCHMARK COMPLETE")
            print("=" * 60)
            summary = results["summary"]
            print(f"CLI Avg Score: {summary['cli_avg_score']:.2f}/5")
            print(f"MCP Avg Score: {summary['mcp_avg_score']:.2f}/5")
            print(f"CLI Avg Latency: {summary['cli_avg_latency']:.2f}s")
            print(f"MCP Avg Latency: {summary['mcp_avg_latency']:.2f}s")
            print(f"CLI Avg Tool Calls: {summary['cli_avg_tool_calls']:.1f}")
            print(f"MCP Avg Tool Calls: {summary['mcp_avg_tool_calls']:.1f}")
            print("=" * 60)
        finally:
            pass  # Cleanup handled in runner
    
    asyncio.run(main())
