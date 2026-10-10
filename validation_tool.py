"""Validation Tool: parse LLM output and normalise it to a safe, complete schema."""
import json
import math
import re


def extract_json(text):
    """Parse JSON from an LLM reply, tolerating code fences and surrounding prose."""
    if not isinstance(text, str) or not text.strip():
        return None
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _to_number(value):
    """Convert 8, '8', '8/10', '7.5 out of 10' to float; None when impossible."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(value) else None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(match.group()) if match else None


def _text(value, limit=1500):
    return value.strip()[:limit] if isinstance(value, str) else ""


def validate_evaluation(raw, criteria, supplier_name):
    """Return (clean_evaluation, warnings). One result per active criterion, always.

    Rules: DB max_score is authoritative; scores are clipped to [0, max];
    missing / non-numeric scores become 0 and are flagged; unknown ids are ignored.
    status per criterion: ok | clipped | missing | malformed
    """
    warnings = []
    items = []
    if isinstance(raw, dict) and isinstance(raw.get("criteria"), list):
        items = [i for i in raw["criteria"] if isinstance(i, dict)]
    else:
        warnings.append(f"{supplier_name}: LLM output has no valid 'criteria' list - all criteria set to 0.")

    by_id, by_name = {}, {}
    for item in items:
        cid = _to_number(item.get("criterion_id"))
        if cid is not None:
            if int(cid) in by_id:
                warnings.append(f"{supplier_name}: duplicate result for criterion {int(cid)} ignored.")
            else:
                by_id[int(cid)] = item
        if isinstance(item.get("name"), str):
            by_name.setdefault(item["name"].strip().lower(), item)

    known = {c["criterion_id"] for c in criteria}
    for cid in by_id:
        if cid not in known:
            warnings.append(f"{supplier_name}: result for unknown criterion {cid} ignored.")

    clean = []
    for c in criteria:
        cid, mx = c["criterion_id"], float(c["max_score"])
        item = by_id.get(cid) or by_name.get(c["name"].lower())
        row = {"criterion_id": cid, "name": c["name"], "max_score": mx,
               "justification": "", "evidence": "", "status": "ok"}
        if item is None:
            row.update(score=0.0, status="missing",
                       justification="No result returned by the LLM; scored 0.")
            warnings.append(f"{supplier_name}: criterion '{c['name']}' missing from LLM output - scored 0.")
        else:
            score = _to_number(item.get("score"))
            row["justification"] = _text(item.get("justification"))
            row["evidence"] = _text(item.get("evidence"))
            reported_max = _to_number(item.get("max_score"))
            if reported_max is not None and reported_max != mx:
                warnings.append(f"{supplier_name}: '{c['name']}' reported max_score {reported_max:g}; "
                                f"database value {mx:g} used.")
            if score is None:
                row.update(score=0.0, status="malformed")
                warnings.append(f"{supplier_name}: '{c['name']}' score {item.get('score')!r} is not numeric - scored 0.")
            else:
                clipped = min(max(score, 0.0), mx)
                if clipped != score:
                    row["status"] = "clipped"
                    warnings.append(f"{supplier_name}: '{c['name']}' score {score:g} outside 0-{mx:g}; clipped to {clipped:g}.")
                row["score"] = round(clipped, 2)
                if clipped > 0 and not row["evidence"]:
                    warnings.append(f"{supplier_name}: '{c['name']}' has a score but no supporting evidence.")
        clean.append(row)

    risks = raw.get("risks") if isinstance(raw, dict) else None
    risks = [_text(r, 300) for r in risks if isinstance(r, str)] if isinstance(risks, list) else []
    summary = _text(raw.get("overall_summary"), 1500) if isinstance(raw, dict) else ""
    return {"supplier_name": supplier_name, "criteria": clean, "risks": risks,
            "overall_summary": summary}, warnings
