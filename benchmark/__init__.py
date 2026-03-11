"""
CERN GitLab Benchmark Module.

Compare cerngitlab-cli vs cerngitlab-mcp performance using AI evaluation.
"""

from .config import BenchmarkConfig, BenchmarkRunConfig
from .judge import AIJudge, JudgeResult
from .runner import BenchmarkRunner, BenchmarkResults, ModelResponse, QuestionResult
from .analyzer import ResultsAnalyzer, ComparativeAnalysis

__all__ = [
    "BenchmarkConfig",
    "BenchmarkRunConfig",
    "AIJudge",
    "JudgeResult",
    "BenchmarkRunner",
    "BenchmarkResults",
    "ModelResponse",
    "QuestionResult",
    "ResultsAnalyzer",
    "ComparativeAnalysis",
]

__version__ = "1.0.0"
