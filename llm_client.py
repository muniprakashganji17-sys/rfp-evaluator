"""Thin LLM wrapper: Anthropic, OpenAI-compatible, or a deterministic offline 'mock'."""
import json
import re
from dataclasses import dataclass

DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-4o-mini", "mock": "mock-keyword-scorer"}


class LLMError(Exception):
    pass


@dataclass
class LLMConfig:
    provider: str = "mock"          # mock | anthropic | openai
    api_key: str = ""
    model: str = ""
    base_url: str = ""              # OpenAI-compatible endpoints (Groq, Gemini, ...)
    inject_faults: bool = False     # mock only: simulate a malformed LLM answer

    @property
    def model_name(self):
        return self.model or DEFAULT_MODELS[self.provider]


class LLMClient:
    def __init__(self, cfg: LLMConfig):
        self.cfg = cfg

    def complete(self, system: str, user: str, meta: dict | None = None) -> str:
        p = self.cfg.provider
        try:
            if p == "anthropic":
                return self._anthropic(system, user)
            if p == "openai":
                return self._openai(system, user)
            if p == "mock":
                return _mock_reply(meta or {}, self.cfg.inject_faults)
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"{p} call failed: {exc}") from exc
        raise LLMError(f"Unknown provider '{p}'")

    def _anthropic(self, system, user):
        if not self.cfg.api_key:
            raise LLMError("Anthropic API key missing.")
        import anthropic
        client = anthropic.Anthropic(api_key=self.cfg.api_key)
        msg = client.messages.create(model=self.cfg.model_name, max_tokens=4000, system=system,
                                     messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

    def _openai(self, system, user):
        if not self.cfg.api_key:
            raise LLMError("OpenAI-compatible API key missing.")
        from openai import OpenAI
        client = OpenAI(api_key=self.cfg.api_key, base_url=self.cfg.base_url or None)
        kwargs = dict(model=self.cfg.model_name, temperature=0,
                      messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        try:
            r = client.chat.completions.create(response_format={"type": "json_object"}, **kwargs)
        except Exception:  # some compatible endpoints reject response_format
            r = client.chat.completions.create(**kwargs)
        return r.choices[0].message.content or ""


# ---------------- offline mock (for demos / tests without an API key) ----------------
KEYWORDS = {
    "technical": ["architecture", "microservice", "api", "integration", "scalab", "load test",
                  "sso", "erp", "kubernetes", "high availability"],
    "implementation": ["milestone", "phase", "week", "sprint", "raci", "risk register",
                       "go-live", "uat", "staffing", "training"],
    "commercial": ["usd", "total cost", "fixed price", "assumption", "licen", "per user",
                   "payment", "discount", "tco", "contingency"],
    "security": ["iso 27001", "soc 2", "encrypt", "audit", "gdpr", "penetration", "mfa",
                 "rbac", "retention", "vulnerability"],
    "support": ["24x7", "sla", "reference", "similar", "clients", "customer success",
                "case study", "support desk", "escalation", "years"],
}


def _mock_reply(meta, inject_faults):
    text, criteria = meta.get("text", ""), meta.get("criteria", [])
    low = text.lower()
    sentences = re.split(r"(?<=[.!?])\s+|\n", text)
    out = []
    for c in criteria:
        key = next((k for k in KEYWORDS if k in c["name"].lower()), None)
        kws = KEYWORDS.get(key) or [w for w in re.findall(r"[a-z]{5,}", (c["name"] + " " + c["description"]).lower())]
        hits = [k for k in kws if k in low]
        score = round(c["max_score"] * (0.1 + 0.9 * len(hits) / max(len(kws), 1)), 1)
        evidence = next((s.strip()[:220] for s in sentences if any(h in s.lower() for h in hits)), "")
        out.append({"criterion_id": c["criterion_id"], "score": score if hits else 0,
                    "max_score": c["max_score"],
                    "justification": f"Mock scorer matched {len(hits)} of {len(kws)} indicators ({', '.join(hits[:5]) or 'none'}).",
                    "evidence": evidence})
    if inject_faults and meta.get("index") == 0 and meta.get("attempt") == 1 and len(out) >= 3:
        out[0]["score"] = out[0]["max_score"] + 4           # out of range
        out[1]["score"] = "n/a"                            # non-numeric
        out = out[:-1]                                     # missing criterion
        return "Here is my evaluation:\n```json\n" + json.dumps({"criteria": out}) + "\n```\nHope this helps!"
    return json.dumps({"supplier_name": meta.get("supplier_name"), "criteria": out,
                       "risks": ["Mock risk: verify claims with the supplier."],
                       "overall_summary": "Offline mock evaluation based on keyword evidence."})
