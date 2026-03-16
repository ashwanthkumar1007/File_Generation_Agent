"""Node: generate a new DocumentSpec from the user prompt."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from pdf_agent.graph.state import PDFAgentState
from pdf_agent.schemas.document_spec import DocumentSpec
from pdf_agent.utils.logger import get_logger

logger = get_logger(__name__)


SYSTEM_PROMPT = SystemMessage(content="""\
You are a document architect.  Given the user's request, produce a complete
DocumentSpec JSON object that describes a professional PDF report.

Guidelines:
- Use clear, concise section headings.
- Include tables when data is presented.
- Include chart specs when data visualization is appropriate.
- Use bullet lists for enumerations.
- Keep a logical reading order.
- Fill in realistic placeholder data when the user doesn't provide exact figures.

Return ONLY a valid DocumentSpec.
""")


def generate_content(state: PDFAgentState, *, llm: BaseChatModel) -> dict:
    """Create a brand-new DocumentSpec from the user prompt.

    Uses `llm.with_structured_output` so the LLM returns a validated
    Pydantic model rather than free-form text.
    """
    structured_llm = llm.with_structured_output(DocumentSpec, method="function_calling")

    try:
        doc_spec: DocumentSpec = structured_llm.invoke(
            [SYSTEM_PROMPT, *state["messages"]]
        )
    except Exception as exc:
        logger.error("Content generation failed: %s", exc)
        return {
            "error": f"Content generation failed: {exc}",
            "document_spec": state.get("document_spec"),
        }

    spec_dict = doc_spec.model_dump()
    logger.info("Document spec created: '%s'", doc_spec.title)
    return {
        "document_spec": spec_dict,
        "messages": [
            *state["messages"],
            AIMessage(content=f"Document spec created: {json.dumps(spec_dict, indent=2)[:200]}…"),
        ],
        "error": None,
    }
