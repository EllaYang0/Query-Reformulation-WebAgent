# Query Reformulation Web Agent

## Project Overview

This project studies whether a web-search agent can recover from bad search
trajectories more efficiently by correcting queries *during* the trajectory
rather than waiting for the whole trajectory to fail.

The project is inspired by RE-TRAC-style recovery methods, where an agent runs a
complete search trajectory, compresses the trajectory into a structured state,
and then starts another rollout using that state. This project tests an
alternative approach: detect weak search results early, reformulate the query
mid-trajectory, and only fetch or reason over pages once the search direction is
useful.

The main comparison is:

- **RE-TRAC-style recovery**: full trajectory -> structured compression -> new
  full trajectory.
- **Mid-trajectory query reformulation**: search -> evaluate search quality ->
  rewrite query or add targeted follow-up search before wasting work on
  irrelevant pages.

Main features:

- Web search through Serper's Google Search API.
- Page fetching and text extraction with Playwright.
- LLM-based answer synthesis and search-result evaluation.
- Three agent strategies:
  - single-query baseline,
  - RE-TRAC-style trajectory-compression baseline,
  - mid-trajectory query reformulation agent.
- Evaluation on HotpotQA hard bridge questions and BrowseComp.
- CI workflow for syntax checks and smoke tests.

Latest clean HotpotQA hard bridge result, using 30 questions with seed 42:

| Agent | Accuracy | Tool Errors | Avg Time | Avg Steps | Avg Pages |
| --- | ---: | ---: | ---: | ---: | ---: |
| RE-TRAC-style recovery | 17/30 | 0/30 | 55.0s | 19.3 | 7.3 |
| Mid-trajectory reformulation | 20/30 | 0/30 | 27.1s | 10.2 | 3.1 |

The current result suggests that early query correction can improve accuracy
over full trajectory recovery while using fewer steps, less time, and fewer page
fetches. The saved run for this result is `results/hotpot_1780028038.json`
locally; the `results/` directory is intentionally ignored by Git.

## Repository Organization

```text
.
├── agent.py                  # CLI for running one question interactively
├── eval.py                   # Batch evaluation runner
├── requirements.txt          # Python dependencies
├── docs/
│   ├── pipeline.md           # Diagrams and explanation of agent pipelines
│   ├── demo_cases.md         # Qualitative examples for final presentation
│   └── final_report_notes.md # Limitations and presentation talking points
├── scripts/
│   └── summarize_results.py  # Convert saved eval JSON to Markdown tables
├── src/
│   ├── baseline.py           # Single-query baseline agent
│   ├── restart.py            # RE-TRAC-style trajectory-compression agent
│   ├── reformulator.py       # Mid-trajectory query reformulation agent
│   ├── browser.py            # Serper search + Playwright page fetching
│   ├── llm.py                # Gemini/Groq API wrapper with retry logic
│   ├── hotpotqa.py           # HotpotQA dataset loader
│   ├── browsecomp.py         # BrowseComp dataset loader and decryptor
│   └── __init__.py
├── tests/
│   └── smoke_test.py         # Lightweight CI tests without API calls
├── .github/workflows/
│   └── ci.yml                # GitHub Actions CI workflow
└── results/                  # Local experiment outputs, ignored by Git
```

The code is organized around agent implementations in `src/`:

- `BaselineAgent` searches the original question once, fetches the top pages,
  and asks the LLM to synthesize an answer.
- `RestartAgent` approximates a RE-TRAC-style loop: each round runs a full
  search/fetch/answer trajectory, compresses the trajectory into a structured
  state, and conditions the next round on that state.
- `ReformulationAgent` performs earlier intervention: it evaluates search
  results immediately, rewrites weak queries, and plans targeted follow-up
  searches only when evidence is missing a key step.

`eval.py` connects these agents to benchmark datasets and reports accuracy,
average runtime, average steps, pages fetched, restarts, and reformulations.
See `docs/pipeline.md` for diagrams comparing the RE-TRAC-style restart
pipeline with the mid-trajectory reformulation pipeline.
See `docs/demo_cases.md` for selected qualitative examples from the evaluation
run.
See `docs/final_report_notes.md` for limitations, interpretation of the
results, and suggested final presentation talking points.

## Build / Installation Instructions

### 1. Clone the repository

```bash
git clone https://github.com/EllaYang0/Query-Reformulation-WebAgent.git
cd Query-Reformulation-WebAgent
```

### 2. Create and activate a Python environment

Python 3.11 is recommended.

```bash
python -m venv .venv
source .venv/bin/activate
```

If you use Conda instead:

```bash
conda create -n query-agent python=3.11
conda activate query-agent
```

### 3. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install Playwright's Chromium browser

```bash
python -m playwright install chromium
```

### 5. Configure API keys

Create a local `.env` file in the repository root:

```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
SERPER_API_KEY=your_serper_api_key
```

Optional Groq fallback:

```bash
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile
```

Notes:

- `.env` is ignored by Git and should not be committed.
- `SERPER_API_KEY` is required for web search.
- `GEMINI_API_KEY` is required if `LLM_PROVIDER=gemini`.
- The evaluation uses external APIs, so repeated large runs may incur API cost.

### 6. Verify local setup

Run the same checks used by CI:

```bash
python -m py_compile agent.py eval.py src/*.py tests/*.py
pytest -q tests
```

These checks do not call external APIs.

## Run Instructions

### Run a single agent on one question

Baseline, single-query search:

```bash
python agent.py --baseline "What is the population of Bonn?"
```

Mid-trajectory query reformulation:

```bash
python agent.py --reform "At what theater is the composer and lyricist for the musical Big Fish a residential artist?"
```

RE-TRAC-style trajectory compression:

```bash
python agent.py --restart "The organization that Nicolae Titulescu served two terms as president was founded on what date?"
```

### Compare baseline vs reformulation on one question

```bash
python agent.py --compare "How many laps did Harry Prowell run during the 10,000 metres race at the 1967 Pan American Games?"
```

### Compare RE-TRAC-style recovery vs mid-trajectory reformulation

This is the main comparison for the project:

```bash
python agent.py --compare-recovery "At what theater is the composer and lyricist for the musical Big Fish a residential artist?"
```

### Run benchmark evaluation

HotpotQA hard bridge questions:

```bash
python eval.py --benchmark hotpot --n 30 --seed 42 --compare-recovery
```

BrowseComp:

```bash
python eval.py --benchmark browsecomp --n 5 --seed 42 --compare-recovery
```

Run only one agent type:

```bash
python eval.py --benchmark hotpot --n 10 --seed 42 --baseline-only
python eval.py --benchmark hotpot --n 10 --seed 42 --restart-only
python eval.py --benchmark hotpot --n 10 --seed 42 --reform-only
```

Show the browser window instead of running headless:

```bash
python eval.py --benchmark hotpot --n 10 --seed 42 --compare-recovery --no-headless
```

Evaluation results are saved locally under:

```text
results/
```

The `results/` directory is ignored by Git because outputs can be large and may
vary between runs due to live web search results.

Summarize a saved result file as Markdown:

```bash
python scripts/summarize_results.py results/hotpot_1780028038.json
```

The summary includes aggregate metrics, valid-only accuracy, tool-error counts,
pairwise wins between RE-TRAC-style recovery and reformulation, and per-question
outcomes.
