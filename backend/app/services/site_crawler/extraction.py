import json
import logging
import re
from typing import Any, Type
from pydantic import BaseModel, create_model

from app.core.config import settings
from app.core.model_catalog import DEFAULT_CHAT_MODEL_ID
from app.schemas.chat import ChatMessage
from app.schemas.site_crawler import ExtractionSchema, FieldDefinition
from app.services.inference_service import (
    InferenceError,
    ModelNotAvailableError,
    inference_engine_manager,
)

logger = logging.getLogger(__name__)


def _clean_json_text(text: str) -> str:
    cleaned = text.strip()
    # Strip markdown code blocks
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

    # Find first '{' or '[' and last '}' or ']'
    start_brace = cleaned.find("{")
    start_bracket = cleaned.find("[")

    start_idx = -1
    end_char = ""
    if start_brace != -1 and (start_bracket == -1 or start_brace < start_bracket):
        start_idx = start_brace
        end_char = "}"
    elif start_bracket != -1:
        start_idx = start_bracket
        end_char = "]"

    if start_idx != -1:
        end_idx = cleaned.rfind(end_char)
        if end_idx != -1 and end_idx >= start_idx:
            cleaned = cleaned[start_idx : end_idx + 1]

    return cleaned


def _coerce_numbers(val: Any) -> Any:
    """Lenient coercion of strings like '$1,299' or '45%' to numbers."""
    if isinstance(val, (int, float)):
        return val
    if isinstance(val, str):
        cleaned = re.sub(r"[^\d.-]", "", val)
        if cleaned:
            try:
                if "." in cleaned:
                    return float(cleaned)
                return int(cleaned)
            except ValueError:
                pass
    return val


def build_pydantic_model(schema: ExtractionSchema) -> Type[BaseModel]:
    def _field_to_type(f: FieldDefinition) -> tuple[Any, Any]:
        t: Any = str
        if f.type == "number":
            t = float | int
        elif f.type == "boolean":
            t = bool
        elif f.type == "string_list":
            t = list[str]
        elif f.type == "object" and f.fields:
            sub_dict: dict[str, Any] = {}
            for sf in f.fields:
                st, sdef = _field_to_type(sf)
                sub_dict[sf.name] = (st, sdef)
            t = create_model(f"Nested_{f.name}", **sub_dict)

        if f.required:
            return (t, ...)
        return (t | None, None)

    field_defs: dict[str, Any] = {}
    for f in schema.fields:
        field_defs[f.name] = _field_to_type(f)

    record_model = create_model("ExtractedRecord", **field_defs)

    if schema.mode == "many":
        return create_model("ExtractedRecordsWrapper", records=(list[record_model], ...))
    return record_model


def build_system_prompt(schema: ExtractionSchema) -> str:
    field_descriptions = []
    for f in schema.fields:
        req_str = " (REQUIRED)" if f.required else " (optional)"
        desc = f": {f.description}" if f.description else ""
        field_descriptions.append(f"- `{f.name}` ({f.type}){req_str}{desc}")

    prompt = (
        "You are an expert data extraction agent. Your job is to extract structured information "
        "from the provided webpage markdown content exactly conforming to the requested schema.\n\n"
        "FIELDS TO EXTRACT:\n"
        + "\n".join(field_descriptions)
        + "\n\n"
    )

    if schema.mode == "many":
        prompt += (
            "EXTRACTION MODE: MANY RECORDS.\n"
            "Extract an array of records matching the fields above.\n"
            'Return a JSON object in the exact format: `{"records": [{...}, {...}]}`.\n'
        )
    else:
        prompt += (
            "EXTRACTION MODE: SINGLE RECORD.\n"
            "Extract a single record matching the fields above.\n"
            "Return a single JSON object with the requested field keys.\n"
        )

    prompt += (
        "\nRULES:\n"
        "1. Return ONLY a valid JSON object. Do not include introductory text, explanations, or code commentary.\n"
        "2. If an optional field is not found in the content, set its value to null.\n"
        "3. Strictly adhere to the requested data types (e.g. number for prices or counts, boolean for true/false).\n"
    )
    return prompt


def chunk_markdown(markdown: str, max_chunk_tokens: int = 8000) -> list[str]:
    # Rough estimate ~4 chars per token
    approx_chars = max_chunk_tokens * 4
    if len(markdown) <= approx_chars:
        return [markdown]

    # Split by headings
    sections = re.split(r"(?m)(?=^#{1,3}\s)", markdown)
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_len = 0

    for sec in sections:
        sec_len = len(sec)
        if current_len + sec_len > approx_chars and current_chunk:
            chunks.append("".join(current_chunk))
            current_chunk = [sec]
            current_len = sec_len
        else:
            current_chunk.append(sec)
            current_len += sec_len

    if current_chunk:
        chunks.append("".join(current_chunk))

    return chunks or [markdown]


class ExtractionResult:
    def __init__(
        self,
        status: str,
        records: list[dict[str, Any]],
        error: str | None = None,
        attempts: int = 1,
    ) -> None:
        self.status = status
        self.records = records
        self.error = error
        self.attempts = attempts


async def extract_from_markdown(
    markdown: str,
    url: str,
    title: str | None,
    schema: ExtractionSchema,
    model_id: str | None = None,
) -> ExtractionResult:
    cleaned_md = markdown.strip()
    if len(cleaned_md) < 50:
        return ExtractionResult(status="empty_content", records=[], attempts=0)

    active_model = model_id or DEFAULT_CHAT_MODEL_ID
    model_cls = build_pydantic_model(schema)
    system_prompt = build_system_prompt(schema)

    # Determine token budget
    try:
        engine_max = inference_engine_manager.get_current_max_tokens()
    except Exception:
        engine_max = 16384
    input_budget = int(engine_max * settings.site_crawler_input_token_ratio)
    chunks = chunk_markdown(cleaned_md, max_chunk_tokens=input_budget)

    extracted_records: list[dict[str, Any]] = []
    total_attempts = 0

    for chunk in chunks:
        user_content = (
            f"SOURCE URL: {url}\n"
            f"PAGE TITLE: {title or 'Unknown'}\n\n"
            f"--- WEBPAGE CONTENT ---\n"
            f"{chunk}\n"
            f"--- END WEBPAGE CONTENT ---\n\n"
            "Extract the requested JSON structure now:"
        )

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_content),
        ]

        chunk_success = False
        last_error = None
        max_attempts = 3  # 1 initial + up to 2 repair retries

        for attempt in range(1, max_attempts + 1):
            total_attempts += 1
            try:
                text, _, _, _ = await inference_engine_manager.generate(
                    messages=messages,
                    max_tokens=settings.site_crawler_max_output_tokens,
                    enable_thinking=False,
                    model_id=active_model,
                )

                cleaned_json = _clean_json_text(text)
                parsed_raw = json.loads(cleaned_json)

                # Pre-clean numbers if schema specifies number fields
                if isinstance(parsed_raw, dict):
                    if schema.mode == "many" and "records" in parsed_raw and isinstance(parsed_raw["records"], list):
                        for rec in parsed_raw["records"]:
                            if isinstance(rec, dict):
                                for f in schema.fields:
                                    if f.type == "number" and f.name in rec:
                                        rec[f.name] = _coerce_numbers(rec[f.name])
                    else:
                        for f in schema.fields:
                            if f.type == "number" and f.name in parsed_raw:
                                parsed_raw[f.name] = _coerce_numbers(parsed_raw[f.name])

                # Validate with Pydantic
                validated = model_cls.model_validate(parsed_raw)
                val_dict = validated.model_dump()

                if schema.mode == "many":
                    records_list = val_dict.get("records", [])
                    for r in records_list:
                        r["source_url"] = url
                    extracted_records.extend(records_list)
                else:
                    val_dict["source_url"] = url
                    extracted_records.append(val_dict)

                chunk_success = True
                break

            except (ModelNotAvailableError, InferenceError) as exc:
                logger.error("LLM generation error on %s: %s", url, exc)
                return ExtractionResult(status="extraction_failed", records=[], error=str(exc), attempts=total_attempts)
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Extraction validation failed for %s (attempt %d/%d): %s",
                    url,
                    attempt,
                    max_attempts,
                    exc,
                )
                if attempt < max_attempts:
                    # Append assistant message & repair instruction
                    messages.append(ChatMessage(role="assistant", content=text if 'text' in locals() else ""))
                    messages.append(
                        ChatMessage(
                            role="user",
                            content=(
                                f"The output failed validation with error: {last_error}\n"
                                "Please correct the output and return ONLY the valid JSON object conforming strictly to the schema."
                            ),
                        )
                    )

        if not chunk_success:
            logger.error("Failed to extract chunk from %s after %d attempts: %s", url, max_attempts, last_error)

    if not extracted_records:
        return ExtractionResult(
            status="extraction_failed",
            records=[],
            error=last_error or "No valid records extracted",
            attempts=total_attempts,
        )

    # For single mode, if multiple chunks were extracted, merge non-null fields
    if schema.mode == "single" and len(extracted_records) > 1:
        merged: dict[str, Any] = {"source_url": url}
        for rec in extracted_records:
            for k, v in rec.items():
                if k not in merged or merged[k] is None:
                    merged[k] = v
        extracted_records = [merged]

    # For many mode, deduplicate records by json hash
    if schema.mode == "many" and len(extracted_records) > 1:
        seen = set()
        deduped = []
        for r in extracted_records:
            # Hash without source_url
            r_copy = {k: v for k, v in r.items() if k != "source_url"}
            h = hashlib.sha1(json.dumps(r_copy, sort_keys=True).encode()).hexdigest()
            if h not in seen:
                seen.add(h)
                deduped.append(r)
        extracted_records = deduped

    return ExtractionResult(status="ok", records=extracted_records, attempts=total_attempts)
