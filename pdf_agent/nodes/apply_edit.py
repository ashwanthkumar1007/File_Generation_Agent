"""Node: apply an edit instruction to an existing DocumentSpec."""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from pdf_agent.graph.state import PDFAgentState
from pdf_agent.schemas.document_spec import DocumentSpec
from pdf_agent.utils.logger import get_logger

logger = get_logger(__name__)


SYSTEM_PROMPT = SystemMessage(content="""\
You are a document editor.  You will receive:

1. The current DocumentSpec as JSON.
2. The user's edit instruction.

You must return a **complete** updated DocumentSpec that incorporates the
requested changes while preserving all unchanged content.

Return ONLY a valid DocumentSpec.
""")


def apply_edit(state: PDFAgentState, *, llm: BaseChatModel) -> dict:
    """Apply a user-requested edit to the current document spec.

    Sends the existing spec + edit instruction to the LLM and expects a
    full replacement DocumentSpec back.
    """
    current_spec = state.get("document_spec")
    if current_spec is None:
        logger.warning("Edit requested but no existing document found")
        return {"error": "No existing document to edit."}

    structured_llm = llm.with_structured_output(DocumentSpec, method="function_calling")

    context_msg = HumanMessage(
        content=(
            f"Current DocumentSpec:\n```json\n{json.dumps(current_spec, indent=2)}\n```\n\n"
            f"Apply the following edit and return the full updated DocumentSpec."
        )
    )
    logger.info("Applying edit to document spec: '%s'", state["messages"][-1].content)
    try:
        updated_spec: DocumentSpec = structured_llm.invoke(
            [SYSTEM_PROMPT, context_msg, *state["messages"][-1:]]
        )
    except Exception as exc:
        logger.error("Edit application failed: %s", exc)
        return {
            "error": f"Edit application failed: {exc}",
            "document_spec": current_spec,
        }

    spec_dict = updated_spec.model_dump()
    logger.info("Document spec updated successfully")
    return {
        "document_spec": spec_dict,
        "messages": [
            *state["messages"],
            AIMessage(content="Document spec updated successfully."),
        ],
        "error": None,
    }
