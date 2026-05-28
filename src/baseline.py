"""
baseline.py - Single-trajectory baseline.
"""

import time
from .browser import Browser
from .llm import ask_llm

TOP_N = 3


class BaselineAgent:
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
        query = question.strip()

        print(f"  📋 Question: {question}")
        print(f"  🔍 Query: \"{query}\"")
        self._record("generate_query", question=question, query=query)

        search_result = self.browser.search(query)
        results = search_result["results"]
        self._record("search", query=query, result_count=len(results))
        print(f"  → {len(results)} results")
        for r in results[:5]:
            print(f"    {r['index']}. {r['title']}")

        pages = []
        for r in results[:TOP_N]:
            print(f"  📄 Fetching: {r['title'][:60]}...")
            page = self.browser.fetch_page(r["url"])
            if page["ok"] and len(page["text"]) > 100:
                pages.append({**r, "text": page["text"]})
                self._record("fetch_page", url=r["url"], text_len=len(page["text"]))
        print(f"  → Fetched {len(pages)}/{min(TOP_N, len(results))} pages")

        answer = self._synthesize(question, results, pages)
        elapsed = round(time.time() - start, 1)
        self._record("answer", answer=answer, elapsed=elapsed)

        print(f"\n  💡 Answer:\n  {answer}\n")
        print(f"  ⏱ {elapsed}s | {len(self.trace)} steps | {len(pages)} pages")

        return {
            "question": question,
            "query": query,
            "answer": answer,
            "search_results": results,
            "pages_fetched": len(pages),
            "elapsed_sec": elapsed,
            "total_steps": len(self.trace),
            "reformulations": 0,
            "trace": self.trace,
        }

    def _synthesize(self, question, search_results, pages):
        context = ""
        for i, r in enumerate(search_results[:5]):
            if r["snippet"]:
                context += f"[Snippet {i+1}] {r['title']}\n{r['snippet']}\n\n"
        for i, p in enumerate(pages):
            context += f"[Page {i+1}] {p['title']} ({p['url']})\n{p['text'][:2000]}\n\n"

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

    def _record(self, action, **data):
        self.trace.append({"step": len(self.trace) + 1, "action": action, **data})
