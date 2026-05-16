import json, re
from langchain_core.messages import HumanMessage, SystemMessage
from app.llm import get_llm

TAXONOMY = {
    "infinite_loop":     "Agent/tool calling itself in a cycle with no exit condition",
    "hallucination":     "Agent fabricated facts, citations, or data not in context",
    "tool_misuse":       "Wrong arguments, schema mismatch, or wrong tool chosen",
    "context_overflow":  "Input exceeded model context window limit",
    "empty_response":    "Agent returned empty or null output",
    "format_error":      "Response did not match required output schema",
    "reasoning_failure": "Chain-of-thought broke down, wrong conclusion",
    "latency_regression":"Response time degraded significantly from baseline",
    "tool_timeout":      "External tool/API call timed out, no fallback",
    "unknown":           "Could not map to a known failure type",
}

SYSTEM_PROMPT = f"""You are TraceGuard AI, an expert LLMOps engineer.
Classify this LangSmith execution trace.

Known taxonomy:
{json.dumps(TAXONOMY, indent=2)}

Return ONLY valid JSON:
{{
  "failure_type": "<key from taxonomy>",
  "failure_category": "<tool_usage|reasoning|memory|output_format|latency|auth|unknown>",
  "severity": "<low|medium|high|critical>",
  "title": "<short title max 12 words>",
  "description": "<1-2 sentences what went wrong>",
  "root_cause_summary": "<technical root cause 2-4 sentences>",
  "trace_evidence": ["<direct quote from trace showing the problem>"]
}}"""

def _trim(value, max_chars: int = 400) -> str:
    """Truncate any value to a safe string length for the LLM prompt."""
    s = json.dumps(value) if not isinstance(value, str) else value
    return s[:max_chars] + "…" if len(s) > max_chars else s


async def classify_trace_async(trace: dict) -> dict:
    llm = get_llm(temperature=0)
    # Keep the excerpt small — Groq free tier has a 12k TPM limit
    excerpt = {
        "run_id":     trace.get("id"),
        "name":       trace.get("name"),
        "inputs":     _trim(trace.get("inputs"), 300),
        "outputs":    _trim(trace.get("outputs"), 300),
        "error":      _trim(trace.get("error"), 600),
        "child_runs": [
            {"run_type": r.get("run_type"), "name": r.get("name"),
             "error": _trim(r.get("error"), 200)}
            for r in (trace.get("child_runs") or [])[:8]
        ],
        "latency_ms": trace.get("latency_ms"),
    }
    resp = await llm.ainvoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Classify this trace:\n\n{json.dumps(excerpt, indent=2)}")
    ])
    m = re.search(r"\{[\s\S]*\}", resp.content)
    if m:
        return json.loads(m.group())
    return {"failure_type": "unknown", "failure_category": "unknown",
            "severity": "medium", "title": "Classification failed",
            "description": "Classifier could not parse a structured response.",
            "root_cause_summary": resp.content[:400], "trace_evidence": []}