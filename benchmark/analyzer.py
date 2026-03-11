"""
Results Analyzer for CERN GitLab Benchmark.

Provides detailed analysis and visualization of benchmark results.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ComparativeAnalysis:
    """Comparative analysis between CLI and MCP approaches."""

    # Accuracy metrics
    cli_avg_score: float
    mcp_avg_score: float
    score_difference: float
    score_winner: str  # "CLI", "MCP", or "Tie"

    # Latency metrics
    cli_avg_latency: float
    mcp_avg_latency: float
    latency_difference: float
    latency_winner: str  # "CLI", "MCP", or "Tie"

    # Success rate metrics
    cli_success_rate: float
    mcp_success_rate: float

    # Category breakdown
    category_scores: dict[str, dict[str, float]]

    # Error analysis
    cli_errors: list[dict[str, Any]]
    mcp_errors: list[dict[str, Any]]

    # Hallucination analysis
    cli_hallucination_rate: float
    mcp_hallucination_rate: float


class ResultsAnalyzer:
    """Analyzes benchmark results and generates reports."""

    def __init__(self, results_file: str | Path):
        """Initialize analyzer with results file.

        Args:
            results_file: Path to benchmark results JSON file.
        """
        self.results_file = Path(results_file)
        self.data = self._load_results()

    def _load_results(self) -> dict:
        """Load results from JSON file."""
        with open(self.results_file, "r") as f:
            return json.load(f)

    def analyze(self) -> ComparativeAnalysis:
        """Perform comprehensive comparative analysis.

        Returns:
            ComparativeAnalysis with all metrics.
        """
        summary = self.data["summary"]
        question_results = self.data["question_results"]

        # Calculate category breakdown
        category_scores = self._analyze_by_category(question_results)

        # Analyze errors
        cli_errors = self._extract_errors(question_results, "cli")
        mcp_errors = self._extract_errors(question_results, "mcp")

        # Calculate hallucination rates
        cli_hallucination_rate = self._calculate_hallucination_rate(
            question_results, "cli"
        )
        mcp_hallucination_rate = self._calculate_hallucination_rate(
            question_results, "mcp"
        )

        # Determine winners
        score_diff = summary["mcp_avg_score"] - summary["cli_avg_score"]
        score_winner = "MCP" if score_diff > 0.1 else ("CLI" if score_diff < -0.1 else "Tie")

        latency_diff = summary["cli_avg_latency"] - summary["mcp_avg_latency"]
        latency_winner = (
            "MCP" if latency_diff > 1.0 else ("CLI" if latency_diff < -1.0 else "Tie")
        )

        return ComparativeAnalysis(
            cli_avg_score=summary["cli_avg_score"],
            mcp_avg_score=summary["mcp_avg_score"],
            score_difference=score_diff,
            score_winner=score_winner,
            cli_avg_latency=summary["cli_avg_latency"],
            mcp_avg_latency=summary["mcp_avg_latency"],
            latency_difference=latency_diff,
            latency_winner=latency_winner,
            cli_success_rate=summary["cli_success_rate"],
            mcp_success_rate=summary["mcp_success_rate"],
            category_scores=category_scores,
            cli_errors=cli_errors,
            mcp_errors=mcp_errors,
            cli_hallucination_rate=cli_hallucination_rate,
            mcp_hallucination_rate=mcp_hallucination_rate,
        )

    def _analyze_by_category(
        self, question_results: list[dict]
    ) -> dict[str, dict[str, float]]:
        """Analyze scores by category.

        Returns:
            Dictionary mapping category to CLI and MCP average scores.
        """
        category_data: dict[str, dict[str, list[float]]] = {}

        for qr in question_results:
            category = qr.get("category", "Unknown")

            if category not in category_data:
                category_data[category] = {"cli": [], "mcp": []}

            if "cli_judge" in qr:
                category_data[category]["cli"].append(qr["cli_judge"]["score"])
            if "mcp_judge" in qr:
                category_data[category]["mcp"].append(qr["mcp_judge"]["score"])

        # Calculate averages
        category_scores = {}
        for category, scores in category_data.items():
            category_scores[category] = {
                "cli_avg": (
                    sum(scores["cli"]) / len(scores["cli"]) if scores["cli"] else 0.0
                ),
                "mcp_avg": (
                    sum(scores["mcp"]) / len(scores["mcp"]) if scores["mcp"] else 0.0
                ),
                "question_count": len(scores["cli"]) + len(scores["mcp"]),
            }

        return category_scores

    def _extract_errors(
        self, question_results: list[dict], approach: str
    ) -> list[dict[str, Any]]:
        """Extract errors for a specific approach."""
        errors = []

        for qr in question_results:
            response_key = f"{approach}_response"
            if response_key in qr and qr[response_key].get("error"):
                errors.append(
                    {
                        "question_id": qr["question_id"],
                        "category": qr.get("category", "Unknown"),
                        "error": qr[response_key]["error"],
                        "latency": qr[response_key].get("total_time", 0),
                    }
                )

        return errors

    def _calculate_hallucination_rate(
        self, question_results: list[dict], approach: str
    ) -> float:
        """Calculate hallucination rate for an approach."""
        judge_key = f"{approach}_judge"
        total_judged = 0
        total_hallucinations = 0

        for qr in question_results:
            if judge_key in qr:
                total_judged += 1
                hallucinations = qr[judge_key].get("hallucinations", [])
                total_hallucinations += len(hallucinations)

        return (
            total_hallucinations / total_judged if total_judged > 0 else 0.0
        )

    def generate_report(self, output_file: str | Path | None = None) -> str:
        """Generate a detailed analysis report.

        Args:
            output_file: Optional file path to save the report.

        Returns:
            Report text.
        """
        analysis = self.analyze()

        lines = [
            "=" * 70,
            "CERN GITLAB BENCHMARK ANALYSIS REPORT",
            "=" * 70,
            "",
            f"Run ID: {self.data['run_id']}",
            f"Started: {self.data['started_at']}",
            f"Completed: {self.data['completed_at']}",
            f"Model: {self.data['config'].get('model', 'Unknown')}",
            "",
            "-" * 70,
            "EXECUTIVE SUMMARY",
            "-" * 70,
            "",
            f"Total Questions: {self.data['summary']['total_questions']}",
            "",
            "OVERALL WINNER:",
            f"  Accuracy: {analysis.score_winner}",
            f"  Speed: {analysis.latency_winner}",
            "",
            "-" * 70,
            "ACCURACY METRICS",
            "-" * 70,
            "",
            f"CLI Average Score:  {analysis.cli_avg_score:.2f}/5",
            f"MCP Average Score:  {analysis.mcp_avg_score:.2f}/5",
            f"Difference:         {analysis.score_difference:+.2f} "
            f"({'MCP' if analysis.score_difference > 0 else 'CLI'} better)",
            "",
            f"CLI Success Rate:   {analysis.cli_success_rate * 100:.1f}%",
            f"MCP Success Rate:   {analysis.mcp_success_rate * 100:.1f}%",
            "",
            f"CLI Hallucination Rate: {analysis.cli_hallucination_rate:.2f}",
            f"MCP Hallucination Rate: {analysis.mcp_hallucination_rate:.2f}",
            "",
            "-" * 70,
            "LATENCY METRICS",
            "-" * 70,
            "",
            f"CLI Average Latency:  {analysis.cli_avg_latency:.2f}s",
            f"MCP Average Latency:  {analysis.mcp_avg_latency:.2f}s",
            f"Difference:           {analysis.latency_difference:+.2f}s "
            f"({'MCP' if analysis.latency_difference > 0 else 'CLI'} faster)",
            "",
            "-" * 70,
            "SCORES BY CATEGORY",
            "-" * 70,
            "",
        ]

        # Category breakdown
        for category, scores in analysis.category_scores.items():
            lines.append(f"{category}:")
            lines.append(
                f"  CLI: {scores['cli_avg']:.2f}  |  MCP: {scores['mcp_avg']:.2f}  "
                f"({scores['question_count']} questions)"
            )
            diff = scores["mcp_avg"] - scores["cli_avg"]
            winner = "MCP" if diff > 0.1 else ("CLI" if diff < -0.1 else "Tie")
            lines.append(f"  Winner: {winner}")
            lines.append("")

        # Error analysis
        if analysis.cli_errors or analysis.mcp_errors:
            lines.append("-" * 70)
            lines.append("ERROR ANALYSIS")
            lines.append("-" * 70)
            lines.append("")

            if analysis.cli_errors:
                lines.append(f"CLI Errors ({len(analysis.cli_errors)}):")
                for err in analysis.cli_errors[:5]:  # Show first 5
                    lines.append(
                        f"  - {err['question_id']}: {err['error'][:50]}..."
                    )
                if len(analysis.cli_errors) > 5:
                    lines.append(f"  ... and {len(analysis.cli_errors) - 5} more")
                lines.append("")

            if analysis.mcp_errors:
                lines.append(f"MCP Errors ({len(analysis.mcp_errors)}):")
                for err in analysis.mcp_errors[:5]:  # Show first 5
                    lines.append(
                        f"  - {err['question_id']}: {err['error'][:50]}..."
                    )
                if len(analysis.mcp_errors) > 5:
                    lines.append(f"  ... and {len(analysis.mcp_errors) - 5} more")
                lines.append("")

        # Recommendations
        lines.append("-" * 70)
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 70)
        lines.append("")

        if analysis.score_winner == "MCP" and analysis.latency_winner == "MCP":
            lines.append(
                "✓ MCP approach is superior in both accuracy and speed. "
                "Recommend using MCP for production."
            )
        elif analysis.score_winner == "CLI" and analysis.latency_winner == "CLI":
            lines.append(
                "✓ CLI approach is superior in both accuracy and speed. "
                "Recommend using CLI for production."
            )
        elif analysis.score_winner == "MCP":
            lines.append(
                "⚡ MCP has better accuracy but CLI is faster. "
                "Recommend MCP for accuracy-critical tasks, CLI for speed-critical tasks."
            )
        elif analysis.score_winner == "CLI":
            lines.append(
                "⚡ CLI has better accuracy but MCP is faster. "
                "Recommend CLI for accuracy-critical tasks, MCP for speed-critical tasks."
            )
        else:
            lines.append(
                "⚖️ Both approaches perform similarly. "
                "Consider other factors like ease of integration."
            )

        lines.append("")
        lines.append("=" * 70)

        report = "\n".join(lines)

        # Save to file if requested
        if output_file:
            output_path = Path(output_file)
            with open(output_path, "w") as f:
                f.write(report)

        return report

    def export_csv(self, output_file: str | Path) -> None:
        """Export results to CSV format.

        Args:
            output_file: Path to output CSV file.
        """
        import csv

        output_path = Path(output_file)
        question_results = self.data["question_results"]

        with open(output_path, "w", newline="") as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(
                [
                    "Question ID",
                    "Category",
                    "Difficulty",
                    "CLI Score",
                    "CLI Latency",
                    "CLI Confidence",
                    "MCP Score",
                    "MCP Latency",
                    "MCP Confidence",
                    "Score Winner",
                ]
            )

            # Data rows
            for qr in question_results:
                cli_score = (
                    qr.get("cli_judge", {}).get("score", "N/A")
                    if "cli_judge" in qr
                    else "N/A"
                )
                cli_latency = (
                    qr.get("cli_response", {}).get("total_time", "N/A")
                    if "cli_response" in qr
                    else "N/A"
                )
                cli_confidence = (
                    qr.get("cli_judge", {}).get("confidence", "N/A")
                    if "cli_judge" in qr
                    else "N/A"
                )

                mcp_score = (
                    qr.get("mcp_judge", {}).get("score", "N/A")
                    if "mcp_judge" in qr
                    else "N/A"
                )
                mcp_latency = (
                    qr.get("mcp_response", {}).get("total_time", "N/A")
                    if "mcp_response" in qr
                    else "N/A"
                )
                mcp_confidence = (
                    qr.get("mcp_judge", {}).get("confidence", "N/A")
                    if "mcp_judge" in qr
                    else "N/A"
                )

                # Determine winner
                if isinstance(cli_score, (int, float)) and isinstance(
                    mcp_score, (int, float)
                ):
                    if mcp_score > cli_score:
                        winner = "MCP"
                    elif cli_score > mcp_score:
                        winner = "CLI"
                    else:
                        winner = "Tie"
                else:
                    winner = "N/A"

                writer.writerow(
                    [
                        qr["question_id"],
                        qr.get("category", "Unknown"),
                        qr.get("difficulty", "Unknown"),
                        cli_score,
                        f"{cli_latency:.2f}" if isinstance(cli_latency, float) else cli_latency,
                        (
                            f"{cli_confidence:.2f}"
                            if isinstance(cli_confidence, float)
                            else cli_confidence
                        ),
                        mcp_score,
                        f"{mcp_latency:.2f}" if isinstance(mcp_latency, float) else mcp_latency,
                        (
                            f"{mcp_confidence:.2f}"
                            if isinstance(mcp_confidence, float)
                            else mcp_confidence
                        ),
                        winner,
                    ]
                )
