"""
Summarize an evaluation JSON file as Markdown.

Usage:
    python scripts/summarize_results.py results/hotpot_1780028038.json
"""

import argparse
import json
from pathlib import Path


AGENTS = [
    ("baseline", "Baseline"),
    ("restart", "RE-TRAC-style recovery"),
    ("reform", "Mid-trajectory reformulation"),
]


def is_correct(result):
    return bool((result or {}).get("grade", {}).get("correct"))


def is_tool_error(result):
    return bool((result or {}).get("tool_error"))


def answered(result):
    return bool(result) and not result.get("error") and "elapsed_sec" in result


def avg(values):
    return sum(values) / len(values) if values else 0.0


def pct(num, denom):
    return f"{(num / denom * 100):.1f}%" if denom else "0.0%"


def summarize_agent(results, key):
    vals = [row.get(key) for row in results if row.get(key)]
    valid = [v for v in vals if answered(v)]
    correct_all = sum(is_correct(v) for v in vals)
    correct_valid = sum(is_correct(v) for v in valid)
    tool_errors = sum(is_tool_error(v) for v in vals)

    extra_field = "restarts" if key == "restart" else "reformulations"
    extra_total = sum(v.get(extra_field, 0) for v in vals)

    return {
        "count": len(vals),
        "valid_count": len(valid),
        "correct_all": correct_all,
        "correct_valid": correct_valid,
        "tool_errors": tool_errors,
        "avg_time": avg([v.get("elapsed_sec", 0) for v in valid]),
        "avg_steps": avg([v.get("total_steps", 0) for v in valid]),
        "avg_pages": avg([v.get("pages_fetched", 0) for v in valid]),
        "extra_total": extra_total,
        "extra_avg": extra_total / len(valid) if valid else 0.0,
    }


def status(result):
    if not result:
        return "-"
    if result.get("tool_error"):
        return "tool_error"
    if result.get("error"):
        return "error"
    return "correct" if is_correct(result) else "wrong"


def pairwise(results, left_key, right_key):
    rows = [
        row
        for row in results
        if answered(row.get(left_key)) and answered(row.get(right_key))
    ]
    left_wins = sum(is_correct(r[left_key]) and not is_correct(r[right_key]) for r in rows)
    right_wins = sum(is_correct(r[right_key]) and not is_correct(r[left_key]) for r in rows)
    ties_correct = sum(is_correct(r[left_key]) and is_correct(r[right_key]) for r in rows)
    ties_wrong = sum((not is_correct(r[left_key])) and (not is_correct(r[right_key])) for r in rows)
    return {
        "count": len(rows),
        "left_wins": left_wins,
        "right_wins": right_wins,
        "ties_correct": ties_correct,
        "ties_wrong": ties_wrong,
    }


def print_summary(path):
    data = json.loads(Path(path).read_text())
    results = data["results"]
    benchmark = data.get("benchmark", "unknown")
    n = data.get("n", len(results))

    print(f"# Evaluation Summary: `{Path(path).name}`\n")
    print(f"- Benchmark: `{benchmark}`")
    print(f"- Questions: `{n}`\n")

    print("## Aggregate Results\n")
    print("| Agent | Accuracy All | Accuracy Valid | Tool Errors | Avg Time | Avg Steps | Avg Pages | Extra Work |")
    print("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")

    present_agents = [(key, label) for key, label in AGENTS if any(row.get(key) for row in results)]
    for key, label in present_agents:
        s = summarize_agent(results, key)
        extra_label = "restarts" if key == "restart" else "reforms"
        print(
            f"| {label} | "
            f"{s['correct_all']}/{n} ({pct(s['correct_all'], n)}) | "
            f"{s['correct_valid']}/{s['valid_count']} ({pct(s['correct_valid'], s['valid_count'])}) | "
            f"{s['tool_errors']}/{s['count']} | "
            f"{s['avg_time']:.1f}s | "
            f"{s['avg_steps']:.1f} | "
            f"{s['avg_pages']:.1f} | "
            f"{s['extra_total']} {extra_label} ({s['extra_avg']:.1f} avg) |"
        )

    if "restart" in [key for key, _ in present_agents] and "reform" in [key for key, _ in present_agents]:
        p = pairwise(results, "restart", "reform")
        print("\n## Pairwise: RE-TRAC vs Reformulation\n")
        print("| Comparable Questions | RE-TRAC Only Correct | Reform Only Correct | Both Correct | Both Wrong |")
        print("| ---: | ---: | ---: | ---: | ---: |")
        print(
            f"| {p['count']} | {p['left_wins']} | {p['right_wins']} | "
            f"{p['ties_correct']} | {p['ties_wrong']} |"
        )

    print("\n## Per-Question Outcomes\n")
    headers = ["#", "Expected"]
    headers.extend(label for key, label in present_agents)
    headers.append("Question")
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join(["---"] * len(headers)) + " |")
    for i, row in enumerate(results, 1):
        cells = [str(i), str(row.get("correct_answer", ""))[:50]]
        cells.extend(status(row.get(key)) for key, _ in present_agents)
        cells.append(row.get("question", "")[:80].replace("|", "\\|"))
        print("| " + " | ".join(cells) + " |")


def main():
    parser = argparse.ArgumentParser(description="Summarize evaluation JSON as Markdown")
    parser.add_argument("result_json", help="Path to a results/*.json file")
    args = parser.parse_args()
    print_summary(args.result_json)


if __name__ == "__main__":
    main()
