"""Node: render the current DocumentSpec into a PDF using Borb.

This node is pure Python — no LLM calls are made here.
Best for: contracts, legal documents, interactive forms, annotations,
          digital signatures, or documents needing advanced PDF features.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

from pdf_agent.config import AgentConfig
from pdf_agent.graph.state import PDFAgentState
from pdf_agent.rendering.chart_renderer import generate_chart
from pdf_agent.schemas.document_spec import (
    BulletSection, ChartSection, DocumentSpec, Section, TableSection, TextSection,
)
from pdf_agent.utils.logger import get_logger

logger = get_logger(__name__)


def _build_pdf(doc: DocumentSpec, output_path: Path) -> None:  # noqa: C901
    """Build the PDF document using Borb library."""
    from borb.pdf import Document, Page, PDF
    from borb.pdf import SingleColumnLayout, MultiColumnLayout
    from borb.pdf.canvas.layout.text.paragraph import Paragraph
    from borb.pdf.canvas.layout.table.fixed_column_width_table import FixedColumnWidthTable
    from borb.pdf.canvas.layout.list.unordered_list import UnorderedList
    from borb.pdf.canvas.color.color import HexColor, X11Color
    from borb.pdf.canvas.layout.image.image import Image as BorbImage
    from borb.pdf.canvas.layout.page_layout.margin_paragraph import MarginParagraph
    import base64
    import tempfile
    from PIL import Image as PILImage
    import io

    # ── Create document structure ──────────────────────────────────────────
    pdf_doc = Document()
    page = Page()
    pdf_doc.add_page(page)
    layout = SingleColumnLayout(page)

    # ── Title ──────────────────────────────────────────────────────────────
    layout.add(
        Paragraph(
            doc.title,
            font="Helvetica-Bold",
            font_size=Decimal(20),
            font_color=HexColor("1E1EB4"),
        )
    )

    # ── Header (if present) ────────────────────────────────────────────────
    if doc.header:
        layout.add(
            Paragraph(
                doc.header,
                font="Helvetica-Oblique",
                font_size=Decimal(9),
                font_color=X11Color("Gray"),
            )
        )

    # ── Sections ───────────────────────────────────────────────────────────
    for section in doc.sections:
        if isinstance(section, TextSection):
            if section.type == "heading":
                layout.add(
                    Paragraph(
                        section.content,
                        font="Helvetica-Bold",
                        font_size=Decimal(14),
                        font_color=HexColor("1E1E1E"),
                    )
                )
            else:
                layout.add(
                    Paragraph(
                        section.content,
                        font="Helvetica",
                        font_size=Decimal(11),
                    )
                )

        elif isinstance(section, BulletSection):
            ul = UnorderedList()
            for item in section.content:
                ul.add(Paragraph(item, font="Helvetica", font_size=Decimal(11)))
            layout.add(ul)

        elif isinstance(section, TableSection):
            headers = section.content.headers
            rows = section.content.rows
            if headers:
                num_cols = len(headers)
                table = FixedColumnWidthTable(
                    number_of_columns=num_cols,
                    number_of_rows=len(rows) + 1,
                )
                # Header cells
                for h in headers:
                    table.add(
                        Paragraph(
                            str(h),
                            font="Helvetica-Bold",
                            font_size=Decimal(10),
                            font_color=HexColor("FFFFFF"),
                            background_color=HexColor("3C50B4"),
                        )
                    )
                # Data cells
                for i, row in enumerate(rows):
                    bg = HexColor("F0F2FF") if i % 2 == 0 else HexColor("FFFFFF")
                    for cell in row:
                        table.add(
                            Paragraph(
                                str(cell),
                                font="Helvetica",
                                font_size=Decimal(10),
                                background_color=bg,
                            )
                        )
                table.set_padding_on_all_cells(
                    Decimal(5), Decimal(5), Decimal(5), Decimal(5)
                )
                layout.add(table)

        elif isinstance(section, ChartSection):
            image_b64 = generate_chart(section.content)
            if image_b64:
                img_bytes = base64.b64decode(image_b64)
                pil_img = PILImage.open(io.BytesIO(img_bytes))
                layout.add(
                    Paragraph(
                        section.content.title,
                        font="Helvetica-Oblique",
                        font_size=Decimal(10),
                    )
                )
                layout.add(
                    BorbImage(
                        pil_img,
                        width=Decimal(400),
                        height=Decimal(250),
                    )
                )

    # ── Footer annotation (metadata) ──────────────────────────────────────
    if doc.footer:
        layout.add(
            Paragraph(
                doc.footer,
                font="Helvetica-Oblique",
                font_size=Decimal(8),
                font_color=X11Color("Gray"),
            )
        )

    # ── Write to disk ──────────────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as fh:
        PDF.dumps(fh, pdf_doc)


def render_borb(state: PDFAgentState, *, config: AgentConfig) -> dict:
    """Render the document spec to a PDF using Borb.

    Steps:
        1. Validate and parse the spec.
        2. Build the Borb document with typed layout elements.
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

    output_dir = config.ensure_output_dir()
    filename = f"{uuid.uuid4().hex[:12]}_borb.pdf"
    output_path: Path = output_dir / filename

    try:
        _build_pdf(doc, output_path)
    except Exception as exc:
        logger.error("Borb rendering failed: %s", exc)
        return {"error": f"Borb rendering failed: {exc}"}

    logger.info("Borb PDF rendered to %s", output_path)
    return {"pdf_path": str(output_path), "error": None}
