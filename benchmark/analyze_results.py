#!/usr/bin/env python3
"""
Analyze benchmark results.

Usage:
    python analyze_results.py results/benchmark_*.json
"""

import json
import sys
from pathlib import Path
from datetime import datetime


def analyze_results(filepath: str) -> None:
    """Analyze and print benchmark results."""
    with open(filepath, "r") as f:
        data = json.load(f)
    
    summary = data["summary"]
    
    print("\n" + "=" * 70)
    print("CERN GITLAB BENCHMARK ANALYSIS REPORT")
    print("=" * 70)
    print(f"Run ID: {data['run_id']}")
    print(f"Started: {data['started_at']}")
    print(f"Completed: {data['completed_at']}")
    print(f"Model: {data['config'].get('model', 'Unknown')}")
    print("")
    print("-" * 70)
    print("SUMMARY")
    print("-" * 70)
    print(f"Total Questions: {summary['total_questions']}")
    print("")
    print("CLI Approach:")
    print(f"  Average Score:  {summary['cli_avg_score']:.2f}/5")
    print(f"  Average Latency: {summary['cli_avg_latency']:.2f}s")
    print(f"  Success Rate:   {summary['cli_success_rate'] * 100:.1f}%")
    print("")
    print("MCP Approach:")
    print(f"  Average Score:  {summary['mcp_avg_score']:.2f}/5")
    print(f"  Average Latency: {summary['mcp_avg_latency']:.2f}s")
    print(f"  Success Rate:   {summary['mcp_success_rate'] * 100:.1f}%")
    print("")
    
    # Determine winner
    score_diff = summary["mcp_avg_score"] - summary["cli_avg_score"]
    latency_diff = summary["cli_avg_latency"] - summary["mcp_avg_latency"]
    
    print("-" * 70)
    print("COMPARISON")
    print("-" * 70)
    
    if score_diff > 0.1:
        print(f"✓ MCP scores {score_diff:.2f} points higher")
    elif score_diff < -0.1:
        print(f"✓ CLI scores {abs(score_diff):.2f} points higher")
    else:
        print("⚖ Scores are tied")
    
    if latency_diff > 1.0:
        print(f"✓ CLI is {latency_diff:.2f}s faster")
    elif latency_diff < -1.0:
        print(f"✓ MCP is {abs(latency_diff):.2f}s faster")
    else:
        print("⚖ Latency is similar")
    
    print("")
    print("-" * 70)
    print("PER-QUESTION BREAKDOWN")
    print("-" * 70)
    
    for qr in data["question_results"]:
        print(f"\n{qr['question_id']} - {qr['category']} ({qr['difficulty']}):")
        print(f"  Question: {qr['question_text'][:70]}...")
        
        if "cli_judge" in qr:
            cli = qr["cli_judge"]
            print(f"  CLI Score: {cli['score']}/5 (confidence: {cli['confidence']:.2f})")
            print(f"    Reasoning: {cli['reasoning'][:80]}...")
            if cli.get('hallucinations'):
                print(f"    Hallucinations: {cli['hallucinations']}")
        
        if "mcp_judge" in qr:
            mcp = qr["mcp_judge"]
            print(f"  MCP Score: {mcp['score']}/5 (confidence: {mcp['confidence']:.2f})")
            print(f"    Reasoning: {mcp['reasoning'][:80]}...")
            if mcp.get('hallucinations'):
                print(f"    Hallucinations: {mcp['hallucinations']}")
    
    print("")
    print("=" * 70)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_results.py <results_file.json>")
        print("Example: python analyze_results.py results/benchmark_20260311_120000.json")
        sys.exit(1)
    
    filepath = sys.argv[1]
    if not Path(filepath).exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)
    
    analyze_results(filepath)
