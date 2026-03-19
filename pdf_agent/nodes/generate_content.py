"""Node: generate a new DocumentSpec from the user prompt."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from pdf_agent.graph.state import PDFAgentState
from pdf_agent.schemas.document_spec import DocumentSpec
from pdf_agent.utils.logger import get_logger

logger = get_logger(__name__)


# ── Base identity shared by all renderer prompts ──────────────────────────────
_BASE_PROMPT = """\
You are a document architect. Given the user's request, produce a complete \
DocumentSpec JSON object that will be rendered into a final document.

Always follow these universal rules:
- Keep a logical reading order (title → context → body → summary/conclusion).
- Use clear, concise section headings.
- Fill in realistic placeholder data when the user doesn't provide exact figures.
- Return ONLY a valid DocumentSpec — no prose, markdown fences, or commentary.
- CRITICAL: Always respect the DOCUMENT TYPE RULES below. They take priority \
  over renderer guidance. Never add content elements that the document type \
  forbids, even if the renderer supports them.
"""

# ── Per document-category hard constraints ────────────────────────────────────
_DOCUMENT_CATEGORY_RULES: dict[str, str] = {
    "resume": """\
DOCUMENT TYPE RULES — Resume / CV (STRICT — override all renderer guidance):
- NEVER include charts, graphs, or any visualisation sections.
- NEVER include generic data tables — resumes use structured prose and lists.
- Allowed section types: heading, paragraph, bullet_list ONLY.
- Typical sections: Contact Info, Professional Summary, Work Experience, \
  Education, Skills, Certifications, Projects, Languages.
- Each job / education entry is a heading followed by bullet points.
- Keep the title equal to the candidate's name (e.g. "Jane Doe — Software Engineer").
- Do NOT add header/footer boilerplate unless the renderer requires it.
""",
    "cover_letter": """\
DOCUMENT TYPE RULES — Cover Letter (STRICT — override all renderer guidance):
- NEVER include charts, graphs, tables, or bullet lists in the body.
- Allowed section types: heading, paragraph ONLY.
- Structure: salutation → opening paragraph → 2–3 body paragraphs → closing.
- Formal, first-person prose throughout.
""",
    "invoice": """\
DOCUMENT TYPE RULES — Invoice / Bill:
- NEVER include charts or graphs — invoices are purely transactional.
- Use a table for line items (description, quantity, unit price, total).
- Sections: sender/recipient info (paragraphs), line-items table, totals \
  paragraph, payment terms paragraph.
""",
    "contract": """\
DOCUMENT TYPE RULES — Contract / Legal Document (STRICT — override all renderer guidance):
- NEVER include charts or graphs.
- NEVER use bullet lists for the main body — use numbered paragraph sections instead.
- Tables may be used only for schedules, fee summaries, or signature blocks.
- All content must be formal legal prose with numbered clauses.
""",
    "letter": """\
DOCUMENT TYPE RULES — Formal Letter:
- NEVER include charts, graphs, or data tables.
- Allowed section types: heading, paragraph ONLY.
- Structure: date/address block → greeting → body paragraphs → sign-off.
""",
    "report": """\
DOCUMENT TYPE RULES — Report / Analysis:
- Charts and tables are welcome where data genuinely benefits from visualisation.
- Only add a chart when it illustrates a real trend, comparison, or breakdown.
- Include: executive summary, findings/body, conclusion, and optionally appendix.
""",
    "technical_doc": """\
DOCUMENT TYPE RULES — Technical Document / Manual / Spec:
- Tables are appropriate for parameters, options, or comparison matrices.
- Bullet lists are good for requirements, feature lists, CLI flags.
- Charts are rarely needed; only include if explicitly requested.
- Use precise, technical language.
""",
    "presentation": """\
DOCUMENT TYPE RULES — Presentation / Slide Deck:
- Each major section represents one slide — keep content brief and punchy.
- Bullet lists are the primary content element.
- Charts are appropriate for data slides.
- Avoid long prose paragraphs.
""",
    "newsletter": """\
DOCUMENT TYPE RULES — Newsletter:
- Mix of headings, short paragraphs, and bullet highlights.
- Charts are rarely appropriate; only include if summarising survey/data results.
- Focus on narrative, announcements, and highlights.
""",
    "brochure": """\
DOCUMENT TYPE RULES — Brochure / Marketing Material:
- Prefer headings, short persuasive paragraphs, and bullet benefit lists.
- Charts are appropriate only for statistics or impact metrics.
- Keep the tone positive and benefit-focused.
""",
    "general": "",  # No extra constraints — renderer guidance applies as-is
}


# ── Per-renderer guidance injected on top of the base prompt ─────────────────
_RENDERER_GUIDANCE: dict[str, str] = {
    "weasyprint": """\
RENDERER: WeasyPrint (HTML/CSS → PDF)
You are generating content for a pixel-perfect, professionally designed document
rendered from HTML and CSS via WeasyPrint.

Content strategy:
- Prefer rich structure: use a mix of headings, paragraphs, tables, and charts.
- Tables shine here — use them freely for comparisons, datasets, and summaries; \
  include descriptive column headers.
- Charts are fully supported — add bar/line/pie/scatter charts whenever data \
  visualisation adds value.
- Include a `header` (e.g. company name or report subtitle) and a `footer` \
  (e.g. confidentiality notice or page credit) for a polished look.
- Use multi-paragraph prose sections for narrative content; avoid overly long \
  single paragraphs — split them.
- Design for A4 page size with standard margins unless the user specifies otherwise.
""",

    "fpdf2": """\
RENDERER: FPDF2 (programmatic PDF)
You are generating content for a clean, template-driven PDF built programmatically \
with FPDF2. This renderer excels at structured, form-like layouts.

Content strategy:
- Prefer clarity and regularity: well-labelled sections, concise paragraphs, \
  and neat tables.
- Tables are ideal — keep column counts between 2 and 6 so they fit the page \
  width cleanly; all cell values must be strings.
- Bullet lists work well for enumerations and feature lists.
- Limit charts to 1–2 per document; they are embedded as PNG images and each \
  takes significant vertical space.
- Avoid excessively long paragraphs — FPDF2 wraps text per cell but very long \
  strings can overflow; break content into shorter, punchy sentences.
- A `header` and `footer` are rendered on every page — keep them short \
  (≤ 80 characters each).
- Do NOT rely on advanced typography (custom fonts, colours per cell) — the \
  renderer applies its own consistent styling.
""",

    "borb": """\
RENDERER: Borb (advanced PDF features)
You are generating content for a sophisticated PDF built with the Borb library, \
which supports annotations, precise table control, and rich layout primitives.

Content strategy:
- Leverage Borb's strengths: detailed tables with many columns, multi-section \
  long-form documents, and documents that benefit from structured typography.
- Tables are a first-class citizen — use them for any comparative or relational \
  data; include a clear header row.
- You may include multiple charts; they render as embedded images with captions.
- Structure content with an explicit hierarchy: one top-level heading section per \
  major topic, followed by supporting paragraphs and data.
- Use bullet lists for requirements, feature sets, or action items.
- Include a `header` (document title / organisation) and `footer` \
  (version, date, or legal note).
- Aim for completeness — Borb is chosen for complex documents, so produce \
  comprehensive content rather than a brief overview.
""",

    "markdown": """\
RENDERER: Markdown (plain text → PDF)
You are generating content that will first be written as a Markdown file and \
optionally converted to PDF. The target audience is typically developers or \
technical readers.

Content strategy:
- Prefer simple, clean structure: headings → paragraphs → bullet lists → tables.
- Use bullet lists liberally — they translate directly to Markdown `- item` syntax.
- Tables are supported (GFM pipe tables) — keep them modest (≤ 5 columns) so \
  they remain readable in plain text.
- Avoid charts if possible; they cannot be natively represented in Markdown and \
  will appear as text placeholders. Only include a chart section if the user \
  explicitly requests a visualisation.
- Write in a direct, technical tone — short sentences, active voice, numbered \
  steps for processes.
- Do NOT include a `header` or `footer`; they add little value in Markdown output.
- Code references, command-line examples, or API names should appear in their \
  own `paragraph` section with backtick notation in the text.
""",
}

_FALLBACK_GUIDANCE = """\
RENDERER: Default (general-purpose)
Produce a well-rounded document with a balanced mix of headings, paragraphs, \
tables, bullet lists, and (where appropriate) charts.
"""


def _build_system_prompt(renderer: str | None, document_category: str | None) -> SystemMessage:
    """Compose a renderer-specific + document-category-aware system prompt."""
    guidance = _RENDERER_GUIDANCE.get(renderer or "", _FALLBACK_GUIDANCE)
    category_rules = _DOCUMENT_CATEGORY_RULES.get(document_category or "general", "")
    # Category rules are prepended right after the base so they take priority
    sections = [_BASE_PROMPT]
    if category_rules:
        sections.append(category_rules)
    sections.append(guidance)
    return SystemMessage(content="\n".join(sections))


def generate_content(state: PDFAgentState, *, llm: BaseChatModel) -> dict:
    """Create a brand-new DocumentSpec from the user prompt.

    Uses ``llm.with_structured_output`` so the LLM returns a validated
    Pydantic model rather than free-form text.

    The system prompt is tailored to the renderer chosen by ``select_renderer``
    so the LLM produces content best suited to that backend's strengths and
    constraints (e.g. table width limits for FPDF2, plain structure for Markdown).
    """
    selected_renderer = state.get("renderer")
    document_category = state.get("document_category") or "general"
    system_prompt = _build_system_prompt(selected_renderer, document_category)

    logger.info(
        "Generating content for renderer: %s, document_category: %s",
        selected_renderer or "default (fallback)",
        document_category,
    )
    logger.debug("System prompt renderer section:\n%s", system_prompt.content[:300])

    structured_llm = llm.with_structured_output(DocumentSpec, method="function_calling")

    try:
        doc_spec: DocumentSpec = structured_llm.invoke(
            [system_prompt, *state["messages"]]
        )
    except Exception as exc:
        logger.error("Content generation failed: %s", exc)
        return {
            "error": f"Content generation failed: {exc}",
            "document_spec": state.get("document_spec"),
        }

    spec_dict = doc_spec.model_dump()
    logger.info(
        "Document spec created: '%s' (renderer: %s, sections: %d)",
        doc_spec.title,
        selected_renderer or "default",
        len(doc_spec.sections),
    )
    return {
        "document_spec": spec_dict,
        "messages": [
            *state["messages"],
            AIMessage(content=f"Document spec created: {json.dumps(spec_dict, indent=2)[:200]}…"),
        ],
        "error": None,
    }
