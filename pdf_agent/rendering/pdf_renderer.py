"""PDF rendering pipeline: Jinja2 HTML → WeasyPrint PDF."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML


def build_html(
    *,
    title: str,
    header: str | None,
    footer: str | None,
    sections: list[dict],
    margins: dict[str, str],
    page_size: str,
    template_dir: Path,
) -> str:
    """Render the Jinja2 report template into an HTML string.

    Parameters
    ----------
    title:
        Document title.
    header / footer:
        Optional page header / footer text.
    sections:
        Pre-processed section dicts (charts already converted to base64).
    margins:
        Page margin mapping (top, bottom, left, right).
    page_size:
        CSS page size value (e.g. "A4", "Letter").
    template_dir:
        Directory containing Jinja2 templates.
    """
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=True,
    )
    template = env.get_template("report_template.html")

    return template.render(
        title=title,
        header=header,
        footer=footer,
        sections=sections,
        margins=margins,
        page_size=page_size,
    )


def render_html_to_pdf(html: str, output_path: Path) -> None:
    """Convert an HTML string to a PDF file using WeasyPrint."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html).write_pdf(str(output_path))
