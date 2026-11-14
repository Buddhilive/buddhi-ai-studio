from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

EGM_ROOT = Path(__file__).resolve().parent
PERSONAS_DIR = EGM_ROOT / "personas"
STANDARDS_DIR = EGM_ROOT / "standards"


@lru_cache(maxsize=32)
def load_persona(persona_name: str) -> str:
    """Load a vendored persona prompt markdown file by short name.

    Args:
        persona_name: e.g. "zoom_out", "comprehension", "design_critic"
    Returns:
        The markdown text content of the persona system prompt.
    """
    clean_name = persona_name.removesuffix(".md").replace("-", "_")
    persona_path = PERSONAS_DIR / f"{clean_name}.md"
    if not persona_path.exists():
        # Fallback to direct name if custom
        persona_path = PERSONAS_DIR / persona_name
        if not persona_path.exists():
            raise FileNotFoundError(f"EGM persona '{persona_name}' not found at {persona_path}")

    return persona_path.read_text(encoding="utf-8")


@lru_cache(maxsize=32)
def load_standard(standard_name: str) -> str:
    """Load a vendored document standard rubric markdown file by short name.

    Args:
        standard_name: e.g. "feature-spec-standard", "zoom-out-standard"
    Returns:
        The markdown text content of the rubric.
    """
    clean_name = standard_name.removesuffix(".md")
    std_path = STANDARDS_DIR / f"{clean_name}.md"
    if not std_path.exists():
        # Fallback to underscore variant or direct
        std_path = STANDARDS_DIR / f"{clean_name.replace('-', '_')}.md"
        if not std_path.exists():
            std_path = STANDARDS_DIR / standard_name
            if not std_path.exists():
                raise FileNotFoundError(f"EGM standard '{standard_name}' not found at {std_path}")

    return std_path.read_text(encoding="utf-8")


def list_available_personas() -> list[str]:
    """Return all available persona names without .md extension."""
    if not PERSONAS_DIR.exists():
        return []
    return sorted(p.stem for p in PERSONAS_DIR.glob("*.md"))


def list_available_standards() -> list[str]:
    """Return all available standard names without .md extension."""
    if not STANDARDS_DIR.exists():
        return []
    return sorted(s.stem for s in STANDARDS_DIR.glob("*.md"))
