"""
restart.py - RE-TRAC-style recursive trajectory compression agent.
"""

import json
import time
from .browser import Browser
from .llm import ask_llm, ask_llm_json

TOP_N = 3
MAX_ROUNDS = 3


class RestartAgent:
    def __init__(self, headless=True):
        self.browser = Browser(headless=headless)
        self.trace = []

    def init(self):
        self.browser.launch()
        return self

    def close(self):
        self.browser.close()

    def answer(self, question):
        start = time.time()
        self.trace = []
        state = self._initial_state()
        attempts = []

        print(f"  📋 Question: {question}")

        for round_idx in range(1, MAX_ROUNDS + 1):
            print(f"\n  ── RE-TRAC round {round_idx}/{MAX_ROUNDS} ──")
            query = self._plan_query(question, state, round_idx)
            trajectory = self._run_trajectory(question, query, round_idx)
            attempts.append(trajectory)
            state = self._compress_state(question, state, trajectory, round_idx)
            self._record("compress_state", round=round_idx, state=state)
            print("  🧠 Compressed trajectory state:")
            print(f"     conclusions: {self._short(state.get('conclusions', []))}")
            print(f"     uncertainties: {self._short(state.get('uncertainties', []))}")
            print(f"     next plan: {self._short(state.get('future_plan', []))}")

        final_answer = self._final_answer(question, state, attempts)
        elapsed = round(time.time() - start, 1)
        final = attempts[-1]

        print(f"\n  💡 Answer:\n  {final_answer}\n")
        print(f"  ⏱ {elapsed}s | {len(self.trace)} steps | {MAX_ROUNDS - 1} compressed restarts | {sum(a['pages_fetched'] for a in attempts)} total pages")

        return {
            "question": question,
            "query": final["query"],
            "answer": final_answer,
            "search_results": final["search_results"],
            "pages_fetched": sum(a["pages_fetched"] for a in attempts),
            "final_pages_fetched": final["pages_fetched"],
            "elapsed_sec": elapsed,
            "total_steps": len(self.trace),
            "restarts": MAX_ROUNDS - 1,
            "attempts": attempts,
            "compressed_state": state,
            "trace": self.trace,
        }

    def _initial_state(self):
        return {
            "conclusions": [],
            "verified_evidence": [],
            "uncertainties": [],
            "failed_directions": [],
            "future_plan": [],
            "candidate_answer": "",
        }

    def _plan_query(self, question, state, round_idx):
        if round_idx == 1:
            query = question.strip()
            self._record("plan_query", round=round_idx, query=query, state_used=False)
            print(f"  🔍 Query: \"{query}\"")
            return query

        prompt = (
            "You are running the next rollout of a RE-TRAC-style web research agent. "
            "Use the compressed state from previous trajectories to avoid repeating failed directions.\n\n"
            f"Question: {question}\n\nCompressed state:\n{json.dumps(state, indent=2)}\n\n"
            "Generate ONE search query for this new full trajectory. Output ONLY the query text."
        )
        try:
            query = ask_llm(prompt, max_tokens=64, temperature=0.4).strip().strip("'\"")[:120]
        except Exception as e:
            print(f"  ⚠ State-conditioned query error: {e}")
            plan = state.get("future_plan") or []
            query = str(plan[0]) if plan else question.strip()
        self._record("plan_query", round=round_idx, query=query, state_used=True)
        print(f"  🔍 Query: \"{query}\"")
        return query

    def _run_trajectory(self, question, query, round_idx):
        results = self.browser.search(query)["results"]
        self._record("search", round=round_idx, query=query, result_count=len(results))
        print(f"  → {len(results)} results")
        for r in results[:5]:
            print(f"    {r['index']}. {r['title']}")

        pages = []
        for r in results[:TOP_N]:
            print(f"  📄 Fetching: {r['title'][:60]}...")
            page = self.browser.fetch_page(r["url"])
            if page["ok"] and len(page["text"]) > 100:
                pages.append({**r, "text": page["text"]})
                self._record("fetch_page", round=round_idx, url=r["url"], text_len=len(page["text"]))
        print(f"  → Fetched {len(pages)}/{min(TOP_N, len(results))} pages")

        answer = self._synthesize(question, results, pages)
        self._record("answer", round=round_idx, answer=answer)
        return {"round": round_idx, "query": query, "answer": answer, "search_results": results, "pages_fetched": len(pages), "pages": pages}

    def _synthesize(self, question, search_results, pages):
        context = self._trajectory_context(search_results, pages)
        if not context.strip():
            return "I could not find relevant information to answer this question."
        prompt = (
            "Based on the evidence below, answer this question in 2-3 sentences. "
            "Give a direct, specific answer with names/dates/numbers. Do not hedge.\n\n"
            f"Question: {question}\n\nEvidence:\n{context}\n\nAnswer concisely:"
        )
        try:
            print("  🤖 Asking LLM to synthesize answer...")
            return ask_llm(prompt, max_tokens=1024, temperature=0.1)
        except Exception as e:
            print(f"  ⚠ LLM error: {e}")
            fallback = next((r["snippet"] for r in search_results if r["snippet"]), "")
            return f"(LLM unavailable) {fallback}" if fallback else "Could not generate answer."

    def _compress_state(self, question, previous_state, trajectory, round_idx):
        context = self._trajectory_context(trajectory["search_results"], trajectory["pages"], max_page_chars=1400)
        prompt = (
            "Compress this completed web-agent trajectory into a structured RE-TRAC state. "
            "The next rollout will only see this state, not the full trajectory.\n\n"
            f"Question: {question}\nPrevious state:\n{json.dumps(previous_state, indent=2)}\n\n"
            f"Round: {round_idx}\nQuery: {trajectory['query']}\nAnswer: {trajectory['answer']}\n\nEvidence:\n{context}\n\n"
            "Respond with JSON only using keys: conclusions, verified_evidence, uncertainties, failed_directions, future_plan, candidate_answer."
        )
        try:
            state = ask_llm_json(prompt, max_tokens=900, temperature=0.1)
            if isinstance(state, dict):
                return self._normalize_state(state)
        except Exception as e:
            print(f"  ⚠ State compression error: {e}")
        merged = dict(previous_state)
        merged["conclusions"] = list(previous_state.get("conclusions", [])) + [trajectory["answer"][:300]]
        merged["failed_directions"] = list(previous_state.get("failed_directions", [])) + [trajectory["query"]]
        merged["future_plan"] = [f"{question} missing detail"]
        merged["candidate_answer"] = trajectory["answer"]
        return self._normalize_state(merged)

    def _final_answer(self, question, state, attempts):
        summaries = "\n".join(f"Round {a['round']} query: {a['query']}\nRound {a['round']} answer: {a['answer']}\n" for a in attempts)
        prompt = (
            "Produce the final answer after multiple RE-TRAC rounds. Use the compressed state and trajectory summaries. "
            "Prefer verified evidence; ignore failed directions and unsupported guesses.\n\n"
            f"Question: {question}\n\nCompressed state:\n{json.dumps(state, indent=2)}\n\nRound summaries:\n{summaries}\nFinal answer, concise:"
        )
        try:
            return ask_llm(prompt, max_tokens=512, temperature=0.1)
        except Exception as e:
            print(f"  ⚠ Final answer error: {e}")
            return state.get("candidate_answer") or attempts[-1]["answer"]

    def _trajectory_context(self, search_results, pages, max_page_chars=2000):
        context = ""
        for i, r in enumerate(search_results[:5]):
            if r["snippet"]:
                context += f"[Snippet {i+1}] {r['title']}\n{r['snippet']}\n\n"
        for i, p in enumerate(pages):
            context += f"[Page {i+1}] {p['title']} ({p['url']})\n{p['text'][:max_page_chars]}\n\n"
        return context

    def _normalize_state(self, state):
        return {
            "conclusions": self._as_list(state.get("conclusions")),
            "verified_evidence": self._as_list(state.get("verified_evidence")),
            "uncertainties": self._as_list(state.get("uncertainties")),
            "failed_directions": self._as_list(state.get("failed_directions")),
            "future_plan": self._as_list(state.get("future_plan")),
            "candidate_answer": str(state.get("candidate_answer", "")),
        }

    def _as_list(self, value):
        if value is None:
            return []
        if isinstance(value, list):
            return value[:8]
        return [str(value)]

    def _short(self, value):
        text = json.dumps(value, ensure_ascii=False)
        return text[:160] + ("..." if len(text) > 160 else "")

    def _record(self, action, **data):
        self.trace.append({"step": len(self.trace) + 1, "action": action, **data})
