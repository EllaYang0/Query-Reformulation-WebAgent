"""
eval.py - Evaluation Runner for BrowseComp or HotpotQA.
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
from src.browsecomp import load_browsecomp
from src.llm import ask_llm_json

GRADER_TEMPLATE = """Judge whether the following [response] to [question] is correct or not based on the precise and unambiguous [correct_answer] below.

[question]: {question}
[correct_answer]: {correct_answer}
[response]: {response}

Respond with JSON only:
{{"extracted_final_answer": "<extracted answer or None>", "correctness": "CORRECT" or "INCORRECT", "reasoning": "<brief explanation>"}}"""


def grade_answer(question, correct_answer, response):
    try:
        result = ask_llm_json(GRADER_TEMPLATE.format(question=question, correct_answer=correct_answer, response=response), max_tokens=512, temperature=0.1)
        return {"correct": result.get("correctness") == "CORRECT", "extracted": result.get("extracted_final_answer", "None"), "reasoning": result.get("reasoning", "")}
    except Exception as e:
        return {"correct": False, "extracted": "None", "reasoning": f"Grading error: {e}"}


def main():
    parser = argparse.ArgumentParser(description="Evaluation Runner")
    parser.add_argument("--n", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--reform-only", action="store_true")
    parser.add_argument("--restart-only", action="store_true")
    parser.add_argument("--compare-recovery", action="store_true", help="Compare RE-TRAC-style trajectory compression against mid-trajectory reformulation")
    parser.add_argument("--no-headless", action="store_true")
    parser.add_argument("--benchmark", choices=["browsecomp", "hotpot"], default="browsecomp")
    args = parser.parse_args()

    headless = not args.no_headless
    print()
    print("╔═══════════════════════════════════════════════════╗")
    print(f"║  EVALUATION: {args.benchmark.upper():<37}║")
    print(f"║  {args.n} questions | seed: {args.seed:<30}║")
    print("╚═══════════════════════════════════════════════════╝")
    print()

    if args.benchmark == "hotpot":
        from src.hotpotqa import load_hotpotqa
        questions = load_hotpotqa(args.n, seed=args.seed, level="hard", q_type="bridge")
    else:
        questions = load_browsecomp(args.n, seed=args.seed)

    all_results = []
    for i, item in enumerate(questions):
        question = item["question"]
        correct_answer = item["answer"]
        print(f"\n{'═' * 60}")
        print(f"  Question {i+1}/{len(questions)}")
        print(f"  Q: {question[:120]}...")
        print(f"  Expected: {correct_answer[:80]}")
        print(f"{'═' * 60}")

        entry = {"question": question, "correct_answer": correct_answer, "type": item.get("type"), "level": item.get("level"), "baseline": None, "restart": None, "reform": None}
        run_baseline = not args.reform_only and not args.restart_only and not args.compare_recovery
        run_restart = args.restart_only or args.compare_recovery
        run_reform = not args.baseline_only and not args.restart_only

        if run_baseline:
            agent = BaselineAgent(headless=headless).init()
            try:
                print("\n  ── Baseline ──")
                result = agent.answer(question)
                grade = grade_answer(question, correct_answer, result["answer"])
                entry["baseline"] = {**result, "grade": grade}
                print(f"  📊 {'✓ CORRECT' if grade['correct'] else '✗ WRONG'} (extracted: \"{grade['extracted']}\")")
            except Exception as e:
                print(f"  ❌ Baseline error: {e}")
                entry["baseline"] = {"error": str(e), "grade": {"correct": False}}
            finally:
                agent.close()

        if run_restart:
            agent = RestartAgent(headless=headless).init()
            try:
                print("\n  ── RE-TRAC (trajectory compression recovery) ──")
                result = agent.answer(question)
                grade = grade_answer(question, correct_answer, result["answer"])
                entry["restart"] = {**result, "grade": grade}
                print(f"  📊 {'✓ CORRECT' if grade['correct'] else '✗ WRONG'} (extracted: \"{grade['extracted']}\")")
            except Exception as e:
                print(f"  ❌ RE-TRAC error: {e}")
                entry["restart"] = {"error": str(e), "grade": {"correct": False}}
            finally:
                agent.close()

        if run_reform:
            agent = ReformulationAgent(headless=headless).init()
            try:
                print("\n  ── Reformulation ──")
                result = agent.answer(question)
                grade = grade_answer(question, correct_answer, result["answer"])
                entry["reform"] = {**result, "grade": grade}
                print(f"  📊 {'✓ CORRECT' if grade['correct'] else '✗ WRONG'} (extracted: \"{grade['extracted']}\")")
            except Exception as e:
                print(f"  ❌ Reform error: {e}")
                entry["reform"] = {"error": str(e), "grade": {"correct": False}}
            finally:
                agent.close()

        all_results.append(entry)
        time.sleep(15)

    summarize(args, all_results)


def summarize(args, all_results):
    n = len(all_results)
    print(f"\n\n{'═' * 60}")
    print(f"  {args.benchmark.upper()} EVALUATION SUMMARY")
    print(f"{'═' * 60}\n")

    for key, label, extra_name in [("baseline", "BASELINE", None), ("restart", "RE-TRAC", "Rounds after first"), ("reform", "REFORMULATION", "Reformulations")]:
        vals = [r[key] for r in all_results if r.get(key)]
        if not vals:
            continue
        correct = sum(1 for v in vals if v.get("grade", {}).get("correct"))
        valid = [v for v in vals if "elapsed_sec" in v]
        print(f"  {label}:")
        print(f"    Accuracy:    {correct}/{n} ({correct/n*100:.1f}%)")
        print(f"    Avg time:    {sum(v.get('elapsed_sec', 0) for v in valid)/max(len(valid),1):.1f}s")
        print(f"    Avg steps:   {sum(v.get('total_steps', 0) for v in valid)/max(len(valid),1):.1f}")
        print(f"    Avg pages:   {sum(v.get('pages_fetched', 0) for v in valid)/max(len(valid),1):.1f}")
        if extra_name:
            field = "restarts" if key == "restart" else "reformulations"
            total = sum(v.get(field, 0) for v in vals)
            print(f"    {extra_name}: {total} total ({total/max(len(valid),1):.1f} avg)")
        print()

    if args.compare_recovery:
        print(f"  {'#':<4} {'RE-TRAC':<12} {'Reform':<12} {'Rounds+':<9} {'Reform#':<8} Question")
        print(f"  {'─' * 85}")
        for i, r in enumerate(all_results):
            st = "✓" if r["restart"] and r["restart"].get("grade", {}).get("correct") else "✗"
            rf = "✓" if r["reform"] and r["reform"].get("grade", {}).get("correct") else "✗"
            print(f"  {i+1:<4} {st:<12} {rf:<12} {str((r['restart'] or {}).get('restarts', '?')):<9} {str((r['reform'] or {}).get('reformulations', '?')):<8} {r['question'][:38]}...")

    Path("results").mkdir(exist_ok=True)
    fname = f"results/{args.benchmark}_{int(time.time())}.json"
    with open(fname, "w") as f:
        json.dump({"benchmark": args.benchmark, "n": n, "results": all_results}, f, indent=2, default=str)
    print(f"\n  💾 Results saved to {fname}\n")


if __name__ == "__main__":
    main()
