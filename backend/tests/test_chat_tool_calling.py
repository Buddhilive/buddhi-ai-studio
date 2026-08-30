import json
import pytest

from app.core.tool_parser import extract_tool_calls, normalize_tool_arguments
from app.schemas.chat import (
    ChatCompletionRequest,
    ChatMessage,
    FunctionDefinition,
    ToolCall,
    ToolDefinition,
)


def test_normalize_tool_arguments_strict_json():
    raw = '{"queries": [["current president of Sri Lanka"]]}'
    normalized = normalize_tool_arguments(raw)
    assert json.loads(normalized) == {"queries": [["current president of Sri Lanka"]]}


def test_normalize_tool_arguments_unquoted_keys():
    raw = '{queries:[["current president of Sri Lanka"]]}'
    normalized = normalize_tool_arguments(raw)
    assert json.loads(normalized) == {"queries": [["current president of Sri Lanka"]]}


def test_normalize_tool_arguments_nested_and_python_types():
    raw = '{filter: {category: "news", active: True, limit: None}, query: "election"}'
    normalized = normalize_tool_arguments(raw)
    parsed = json.loads(normalized)
    assert parsed["query"] == "election"
    assert parsed["filter"]["category"] == "news"
    assert parsed["filter"]["active"] is True
    assert parsed["filter"]["limit"] is None


def test_normalize_tool_arguments_single_quotes():
    raw = "{'query': 'Sri Lanka president', 'count': 5}"
    normalized = normalize_tool_arguments(raw)
    parsed = json.loads(normalized)
    assert parsed == {"query": "Sri Lanka president", "count": 5}


def test_extract_tool_calls_user_example():
    text = '<|tool_call>call:web_search{queries:[["current president of Sri Lanka"]]}<tool_call|>'
    residual, tool_calls = extract_tool_calls(text)

    assert residual is None
    assert len(tool_calls) == 1
    assert tool_calls[0].function.name == "web_search"
    assert json.loads(tool_calls[0].function.arguments) == {
        "queries": [["current president of Sri Lanka"]]
    }
    assert tool_calls[0].id.startswith("call_")
    assert tool_calls[0].type == "function"


def test_extract_multiple_tool_calls():
    text = (
        '<|tool_call>call:get_weather{city: "Colombo"}<tool_call|>\n'
        '<|tool_call>call:get_currency{code: "LKR"}<tool_call|>'
    )
    residual, tool_calls = extract_tool_calls(text)

    assert residual is None
    assert len(tool_calls) == 2
    assert tool_calls[0].function.name == "get_weather"
    assert json.loads(tool_calls[0].function.arguments) == {"city": "Colombo"}
    assert tool_calls[1].function.name == "get_currency"
    assert json.loads(tool_calls[1].function.arguments) == {"code": "LKR"}


def test_extract_tool_calls_with_residual_content():
    text = (
        "I will search the web for that information.\n"
        '<|tool_call>call:web_search{q: "Sri Lanka"}<tool_call|>'
    )
    residual, tool_calls = extract_tool_calls(text)

    assert residual == "I will search the web for that information."
    assert len(tool_calls) == 1
    assert tool_calls[0].function.name == "web_search"


def test_extract_tool_calls_none_present():
    text = "Hello! How can I assist you today?"
    residual, tool_calls = extract_tool_calls(text)

    assert residual == text
    assert tool_calls == []


def test_chat_schema_with_tools_and_roles():
    req_data = {
        "model": "gemma-4-9b-it",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the weather?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {"name": "get_weather", "arguments": '{"city": "Paris"}'},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_123", "content": '{"temp": 22}'},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather for a city",
                    "parameters": {
                        "type": "object",
                        "properties": {"city": {"type": "string"}},
                    },
                },
            }
        ],
        "tool_choice": "auto",
    }
    req = ChatCompletionRequest.model_validate(req_data)
    assert req.tools is not None
    assert req.tools[0].function.name == "get_weather"
    assert req.messages[3].role == "tool"
    assert req.messages[3].tool_call_id == "call_123"
    assert req.messages[2].tool_calls[0].function.name == "get_weather"


def test_blocking_chat_completion_with_gemma_tool_call():
    from unittest.mock import AsyncMock, patch
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    gemma_output = '<|tool_call>call:web_search{queries:[["current president of Sri Lanka"]]}<tool_call|>'

    with patch("app.routers.chat._validate_model"), \
         patch("app.routers.chat.inference_engine_manager.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = (gemma_output, "", 15, 25)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemma-4-9b-it",
                "messages": [{"role": "user", "content": "Who is the president of Sri Lanka?"}],
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["finish_reason"] == "tool_calls"
        assert data["choices"][0]["message"]["content"] is None
        tool_calls = data["choices"][0]["message"]["tool_calls"]
        assert len(tool_calls) == 1
        assert tool_calls[0]["function"]["name"] == "web_search"
        assert json.loads(tool_calls[0]["function"]["arguments"]) == {
            "queries": [["current president of Sri Lanka"]]
        }
        assert tool_calls[0]["id"].startswith("call_")


def test_blocking_chat_completion_with_preamble_and_tool_call():
    from unittest.mock import AsyncMock, patch
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    gemma_output = (
        "Searching for the latest information...\n"
        '<|tool_call>call:web_search{queries:[["current president of Sri Lanka"]]}<tool_call|>'
    )

    with patch("app.routers.chat._validate_model"), \
         patch("app.routers.chat.inference_engine_manager.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = (gemma_output, "", 15, 25)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemma-4-9b-it",
                "messages": [{"role": "user", "content": "Who is the president of Sri Lanka?"}],
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["finish_reason"] == "tool_calls"
        assert data["choices"][0]["message"]["content"] == "Searching for the latest information..."
        assert len(data["choices"][0]["message"]["tool_calls"]) == 1


def test_blocking_chat_completion_without_tool_call():
    from unittest.mock import AsyncMock, patch
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    normal_output = "The capital of France is Paris."

    with patch("app.routers.chat._validate_model"), \
         patch("app.routers.chat.inference_engine_manager.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = (normal_output, "", 10, 10)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemma-4-9b-it",
                "messages": [{"role": "user", "content": "What is the capital of France?"}],
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["finish_reason"] == "stop"
        assert data["choices"][0]["message"]["content"] == "The capital of France is Paris."
        assert data["choices"][0]["message"].get("tool_calls") is None


def test_stream_chat_completion_with_gemma_tool_call():
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from app.main import app
    from app.schemas.chat import ChatCompletionChunkDelta

    client = TestClient(app)

    async def mock_stream(*args, **kwargs):
        yield ChatCompletionChunkDelta(content="Looking up president...\n")
        yield ChatCompletionChunkDelta(content='<|tool_call>call:web_search{queries:[["current president of Sri Lanka"]]}')
        yield ChatCompletionChunkDelta(content="<tool_call|>")

    with patch("app.routers.chat._validate_model"), \
         patch("app.routers.chat.inference_engine_manager.generate_stream", side_effect=mock_stream), \
         patch("app.routers.chat.inference_engine_manager.count_tokens", return_value=10):

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemma-4-9b-it",
                "messages": [{"role": "user", "content": "Who is the president of Sri Lanka?"}],
                "stream": True,
            },
        )

        assert response.status_code == 200
        chunks = []
        for line in response.text.strip().split("\n"):
            if line.startswith("data: ") and not line.endswith("[DONE]"):
                chunks.append(json.loads(line[len("data: "):]))

        # Verify no raw <|tool_call> in content
        for chunk in chunks:
            for choice in chunk.get("choices", []):
                delta = choice.get("delta", {})
                if delta.get("content"):
                    assert "<|tool_call" not in delta["content"]
                    assert "<tool_call|>" not in delta["content"]

        # Verify tool call delta was yielded
        tool_call_chunks = [
            c for c in chunks
            if c.get("choices") and c["choices"][0].get("delta", {}).get("tool_calls")
        ]
        assert len(tool_call_chunks) == 1
        tc_delta = tool_call_chunks[0]["choices"][0]["delta"]["tool_calls"][0]
        assert tc_delta["function"]["name"] == "web_search"
        assert json.loads(tc_delta["function"]["arguments"]) == {
            "queries": [["current president of Sri Lanka"]]
        }

        # Verify final chunk finish_reason is tool_calls
        final_chunk = [
            c for c in chunks
            if c.get("choices") and c["choices"][0].get("finish_reason") is not None
        ][-1]
        assert final_chunk["choices"][0]["finish_reason"] == "tool_calls"


def test_stream_chat_completion_without_tool_call():
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from app.main import app
    from app.schemas.chat import ChatCompletionChunkDelta

    client = TestClient(app)

    async def mock_stream(*args, **kwargs):
        yield ChatCompletionChunkDelta(content="Hello ")
        yield ChatCompletionChunkDelta(content="world!")

    with patch("app.routers.chat._validate_model"), \
         patch("app.routers.chat.inference_engine_manager.generate_stream", side_effect=mock_stream), \
         patch("app.routers.chat.inference_engine_manager.count_tokens", return_value=5):

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemma-4-9b-it",
                "messages": [{"role": "user", "content": "Say hello"}],
                "stream": True,
            },
        )

        assert response.status_code == 200
        chunks = []
        for line in response.text.strip().split("\n"):
            if line.startswith("data: ") and not line.endswith("[DONE]"):
                chunks.append(json.loads(line[len("data: "):]))

        content_parts = [
            c["choices"][0]["delta"]["content"]
            for c in chunks
            if c.get("choices") and c["choices"][0].get("delta", {}).get("content")
        ]
        assert "".join(content_parts) == "Hello world!"

        final_chunk = [
            c for c in chunks
            if c.get("choices") and c["choices"][0].get("finish_reason") is not None
        ][-1]
        assert final_chunk["choices"][0]["finish_reason"] == "stop"


def test_history_formatting_with_tool_calls_and_tool_response():
    from app.services.inference_service import (
        InferenceEngineManager,
        _message_to_engine_content,
        _message_to_engine_input,
    )
    from app.schemas.chat import FunctionCall, ToolCall

    asst_msg = ChatMessage(
        role="assistant",
        content="I will search.",
        tool_calls=[
            ToolCall(
                id="call_abc",
                type="function",
                function=FunctionCall(name="web_search", arguments='{"q": "Sri Lanka"}'),
            )
        ],
    )
    asst_formatted = _message_to_engine_content(asst_msg)
    assert "<|tool_call>call:web_search" in asst_formatted
    assert "<tool_call|>" in asst_formatted
    assert "I will search." in asst_formatted

    tool_msg = ChatMessage(
        role="tool",
        tool_call_id="call_abc",
        content='{"result": "President Anura Kumara Dissanayake"}',
    )
    tool_formatted = _message_to_engine_content(tool_msg)
    assert tool_formatted == '<|tool_response>{"result": "President Anura Kumara Dissanayake"}<tool_response|>'

    tool_input = _message_to_engine_input(tool_msg)
    assert tool_input == '<|tool_response>{"result": "President Anura Kumara Dissanayake"}<tool_response|>'


def test_system_prompt_tool_declarations_and_multi_turn_split():
    from app.services.inference_service import InferenceEngineManager
    from app.schemas.chat import FunctionCall, ToolCall

    messages = [
        ChatMessage(role="system", content="You are a helpful assistant."),
        ChatMessage(role="user", content="Who is the president of Sri Lanka?"),
        ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[
                ToolCall(
                    id="call_abc",
                    type="function",
                    function=FunctionCall(
                        name="web_search", arguments='{"queries": [["president"]]}'
                    ),
                )
            ],
        ),
        ChatMessage(
            role="tool",
            tool_call_id="call_abc",
            content='{"result": "Anura Kumara Dissanayake"}',
        ),
    ]

    tools = [
        ToolDefinition(
            type="function",
            function=FunctionDefinition(
                name="web_search",
                description="Search the web",
                parameters={"type": "object"},
            ),
        )
    ]

    sys_msg, history, last_input = InferenceEngineManager._split_history(messages, tools=tools)

    assert "declaration:web_search" in sys_msg
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "model"
    assert "<|tool_call>call:web_search" in history[1]["content"]
    assert "<|tool_response>" in last_input


def test_endpoint_multi_turn_tool_history():
    from unittest.mock import AsyncMock, patch
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    with patch("app.routers.chat._validate_model"), \
         patch("app.routers.chat.inference_engine_manager.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = (
            "The current president of Sri Lanka is Anura Kumara Dissanayake.",
            "",
            50,
            20,
        )

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemma-4-9b-it",
                "messages": [
                    {"role": "user", "content": "Who is the president of Sri Lanka?"},
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_123",
                                "type": "function",
                                "function": {
                                    "name": "web_search",
                                    "arguments": '{"queries": [["president"]]}',
                                },
                            }
                        ],
                    },
                    {
                        "role": "tool",
                        "tool_call_id": "call_123",
                        "content": '{"result": "Anura Kumara Dissanayake"}',
                    },
                ],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "web_search",
                            "description": "Web search",
                        },
                    }
                ],
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["finish_reason"] == "stop"
        assert "Anura Kumara Dissanayake" in data["choices"][0]["message"]["content"]
        # Verify that inference_engine_manager.generate received the messages and tools
        call_kwargs = mock_gen.call_args.kwargs
        assert len(call_kwargs["tools"]) == 1
        assert call_kwargs["tools"][0].function.name == "web_search"


def test_tool_parser_empty_arguments():
    text = "<|tool_call>call:ping{}<tool_call|>"
    residual, tool_calls = extract_tool_calls(text)
    assert residual is None
    assert len(tool_calls) == 1
    assert tool_calls[0].function.name == "ping"
    assert json.loads(tool_calls[0].function.arguments) == {}


def test_tool_parser_malformed_arguments():
    # If the model emits non-JSON text in args, it should not raise an exception
    text = "<|tool_call>call:custom_func{some plain text}<tool_call|>"
    residual, tool_calls = extract_tool_calls(text)
    assert residual is None
    assert len(tool_calls) == 1
    assert tool_calls[0].function.name == "custom_func"
    assert tool_calls[0].function.arguments != ""


def test_blocking_chat_completion_with_thinking_and_tool_call():
    from unittest.mock import AsyncMock, patch
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    gemma_output = '<|tool_call>call:web_search{queries:[["current president of Sri Lanka"]]}<tool_call|>'
    reasoning_output = "I need to check the official government records."

    with patch("app.routers.chat._validate_model"), \
         patch("app.routers.chat.inference_engine_manager.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = (gemma_output, reasoning_output, 20, 30)

        response = client.post(
            "/v1/chat/completions",
            json={
                "model": "gemma-4-9b-it",
                "messages": [{"role": "user", "content": "Who is the president of Sri Lanka?"}],
                "enable_thinking": True,
                "stream": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["choices"][0]["finish_reason"] == "tool_calls"
        assert "<think>I need to check the official government records.</think>" in data["choices"][0]["message"]["content"]
        tool_calls = data["choices"][0]["message"]["tool_calls"]
        assert len(tool_calls) == 1
        assert tool_calls[0]["function"]["name"] == "web_search"


def test_extract_tool_calls_deepseek_json_format():
    text = (
        "<tool_call>\n"
        '{"name": "bash", "arguments": {"command": "ls -la"}}\n'
        "</tool_call>"
    )
    residual, tool_calls = extract_tool_calls(text)
    assert residual is None
    assert len(tool_calls) == 1
    assert tool_calls[0].function.name == "bash"
    assert json.loads(tool_calls[0].function.arguments) == {"command": "ls -la"}


def test_streaming_fallback_when_not_a_tool_call():
    from app.core.tool_parser import StreamingToolCallBuffer

    buf = StreamingToolCallBuffer()
    # Stream an XML block that is not a tool call
    text1, calls1 = buf.process_chunk("<tool_call>Some arbitrary explanation that is not JSON</tool_call>")
    text_fin, calls_fin = buf.finalize()

    total_text = (text1 or "") + (text_fin or "")
    assert "<tool_call>Some arbitrary explanation that is not JSON</tool_call>" in total_text
    assert len(calls1) == 0
    assert len(calls_fin) == 0





