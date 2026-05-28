"""
agent.py - CLI entry point for single-question runs.
"""

import argparse
import json
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from src.baseline import BaselineAgent
from src.reformulator import ReformulationAgent
from src.restart import RestartAgent


def main():
    parser = argparse.ArgumentParser(description="Query Reformulation Web Agent")
    parser.add_argument("question", nargs="?", help="The question to answer")
    parser.add_argument("--baseline", action="store_true", help="Run single-query baseline")
    parser.add_argument("--reform", action="store_true", help="Run mid-trajectory query reformulation")
    parser.add_argument("--restart", action="store_true", help="Run RE-TRAC-style recovery")
    parser.add_argument("--compare", action="store_true", help="Run baseline vs reform")
    parser.add_argument("--compare-recovery", action="store_true", help="Run RE-TRAC vs reform")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--no-headless", action="store_true")
    parser.add_argument("--save", action="store_true")
    args = parser.parse_args()

    if not args.question:
        parser.print_help()
        return

    headless = not args.no_headless
    question = args.question

    if args.compare_recovery:
        mode = "compare-recovery"
    elif args.compare:
        mode = "compare"
    elif args.restart:
        mode = "restart"
    elif args.reform:
        mode = "reform"
    else:
        mode = "baseline"

    print()
    print("╔═══════════════════════════════════════════════╗")
    print("║  WEB AGENT — Query Reformulation Study        ║")
    print(f"║  Mode: {mode:<40}║")
    print("╚═══════════════════════════════════════════════╝")
    print()

    results = {}

    if mode in ("baseline", "compare"):
        print("━━━ BASELINE AGENT ━━━━━━━━━━━━━━━━━━━━━━━━━━")
        agent = BaselineAgent(headless=headless).init()
        try:
            results["baseline"] = agent.answer(question)
        finally:
            agent.close()

    if mode in ("restart", "compare-recovery"):
        print("━━━ RE-TRAC AGENT — Trajectory Compression Recovery ━━━━━━━━━")
        agent = RestartAgent(headless=headless).init()
        try:
            results["restart"] = agent.answer(question)
        finally:
            agent.close()

    if mode in ("reform", "compare", "compare-recovery"):
        if mode in ("compare", "compare-recovery"):
            print("\n━━━ REFORMULATION AGENT ━━━━━━━━━━━━━━━━━━━━━")
        agent = ReformulationAgent(headless=headless).init()
        try:
            results["reform"] = agent.answer(question)
        finally:
            agent.close()

    if mode == "compare" and "baseline" in results and "reform" in results:
        _print_compare("Baseline", results["baseline"], "Reformulation", results["reform"])

    if mode == "compare-recovery" and "restart" in results and "reform" in results:
        _print_compare("RE-TRAC", results["restart"], "Reformulation", results["reform"])

    if args.save:
        Path("results").mkdir(exist_ok=True)
        fname = f"results/{int(time.time())}_{mode}.json"
        with open(fname, "w") as f:
            json.dump({"question": question, "mode": mode, **results}, f, indent=2, default=str)
        print(f"\n  💾 Saved to {fname}")


def _print_compare(left_name, left, right_name, right):
    print("\n╔═══════════════════════════════════════════════╗")
    print("║  COMPARISON                                   ║")
    print("╚═══════════════════════════════════════════════╝\n")
    rows = [
        ("Query used", left["query"], right["query"]),
        ("Search results", str(len(left["search_results"])), str(len(right["search_results"]))),
        ("Pages fetched", str(left["pages_fetched"]), str(right["pages_fetched"])),
        ("Total steps", str(left["total_steps"]), str(right["total_steps"])),
        ("Restarts/Reforms", str(left.get("restarts", 0)), str(right.get("reformulations", 0))),
        ("Time (sec)", str(left["elapsed_sec"]), str(right["elapsed_sec"])),
        ("Answer length", str(len(left["answer"])), str(len(right["answer"]))),
    ]
    print(f"  {'Metric':<18} {left_name:<25} {right_name:<25}")
    print(f"  {'─' * 68}")
    for label, lv, rv in rows:
        print(f"  {label:<18} {lv:<25} {rv:<25}")


if __name__ == "__main__":
    main()
