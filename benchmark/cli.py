#!/usr/bin/env python3
"""
CERN GitLab Benchmark CLI.

Run benchmarks comparing cerngitlab-cli vs cerngitlab-mcp approaches.
"""

import asyncio
import logging
import sys
from pathlib import Path

import click

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmark.config import BenchmarkConfig, BenchmarkRunConfig
from benchmark.runner import BenchmarkRunner


def setup_logging(verbose: bool = False) -> None:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
    )


@click.group()
@click.version_option(version="1.0.0")
def cli() -> None:
    """CERN GitLab Benchmark CLI.

    Run benchmarks to compare cerngitlab-cli vs cerngitlab-mcp performance.
    """
    pass


@cli.command()
@click.option(
    "--questions",
    "-q",
    multiple=True,
    help="Specific question IDs to run (can be repeated). If not specified, runs all questions.",
)
@click.option(
    "--cli-only",
    is_flag=True,
    help="Only test CLI approach.",
)
@click.option(
    "--mcp-only",
    is_flag=True,
    help="Only test MCP approach.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging.",
)
@click.option(
    "--output-dir",
    "-o",
    type=click.Path(file_okay=False, dir_okay=True),
    help="Output directory for results (default: benchmark/results).",
)
def run(
    questions: tuple[str, ...],
    cli_only: bool,
    mcp_only: bool,
    verbose: bool,
    output_dir: str | None,
) -> None:
    """Run the benchmark.

    Examples:

    \b
        # Run all questions
        python -m benchmark run

    \b
        # Run specific questions
        python -m benchmark run -q q1 -q q2 -q q3

    \b
        # Test only CLI approach
        python -m benchmark run --cli-only

    \b
        # Test only MCP approach
        python -m benchmark run --mcp-only
    """
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    try:
        # Load configuration from environment
        config = BenchmarkConfig.from_env()

        # Override output directory if specified
        if output_dir:
            config.results_dir = output_dir

        # Validate configuration
        config.validate()

        # Create run configuration
        run_config = BenchmarkRunConfig(
            test_cli=not mcp_only,
            test_mcp=not cli_only,
            question_ids=list(questions) if questions else None,
        )
        run_config.validate()

        logger.info("Starting benchmark run...")
        logger.info(f"Model: {config.litellm_model}")
        logger.info(f"Questions to run: {len(questions) if questions else 'all'}")
        logger.info(f"Test CLI: {run_config.test_cli}, Test MCP: {run_config.test_mcp}")

        # Run benchmark
        async def _run() -> None:
            runner = BenchmarkRunner(config, run_config)
            try:
                results = await runner.run_benchmark()

                # Print summary
                click.echo("\n" + "=" * 60)
                click.echo("BENCHMARK SUMMARY")
                click.echo("=" * 60)
                click.echo(f"Run ID: {results.run_id}")
                click.echo(f"Total Questions: {results.total_questions}")
                click.echo("")
                click.echo("CLI Approach:")
                click.echo(f"  Average Score: {results.cli_avg_score:.2f}/5")
                click.echo(f"  Average Latency: {results.cli_avg_latency:.2f}s")
                click.echo(f"  Success Rate: {results.cli_success_rate * 100:.1f}%")
                click.echo("")
                click.echo("MCP Approach:")
                click.echo(f"  Average Score: {results.mcp_avg_score:.2f}/5")
                click.echo(f"  Average Latency: {results.mcp_avg_latency:.2f}s")
                click.echo(f"  Success Rate: {results.mcp_success_rate * 100:.1f}%")
                click.echo("=" * 60)
                click.echo(f"Results saved to: {config.results_dir}/")

            finally:
                await runner.close()

        asyncio.run(_run())

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Benchmark interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Benchmark failed: {e}")
        sys.exit(1)


@cli.command()
@click.argument("result_file", type=click.Path(exists=True, file_okay=True))
def analyze(result_file: str) -> None:
    """Analyze benchmark results from a JSON file.

    Example:

    \b
        python -m benchmark analyze benchmark/results/benchmark_20260311_120000.json
    """
    import json

    with open(result_file, "r") as f:
        data = json.load(f)

    click.echo("\n" + "=" * 60)
    click.echo("BENCHMARK ANALYSIS")
    click.echo("=" * 60)
    click.echo(f"Run ID: {data['run_id']}")
    click.echo(f"Started: {data['started_at']}")
    click.echo(f"Completed: {data['completed_at']}")
    click.echo("")

    summary = data["summary"]
    click.echo("SUMMARY")
    click.echo("-" * 40)
    click.echo(f"Total Questions: {summary['total_questions']}")
    click.echo("")
    click.echo("CLI Approach:")
    click.echo(f"  Avg Score: {summary['cli_avg_score']:.2f}/5")
    click.echo(f"  Avg Latency: {summary['cli_avg_latency']:.2f}s")
    click.echo(f"  Success Rate: {summary['cli_success_rate'] * 100:.1f}%")
    click.echo("")
    click.echo("MCP Approach:")
    click.echo(f"  Avg Score: {summary['mcp_avg_score']:.2f}/5")
    click.echo(f"  Avg Latency: {summary['mcp_avg_latency']:.2f}s")
    click.echo(f"  Success Rate: {summary['mcp_success_rate'] * 100:.1f}%")
    click.echo("")

    # Comparison
    click.echo("COMPARISON")
    click.echo("-" * 40)
    score_diff = summary["mcp_avg_score"] - summary["cli_avg_score"]
    latency_diff = summary["mcp_avg_latency"] - summary["cli_avg_latency"]

    if score_diff > 0:
        click.echo(f"MCP scores {abs(score_diff):.2f} points higher")
    elif score_diff < 0:
        click.echo(f"CLI scores {abs(score_diff):.2f} points higher")
    else:
        click.echo("Both approaches scored equally")

    if latency_diff > 0:
        click.echo(f"MCP is {abs(latency_diff):.2f}s slower")
    elif latency_diff < 0:
        click.echo(f"MCP is {abs(latency_diff):.2f}s faster")
    else:
        click.echo("Both approaches have equal latency")

    click.echo("=" * 60)

    # Per-question breakdown
    click.echo("\nPER-QUESTION BREAKDOWN")
    click.echo("-" * 40)

    for qr in data["question_results"]:
        click.echo(f"\n{qr['question_id']} ({qr['category']}):")
        click.echo(f"  Question: {qr['question_text'][:60]}...")

        if "cli_judge" in qr:
            cli = qr["cli_judge"]
            click.echo(f"  CLI Score: {cli['score']}/5 (confidence: {cli['confidence']:.2f})")
            click.echo(f"    Reasoning: {cli['reasoning'][:80]}...")

        if "mcp_judge" in qr:
            mcp = qr["mcp_judge"]
            click.echo(f"  MCP Score: {mcp['score']}/5 (confidence: {mcp['confidence']:.2f})")
            click.echo(f"    Reasoning: {mcp['reasoning'][:80]}...")


@cli.command()
def info() -> None:
    """Show benchmark configuration info."""
    click.echo("\n" + "=" * 60)
    click.echo("BENCHMARK CONFIGURATION")
    click.echo("=" * 60)
    click.echo("""
Required Environment Variables:
  - CERNGITLAB_LITELLM_API_KEY: LiteLLM API key from CERN
  - CERNGITLAB_GITLAB_TOKEN: Personal access token for GitLab

Optional Environment Variables:
  - CERNGITLAB_LITELLM_BASE: LiteLLM API base URL
    (default: https://llmgw-litellm.web.cern.ch/v1)
  - CERNGITLAB_LITELLM_MODEL: Model name
    (default: gpt-5.2)
  - CERNGITLAB_GITLAB_URL: GitLab URL
    (default: https://gitlab.cern.ch)
  - CERNGITLAB_LLM_TIMEOUT: LLM timeout in seconds
    (default: 120)
  - CERNGITLAB_GITLAB_TIMEOUT: GitLab timeout in seconds
    (default: 60)
  - CERNGITLAB_MAX_RETRIES: Max retry attempts
    (default: 3)
  - CERNGITLAB_RETRY_DELAY: Delay between retries
    (default: 2.0 seconds)
  - CERNGITLAB_SESSION_TIMEOUT: Session timeout
    (default: 300 seconds)

Example:
  export CERNGITLAB_LITELLM_API_KEY="your-api-key"
  export CERNGITLAB_GITLAB_TOKEN="glpat-xxxxx"
  python -m benchmark run
""")
    click.echo("=" * 60)


if __name__ == "__main__":
    cli()
