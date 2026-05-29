# Demo Cases

These cases are selected from the clean HotpotQA hard bridge run:

```text
results/hotpot_1780028038.json
```

They are intended for slides, final-report examples, or a short live demo.

## Case 1: Reformulation Recovers From A Bad Initial Direction

Question:

> What made the man who abolished the Consell in 1718 resume the throne?

Expected answer:

> upon his son's death

### RE-TRAC-Style Recovery

| Metric | Value |
| --- | ---: |
| Correct | No |
| Time | 44.8s |
| Steps | 20 |
| Pages fetched | 8 |
| Restarts | 2 |

Trajectory summary:

| Round | Query | Outcome |
| ---: | --- | --- |
| 1 | `What made the man who abolished the Consell in 1718 resume the throne?` | Search drifted toward unrelated abolition/restoration history. |
| 2 | `Who abolished the Consell in 1718 and resumed the throne?` | Still failed to identify the Spanish/Catalan context. |
| 3 | `Consell 1718 abolition` | Returned generic abolition material and did not recover the target entity. |

Final answer:

> The provided evidence does not contain any information about a man who
> abolished the "Consell" in 1718 or subsequently resumed the throne.

### Mid-Trajectory Reformulation

| Metric | Value |
| --- | ---: |
| Correct | Yes |
| Time | 19.7s |
| Steps | 11 |
| Pages fetched | 5 |
| Reformulations | 1 |

Trajectory summary:

| Step | Query | Search-quality decision |
| ---: | --- | --- |
| 1 | `What made the man who abolished the Consell in 1718 resume the throne?` | Poor results, score 1/10. |
| 2 | `Philip V of Spain resume throne` | Useful results, score 8/10. |
| 3 | `Philip V abolished Consell 1718` | Follow-up confirms the historical entity. |
| 4 | `Philip V abdication 1724 reason` | Follow-up identifies why he resumed the throne. |

Final answer:

> Philip V, who abolished the Gran i General Consell on July 22, 1718,
> resumed the throne in September 1724 after his son, Louis I, died.

Why this is a good demo:

- The first search was plausible but wrong.
- Reformulation recognized the mismatch early.
- A single better query moved the search into the correct historical context.
- The reformulation agent answered correctly with less than half the time and
  fewer fetched pages.

## Case 2: Same Answer, Much Less Work

Question:

> In addition to the best known comic servant from Commedia dell'arte, who else
> is featured in La Surprise de l'amour?

Expected answer:

> Columbine

### Result Comparison

| Agent | Correct | Time | Steps | Pages fetched |
| --- | --- | ---: | ---: | ---: |
| RE-TRAC-style recovery | Yes | 114.3s | 20 | 8 |
| Mid-trajectory reformulation | Yes | 22.4s | 18 | 2 |

RE-TRAC eventually found the answer, but it spent full restart rounds fetching
more pages. Reformulation repeatedly rejected overly broad or wrong-title
queries until it found a useful query for the original Marivaux play.

Useful reformulation sequence:

```text
Initial query:
In addition to the best known comic servant from Commedia dell'arte, who else is featured in La Surprise de l'amour?

Rewritten queries:
La Surprise de l'amour characters
Marivaux La Surprise de l'amour characters
La Surprise de l'amour specific characters
La Surprise de l'amour characters Marivaux 1722
```

Why this is a good demo:

- Both agents answer correctly, so the comparison is not only about accuracy.
- The difference is efficiency: fewer pages, much lower runtime.
- This supports the central claim that mid-trajectory correction can avoid the
  cost of complete restarts.

## Case 3: Limitation - Good Retrieval Can Still Produce A Less Specific Answer

Question:

> Rynella is an unincorporated community named after the daughters of a
> conservationist who presided of the maker of a brand of hot sauce made from
> vinegar, salt and what kind of peppers?

Expected answer:

> tabasco peppers

### Result Comparison

| Agent | Correct | Answer |
| --- | --- | --- |
| RE-TRAC-style recovery | Yes | `Tabasco peppers` |
| Mid-trajectory reformulation | No | `red peppers` |

The reformulation agent retrieved useful evidence about Rynella, Edward Avery
McIlhenny, and the McIlhenny Company. The failure happened during final
synthesis: it returned the broader ingredient phrase `red peppers` instead of
the more specific expected answer `tabasco peppers`.

Why this belongs in the demo:

- It shows the system is not just "magically better"; there are real failure
  modes.
- It separates retrieval success from synthesis precision.
- It motivates future work: add a final verification step that asks whether the
  candidate answer is specific enough for the original question.

## Slide-Friendly Takeaway

Use these three cases together:

1. **Case 1:** reformulation improves accuracy by redirecting a bad search.
2. **Case 2:** reformulation preserves accuracy while reducing work.
3. **Case 3:** reformulation still needs better answer verification.

This gives a balanced final story: the method is promising, measurable, and
honest about its remaining bottlenecks.

