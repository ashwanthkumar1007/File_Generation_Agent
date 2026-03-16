"""Pydantic schemas for the structured document specification.

The LLM produces instances of these models; rendering is handled separately.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, model_validator


# ── Leaf content models ──────────────────────────────────────────────────────

class TableContent(BaseModel):
    """Tabular data with headers and rows."""

    headers: list[str] = Field(..., description="Column headers for the table.")
    rows: list[list[str]] = Field(
        ...,
        description="Row data; each inner list matches the headers. Convert all cell values to strings.",
    )


class ChartContent(BaseModel):
    """Specification for a rendered chart."""

    chart_type: Literal["bar", "line", "pie", "scatter"] = Field(
        ..., description="Type of chart to render."
    )
    title: str = Field("", description="Chart title.")
    labels: list[str] = Field(..., description="Category / x-axis labels.")
    values: list[float] = Field(..., description="Numeric values for each label.")


# ── Discriminated section types ──────────────────────────────────────────────
# Each section has a `type` literal so the LLM and Pydantic can discriminate
# the union unambiguously — and so OpenAI function-calling can handle them.

class TextSection(BaseModel):
    """A heading or paragraph section."""

    type: Literal["heading", "paragraph"]
    content: str = Field(..., description="Text content of the heading or paragraph.")


class BulletSection(BaseModel):
    """A bullet list section."""

    type: Literal["bullet_list"]
    content: list[str] = Field(..., description="Ordered list of bullet item strings.")


class TableSection(BaseModel):
    """A table section."""

    type: Literal["table"]
    content: TableContent = Field(..., description="Table data with headers and rows.")


class ChartSection(BaseModel):
    """A chart section."""

    type: Literal["chart"]
    content: ChartContent = Field(..., description="Chart specification.")


# Convenience alias used in type hints across the codebase
Section = Union[TextSection, BulletSection, TableSection, ChartSection]


# ── Document spec ────────────────────────────────────────────────────────────

# Maps known LLM type aliases → canonical discriminator values
_TYPE_ALIASES: dict[str, str] = {
    "bullets": "bullet_list",
    "bullet": "bullet_list",
    "list": "bullet_list",
    "unordered_list": "bullet_list",
    "ordered_list": "bullet_list",
    "text": "paragraph",
    "body": "paragraph",
    "content": "paragraph",
    "header": "heading",
    "title": "heading",
    "subheading": "heading",
    "data_table": "table",
    "graph": "chart",
    "visualization": "chart",
    "figure": "chart",
}


class DocumentSpec(BaseModel):
    """Complete structured specification for a PDF document.

    The LLM creates and edits this model; the renderer converts it to PDF.
    """

    title: str = Field(..., description="Document title.")
    page_size: str = Field("A4", description="Paper size (e.g. A4, Letter).")
    margins: dict[str, str] = Field(
        default_factory=lambda: {
            "top": "2cm",
            "bottom": "2cm",
            "left": "2.5cm",
            "right": "2.5cm",
        },
        description="Page margins keyed by side.",
    )
    header: str | None = Field(None, description="Optional page header text.")
    footer: str | None = Field(None, description="Optional page footer text.")
    sections: list[Annotated[Section, Field(discriminator="type")]] = Field(
        default_factory=list,
        description="Ordered list of document sections.",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalise_section_types(cls, data: Any) -> Any:
        """Remap LLM-generated section type aliases to canonical values.

        The LLM sometimes returns e.g. ``'bullets'`` instead of
        ``'bullet_list'``.  This pre-validator silently corrects all known
        variants before the discriminated union is evaluated.
        """
        if isinstance(data, dict) and "sections" in data:
            for section in data["sections"]:
                if isinstance(section, dict) and "type" in section:
                    section["type"] = _TYPE_ALIASES.get(
                        section["type"], section["type"]
                    )
        return data

