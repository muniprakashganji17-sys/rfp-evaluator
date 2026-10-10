"""Ranking Tool: ALL arithmetic, benchmarking, tie-breaks and ranking. Pure Python, no LLM."""
from datetime import date


def _norm_weights(criteria):
    total = sum(float(c["weight"]) for c in criteria)
    if total <= 0:
        raise ValueError("Active criteria weights must sum to more than 0.")
    return {c["criterion_id"]: float(c["weight"]) / total * 100.0 for c in criteria}, total


def relative_pct(score, benchmark):
    """(score / benchmark) x 100. Safe handling: if the benchmark is 0 nobody scored on the
    criterion, so every supplier is level with the best -> 100 (avoids division by zero)."""
    if benchmark <= 0:
        return 100.0
    return score / benchmark * 100.0


def compute_and_rank(suppliers, criteria):
    """suppliers: [{supplier_name, submission_date(date), experience_rating, evaluation}]
    Returns (ranked_results, tie_break_explanations, warnings)."""
    warnings = []
    weights, raw_total = _norm_weights(criteria)
    if abs(raw_total - 100.0) > 1e-6:
        warnings.append(f"Active weights total {raw_total:g}%, not 100%. Weights were normalised to 100% for scoring.")

    # Step: criterion benchmark = best score observed across suppliers
    benchmark = {}
    for c in criteria:
        cid = c["criterion_id"]
        benchmark[cid] = max(
            next(r["score"] for r in s["evaluation"]["criteria"] if r["criterion_id"] == cid)
            for s in suppliers)

    results = []
    for s in suppliers:
        rows, absolute, ppi = [], 0.0, 0.0
        for r in s["evaluation"]["criteria"]:
            cid = r["criterion_id"]
            w = weights[cid]
            contribution = r["score"] / r["max_score"] * w
            rel = relative_pct(r["score"], benchmark[cid])
            absolute += contribution
            ppi += rel * w / 100.0
            rows.append({**r, "weight": round(w, 4), "benchmark": benchmark[cid],
                         "gap": round(r["score"] - benchmark[cid], 4),
                         "relative_pct": round(rel, 2),
                         "weighted_contribution": round(contribution, 4)})
        results.append({
            "supplier_name": s["supplier_name"],
            "submission_date": s["submission_date"].isoformat(),
            "experience_rating": float(s["experience_rating"]),
            "absolute_score": round(absolute, 2),
            "ppi": round(ppi, 4),
            "criteria_results": rows,
            "risks": s["evaluation"]["risks"],
            "overall_summary": s["evaluation"]["overall_summary"],
            "warnings": s.get("warnings", []),
        })

    # Mandatory tie-break: PPI desc -> earlier date -> higher experience -> name asc
    results.sort(key=lambda r: (-r["ppi"], date.fromisoformat(r["submission_date"]),
                                -r["experience_rating"], r["supplier_name"].casefold(), r["supplier_name"]))
    for i, r in enumerate(results, 1):
        r["final_rank"] = i
    return results, explain_order(results), warnings


def explain_order(ranked):
    """Human-readable reason for each adjacent pair, naming the tie-break rule that decided it."""
    notes = []
    for a, b in zip(ranked, ranked[1:]):
        pair = f"#{a['final_rank']} {a['supplier_name']} vs #{b['final_rank']} {b['supplier_name']}: "
        if a["ppi"] != b["ppi"]:
            notes.append(pair + f"decided by PPI ({a['ppi']:.4f} > {b['ppi']:.4f}).")
        elif a["submission_date"] != b["submission_date"]:
            notes.append(pair + f"PPI tied at {a['ppi']:.4f}; decided by earlier submission date "
                                f"({a['submission_date']} < {b['submission_date']}).")
        elif a["experience_rating"] != b["experience_rating"]:
            notes.append(pair + f"PPI and date tied; decided by higher experience rating "
                                f"({a['experience_rating']:g} > {b['experience_rating']:g}).")
        else:
            notes.append(pair + "PPI, date and experience tied; decided by supplier name (A-Z).")
    if not notes:
        notes.append("Only one supplier - no comparison needed.")
    return notes
