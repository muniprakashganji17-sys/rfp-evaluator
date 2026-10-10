"""Orchestrator Agent: runs the workflow in the required order and calls each tool/agent."""
from datetime import datetime, timezone

from src import database
from src.evaluator import evaluate_supplier
from src.tools import document_tool, ranking_tool, validation_tool


def run_evaluation(suppliers, llm, db_path=None, progress=None):
    """suppliers: [{supplier_name, submission_date(date), experience_rating, pdf_bytes, filename}]
    Returns the complete result dict (also persisted to SQLite under one RFP_RUN_ID)."""
    trace, warnings = [], []

    def log(step, detail):
        trace.append({"step": step, "detail": detail})

    def tick(i, msg):
        if progress:
            progress(i / max(len(suppliers), 1), msg)

    # 3. Batch
    criteria = database.get_criteria(db_path)              # 4. reload latest ACTIVE criteria
    if not criteria:
        raise ValueError("No active evaluation criteria found. Activate at least one criterion.")
    run_id = database.new_run_id()
    database.create_run(run_id, db_path)
    log("Batch", f"Created {run_id} with {len(suppliers)} supplier(s); {len(criteria)} active criteria loaded.")

    try:
        evaluated = []
        for i, s in enumerate(suppliers):
            name = s["supplier_name"]
            tick(i, f"Reading {name}...")
            text, info = document_tool.extract_text(s["pdf_bytes"])           # Document Tool
            sup_warn = [f"{name}: {w}" for w in info["warnings"]]
            log("Extract", f"{name}: {info['pages']} page(s), {info['chars']} characters.")

            raw = None
            if text:
                tick(i, f"Asking the LLM to score {name}...")
                raw, llm_warn = evaluate_supplier(llm, criteria, name, text, index=i)   # Evaluation Agent
                sup_warn += llm_warn
            else:
                sup_warn.append(f"{name}: no text available - LLM skipped, all criteria scored 0.")

            clean, val_warn = validation_tool.validate_evaluation(raw, criteria, name)  # Validation Tool
            sup_warn += val_warn
            log("Validate", f"{name}: {len(val_warn)} validation warning(s).")
            evaluated.append({"supplier_name": name, "submission_date": s["submission_date"],
                              "experience_rating": s["experience_rating"], "evaluation": clean,
                              "warnings": sup_warn})
            warnings += sup_warn

        tick(len(suppliers), "Scoring, benchmarking and ranking...")
        ranked, tie_notes, rank_warn = ranking_tool.compute_and_rank(evaluated, criteria)  # Ranking Tool
        warnings += rank_warn
        log("Score", "Absolute weighted scores calculated for all suppliers.")
        log("Benchmark", "Best score per criterion found; gaps, relative % and PPI calculated.")
        log("Rank", "Tie-break order applied: PPI -> earlier date -> higher experience -> name A-Z.")

        result = {
            "rfp_run_id": run_id,
            "created_at": database.get_run_created_at(run_id, db_path),
            "llm": {"provider": llm.cfg.provider, "model": llm.cfg.model_name},
            "criteria": [{k: c[k] for k in ("criterion_id", "name", "description", "weight", "max_score")}
                         for c in criteria],
            "suppliers": ranked,
            "tie_break_explanation": tie_notes,
            "warnings": warnings,
            "trace": trace,
        }
        log("Persist", f"Results saved to SQLite under {run_id}.")
        database.save_run(result, db_path)                                   # 9. Persist
        return result
    except Exception as exc:
        database.mark_run_failed(run_id, str(exc), db_path)
        raise
