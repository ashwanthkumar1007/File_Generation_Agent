"""LangGraph workflow for the PDF agent.

Graph topology:

    user message
         │
         ▼
    classify_intent
         │
    ┌────┼────────┐
    │    │        │
  create edit    chat
    │    │        │
    ▼    ▼        ▼
generate apply  chat_response
    │    │        │
    └────┤        END
         ▼
     render_pdf
"""

from __future__ import annotations

from functools import partial
from typing import Literal

from langgraph.graph import END, StateGraph

from pdf_agent.config import AgentConfig
from pdf_agent.graph.state import PDFAgentState
from pdf_agent.nodes.apply_edit import apply_edit
from pdf_agent.nodes.chat_response import chat_response
from pdf_agent.nodes.classify_intent import classify_intent
from pdf_agent.nodes.generate_content import generate_content
from pdf_agent.nodes.render_pdf import render_pdf

from langchain_core.language_models import BaseChatModel


def _route_by_intent(
    state: PDFAgentState,
) -> Literal["generate_content", "apply_edit", "chat_response"]:
    """Route to the correct node based on classified intent."""
    intent = state.get("intent")
    if intent == "chat":
        return "chat_response"
    if intent == "edit" and state.get("document_spec") is not None:
        return "apply_edit"
    return "generate_content"


def build_graph(llm: BaseChatModel, config: AgentConfig) -> StateGraph:
    """Construct and compile the PDF agent LangGraph.

    Parameters
    ----------
    llm:
        The chat model used by LLM-powered nodes.
    config:
        Agent configuration (paths, defaults, etc.).

    Returns
    -------
    Compiled LangGraph ready for ``.invoke()`` or ``.stream()``.
    """
    graph = StateGraph(PDFAgentState)

    # Register nodes — use partial to inject dependencies
    graph.add_node("classify_intent", partial(classify_intent, llm=llm))
    graph.add_node("generate_content", partial(generate_content, llm=llm))
    graph.add_node("apply_edit", partial(apply_edit, llm=llm))
    graph.add_node("render_pdf", partial(render_pdf, config=config))
    graph.add_node("chat_response", partial(chat_response, llm=llm))

    # Entry point
    graph.set_entry_point("classify_intent")

    # Conditional edge after classification
    graph.add_conditional_edges(
        "classify_intent",
        _route_by_intent,
        {
            "generate_content": "generate_content",
            "apply_edit": "apply_edit",
            "chat_response": "chat_response",
        },
    )

    # Both PDF-producing nodes flow into render
    graph.add_edge("generate_content", "render_pdf")
    graph.add_edge("apply_edit", "render_pdf")

    # Terminal nodes
    graph.add_edge("render_pdf", END)
    graph.add_edge("chat_response", END)

    return graph.compile()
