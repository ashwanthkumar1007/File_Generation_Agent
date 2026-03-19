"""LangGraph state definition for the PDF agent."""

from __future__ import annotations

from typing import TypedDict

from langchain_core.messages import BaseMessage


class PDFAgentState(TypedDict):
    """Shared state passed between LangGraph nodes."""

    messages: list[BaseMessage]
    intent: str
    renderer: str | None
    document_category: str | None
    document_spec: dict | None
    pdf_path: str | None
    chat_response: str | None
    error: str | None
