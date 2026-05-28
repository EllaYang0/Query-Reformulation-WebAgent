"""
reformulator.py - Mid-trajectory query correction agent.

This agent corrects weak search trajectories early:
  direct search -> evaluate search quality -> rewrite query if poor
  -> inspect evidence -> run targeted follow-up searches only for missing hops
  -> synthesize final answer
"""

import re
import time
from .browser import Browser
from .llm import ask_llm, ask_llm_json

TOP_N = 2
MAX_RETRIES = 3
MAX_FOLLOWUPS = 2


class ReformulationAgent:
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
        all_evidence = []
        all_search_results = []
        reformulations = 0

        print(f"  📋 Question: {question}")
        print(f"\n  ── Direct trajectory: \"{question}\" ──")

        evidence, ref_count, results = self._search_with_retry(question, question)
        all_evidence.extend(evidence)
        all_search_results.extend(results)
        reformulations += ref_count

        followups = self._dedupe_queries(self._plan_followups(question, all_evidence))[:MAX_FOLLOWUPS]
        self._record("plan_followups", question=question, followup_queries=followups)

        if followups:
            print(f"\n  🧭 Planned {len(followups)} follow-up searches:")
            for i, q in enumerate(followups):
                print(f"     {i+1}. \"{q}\"")
        else:
            print("\n  🧭 No follow-up searches needed.")

        for i, query in enumerate(followups):
            print(f"\n  ── Follow-up {i+1}/{len(followups)}: \"{query}\" ──")
            evidence, ref_count, results = self._search_with_retry(question, query)
            all_evidence.extend(evidence)
            all_search_results.extend(self._dedupe_results(results, all_search_results))
            reformulations += ref_count

        if not all_evidence:
            generated = self._generate_query(question)
            evidence, ref_count, results = self._search_with_retry(question, generated)
            all_evidence.extend(evidence)
            all_search_results.extend(self._dedupe_results(results, all_search_results))
            reformulations += ref_count

        print(f"\n  📚 Total evidence collected: {len(all_evidence)} pieces")
        answer = self._synthesize(question, all_evidence)
        elapsed = round(time.time() - start, 1)
        self._record("answer", answer=answer, elapsed=elapsed, reformulations=reformulations)

        print(f"\n  💡 Answer:\n  {answer}\n")
        print(f"  ⏱ {elapsed}s | {len(self.trace)} steps | {reformulations} reformulations | {len(all_evidence)} evidence pieces")

        return {
            "question": question,
            "query": ", ".join([question, *followups]),
            "answer": answer,
            "search_results": all_search_results,
            "pages_fetched": len([e for e in all_evidence if e["source"] == "page"]),
            "elapsed_sec": elapsed,
            "total_steps": len(self.trace),
            "reformulations": reformulations,
            "trace": self.trace,
        }

    def _search_with_retry(self, original_question, query):
        evidence = []
        search_results = []
        reformulations = 0
        attempts = 0

        while attempts <= MAX_RETRIES:
            attempts += 1
            search_result = self.browser.search(query)
            results = search_result["results"]
            search_results.extend(self._dedupe_results(results, search_results))
            self._record("search", attempt=attempts, query=query, result_count=len(results))

            print(f"    🔍 [{attempts}] \"{query}\" → {len(results)} results")
            for r in results[:3]:
                print(f"       {r['index']}. {r['title'][:70]}")

            evaluation = {"score": 0, "is_good": False, "reason": "no_results"} if not results else self._evaluate_results(original_question, query, results)
            self._record("evaluate", **evaluation)

            if evaluation["is_good"]:
                print(f"    ✓ Good (score: {evaluation['score']}/10)")
                for r in results[:TOP_N]:
                    page = self.browser.fetch_page(r["url"])
                    if page["ok"] and len(page["text"]) > 100:
                        evidence.append({"source": "page", "query": query, "title": r["title"], "url": r["url"], "text": page["text"][:3000]})
                for r in results[:5]:
                    if r["snippet"]:
                        evidence.append({"source": "snippet", "query": query, "title": r["title"], "text": r["snippet"]})
                break

            print(f"    ⚠ Poor (score: {evaluation['score']}/10, reason: {evaluation['reason']})")
            if attempts > MAX_RETRIES:
                for r in results[:TOP_N]:
                    if r["snippet"]:
                        evidence.append({"source": "snippet", "query": query, "title": r["title"], "text": r["snippet"]})
                break

            new_query = self._reformulate_query(original_question, query, results, evaluation["reason"])
            self._record("reformulate", old_query=query, new_query=new_query)
            print(f"    🔄 \"{query}\" → \"{new_query}\"")
            query = new_query
            reformulations += 1

        return evidence, reformulations, search_results

    def _evaluate_results(self, question, query, results):
        snippet_summary = "\n".join(f"{r['index']}. {r['title']}\n   {r['snippet'] or '(no snippet)'}" for r in results[:5])
        prompt = (
            "Evaluate whether these search results contain useful information for answering the question. "
            "For a follow-up query, results only need to answer the targeted missing piece.\n\n"
            f"Question: {question[:400]}\nQuery: {query}\n\nResults:\n{snippet_summary}\n\n"
            'Respond JSON only: {"score": <1-10>, "isGood": <true if score >= 6>, "reason": "<short phrase>"}'
        )
        try:
            result = ask_llm_json(prompt, max_tokens=256, temperature=0.1)
            score = result.get("score", 0)
            return {"score": score, "is_good": result.get("isGood", score >= 6), "reason": result.get("reason", "unknown")}
        except Exception as e:
            print(f"    ⚠ Evaluate error: {e}")
            return {"score": 5, "is_good": True, "reason": "evaluation_failed"}

    def _reformulate_query(self, question, current_query, results, failure_reason):
        snippets = "\n".join(f"{r['index']}. {r['title']}: {r['snippet'] or ''}" for r in results[:3])
        prompt = (
            "A web search query returned poor results. Generate a better query now, before the agent wastes work fetching irrelevant pages.\n\n"
            f"Question: {question[:400]}\nWeak query: {current_query}\nFailure: {failure_reason}\nResults:\n{snippets}\n\n"
            "Output ONLY the new query, 3-10 words."
        )
        try:
            return ask_llm(prompt, max_tokens=64, temperature=0.5).strip().strip("'\"")[:120]
        except Exception as e:
            print(f"    ⚠ Reformulate error: {e}")
            return f"{current_query} details"

    def _plan_followups(self, question, evidence):
        if not evidence:
            return [self._generate_query(question)]
        summary = ""
        for i, e in enumerate(evidence[:8]):
            summary += f"[Evidence {i+1}] {e.get('title', '')}\n{e.get('text', '')[:700]}\n\n"
        prompt = (
            "You are controlling a web agent mid-trajectory. It has already run a direct search. "
            "Return follow-up searches only for missing intermediate entities or final properties.\n\n"
            f"Question: {question}\n\nCurrent evidence:\n{summary}\n\n"
            "Rules: return [] if enough; otherwise return 1-2 concrete queries. No placeholders.\n"
            'Respond JSON only, e.g. ["Bonn population", "League of Nations founding date"]'
        )
        try:
            result = ask_llm_json(prompt, max_tokens=256, temperature=0.3)
            if isinstance(result, list):
                return [str(q).strip().strip("'\"") for q in result if str(q).strip()]
        except Exception as e:
            print(f"  ⚠ Follow-up planning error: {e}")
        return []

    def _synthesize(self, question, evidence):
        if not evidence:
            return "I could not find relevant information to answer this question."
        context = ""
        for i, e in enumerate(evidence):
            query_line = f"Query: {e.get('query', '')}\n" if e.get("query") else ""
            context += f"[Evidence {i+1}] {e.get('title', f'Source {i+1}')}\n{query_line}{e['text'][:2000]}\n\n"
        if len(context) > 12000:
            context = context[:12000] + "\n... [truncated]"
        prompt = (
            "You are a precise web QA solver. Answer directly using the best-matching evidence. "
            "For comparison, compute the comparison. For yes/no, answer yes/no first. "
            "Ignore irrelevant search results.\n\n"
            f"Question: {question}\n\nEvidence:\n{context}\n\nFinal answer:"
        )
        try:
            print("  🤖 Synthesizing answer from all evidence...")
            return ask_llm(prompt, max_tokens=1024, temperature=0.1)
        except Exception as e:
            print(f"  ⚠ LLM error: {e}")
            return "Could not generate answer."

    def _generate_query(self, question):
        try:
            return ask_llm(f"Generate one concise search query for:\n{question}\n\nQuery:", max_tokens=64, temperature=0.3).strip().strip("'\"")[:120]
        except Exception:
            return re.sub(r"\\?", "", question)[:100].strip()

    def _dedupe_queries(self, queries):
        seen, unique = set(), []
        for q in queries:
            cleaned = str(q).strip().strip("'\"")
            if cleaned and cleaned.lower() not in seen:
                seen.add(cleaned.lower())
                unique.append(cleaned)
        return unique

    def _dedupe_results(self, results, existing=None):
        seen = set()
        for r in existing or []:
            key = r.get("url", "").split("#")[0].rstrip("/") or r.get("title", "").lower()
            seen.add(key)
        unique = []
        for r in results:
            key = r.get("url", "").split("#")[0].rstrip("/") or r.get("title", "").lower()
            if key not in seen:
                seen.add(key)
                unique.append(r)
        return unique

    def _record(self, action, **data):
        self.trace.append({"step": len(self.trace) + 1, "action": action, **data})
