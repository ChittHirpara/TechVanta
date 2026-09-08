"""
LLM-based structured field extraction from raw land-record text.

Public API
──────────
    result: ExtractionResult = await extract_fields(raw_text)
    d: dict                   = result.to_dict()

The function calls an OpenAI-compatible chat endpoint with a strict
prompt, then defensively parses the JSON response:

  Attempt 1 → parse raw response
  Attempt 2 → strip markdown fences, try again
  Attempt 3 → send the broken JSON back to the LLM and ask it to fix it
  Fallback  → return all-null ExtractionResult with low confidence
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Literal

log = logging.getLogger(__name__)

# ── Types ─────────────────────────────────────────────────────────────────────

Confidence = Literal["high", "medium", "low"]

#: All 12 domain fields in declaration order
FIELD_NAMES: tuple[str, ...] = (
    "owner_name",
    "survey_number",
    "khasra_number",
    "khata_number",
    "plot_area",
    "village",
    "tehsil",
    "district",
    "land_classification",
    "ownership_details",
    "mutation_record",
    "registration_info",
)


@dataclass
class FieldExtraction:
    """Value + extraction confidence for a single field."""
    value: str | None
    confidence: Confidence

    def to_dict(self) -> dict:
        return {"value": self.value, "confidence": self.confidence}


@dataclass
class ExtractionResult:
    """
    Structured extraction result for one land-record document.

    ``fields`` maps each of the 12 field names to a FieldExtraction.
    ``raw_llm_response`` preserves the model's original text for auditing.
    """
    fields: dict[str, FieldExtraction]
    raw_llm_response: str
    model: str
    attempt_count: int = 1         # how many parse attempts were needed
    parse_error: str | None = None # set if we fell back to the null result

    def to_dict(self) -> dict:
        return {
            "fields": {k: v.to_dict() for k, v in self.fields.items()},
            "meta": {
                "model": self.model,
                "attempt_count": self.attempt_count,
                "parse_error": self.parse_error,
            },
        }

    def flat_values(self) -> dict[str, str | None]:
        """Convenience: {field_name: value} without confidence."""
        return {k: v.value for k, v in self.fields.items()}


# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a land-record data extraction engine for Indian government documents.
Your only job is to parse the provided raw text and return a single, valid JSON object.

STRICT RULES — follow every rule or the output is invalid:
1. Respond with ONLY the JSON object. No markdown fences, no prose, no explanation.
2. The JSON must contain exactly two top-level keys: "fields" and "extraction_confidence".
3. "fields" must contain exactly these 12 keys (use null if a field is not present):
   owner_name, survey_number, khasra_number, khata_number, plot_area,
   village, tehsil, district, land_classification, ownership_details,
   mutation_record, registration_info
4. "extraction_confidence" must contain the same 12 keys, each mapped to one of:
   "high"   → value appears verbatim / explicitly in the text
   "medium" → value was inferred or normalised from context
   "low"    → value is uncertain, partially matched, or guessed
5. All values must be strings or null. No nested objects or arrays.
6. Do not add any keys not listed above.
7. Do not hallucinate values. If a field is genuinely absent, use null with confidence "low".

Example output format (truncated):
{
  "fields": {
    "owner_name": "Ram Kumar Singh",
    "survey_number": "123/4",
    "khasra_number": null,
    ...
  },
  "extraction_confidence": {
    "owner_name": "high",
    "survey_number": "high",
    "khasra_number": "low",
    ...
  }
}
""".strip()

_USER_TEMPLATE = """\
Extract structured fields from the following land record text.
Return ONLY the JSON as specified. No other text.

--- BEGIN LAND RECORD TEXT ---
{raw_text}
--- END LAND RECORD TEXT ---
""".strip()

_REPAIR_SYSTEM_PROMPT = """\
You are a JSON repair assistant. The text below is a malformed JSON object.
Return ONLY the corrected, valid JSON. No prose, no markdown, no explanation.
""".strip()

_REPAIR_USER_TEMPLATE = """\
Fix the following malformed JSON and return ONLY the corrected version:

{broken_json}
""".strip()


# ── JSON parsing helpers ──────────────────────────────────────────────────────

def _strip_fences(text: str) -> str:
    """Remove ```json … ``` or ``` … ``` markdown code fences."""
    # Match opening fence with optional language tag
    text = re.sub(r"^```(?:json)?\s*\n?", "", text.strip(), flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text.strip())
    return text.strip()


def _extract_json_block(text: str) -> str:
    """
    Last-resort: find the first ``{…}`` block in the text using brace counting.
    Handles cases where the LLM prepends/appends prose.
    """
    start = text.find("{")
    if start == -1:
        return text  # let downstream raise the error
    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]  # truncated – let downstream try


def _parse_json(raw: str) -> dict:
    """Try progressively looser parsing strategies."""
    candidates = [
        raw,                          # 1. as-is
        _strip_fences(raw),           # 2. strip markdown fences
        _extract_json_block(raw),     # 3. extract first {…} block
        _extract_json_block(_strip_fences(raw)),  # 4. both
    ]
    last_err: Exception | None = None
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_err = exc
    raise last_err  # type: ignore[misc]


def _build_extraction_result(
    parsed: dict,
    raw_response: str,
    model: str,
    attempt_count: int,
) -> ExtractionResult:
    """
    Map the parsed LLM dict onto ExtractionResult, tolerating missing /
    extra keys gracefully.
    """
    raw_fields: dict[str, Any] = parsed.get("fields", {})
    raw_conf: dict[str, Any] = parsed.get("extraction_confidence", {})

    fields: dict[str, FieldExtraction] = {}
    for name in FIELD_NAMES:
        value = raw_fields.get(name)
        if value is not None:
            value = str(value).strip() or None  # normalise empty strings → None

        raw_c = str(raw_conf.get(name, "low")).lower()
        confidence: Confidence = raw_c if raw_c in ("high", "medium", "low") else "low"  # type: ignore[assignment]

        # Downgrade confidence to low when the value itself is null
        if value is None:
            confidence = "low"

        fields[name] = FieldExtraction(value=value, confidence=confidence)

    return ExtractionResult(
        fields=fields,
        raw_llm_response=raw_response,
        model=model,
        attempt_count=attempt_count,
    )


def _extract_fields_heuristic(
    raw_text: str,
    raw_response: str = "",
    model: str = "heuristic-regex",
    attempt_count: int = 1,
    error: str | None = None,
) -> ExtractionResult:
    """Fallback rule-based heuristic extraction from OCR text when LLM is offline or unconfigured."""
    patterns = {
        "district": r"(?:District|Zila|ज़िला|जिला)\s*[:\-]?\s*([A-Za-z]+)",
        "tehsil": r"(?:Tehsil|तहसील)\s*[:\-]?\s*([A-Za-z]+)",
        "village": r"(?:Village|Gram|Mauza|गाँव|ग्राम|मौजा)\s*[:\-]?\s*([A-Za-z\s]+?)(?=\s*(?:Owner|Kashtkar|Khatedar|Tehsil|District|Zila|Halqa|Survey|Khas|Khata|Plot|Land|$|\n))",
        "owner_name": r"(?:Owner(?:\s*Name)?|Kashtkar(?:\s*Name)?|Pattedar|Khatedar|नाम|खातेदार|काश्तकार)\s*[:\-]?\s*([A-Za-z\s\.\/\(\)\&]+?)(?=\s*(?:Survey|Khas|Khata|Plot|Rakba|Land|Village|Gram|Tehsil|District|Zila|Mutation|Namantaran|Pegistration|Registration|Registry|$|\n))",
        "survey_number": r"(?:Survey\s*(?:Number|No\.?)?|सर्वे)\s*[:\-]?\s*([A-Za-z0-9\-\/]+)",
        "khasra_number": r"(?:Khas[rma]+\s*(?:Number|No\.?)?|खसरा)\s*[:\-]?\s*([0-9A-Za-z\/\s]+?)(?=\s*(?:Khata|Plot|Rakba|Land|Survey|Owner|Kashtkar|$|\(|\n))",
        "khata_number": r"(?:Khata\s*(?:Number|No\.?)?|खाता)\s*[:\-]?\s*([0-9A-Za-z\[\]]+)",
        "plot_area": r"(?:Plot\s*[KA]?[rR]ea|Land\s*Area|Area|Rakba|रकबा|क्षेत्रफल)\s*[:\-]?\s*([^\n\r]+?)(?=\s*(?:Land\s*Class|Bhoomi|Class|Village|Gram|Tehsil|District|Zila|Mutation|Namantaran|Registration|Pegistration|Registry|$|\n))",
        "land_classification": r"(?:Land\s*Class[a-z]*|Bhoomi\s*Varg|वर्ग|वर्गीकरण|भूमि\s*का\s*वर्गीकरण)\s*[:\-]?\s*([^\n\r]+?)(?=\s*(?:Pegistration|Registration|Registry|Mutation|Namantaran|Ownership|Issued|$|\n))",
        "registration_info": r"(?:[PR]egistration\s*Inf[oa]|Registry(?:\s*Details)?|पंजीकरण)\s*[:\-]?\s*([^\n\r]+?)(?=\s*(?:Mutation|Namantaran|Ownership|Issued|$|\n))",
        "mutation_record": r"(?:Mutation(?:\s*Record)?|Namantaran|नामांतरण)\s*[:\-]?\s*([^\n\r]+?)(?=\s*(?:[PR]egistration|Registry|Ownership|Issued|$|\n))",
        "ownership_details": r"(?:Ownership(?:\s*Details)?|स्वामित्व)\s*[:\-]?\s*([^\n\r]+?)(?=\s*(?:Issued|Date|$|\n))",
    }
    fields: dict[str, FieldExtraction] = {}
    for name in FIELD_NAMES:
        pat = patterns.get(name)
        val: str | None = None
        conf: Confidence = "low"
        if pat:
            m = re.search(pat, raw_text, re.IGNORECASE)
            if m:
                extracted_str = m.group(1).strip()
                if extracted_str and extracted_str.lower() not in ("none", "null", "n/a"):
                    val = extracted_str
                    conf = "high" if len(val) > 2 else "medium"
        fields[name] = FieldExtraction(value=val, confidence=conf)

    found_any = any(f.value is not None for f in fields.values())
    return ExtractionResult(
        fields=fields if found_any else {n: FieldExtraction(value=None, confidence="low") for n in FIELD_NAMES},
        raw_llm_response=raw_response or f"[Heuristic fallback active: {error}]",
        model=f"{model}+heuristic" if found_any else model,
        attempt_count=attempt_count,
        parse_error=error if not found_any else None,
    )


def _null_result(
    raw_response: str,
    model: str,
    attempt_count: int,
    error: str,
) -> ExtractionResult:
    """Fallback when all repair attempts are exhausted."""
    return ExtractionResult(
        fields={
            name: FieldExtraction(value=None, confidence="low")
            for name in FIELD_NAMES
        },
        raw_llm_response=raw_response,
        model=model,
        attempt_count=attempt_count,
        parse_error=error,
    )


# ── OpenAI client factory ─────────────────────────────────────────────────────

def _get_client():
    """Build an AsyncOpenAI client from config, supporting any compatible endpoint."""
    from openai import AsyncOpenAI
    from app.core.config import get_settings

    cfg = get_settings()
    kwargs: dict[str, Any] = {"api_key": cfg.llm_api_key or "sk-no-key"}
    if cfg.llm_base_url:
        kwargs["base_url"] = cfg.llm_base_url
    return AsyncOpenAI(**kwargs)


# ── Main public function ──────────────────────────────────────────────────────

async def extract_fields(raw_text: str) -> ExtractionResult:
    """
    Extract structured land-record fields from *raw_text* using an LLM.

    Strategy
    ────────
    1. Call the LLM with a strict system prompt.
    2. Try to parse the response as JSON (with fence-stripping + brace-finding).
    3. If parsing fails, ask the LLM to repair the broken JSON (up to
       ``LLM_MAX_RETRIES`` attempts total across both phases).
    4. If all attempts fail, fall back to heuristic regex extraction so OCR
       text is never lost, and only return null result if regex also fails.

    Args:
        raw_text: The raw OCR-extracted text from a land record document.

    Returns:
        ExtractionResult with per-field values and confidences.
    """
    from app.core.config import get_settings

    cfg = get_settings()
    client = _get_client()
    model = cfg.llm_model
    max_retries = max(1, cfg.llm_max_retries)

    user_message = _USER_TEMPLATE.format(raw_text=raw_text.strip())

    raw_response = ""
    attempt = 0

    # ── Phase 1: initial extraction call ─────────────────────────────────────
    attempt += 1
    log.info("[extraction] Phase 1 – calling %s (attempt %d)", model, attempt)
    try:
        completion = await client.chat.completions.create(
            model=model,
            temperature=cfg.llm_temperature,
            max_tokens=cfg.llm_max_tokens,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )
        raw_response = completion.choices[0].message.content or ""
        log.debug("[extraction] raw response:\n%s", raw_response)
    except Exception as exc:
        log.error("[extraction] LLM call failed: %s", exc)
        return _extract_fields_heuristic(raw_text, "", model, attempt, str(exc))

    # ── Phase 2: parse with progressive fallbacks ─────────────────────────────
    try:
        parsed = _parse_json(raw_response)
        return _build_extraction_result(parsed, raw_response, model, attempt)
    except json.JSONDecodeError as first_err:
        log.warning("[extraction] JSON parse failed on attempt %d: %s", attempt, first_err)

    # ── Phase 3: repair loop ──────────────────────────────────────────────────
    broken = raw_response
    while attempt < max_retries:
        attempt += 1
        log.info("[extraction] Repair attempt %d / %d", attempt, max_retries)
        try:
            repair_completion = await client.chat.completions.create(
                model=model,
                temperature=0.0,      # always deterministic for repair
                max_tokens=cfg.llm_max_tokens,
                messages=[
                    {"role": "system", "content": _REPAIR_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": _REPAIR_USER_TEMPLATE.format(broken_json=broken),
                    },
                ],
            )
            repaired = repair_completion.choices[0].message.content or ""
            log.debug("[extraction] repaired response:\n%s", repaired)
            parsed = _parse_json(repaired)
            raw_response = repaired       # store the successful repaired version
            return _build_extraction_result(parsed, raw_response, model, attempt)
        except json.JSONDecodeError as repair_err:
            log.warning(
                "[extraction] Repair attempt %d still malformed: %s", attempt, repair_err
            )
            broken = repaired  # try to repair the repair next round
        except Exception as exc:
            log.error("[extraction] Repair LLM call failed: %s", exc)
            return _extract_fields_heuristic(raw_text, raw_response, model, attempt, str(exc))

    # ── Phase 4: give up LLM, fall back to heuristic regex ────────────────────
    msg = (
        f"JSON parsing failed after {attempt} attempt(s). "
        "Raw LLM response preserved in raw_llm_response."
    )
    log.error("[extraction] %s", msg)
    return _extract_fields_heuristic(raw_text, raw_response, model, attempt, msg)
