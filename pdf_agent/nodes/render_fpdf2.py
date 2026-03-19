"""Node: render the current DocumentSpec into a PDF using FPDF2.

This node is pure Python — no LLM calls are made here.
Best for: invoices, certificates, receipts, form-like or templated layouts.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fpdf import FPDF

from pdf_agent.config import AgentConfig
from pdf_agent.graph.state import PDFAgentState
from pdf_agent.rendering.chart_renderer import generate_chart
from pdf_agent.schemas.document_spec import (
    BulletSection, ChartSection, DocumentSpec, Section, TableSection, TextSection,
)
from pdf_agent.utils.logger import get_logger

logger = get_logger(__name__)

# ── Layout constants ──────────────────────────────────────────────────────────
_PAGE_W = 210          # A4 width in mm
_MARGIN = 15           # Left/right/top margin in mm
_CONTENT_W = _PAGE_W - _MARGIN * 2


class _PDFDoc(FPDF):
    """FPDF2 subclass with automatic header/footer support."""

    def __init__(self, title: str, header_text: str | None, footer_text: str | None) -> None:
        super().__init__()
        self._title_text = title
        self._header_text = header_text
        self._footer_text = footer_text
        self.set_margins(_MARGIN, _MARGIN, _MARGIN)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self) -> None:  # type: ignore[override]
        if self._header_text:
            self.set_font("Helvetica", "I", 9)
            self.set_text_color(120, 120, 120)
            self.cell(0, 8, self._header_text, align="C")
            self.ln(4)
            self.set_draw_color(200, 200, 200)
            self.line(_MARGIN, self.get_y(), _PAGE_W - _MARGIN, self.get_y())
            self.ln(3)
            self.set_text_color(0, 0, 0)

    def footer(self) -> None:  # type: ignore[override]
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        text = self._footer_text or f"Page {self.page_no()}"
        self.cell(0, 10, text, align="C")
        self.set_text_color(0, 0, 0)


def _render_heading(pdf: _PDFDoc, text: str) -> None:
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(30, 30, 30)
    pdf.ln(4)
    pdf.multi_cell(_CONTENT_W, 8, text)
    pdf.ln(2)
    pdf.set_draw_color(100, 100, 220)
    pdf.line(_MARGIN, pdf.get_y(), _MARGIN + _CONTENT_W * 0.4, pdf.get_y())
    pdf.ln(4)
    pdf.set_text_color(0, 0, 0)


def _render_paragraph(pdf: _PDFDoc, text: str) -> None:
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(_CONTENT_W, 6, text)
    pdf.ln(3)


def _render_bullets(pdf: _PDFDoc, items: list[str]) -> None:
    pdf.set_font("Helvetica", "", 11)
    for item in items:
        pdf.cell(6, 6, "\u2022")
        pdf.multi_cell(_CONTENT_W - 6, 6, item)
    pdf.ln(2)


def _render_table(pdf: _PDFDoc, headers: list[str], rows: list[list[str]]) -> None:
    if not headers:
        return
    col_w = _CONTENT_W / len(headers)

    # Header row
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(60, 80, 180)
    pdf.set_text_color(255, 255, 255)
    for h in headers:
        pdf.cell(col_w, 8, str(h), border=1, fill=True, align="C")
    pdf.ln()

    # Data rows with alternating shading
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)
    for i, row in enumerate(rows):
        fill = i % 2 == 0
        pdf.set_fill_color(240, 242, 255) if fill else pdf.set_fill_color(255, 255, 255)
        for cell in row:
            pdf.cell(col_w, 7, str(cell), border=1, fill=fill)
        pdf.ln()
    pdf.ln(3)


def _render_chart(pdf: _PDFDoc, title: str, image_b64: str) -> None:
    import base64
    import tempfile

    if not image_b64:
        return

    img_bytes = base64.b64decode(image_b64)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp.write(img_bytes)
        tmp_path = tmp.name

    pdf.set_font("Helvetica", "I", 10)
    pdf.multi_cell(_CONTENT_W, 6, title, align="C")
    pdf.ln(2)
    img_w = min(_CONTENT_W, 150)
    pdf.image(tmp_path, x=_MARGIN + (_CONTENT_W - img_w) / 2, w=img_w)
    pdf.ln(5)

    Path(tmp_path).unlink(missing_ok=True)


def _process_sections(pdf: _PDFDoc, sections: list[Section]) -> None:
    for section in sections:
        if isinstance(section, TextSection):
            if section.type == "heading":
                _render_heading(pdf, section.content)
            else:
                _render_paragraph(pdf, section.content)
        elif isinstance(section, BulletSection):
            _render_bullets(pdf, section.content)
        elif isinstance(section, TableSection):
            _render_table(pdf, section.content.headers, section.content.rows)
        elif isinstance(section, ChartSection):
            image_b64 = generate_chart(section.content)
            _render_chart(pdf, section.content.title, image_b64)


def render_fpdf2(state: PDFAgentState, *, config: AgentConfig) -> dict:
    """Render the document spec to a PDF using FPDF2 (programmatic approach).

    Steps:
        1. Validate and parse the spec.
        2. Render each section type to the FPDF canvas.
        3. Write the output PDF to disk.
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

    pdf = _PDFDoc(
        title=doc.title,
        header_text=doc.header,
        footer_text=doc.footer,
    )
    pdf.add_page()

    # Document title
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(30, 30, 150)
    pdf.multi_cell(_CONTENT_W, 12, doc.title, align="C")
    pdf.ln(6)
    pdf.set_text_color(0, 0, 0)

    _process_sections(pdf, doc.sections)

    output_dir = config.ensure_output_dir()
    filename = f"{uuid.uuid4().hex[:12]}_fpdf2.pdf"
    output_path: Path = output_dir / filename

    try:
        pdf.output(str(output_path))
    except Exception as exc:
        logger.error("FPDF2 rendering failed: %s", exc)
        return {"error": f"FPDF2 rendering failed: {exc}"}

    logger.info("FPDF2 PDF rendered to %s", output_path)
    return {"pdf_path": str(output_path), "error": None}
