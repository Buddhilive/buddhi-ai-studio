from __future__ import annotations

import ast
import json
import logging
import re
import uuid

from app.schemas.chat import FunctionCall, ToolCall

logger = logging.getLogger(__name__)

# Matches Gemma and standard tool call blocks:
# <|tool_call>call:function_name{arg: val}<tool_call|>
# <tool_call>{"name": "...", "arguments": {...}}</tool_call>
TOOL_CALL_BLOCK_RE = re.compile(
    r"(?:<\|tool_call\|?>|<tool_call>)\s*([\s\S]*?)\s*(?:<\|?tool_call\|?>|</tool_call>)",
    re.DOTALL,
)

_GEMMA_CALL_RE = re.compile(r"^call:([a-zA-Z0-9_\-\.]+)\s*([\s\S]*)$", re.DOTALL)
_UNQUOTED_KEY_RE = re.compile(r'([{\s,])([a-zA-Z_][a-zA-Z0-9_]*)\s*:', re.DOTALL)


def normalize_tool_arguments(raw_args: str) -> str:
    """Normalizes raw tool arguments (strict JSON, relaxed JSON, Gemma 4 tokens, or Python dict) to a valid JSON string."""
    args_str = raw_args.strip()
    if not args_str:
        return "{}"

    # Replace Gemma 4 special quote tokens
    args_str = args_str.replace('<|"|>', '"').replace("<|'|>", "'")

    # Standardize wrapping braces
    if args_str.startswith("(") and args_str.endswith(")"):
        args_str = "{" + args_str[1:-1] + "}"
    elif not args_str.startswith("{"):
        args_str = "{" + args_str + "}"

    # 1. Direct JSON parse
    try:
        parsed = json.loads(args_str)
        if isinstance(parsed, dict):
            return json.dumps(parsed)
    except Exception:
        pass

    # 2. Relaxed JSON: quote unquoted dictionary keys
    relaxed = _UNQUOTED_KEY_RE.sub(r'\1"\2":', args_str)
    relaxed = re.sub(r"\bTrue\b", "true", relaxed)
    relaxed = re.sub(r"\bFalse\b", "false", relaxed)
    relaxed = re.sub(r"\bNone\b", "null", relaxed)

    try:
        parsed = json.loads(relaxed)
        if isinstance(parsed, dict):
            return json.dumps(parsed)
    except Exception:
        pass

    # 3. Handle Python dict syntax via ast.literal_eval
    try:
        evaluated = ast.literal_eval(args_str)
        if isinstance(evaluated, dict):
            return json.dumps(evaluated)
    except Exception:
        pass

    # 4. Fallback: single-to-double quote substitution on relaxed string
    try:
        sq_replaced = re.sub(r"(?<!\\)'", '"', relaxed)
        parsed = json.loads(sq_replaced)
        if isinstance(parsed, dict):
            return json.dumps(parsed)
    except Exception:
        pass

    return args_str


def _parse_single_tool_call_body(body: str) -> ToolCall | None:
    """Parses inner content of a <tool_call> block into a ToolCall, supporting Gemma and JSON formats."""
    body_clean = body.strip()
    if not body_clean:
        return None

    call_id = f"call_{uuid.uuid4().hex[:12]}"

    # Format 1: Gemma 4 format (call:func_name{...})
    gemma_match = _GEMMA_CALL_RE.match(body_clean)
    if gemma_match:
        func_name = gemma_match.group(1).strip()
        raw_args = gemma_match.group(2).strip()
        norm_args = normalize_tool_arguments(raw_args)
        return ToolCall(
            id=call_id,
            type="function",
            function=FunctionCall(name=func_name, arguments=norm_args),
        )

    # Format 2: DeepSeek / Standard JSON format ({"name": "...", "arguments": ...})
    try:
        data = json.loads(body_clean)
        if isinstance(data, dict):
            if "name" in data:
                func_name = str(data["name"])
                raw_args = data.get("arguments", {})
                norm_args = (
                    json.dumps(raw_args)
                    if isinstance(raw_args, (dict, list))
                    else str(raw_args)
                )
                return ToolCall(
                    id=call_id,
                    type="function",
                    function=FunctionCall(name=func_name, arguments=norm_args),
                )
            if "function" in data and isinstance(data["function"], dict):
                fn_data = data["function"]
                func_name = str(fn_data.get("name", ""))
                raw_args = fn_data.get("arguments", {})
                norm_args = (
                    json.dumps(raw_args)
                    if isinstance(raw_args, (dict, list))
                    else str(raw_args)
                )
                return ToolCall(
                    id=call_id,
                    type="function",
                    function=FunctionCall(name=func_name, arguments=norm_args),
                )
    except Exception:
        pass

    # Format 3: Relaxed JSON with unquoted keys in DeepSeek format
    try:
        norm_body = normalize_tool_arguments(body_clean)
        data = json.loads(norm_body)
        if isinstance(data, dict) and "name" in data:
            func_name = str(data["name"])
            raw_args = data.get("arguments", {})
            norm_args = (
                json.dumps(raw_args)
                if isinstance(raw_args, (dict, list))
                else str(raw_args)
            )
            return ToolCall(
                id=call_id,
                type="function",
                function=FunctionCall(name=func_name, arguments=norm_args),
            )
    except Exception:
        pass

    return None


def extract_tool_calls(text: str) -> tuple[str | None, list[ToolCall]]:
    """Extracts tool calls from response text supporting Gemma 4 and DeepSeek/JSON formats.

    Returns:
        (residual_content, tool_calls)
    """
    if not text:
        return None, []

    tool_calls: list[ToolCall] = []
    matched_spans: list[tuple[int, int]] = []

    for match in TOOL_CALL_BLOCK_RE.finditer(text):
        inner = match.group(1)
        parsed_call = _parse_single_tool_call_body(inner)
        if parsed_call:
            tool_calls.append(parsed_call)
            matched_spans.append((match.start(), match.end()))

    if not tool_calls:
        return text, []

    # Strip only valid matched tool call blocks from content
    residual_parts: list[str] = []
    last_idx = 0
    for start, end in matched_spans:
        residual_parts.append(text[last_idx:start])
        last_idx = end
    residual_parts.append(text[last_idx:])

    residual = "".join(residual_parts).strip()
    return residual if residual else None, tool_calls


_TOOL_START_MARKERS = ("<|tool_call", "<tool_call")
_TOOL_END_MARKERS = ("<tool_call|>", "<|tool_call|>", "</tool_call>")


class StreamingToolCallBuffer:
    """Buffers streaming token deltas to extract tool calls and prevent tag leakage."""

    def __init__(self) -> None:
        self.buffer = ""
        self.in_tool_call = False
        self.has_tool_calls = False

    def process_chunk(self, chunk: str) -> tuple[str | None, list[ToolCall]]:
        if not chunk:
            return None, []

        self.buffer += chunk
        tool_calls: list[ToolCall] = []
        text_to_yield_parts: list[str] = []

        if not self.in_tool_call:
            start_pos = -1
            for marker in _TOOL_START_MARKERS:
                pos = self.buffer.find(marker)
                if pos != -1 and (start_pos == -1 or pos < start_pos):
                    start_pos = pos

            if start_pos != -1:
                if start_pos > 0:
                    text_to_yield_parts.append(self.buffer[:start_pos])
                self.buffer = self.buffer[start_pos:]
                self.in_tool_call = True
            else:
                max_prefix_len = 0
                for marker in _TOOL_START_MARKERS:
                    for l in range(min(len(self.buffer), len(marker)), 0, -1):
                        if self.buffer.endswith(marker[:l]):
                            if l > max_prefix_len:
                                max_prefix_len = l

                if max_prefix_len > 0:
                    yieldable = self.buffer[:-max_prefix_len]
                    if yieldable:
                        text_to_yield_parts.append(yieldable)
                    self.buffer = self.buffer[-max_prefix_len:]
                else:
                    if self.buffer:
                        text_to_yield_parts.append(self.buffer)
                    self.buffer = ""

        if self.in_tool_call:
            end_pos = -1
            matched_end_len = 0
            for marker in _TOOL_END_MARKERS:
                pos = self.buffer.find(marker)
                if pos != -1 and (end_pos == -1 or pos < end_pos):
                    end_pos = pos
                    matched_end_len = len(marker)

            if end_pos != -1:
                call_segment = self.buffer[: end_pos + matched_end_len]
                self.buffer = self.buffer[end_pos + matched_end_len :]
                self.in_tool_call = False

                _, extracted = extract_tool_calls(call_segment)
                if extracted:
                    tool_calls.extend(extracted)
                    self.has_tool_calls = True
                else:
                    # Not a recognized tool call: yield call_segment as regular text
                    text_to_yield_parts.append(call_segment)

        combined_text = "".join(text_to_yield_parts) if text_to_yield_parts else None
        return combined_text, tool_calls

    def finalize(self) -> tuple[str | None, list[ToolCall]]:
        if not self.buffer:
            return None, []

        if self.in_tool_call:
            residual, extracted = extract_tool_calls(self.buffer)
            self.buffer = ""
            if extracted:
                self.has_tool_calls = True
                return residual, extracted
            return residual or self.buffer, []

        remaining = self.buffer
        self.buffer = ""
        return remaining if remaining else None, []
