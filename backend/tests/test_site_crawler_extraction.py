from typing import Any
import pytest
from unittest.mock import AsyncMock, patch

from app.schemas.site_crawler import ExtractionSchema, FieldDefinition
from app.services.site_crawler.extraction import (
    _clean_json_text,
    _coerce_numbers,
    build_pydantic_model,
    chunk_markdown,
    extract_from_markdown,
)


def test_clean_json_text():
    # Markdown fenced json
    fenced = "```json\n{\"title\": \"Book A\", \"price\": 19.99}\n```"
    assert _clean_json_text(fenced) == '{"title": "Book A", "price": 19.99}'

    # Leading & trailing conversational noise
    noise = "Here is the result:\n{\"title\": \"Book A\"}\nHope this helps!"
    assert _clean_json_text(noise) == '{"title": "Book A"}'

    # Array format
    arr = "Here is array: [{\"name\": \"Item\"}] thank you."
    assert _clean_json_text(arr) == '[{"name": "Item"}]'


def test_coerce_numbers():
    assert _coerce_numbers("$19.99") == 19.99
    assert _coerce_numbers("£1,250") == 1250
    assert _coerce_numbers(42) == 42
    assert _coerce_numbers("not a number") == "not a number"


def test_build_pydantic_model_single():
    schema = ExtractionSchema(
        mode="single",
        fields=[
            FieldDefinition(name="title", type="string", required=True),
            FieldDefinition(name="price", type="number", required=False),
            FieldDefinition(name="tags", type="string_list", required=False),
        ],
    )
    model_cls = build_pydantic_model(schema)
    instance = model_cls.model_validate({"title": "Test Title", "price": 10.5, "tags": ["a", "b"]})
    assert instance.title == "Test Title"
    assert instance.price == 10.5
    assert instance.tags == ["a", "b"]

    # Missing optional field should succeed
    opt_instance = model_cls.model_validate({"title": "Test Title"})
    assert opt_instance.price is None


def test_build_pydantic_model_many():
    schema = ExtractionSchema(
        mode="many",
        fields=[
            FieldDefinition(name="title", type="string", required=True),
            FieldDefinition(name="in_stock", type="boolean", required=True),
        ],
    )
    model_cls = build_pydantic_model(schema)
    instance = model_cls.model_validate(
        {"records": [{"title": "Book 1", "in_stock": True}, {"title": "Book 2", "in_stock": False}]}
    )
    assert len(instance.records) == 2
    assert instance.records[0].title == "Book 1"
    assert instance.records[1].in_stock is False


def test_chunk_markdown():
    text = "# Section 1\nSome long text.\n## Section 2\nAnother section text."
    chunks = chunk_markdown(text, max_chunk_tokens=50)
    assert len(chunks) >= 1


@pytest.mark.asyncio
async def test_extract_from_markdown_empty():
    schema = ExtractionSchema(
        mode="single",
        fields=[FieldDefinition(name="title", type="string", required=True)],
    )
    res = await extract_from_markdown(
        markdown="Too short",
        url="http://example.com",
        title="Example",
        schema=schema,
    )
    assert res.status == "empty_content"
    assert len(res.records) == 0


@pytest.mark.asyncio
async def test_extract_from_markdown_single_success():
    schema = ExtractionSchema(
        mode="single",
        fields=[
            FieldDefinition(name="title", type="string", required=True),
            FieldDefinition(name="price", type="number", required=True),
        ],
    )

    mock_generate = AsyncMock(
        return_value=(
            '```json\n{"title": "Awesome Book", "price": "$29.99"}\n```',
            "",
            100,
            20,
        )
    )

    with patch("app.services.site_crawler.extraction.inference_engine_manager.generate", mock_generate):
        res = await extract_from_markdown(
            markdown="This is a long markdown text describing Awesome Book with price $29.99 on the page.",
            url="http://example.com/book",
            title="Awesome Book",
            schema=schema,
        )
        assert res.status == "ok"
        assert len(res.records) == 1
        assert res.records[0]["title"] == "Awesome Book"
        assert res.records[0]["price"] == 29.99
        assert res.records[0]["source_url"] == "http://example.com/book"
