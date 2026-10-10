# Agentic RFP Evaluation & Supplier Ranking

Streamlit + SQLite + any JSON-capable LLM. The LLM **judges proposal content**; deterministic Python
does **all arithmetic, benchmarking, tie-breaks and ranking**.

**Live app:** _paste your Streamlit Community Cloud URL here_

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/seed_db.py                  # optional - the app also auto-creates/seeds the DB
python scripts/generate_sample_rfps.py     # optional - 4 sample PDFs already in sample_rfps/
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # add your API key
streamlit run app.py
pytest -q                                  # unit tests for validation + ranking
```
No API key? Choose provider **mock** in the sidebar (offline keyword scorer) and tick
"Use the 4 bundled synthetic RFPs".

## Folder structure
```
app.py                     Streamlit UI (5 tabs)
src/orchestrator.py        Orchestrator Agent - runs the 10-step workflow in order
src/evaluator.py           Evaluation Agent - prompt builder + LLM call + one retry
src/llm_client.py          Anthropic / OpenAI-compatible / mock provider
src/tools/document_tool.py PDF -> clean text (pypdf)
src/tools/validation_tool.py  JSON parsing, schema checks, clipping, warnings
src/tools/ranking_tool.py  Scores, benchmarks, gaps, relative %, PPI, tie-breaks, ranks
src/database.py            SQLite schema, seed, persistence
scripts/                   seed_db.py, generate_sample_rfps.py
sample_rfps/               4 fictional supplier PDFs
sample_output/sample_run.json   exported result of one completed run
tests/test_tools.py        edge-case tests
```

## Architecture / data flow
Setup -> Input -> Batch (new `RFP_RUN_ID`) -> Evaluate (reload active criteria, extract text, prompt LLM)
-> Validate -> Score -> Benchmark -> Rank -> Persist (SQLite) -> Present (UI + JSON download).

| Component | Type | Responsibility |
|---|---|---|
| Orchestrator | Python | Controls order of steps, logs a trace, persists the run |
| Document Tool | Deterministic | Extracts text; warns on scanned/corrupt PDFs |
| Evaluation Agent | **LLM** | Scores one supplier per criterion with evidence (JSON only) |
| Validation Tool | Deterministic | Parses JSON, fills missing criteria, clips scores, records warnings |
| Ranking Tool | Deterministic | All formulas, PPI, tie-breaks, sequential ranks |

## Formulas
Let `w_i` = criterion weight (normalised to total 100), `s_i` = validated score, `m_i` = max score.
- **Absolute score** = Σ (s_i / m_i) × w_i
- **Benchmark_i** = max over suppliers of s_i
- **Gap_i** = s_i − benchmark_i (0 for the leader, otherwise negative)
- **Relative %_i** = s_i / benchmark_i × 100 (if benchmark_i = 0 -> 100: nobody scored, so nobody lags)
- **PPI** = Σ (Relative %_i × w_i) / 100
- **Ranking** (stable sort): PPI desc -> earlier submission date -> higher experience rating -> supplier name A-Z

## Validation rules
Database `max_score` is authoritative. Scores are clipped to `[0, max]`; missing or non-numeric scores become 0 and
are flagged (`clipped | missing | malformed`); unknown/duplicate criterion IDs are ignored; JSON inside code fences or
with surrounding prose is recovered; unparseable output triggers one retry, then all criteria score 0 with warnings.

## Assumptions
- Weights not summing to 100 are normalised (with a visible warning).
- Experience rating is a 1-5 number entered by the user.
- PPI is compared at 4 decimal places to avoid floating-point noise.
- Criteria are re-read from SQLite at evaluation time, so edits apply to the next run.
- SQLite on Streamlit Community Cloud is ephemeral; the DB is re-created and re-seeded on restart.

## Deploying to Streamlit Community Cloud
1. Push this folder to a public GitHub repo.
2. share.streamlit.io -> New app -> select repo, branch, `app.py`.
3. Settings -> Secrets: paste the contents of `.streamlit/secrets.toml.example` with your real key.
4. Copy the public URL into this README and your submission.

## Screenshots
Add screenshots of each tab to `docs/screenshots/` and link them here.

## Demo script (one success + one validation case)
1. Tick "Use the 4 bundled synthetic RFPs" -> Evaluate -> show Leaderboard, a Scorecard, Run details, JSON download.
2. Validation case A: untick samples, upload one PDF -> "At least two suppliers" error. Duplicate names -> error.
3. Validation case B: provider *mock* + "Simulate malformed LLM output" -> Evaluate -> Run details shows
   clipped / non-numeric / missing-criterion warnings, and the run still completes.
4. Criteria tab -> deactivate a criterion -> re-run to show dynamic criteria.
