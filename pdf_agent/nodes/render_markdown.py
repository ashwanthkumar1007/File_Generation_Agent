"""Node: render the current DocumentSpec into a Markdown file (+ optional PDF).

This node is pure Python — no LLM calls are made here.
Best for: developer docs, READMEs, technical documentation, changelogs,
          or any content that benefits from plain structured text output.

Primary output:  .md file (always produced)
Secondary output: .pdf via WeasyPrint Markdown→HTML→PDF (when available)
"""

from __future__ import annotations

import uuid
from pathlib import Path

from pdf_agent.config import AgentConfig
from pdf_agent.graph.state import PDFAgentState
from pdf_agent.schemas.document_spec import (
    BulletSection, ChartSection, DocumentSpec, Section, TableSection, TextSection,
)
from pdf_agent.utils.logger import get_logger

logger = get_logger(__name__)


def _section_to_markdown(section: Section) -> str:  # noqa: C901
    """Convert a single section to its Markdown representation."""
    lines: list[str] = []

    if isinstance(section, TextSection):
        if section.type == "heading":
            lines.append(f"## {section.content}")
            lines.append("")
        else:
            lines.append(section.content)
            lines.append("")

    elif isinstance(section, BulletSection):
        for item in section.content:
            lines.append(f"- {item}")
        lines.append("")

    elif isinstance(section, TableSection):
        headers = section.content.headers
        rows = section.content.rows
        if headers:
            lines.append("| " + " | ".join(str(h) for h in headers) + " |")
            lines.append("| " + " | ".join("---" for _ in headers) + " |")
            for row in rows:
                lines.append("| " + " | ".join(str(c) for c in row) + " |")
            lines.append("")

    elif isinstance(section, ChartSection):
        # Charts can't be represented natively in Markdown; emit a placeholder
        chart = section.content
        lines.append(f"> **Chart: {chart.title}** ({chart.chart_type})")
        lines.append(">")
        lines.append(f"> Labels: {', '.join(str(l) for l in chart.labels)}")
        lines.append(f"> Values: {', '.join(str(v) for v in chart.values)}")
        lines.append("")

    return "\n".join(lines)


def _doc_to_markdown(doc: DocumentSpec) -> str:
    """Convert the full DocumentSpec to a Markdown string."""
    parts: list[str] = []

    # Front-matter title
    parts.append(f"# {doc.title}")
    parts.append("")

    if doc.header:
        parts.append(f"_{doc.header}_")
        parts.append("")

    for section in doc.sections:
        parts.append(_section_to_markdown(section))

    if doc.footer:
        parts.append("---")
        parts.append(f"_{doc.footer}_")
        parts.append("")

    return "\n".join(parts)


def _markdown_to_pdf(md_content: str, output_path: Path) -> bool:
    """Attempt to convert Markdown → HTML → PDF using WeasyPrint.

    Returns True on success, False when WeasyPrint is unavailable.
    """
    try:
        import markdown as md_lib
        from weasyprint import HTML

        html_body = md_lib.markdown(
            md_content,
            extensions=["tables", "fenced_code", "codehilite"],
        )
        full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: 'Segoe UI', sans-serif; margin: 40px 60px; color: #222; }}
  h1 {{ color: #1a1ab4; border-bottom: 2px solid #1a1ab4; padding-bottom: 6px; }}
  h2 {{ color: #333; margin-top: 24px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th {{ background: #3c50b4; color: white; padding: 8px; text-align: left; }}
  td {{ border: 1px solid #ccc; padding: 7px; }}
  tr:nth-child(even) td {{ background: #f0f2ff; }}
  code {{ background: #f4f4f4; padding: 2px 5px; border-radius: 3px; font-size: 0.9em; }}
  blockquote {{ border-left: 4px solid #aaa; margin: 0; padding-left: 16px; color: #555; }}
  hr {{ border: none; border-top: 1px solid #ddd; margin: 24px 0; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        HTML(string=full_html).write_pdf(str(output_path))
        return True

    except ImportError as exc:
        logger.warning(
            "Cannot produce PDF from Markdown (%s). Markdown file only.", exc
        )
        return False


def render_markdown(state: PDFAgentState, *, config: AgentConfig) -> dict:
    """Render the document spec to Markdown and optionally to PDF.

    Steps:
        1. Validate and parse the spec.
        2. Serialize each section to its Markdown equivalent.
        3. Write the .md file to disk.
        4. Attempt Markdown → PDF conversion via WeasyPrint (optional).

    Returns:
        pdf_path pointing to the PDF if conversion succeeded,
        otherwise to the .md file so downstream nodes always have a path.
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

    output_dir = config.ensure_output_dir()
    stem = uuid.uuid4().hex[:12]

    # ── Write Markdown ─────────────────────────────────────────────────────
    md_content = _doc_to_markdown(doc)
    md_path = output_dir / f"{stem}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(md_content, encoding="utf-8")
    logger.info("Markdown written to %s", md_path)

    # ── Attempt PDF conversion ─────────────────────────────────────────────
    pdf_path = output_dir / f"{stem}_markdown.pdf"
    pdf_ok = _markdown_to_pdf(md_content, pdf_path)

    if pdf_ok:
        logger.info("Markdown PDF rendered to %s", pdf_path)
        return {"pdf_path": str(pdf_path), "error": None}

    # Fall back to returning the .md path so the graph has a usable output
    logger.info("Returning Markdown file path as output: %s", md_path)
    return {"pdf_path": str(md_path), "error": None}
