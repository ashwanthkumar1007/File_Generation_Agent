"""Node: render the current DocumentSpec into a PDF using WeasyPrint (HTML/CSS).

This node is pure Python — no LLM calls are made here.
Best for: reports, proposals, branded documents, complex layouts.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from pdf_agent.config import AgentConfig
from pdf_agent.graph.state import PDFAgentState
from pdf_agent.rendering.chart_renderer import generate_chart
from pdf_agent.rendering.pdf_renderer import render_html_to_pdf, build_html
from pdf_agent.schemas.document_spec import (
    ChartSection, DocumentSpec, TableSection,
    TextSection, BulletSection, Section,
)
from pdf_agent.utils.logger import get_logger

logger = get_logger(__name__)


def _prepare_sections(sections: list[Section]) -> list[dict]:
    """Convert sections to template-ready dicts, rendering charts as base64."""
    prepared: list[dict] = []
    for section in sections:
        entry: dict = {"type": section.type}

        if isinstance(section, ChartSection):
            entry["content"] = {
                "title": section.content.title,
                "image_b64": generate_chart(section.content),
            }
        elif isinstance(section, TableSection):
            entry["content"] = {
                "headers": section.content.headers,
                "rows": section.content.rows,
            }
        elif isinstance(section, BulletSection):
            entry["content"] = section.content
        else:  # TextSection (heading / paragraph)
            entry["content"] = section.content

        prepared.append(entry)
    return prepared


def render_weasy(state: PDFAgentState, *, config: AgentConfig) -> dict:
    """Render the document spec to a PDF using WeasyPrint (HTML/CSS pipeline).

    Steps:
        1. Validate and parse the spec.
        2. Pre-render chart sections to base64 PNG.
        3. Build HTML via Jinja2.
        4. Convert HTML → PDF with WeasyPrint.
    """
    raw_spec = state.get("document_spec")
    if raw_spec is None:
        logger.warning("Render requested but no document spec in state")
        return {"error": "No document spec to render."}

    try:
        doc = DocumentSpec(**raw_spec)
    except Exception as exc:
        logger.error("Invalid document spec: %s", exc)
        return {"error": f"Invalid document spec: {exc}"}

    sections = _prepare_sections(doc.sections)

    html = build_html(
        title=doc.title,
        header=doc.header,
        footer=doc.footer,
        sections=sections,
        margins=doc.margins,
        page_size=doc.page_size,
        template_dir=config.template_dir,
    )

    output_dir = config.ensure_output_dir()
    filename = f"{uuid.uuid4().hex[:12]}.pdf"
    output_path: Path = output_dir / filename

    try:
        render_html_to_pdf(html, output_path)
    except Exception as exc:
        logger.error("PDF rendering failed: %s", exc)
        return {"error": f"PDF rendering failed: {exc}"}

    logger.info("PDF rendered to %s", output_path)

    return {"pdf_path": str(output_path), "error": None}
