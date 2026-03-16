"""Node: classify the user's intent as *create*, *edit*, or *chat*."""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field

from pdf_agent.graph.state import PDFAgentState
from pdf_agent.utils.logger import get_logger

logger = get_logger(__name__)


class IntentClassification(BaseModel):
    """Structured output for intent classification."""

    intent: Literal["create", "edit", "chat"] = Field(
        ...,
        description=(
            "The user's intent: "
            "'create' — generate a brand-new PDF document; "
            "'edit' — modify the most-recently generated document; "
            "'chat' — general question or conversation, no PDF needed."
        ),
    )


SYSTEM_PROMPT = SystemMessage(content="""\
You are an intent classifier for a PDF document generation agent.

Classify the user's latest message into exactly one of these intents:

- create — the user wants to generate a brand-new PDF document.
- edit   — the user wants to modify the most-recently generated document.
- chat   — the user is asking a general question, having a conversation, or
           requesting information that does NOT require producing a PDF
           (e.g. "what can you do?", "explain X", "how does Y work?").

If ambiguous, default to `create` when there is no existing document,
`edit` when one already exists and the message references it,
or `chat` when the message is clearly conversational and not document-related.
""")


def classify_intent(state: PDFAgentState, *, llm: BaseChatModel) -> dict:
    """Classify the user's intent as 'create', 'edit', or 'chat'.

    Uses structured output so the LLM returns a validated ``IntentClassification``
    directly — no string parsing required.
    """
    structured_llm = llm.with_structured_output(IntentClassification, method="function_calling")

    messages = [SYSTEM_PROMPT, *state["messages"]]

    # Give the LLM context about whether a document already exists
    if state.get("document_spec") is not None:
        messages.append(
            HumanMessage(content="(Note: a document already exists in this session.)")
        )

    result: IntentClassification = structured_llm.invoke(messages)
    logger.info("Classified intent as '%s'", result.intent)
    return {"intent": result.intent}
