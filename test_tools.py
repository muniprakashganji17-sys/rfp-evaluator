import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ranking_tool import compute_and_rank, relative_pct  # noqa: E402
from validation_tool import extract_json, validate_evaluation  # noqa: E402

CRITERIA = [
    {"criterion_id": 1, "name": "Tech", "description": "", "weight": 60, "max_score": 10},
    {"criterion_id": 2, "name": "Price", "description": "", "weight": 40, "max_score": 10},
]


def sup(name, d, exp, s1, s2):
    ev = {"criteria": [
        {"criterion_id": 1, "name": "Tech", "score": s1, "max_score": 10, "justification": "", "evidence": ""},
        {"criterion_id": 2, "name": "Price", "score": s2, "max_score": 10, "justification": "", "evidence": ""}],
        "risks": [], "overall_summary": ""}
    return {"supplier_name": name, "submission_date": d, "experience_rating": exp, "evaluation": ev}


def test_extract_json_handles_fences_and_prose():
    assert extract_json('Sure!\n```json\n{"a": 1}\n```\nDone') == {"a": 1}
    assert extract_json("not json") is None


def test_validation_clips_fills_and_flags():
    raw = {"criteria": [{"criterion_id": 1, "score": 14, "evidence": "x"}]}
    clean, warns = validate_evaluation(raw, CRITERIA, "S")
    assert [r["score"] for r in clean["criteria"]] == [10.0, 0.0]
    assert [r["status"] for r in clean["criteria"]] == ["clipped", "missing"]
    assert len(warns) == 2


def test_validation_non_numeric_and_string_scores():
    raw = {"criteria": [{"criterion_id": 1, "score": "8/10", "evidence": "x"},
                        {"criterion_id": 2, "score": "n/a"}]}
    clean, _ = validate_evaluation(raw, CRITERIA, "S")
    assert clean["criteria"][0]["score"] == 8.0
    assert clean["criteria"][1]["status"] == "malformed"


def test_validation_total_garbage():
    clean, warns = validate_evaluation(None, CRITERIA, "S")
    assert all(r["score"] == 0 for r in clean["criteria"]) and warns


def test_formulas():
    res, _, _ = compute_and_rank([sup("A", date(2026, 1, 1), 3, 8, 5), sup("B", date(2026, 1, 1), 3, 4, 10)], CRITERIA)
    a = next(r for r in res if r["supplier_name"] == "A")
    assert a["absolute_score"] == round(8 / 10 * 60 + 5 / 10 * 40, 2)       # 68.0
    tech = a["criteria_results"][0]
    assert tech["benchmark"] == 8 and tech["gap"] == 0 and tech["relative_pct"] == 100
    price = a["criteria_results"][1]
    assert price["gap"] == -5 and price["relative_pct"] == 50
    assert a["ppi"] == round(100 * 0.6 + 50 * 0.4, 4)                       # 80.0


def test_zero_benchmark_is_safe():
    assert relative_pct(0, 0) == 100.0


def test_tie_break_order():
    same = (8, 8)
    res, notes, _ = compute_and_rank([
        sup("Zeta", date(2026, 2, 1), 4, *same), sup("Alpha", date(2026, 2, 1), 4, *same),
        sup("Early", date(2026, 1, 1), 1, *same), sup("Exp", date(2026, 2, 1), 5, *same)], CRITERIA)
    assert [r["supplier_name"] for r in res] == ["Early", "Exp", "Alpha", "Zeta"]
    assert [r["final_rank"] for r in res] == [1, 2, 3, 4]
    assert "earlier submission date" in notes[0] and "experience" in notes[1] and "name" in notes[2]


def test_deterministic():
    inp = lambda: [sup("A", date(2026, 1, 2), 3, 7, 6), sup("B", date(2026, 1, 1), 4, 6, 7)]
    assert compute_and_rank(inp(), CRITERIA)[0] == compute_and_rank(inp(), CRITERIA)[0]


def test_weight_normalisation_warning():
    crit = [dict(c, weight=c["weight"] / 2) for c in CRITERIA]
    _, _, warns = compute_and_rank([sup("A", date(2026, 1, 1), 3, 8, 5)], crit)
    assert any("normalised" in w for w in warns)
