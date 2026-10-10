"""Evaluation Agent: builds a criteria-driven prompt and asks the LLM to score ONE supplier."""
import json

from llm_client import LLMError
from validation_tool import extract_json

SYSTEM_PROMPT = """You are a procurement evaluation analyst scoring ONE supplier's RFP response.
Rules:
- Use ONLY evidence present in the supplier document. If something is not stated, say so and score low.
- Return exactly one result for EVERY criterion listed, using its criterion_id.
- Each score must be a number between 0 and that criterion's max_score.
- 'evidence' must be a short direct excerpt or close paraphrase from the document.
- Do NOT compute totals, weights, rankings or comparisons with other suppliers.
- Output valid JSON ONLY - no markdown, no commentary."""


def build_user_prompt(criteria, supplier_name, text):
    crit = [{"criterion_id": c["criterion_id"], "name": c["name"], "description": c["description"],
             "max_score": c["max_score"]} for c in criteria]
    schema = {"supplier_name": supplier_name,
              "criteria": [{"criterion_id": 1, "score": 0, "max_score": 10, "justification": "...", "evidence": "..."}],
              "risks": ["..."], "overall_summary": "..."}
    return (f"Supplier: {supplier_name}\n\nEvaluation criteria (JSON):\n{json.dumps(crit, indent=2)}\n\n"
            f"Required output format:\n{json.dumps(schema, indent=2)}\n\n"
            f"--- SUPPLIER DOCUMENT START ---\n{text}\n--- SUPPLIER DOCUMENT END ---")


def evaluate_supplier(llm, criteria, supplier_name, text, index=0, max_attempts=2):
    """Returns (parsed_json_or_None, warnings). Retries once when the reply is not parseable JSON."""
    warnings, user = [], build_user_prompt(criteria, supplier_name, text)
    for attempt in range(1, max_attempts + 1):
        try:
            reply = llm.complete(SYSTEM_PROMPT, user, meta={
                "criteria": criteria, "text": text, "supplier_name": supplier_name,
                "attempt": attempt, "index": index})
        except LLMError as exc:
            warnings.append(f"{supplier_name}: LLM error on attempt {attempt}: {exc}")
            continue
        parsed = extract_json(reply)
        if isinstance(parsed, dict):
            return parsed, warnings
        warnings.append(f"{supplier_name}: attempt {attempt} did not return valid JSON.")
        user += "\n\nYour previous reply was not valid JSON. Reply with the JSON object only."
    return None, warnings
