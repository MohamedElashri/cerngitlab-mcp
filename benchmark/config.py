"""
Configuration module for CERN GitLab Benchmark.

Handles API keys, timeouts, and other benchmark settings.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark runs."""

    # Required Configuration (no defaults)
    litellm_api_key: str
    gitlab_token: str

    # LiteLLM API Configuration
    litellm_api_base: str = "https://llmgw-litellm.web.cern.ch/v1"
    litellm_model: str = "gpt-5.2"

    # CERN GitLab Configuration
    gitlab_url: str = "https://gitlab.cern.ch"

    # Timeout Configuration (in seconds)
    llm_timeout: int = 120  # LiteLLM API timeout
    gitlab_timeout: int = 60  # GitLab API timeout

    # Retry Configuration
    max_retries: int = 3
    retry_delay: float = 2.0  # seconds between retries

    # Benchmark Configuration
    questions_file: str = "benchmark/questions.json"
    reference_answers_file: str = "benchmark/reference_answers.json"
    results_dir: str = "benchmark/results"
    skill_file: str = "SKILL.md"

    # Session Configuration
    session_timeout: int = 300  # 5 minutes per question session

    @classmethod
    def from_env(cls) -> "BenchmarkConfig":
        """Create configuration from environment variables.

        Required environment variables:
            - CERNGITLAB_LITELLM_API_KEY: LiteLLM API key from CERN
            - CERNGITLAB_GITLAB_TOKEN: Personal access token for GitLab

        Optional environment variables:
            - CERNGITLAB_LITELLM_BASE: LiteLLM API base URL
            - CERNGITLAB_LITELLM_MODEL: Model name to use
            - CERNGITLAB_GITLAB_URL: GitLab instance URL
            - CERNGITLAB_LLM_TIMEOUT: LLM API timeout in seconds
            - CERNGITLAB_GITLAB_TIMEOUT: GitLab API timeout in seconds
            - CERNGITLAB_MAX_RETRIES: Max retry attempts
            - CERNGITLAB_RETRY_DELAY: Delay between retries in seconds
            - CERNGITLAB_SESSION_TIMEOUT: Session timeout in seconds
        """
        litellm_api_key = os.getenv("CERNGITLAB_LITELLM_API_KEY")
        if not litellm_api_key:
            raise ValueError(
                "CERNGITLAB_LITELLM_API_KEY environment variable is required"
            )

        gitlab_token = os.getenv("CERNGITLAB_GITLAB_TOKEN")
        if not gitlab_token:
            raise ValueError("CERNGITLAB_GITLAB_TOKEN environment variable is required")

        return cls(
            litellm_api_key=litellm_api_key,
            litellm_api_base=os.getenv(
                "CERNGITLAB_LITELLM_BASE", "https://llmgw-litellm.web.cern.ch/v1"
            ),
            litellm_model=os.getenv("CERNGITLAB_LITELLM_MODEL", "gpt-5.2"),
            gitlab_token=gitlab_token,
            gitlab_url=os.getenv("CERNGITLAB_GITLAB_URL", "https://gitlab.cern.ch"),
            llm_timeout=int(os.getenv("CERNGITLAB_LLM_TIMEOUT", "120")),
            gitlab_timeout=int(os.getenv("CERNGITLAB_GITLAB_TIMEOUT", "60")),
            max_retries=int(os.getenv("CERNGITLAB_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("CERNGITLAB_RETRY_DELAY", "2.0")),
            session_timeout=int(os.getenv("CERNGITLAB_SESSION_TIMEOUT", "300")),
        )

    @property
    def chat_completions_endpoint(self) -> str:
        """Get the full chat completions endpoint URL."""
        return f"{self.litellm_api_base}/chat/completions"

    def validate(self) -> None:
        """Validate the configuration.

        Raises:
            ValueError: If configuration is invalid.
        """
        if not self.litellm_api_key:
            raise ValueError("LiteLLM API key is required")
        if not self.gitlab_token:
            raise ValueError("GitLab token is required")
        if self.llm_timeout <= 0:
            raise ValueError("LLM timeout must be positive")
        if self.gitlab_timeout <= 0:
            raise ValueError("GitLab timeout must be positive")
        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")


@dataclass
class BenchmarkRunConfig:
    """Configuration for a specific benchmark run."""

    # Which approaches to test
    test_cli: bool = True
    test_mcp: bool = True

    # Which questions to run (None = all)
    question_ids: Optional[list[str]] = None

    # Output settings
    save_individual_responses: bool = True
    save_judge_details: bool = True

    # Parallel execution
    max_concurrent_sessions: int = 1  # Keep at 1 for isolated sessions

    def validate(self) -> None:
        """Validate run configuration."""
        if not self.test_cli and not self.test_mcp:
            raise ValueError("At least one of test_cli or test_mcp must be True")
