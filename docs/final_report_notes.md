# Final Report Notes

This document collects concise points for the final report and presentation.

## Project Claim

This project compares full trajectory recovery against mid-trajectory query
reformulation for web-based question answering.

The key idea is:

> Instead of waiting for a complete search trajectory to fail and then
> restarting, the agent can evaluate search quality earlier, repair the query
> mid-trajectory, and avoid spending work on irrelevant pages.

The strongest result so far is from HotpotQA hard bridge questions:

| Agent | Accuracy | Tool Errors | Avg Time | Avg Steps | Avg Pages |
| --- | ---: | ---: | ---: | ---: | ---: |
| RE-TRAC-style recovery | 17/30 | 0/30 | 55.0s | 19.3 | 7.3 |
| Mid-trajectory reformulation | 20/30 | 0/30 | 27.1s | 10.2 | 3.1 |

Pairwise result:

| Comparable Questions | RE-TRAC Only Correct | Reformulation Only Correct | Both Correct | Both Wrong |
| ---: | ---: | ---: | ---: | ---: |
| 30 | 2 | 5 | 15 | 8 |

Interpretation: the reformulation agent answered more questions correctly while
using about half the time, about half the steps, and less than half the page
fetches.

## What Worked

- Query quality evaluation helped catch bad initial searches before page
  fetching.
- Targeted follow-up searches were efficient for bridge questions where one
  intermediate entity had to be resolved before the final answer.
- The reformulation pipeline avoided the fixed cost of full restart rounds.
- HotpotQA hard bridge was a better fit than BrowseComp for measuring this
  stage of the system because the answers are more likely to be retrievable
  through public web search.

## Example Wins For Reformulation

Good examples from the 30-question run:

- Question 11: The direct query for "Minister Pool" was poor; reformulation
  repeatedly recognized irrelevant results and continued searching instead of
  accepting the wrong regional context.
- Question 12: The initial query drifted toward English monarchy restoration;
  reformulation redirected to Philip V of Spain and recovered the correct
  causal answer.
- Question 21: Reformulation eventually found the specific "SKUM fanzine"
  source after several weak searches.
- Question 23: Reformulation distinguished the original *La Surprise de
  l'amour* from similarly named results and found the character list.

These examples support the claim that mid-trajectory correction is especially
useful when the first search result page is topically plausible but missing the
actual bridge needed to answer the question.

## Failure Modes

### 1. Query Drift

The reformulation agent can rewrite a weak query into a different plausible
direction that is still wrong. For example, on the Tabasco/Rynella question, it
collected useful evidence but synthesized "red peppers" instead of the more
specific "tabasco peppers."

Mitigation: require the final answer to preserve the most specific entity found
in evidence, especially when the expected answer asks for a type, name, or
proper noun.

### 2. Over-Accepting Plausible Search Results

Some search results look relevant because they share the right surface terms but
do not answer the intended relation. This happened on questions involving
similarly named works, organizations, or historical entities.

Mitigation: strengthen the search evaluator to check whether results satisfy
the exact relation in the question, not just entity overlap.

### 3. Synthesis Errors After Good Retrieval

Sometimes the evidence contains the answer but the LLM chooses a less precise
or adjacent answer. This shows that retrieval quality and answer synthesis are
separate bottlenecks.

Mitigation: add a final verification prompt that compares the candidate answer
against the original wording and asks whether it is too broad or too narrow.

### 4. Benchmark / Live Web Mismatch

HotpotQA expected answers are static, but live web data changes. For example,
population questions may retrieve newer population numbers than the benchmark
answer expects. This can make a factually current answer grade as incorrect.

Mitigation: report this as an evaluation limitation and prefer questions where
answers are stable names, dates, titles, or historical facts.

### 5. LLM Grader Dependence

The automatic grader is also LLM-based. It is useful for quick iteration, but it
can be inconsistent on partial matches, aliases, or overly verbose answers.

Mitigation: manually inspect representative wins/losses and include exact
examples in the final report.

### 6. External Tool Reliability

The system depends on Serper, Gemini/Groq, and live websites. Rate limits,
temporary 503 errors, DNS issues, and blocked pages can affect results.

Mitigation: the evaluation now reports tool errors separately from answer
accuracy, and the browser/search layer retries transient failures.

## Why BrowseComp Was Not The Main Benchmark

BrowseComp was useful as a stress test, but it was too difficult for the current
system stage. Many questions require extremely specific web facts that were not
retrieved by either agent. When both systems score near zero, the benchmark does
not reveal useful differences between recovery strategies.

HotpotQA hard bridge is more appropriate for the final comparison because it
still requires multi-hop reasoning, but the intermediate facts are more often
retrievable through normal web search.

## Final Presentation Talking Points

Suggested slide order:

1. Project goal: improve web-agent recovery by repairing queries earlier.
2. Motivation: full restarts are expensive when only the query direction is bad.
3. Pipelines: compare RE-TRAC-style restart with mid-trajectory reformulation.
4. Implementation: Serper search, Playwright fetching, LLM evaluation,
   synthesis, and grading.
5. Main result: HotpotQA hard bridge n=30 table.
6. Pairwise result: reformulation only correct on 5 questions vs RE-TRAC only
   correct on 2.
7. Case study: one question where reformulation redirects a bad query.
8. Limitations: query drift, synthesis errors, live web mismatch, grader
   dependence.
9. Future work: better evidence gating, final answer verification, cached
   retrieval, and larger benchmark runs.

## Future Work

- Add stronger evidence gating before accepting a rewritten query as useful.
- Add final answer verification to check specificity and relation matching.
- Cache search results and fetched pages to make evaluation cheaper and more
  reproducible.
- Expand evaluation to 50-100 HotpotQA hard bridge questions once caching is in
  place.
- Add a small curated demo set of intentionally difficult multi-hop web
  questions for qualitative analysis.

